#!/usr/bin/env python3
"""Isolated synthetic pilot DB restore; refuses non-audit container/DB targets."""
import subprocess,json,hashlib,time
from pathlib import Path
container='schulplattform-audit-pg';source='audit';target='audit_restore'
def cmd(*args,**kw):return subprocess.run(list(args),check=True,capture_output=True,**kw)
def sql(db,q):return cmd('docker','exec',container,'psql','-U','postgres','-d',db,'-Atc',q).stdout.decode().strip()
query="SELECT json_build_object('users',(SELECT count(*) FROM kern_nutzer),'documents',(SELECT count(*) FROM kern_dokument),'identities',(SELECT count(*) FROM kern_oidcidentitaet),'owner',(SELECT erstellt_von_id FROM kern_dokument WHERE schluessel='audit-owned'),'groups',(SELECT count(*) FROM kern_nutzer_groups))"
before=sql(source,query);t=time.monotonic();dump=cmd('docker','exec',container,'pg_dump','-U','postgres','-Fc',source).stdout
# Fresh DB required: createdb fails if target already exists; never overwrite it.
cmd('docker','exec',container,'createdb','-U','postgres','-T','template0',target)
cmd('docker','exec','-i',container,'pg_restore','-U','postgres','--exit-on-error','-d',target,input=dump)
after=sql(target,query);assert json.loads(before)==json.loads(after)
result={'source':'synthetic pilot only','empty_target_db':target,'before':json.loads(before),'after':json.loads(after),'dump_bytes':len(dump),'dump_sha256':hashlib.sha256(dump).hexdigest(),'duration_s':round(time.monotonic()-t,3),'passed':True,'scope':'DB only; no IdP/media/keys; not platform RTO'}
Path('/tmp/schulplattform-audit/integration/restore-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
