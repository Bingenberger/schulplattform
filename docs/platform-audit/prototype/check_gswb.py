#!/usr/bin/env python3
"""Reproduce unauthenticated editorial write, SQLite restore and reinitialization."""
import tempfile,json,os,sys,sqlite3,importlib
from pathlib import Path
repo=Path(sys.argv[1]).resolve();sys.path.insert(0,str(repo))
with tempfile.TemporaryDirectory(prefix='gswb-audit-') as d:
 os.environ['AUDIT_FIXTURE_DIR']=d
 fixture=importlib.import_module('gswb_fixture');app=fixture.app;root=Path(d)
 p=root/'imports'/'audit.json';p.write_text(json.dumps({'lemma':'Auditwort','wortart':'Nomen'}))
 c=app.test_client();r=c.post('/review/audit/approve')
 assert r.status_code==302
 assert json.loads(p.read_text())['_review']['approved'] is True
 print('OBSERVED unauthenticated review POST changed synthetic JSON; status=302')
 assert c.get('/api/word/Auditwort0000').status_code==200
 source=sqlite3.connect(root/'words.db')
 with sqlite3.connect(root/'snapshot.db') as target:source.backup(target)
 source.close()
 clean=root/'clean';clean.mkdir()
 with sqlite3.connect(root/'snapshot.db') as s,sqlite3.connect(clean/'words.db') as t:s.backup(t)
 with sqlite3.connect(clean/'words.db') as t:
  assert t.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
  assert t.execute('SELECT count(*) FROM words').fetchone()[0]==1000
 from grundschul_woerterbuch.db import init_db
 init_db(clean/'words.db');init_db(clean/'words.db')
 with sqlite3.connect(clean/'words.db') as t:assert t.execute('SELECT count(*) FROM words').fetchone()[0]==1000
 print('PASS synthetic SQLite snapshot restored into clean directory; integrity_check=ok; rows=1000; schema reinit twice preserved rows')
 print('LIMIT: no media/keys/IdP restored; no platform restore demonstrated')
