"""Real standalone Flask, local personal setup, SQLite, two workers and PDF/mail."""
import json,os,pty,secrets,select,socket,subprocess,time
from pathlib import Path
from kompetenz_fixture import Browser,SEED,CONTRACT
ROOT=Path(__file__).resolve().parents[1]
# Infrastructure image is pinned in the platform module, no external SMTP upstream.
import sys
sys.path.insert(0,str(ROOT))
from schulplattform.pilot import INFRASTRUCTURE
project='sp-kompetenz-standalone-'+secrets.token_hex(5)
private=ROOT/'.work'/project;private.mkdir(mode=0o700)
subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'.work/apps/kompetenz-manager/prepare_secret.py')],cwd=private,capture_output=True,check=True)
key=private/'.private/session-key';assert key.stat().st_mode&0o777==0o444
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
origin='http://localhost:'+str(port)
env=os.environ|{'KM_SECRET_FILE':str(key),'KM_PORT':str(port),'APP_BASE_URL':origin,'SESSION_COOKIE_SECURE':'0','MAIL_SERVER':'mailpit'}
base=[str(ROOT/'.work/docker-compose'),'-p',project,'-f',str(ROOT/'.work/apps/kompetenz-manager/docker-compose.yml')]
operations=[];checks=[];out=ROOT/'docs/implementation/evidence';report={};sink=project+'-mail'
def run(command,expected=0,**kwargs):
 r=subprocess.run(command,env=env,capture_output=True,text=True,timeout=180,**kwargs)
 operations.append({'command':command,'exitCode':r.returncode})
 assert r.returncode==expected,'Standalone fixture command failed; raw payload withheld'
 return r.stdout
def code(source):return run(base+['exec','-T','app','python','-'],input=source)
def query(source):return code('from app import app\nfrom extensions import db\nfrom models import *\nfrom sqlalchemy import text\nimport json\nwith app.app_context():\n '+source)
def wait(path,status=200):
 for _ in range(100):
  try:Browser(port).call('GET',path,expected=status);return
  except (OSError,AssertionError):time.sleep(.2)
 raise AssertionError('HTTP readiness check failed')
def note(value):checks.append(value);print('PASS',value,flush=True)
password=secrets.token_urlsafe(24);(private/'admin-password').write_text(password);(private/'admin-password').chmod(0o600)
def setup():
 master,slave=pty.openpty()
 process=subprocess.Popen(base+['exec','-it','app','python','km_setup.py','fixture.operator'],env=env,
  stdin=slave,stdout=slave,stderr=slave,close_fds=True)
 os.close(slave);output=b'';first=second=False;deadline=time.monotonic()+60
 try:
  while time.monotonic()<deadline:
   if select.select([master],[],[],.2)[0]:
    try:chunk=os.read(master,65536)
    except OSError:break
    if not chunk:break
    output+=chunk
    if b'mindestens 12 Zeichen): ' in output and not first:os.write(master,(password+'\n').encode());first=True
    if b'Wiederholen: ' in output and not second:os.write(master,(password+'\n').encode());second=True
   if process.poll() is not None:break
  process.wait(timeout=5)
  transcript=private/'setup-transcript.private.log';transcript.write_bytes(output);transcript.chmod(0o600)
  assert password.encode() not in output,'Password echoed'
  return process.returncode,first and second
 finally:
  if process.poll() is None:process.kill();process.wait()
  os.close(master)
try:
 run(base+['up','-d','--no-build','app']);wait('/health/live');wait('/health/ready',503)
 run(base+['run','--rm','--no-deps','app','python','-m','km_migrate'])
 wait('/health/ready')
 assert query('print(User.query.count())').strip()=='0'
 headless=subprocess.run(base+['exec','-T','app','python','km_setup.py','headless.operator'],env=env,capture_output=True)
 assert headless.returncode!=0
 assert setup()==(0,True)
 result,prompted=setup();assert result!=0 and prompted
 note('explicit migration; no default accounts; real hidden personal terminal setup; repeat/headless setup refused')
 fixture=json.loads(code(SEED))
 admin,teacher,other,anonymous=[Browser(port) for _ in range(4)]
 admin.login('fixture.operator',password);teacher.login('fixture-teacher0');other.login('fixture-teacher1')
 anonymous.call('GET','/admin',expected=302)
 admin.call('GET','/admin');teacher.call('GET','/konto')
 teacher.call('GET','/admin',expected=302)
 anonymous.call('GET','/setup',expected=403)
 other.form('/diagnostik/foerderangaben/'+str(fixture['students'][0]),{'schuljahr':'2026/2027'},expected=403)
 teacher.form('/diagnostik/foerderangaben/'+str(fixture['students'][0]),{'schuljahr':'2026/2027','externe_foerderung':'1'})
 teacher.form('/konto',{},expected=400,csrf=False)
 teacher.form('/konto',{},headers={'Origin':'https://foreign.invalid'},expected=403)
 anonymous.call('GET','/static/uploads/synthetic.png',expected=403)
 anonymous.call('GET','/media/beobachtung/'+str(fixture['observation']),expected=302)
 assert teacher.call('GET','/media/beobachtung/'+str(fixture['observation'])).startswith(b'\x89PNG')
 note('admin/class-bound diagnosis/CSRF/Origin denied; intended internal observation access and protected upload route retained')
 stale=Browser(port);stale.cookies=teacher.cookies.copy()
 (private/'teacher-cookies.json').write_text(json.dumps(stale.cookies));(private/'teacher-cookies.json').chmod(0o600)
 teacher.form('/logout');stale.call('GET','/konto',expected=302)
 teacher.login('fixture-teacher0');run(base+['restart','app']);wait('/health/ready');teacher.call('GET','/konto')
 query("u=db.session.get(User,"+str(fixture['users'][0])+");u.password_hash=__import__('werkzeug.security',fromlist=['generate_password_hash']).generate_password_hash('new-synthetic-teacher-123');db.session.commit()")
 teacher.call('GET','/konto',expected=302);teacher.login('fixture-teacher0','new-synthetic-teacher-123')
 note('logout copied cookie and password change revoked server-side; ordinary restart preserves active local session')
 odt=teacher.call('GET','/schuelerakte/export/odt/'+str(fixture['students'][0]))
 assert odt.startswith(b'PK')
 pdf=teacher.call('GET','/schuelerakte/export/pdf/'+str(fixture['students'][0]))
 assert pdf.startswith(b'%PDF')
 appid=run(base+['ps','-q','app']).strip()
 holder=subprocess.Popen(['docker','exec',appid,'python','-u','-c',"from km_export import export_slot;import time\nwith export_slot():\n print('held',flush=True);time.sleep(8)"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 try:
  assert holder.stdout.readline().strip()=='held'
  teacher.call('GET','/schuelerakte/export/pdf/'+str(fixture['students'][0]),expected=429)
  Browser(port).call('GET','/health/live')
 finally:holder.wait(timeout=15)
 processes=code("""from pathlib import Path
import json
rows={}
for path in Path('/proc').iterdir():
 if path.name.isdigit():
  try:
   command=(path/'cmdline').read_bytes()
   if (path/'comm').read_text().strip()=='gunicorn':rows[int(path.name)]=int((path/'stat').read_text().rsplit(')',1)[1].split()[1])
  except (OSError,ValueError):pass
print(json.dumps({'workers':sum(parent in rows for parent in rows.values())}))
""")
 assert json.loads(processes)['workers']==2
 note('real ODT and LibreOffice PDF; shared export slot returns 429 with liveness available; two Gunicorn workers observed')
 run(['docker','run','-d','--name',sink,'--network',project+'_default','--network-alias','mailpit',
      '--read-only','--user','10001:10001','--tmpfs','/tmp:size=32m,mode=1777','-e','MP_DATABASE=/tmp/mail.db',INFRASTRUCTURE['mailpit']])
 run(base+['up','-d','--no-build','--wait','worker']);run(base+['stop','worker'])
 run(['docker','stop',sink])
 query("db.session.add(Notification(user_id="+str(fixture['users'][0])+",title='Synthetic queued notification',target_url='/konto'));db.session.commit();from mail_versand import versende;assert versende('sofort')['fehler']==1;assert Notification.query.filter_by(mailed_at=None).count()==1")
 run(['docker','start',sink]);time.sleep(1)
 query("from mail_versand import versende;assert versende('sofort')['mails']==1;assert Notification.query.filter_by(mailed_at=None).count()==0")
 note('separate worker starts/stops; SMTP outage retains durable notification; retry delivers only into private sink')
 run(base+['run','--rm','--no-deps','app','python','-m','km_migrate'])
 before=json.loads(code(CONTRACT));run(base+['restart','app']);wait('/health/ready');assert json.loads(code(CONTRACT))==before
 query("db.session.execute(text(\"UPDATE km_schema SET checksum='invalid'\"));db.session.commit()");wait('/health/ready',503)
 query("from km_migrate import checksum;db.session.execute(text('UPDATE km_schema SET checksum=:c'),{'c':checksum()});db.session.commit()");wait('/health/ready')
 info=json.loads(run(['docker','inspect',appid]))[0]
 assert info['Config']['User']=='10001:10001' and info['HostConfig']['ReadonlyRootfs']
 assert not any(value.startswith('SECRET_KEY=') for value in info['Config']['Env'])
 logs=subprocess.run(['docker','logs',appid],capture_output=True,text=True)
 assert password not in logs.stdout+logs.stderr and key.read_text() not in logs.stdout+logs.stderr
 volumes={mount['Destination']:mount['Name'] for mount in info['Mounts'] if mount['Type']=='volume'}
 fixture|={'project':project,'secretFile':str(key),'port':port,'contract':json.loads(code(CONTRACT)),
   'instanceVolume':volumes['/app/instance'],'templateVolume':volumes['/app/odt_templates']}
 (private/'fixture.json').write_text(json.dumps(fixture));(private/'fixture.json').chmod(0o600)
 (ROOT/'.work/kompetenz-latest-fixture').write_text(str(private))
 report={'imageId':info['Image'],'standalone':True,'checks':checks,'nonRootReadOnly':True,'privateFileSecret':True,
   'readinessRejectsMigrationDrift':True,'limits':['No real pupil data','No production adoption','No capacity measurement']}
finally:
 run(base+['stop'])
 subprocess.run(['docker','stop',sink],capture_output=True)
 report['stoppedDataRetained']=True
 (out/'kompetenz-standalone.json').write_text(json.dumps(report,indent=2)+'\n')
 (out/'kompetenz-standalone-operations.json').write_text(json.dumps(operations,indent=2)+'\n')
print(json.dumps(report))
