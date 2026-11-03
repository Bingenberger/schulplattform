"""Synthetic regression tests against the isolated app checkouts."""
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

import pytest
from werkzeug.security import generate_password_hash

APPS = Path(__file__).resolve().parents[1] / '.work/apps'
sys.path.insert(0, str(APPS / 'gswb'))
from grundschul_woerterbuch import create_app


@pytest.fixture
def dictionary(tmp_path):
    config = dict(TESTING=True, AUTO_INIT_DB=True, SECRET_KEY='synthetic-test-secret-' * 3,
                  HANDWRITING_MODE='mock', SESSION_COOKIE_SECURE=False,
                  EDITOR_USERNAME='synthetic.editor',
                  EDITOR_PASSWORD_HASH=generate_password_hash('synthetic-password'))
    for name in ['IMPORT_DIR', 'MEDIA_IMAGE_DIR', 'MEDIA_AUDIO_DIR', 'HANDWRITING_UPLOAD_DIR']:
        config[name] = str(tmp_path / name)
    config['DATABASE'] = str(tmp_path / 'dictionary.sqlite3')
    return create_app(config)


def test_missing_secret_blocks_start(monkeypatch):
    monkeypatch.delenv('SECRET_KEY', raising=False)
    with pytest.raises(RuntimeError, match='SECRET_KEY'):
        create_app()


def test_dictionary_public_and_all_editor_routes_protected(dictionary):
    client = dictionary.test_client()
    assert client.get('/').status_code == 200
    assert client.get('/api/autocomplete?q=Haus').headers['Access-Control-Allow-Origin'] == '*'
    for rule in dictionary.url_map.iter_rules():
        if rule.rule.startswith('/review'):
            path = rule.rule.replace('<slug>', 'synthetic')
            for method in rule.methods - {'OPTIONS', 'HEAD'}:
                response = client.open(path, method=method, headers={'Remote-User': 'admin',
                    'X-Forwarded-User': 'admin', 'X-Auth-Request-User': 'admin'})
                assert response.status_code == 401, (path, method)
                assert 'Access-Control-Allow-Origin' not in response.headers


def test_editor_login_csrf_and_logout(dictionary):
    client = dictionary.test_client()
    assert client.post('/editor/login', data={'username': 'synthetic.editor',
        'password': 'synthetic-password'}).status_code == 403
    page = client.get('/editor/login').text
    token = re.search(r'name="csrf_token" value="([^"]+)"', page)[1]
    assert client.post('/editor/login', data={'username': 'synthetic.editor',
        'password': 'synthetic-password', 'csrf_token': token}).status_code == 302
    assert client.get('/review').status_code == 200
    for suffix in ['approve', 'save', 'toggle-regeneration']:
        assert client.post('/review/synthetic/' + suffix).status_code == 403
    with client.session_transaction() as session:
        session['editor_csrf'] = 'synthetic-csrf'
    assert client.post('/editor/logout', data={'csrf_token': 'synthetic-csrf'}).status_code == 302
    assert client.get('/review').status_code == 401


def test_editor_write_requires_csrf_and_persists(dictionary):
    entry = Path(dictionary.config['IMPORT_DIR']) / 'synthetic.json'
    entry.write_text(json.dumps({'lemma': 'Testwort', 'wortart': 'Nomen'}))
    client = dictionary.test_client()
    with client.session_transaction() as session:
        import time
        session.update(editor='synthetic.editor', editor_expires=time.time() + 60,
                       editor_csrf='synthetic-csrf')
    assert 'csrf_token' in client.get('/review/synthetic').text
    assert client.post('/review/synthetic/approve', data={'csrf_token': 'synthetic-csrf'}).status_code == 302
    assert json.loads(entry.read_text())['_review']['approved'] is True


def test_health_checks_migration_version_without_initializing(dictionary):
    import sqlite3
    client = dictionary.test_client()
    assert client.get('/health/ready').status_code == 200
    with sqlite3.connect(dictionary.config['DATABASE']) as db:
        db.execute('PRAGMA user_version=0')
    assert client.get('/health/ready').status_code == 503
    assert client.get('/health/live').status_code == 200


def test_losverkauf_requires_identity_and_rejects_legacy_session(tmp_path, monkeypatch):
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'tickets.sqlite3'))
    monkeypatch.setenv('SECRET_KEY', 'synthetic-ticket-session-key-0123456789')
    monkeypatch.setenv('ELTERN_TOKEN', 'synthetic-ticket-parent-key-0123456789')
    monkeypatch.setenv('BASE_URL', 'http://localhost')
    geometry = tmp_path / 'districts.geojson'
    geometry.write_text(json.dumps({'type': 'FeatureCollection', 'features': []}))
    monkeypatch.setenv('GEOJSON_PATH', str(geometry))
    monkeypatch.setenv('ADMIN_USERNAME', 'synthetic.person')
    monkeypatch.setenv('ADMIN_PASSWORD', 'synthetic-password')
    sys.path.insert(0, str(APPS / 'losverkauf'))
    spec = importlib.util.spec_from_file_location('ticket_app', APPS / 'losverkauf/app.py')
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, 'ticket_app', module)
    spec.loader.exec_module(module)
    import sqlite3
    with sqlite3.connect(module.DB_PATH) as db:
        db.executescript(module.SCHEMA)
        db.execute('CREATE TABLE mail_outbox(id INTEGER PRIMARY KEY)')
        db.execute('PRAGMA user_version=1')
    client = module.app.test_client()
    nonce = re.search(r'name="csrf-token" content="([^"]+)"', client.get('/admin/login').text)[1]
    with client.session_transaction() as session:
        session['admin'] = True
    assert client.get('/admin').status_code == 302
    assert client.post('/admin/login', data={'pw': 'synthetic-password', 'csrf_token': nonce}).status_code == 200
    with client.session_transaction() as session:
        assert 'admin_identity' not in session
    assert client.post('/admin/login', data={'username': 'synthetic.person',
        'pw': 'synthetic-password', 'csrf_token': nonce}).status_code == 302
    with client.session_transaction() as session:
        assert session['admin_identity'] == 'synthetic.person'
