import hashlib
import json

import pytest
from jsonschema.exceptions import ValidationError
from schulplattform.release import validate_manifest, validate_release


@pytest.fixture
def manifest(tmp_path):
    content = b'synthetic validation fixture, not a release acceptance'
    digest = hashlib.sha256(content).hexdigest()
    (tmp_path / digest).write_bytes(content)
    return dict(schemaVersion=1, id='gswb', sourceCommit='a' * 40,
        image='registry.example.invalid/gswb:1.0.0@sha256:' + 'b' * 64, port=8000,
        database=dict(engine='sqlite', name='gswb', account='gswb'),
        persistence=[dict(id='data', mount='/app/data', owner='10001:10001', backup=True)],
        domainEnvironment=[], buildTimePublicUrl=False,
        health=dict(live='/health/live', ready='/health/ready'),
        resources=dict(memoryMiB=512, cpus=1, workers=2, exportSlotsPerProcess=0),
        acceptance={key: digest for key in ['amd64Build', 'standalone', 'negativeAccess',
                    'restore', 'domainRollback', 'licenses', 'sbom']})


def test_release_artifact_checks(manifest, tmp_path):
    validate_release([manifest], tmp_path)
    with pytest.raises(ValueError, match='Duplicate'):
        validate_release([manifest, manifest], tmp_path)
    artifact = tmp_path / manifest['acceptance']['restore']
    artifact.write_text('changed')
    with pytest.raises(ValueError, match='checksum'):
        validate_manifest(manifest, tmp_path)


@pytest.mark.parametrize('field,value', [('image', 'gswb:latest'), ('sourceCommit', 'main'),
    ('schemaVersion', 2), ('port', 80), ('arbitraryCommand', 'rm -rf /')])
def test_invalid_releases_rejected(manifest, tmp_path, field, value):
    manifest[field] = value
    with pytest.raises(ValidationError):
        validate_manifest(manifest, tmp_path)


def test_latest_even_with_digest_rejected(manifest, tmp_path):
    manifest['image'] = 'gswb:latest@sha256:' + 'a' * 64
    with pytest.raises(ValueError, match='latest'):
        validate_manifest(manifest, tmp_path)
