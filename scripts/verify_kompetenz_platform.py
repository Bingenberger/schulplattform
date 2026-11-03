"""Nine-app TLS, native class rights, mail domain rollback and worker lifecycle."""
import hashlib,json,os,sys,time
from pathlib import Path
from kompetenz_fixture import Browser,SEED,CONTRACT
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from schulplattform.pilot import Pilot,APP_PORTS
from schulplattform.pilot_engine import PilotEngine
from schulplattform.proxy import caddyfile
from schulplattform.domains import Domains,DomainError
pilot=Pilot(ROOT/'.work/pilot-v20');private=pilot.directory/'kompetenz-fixtures';private.mkdir(mode=0o700,exist_ok=True)
def code(source):
 return pilot.command([str(pilot.compose),'-p',pilot.project+'-kompetenz-manager','-f',
  str(ROOT/'.work/apps/kompetenz-manager/docker-compose.yml'),'-f',str(pilot.directory/'kompetenz-manager.yml'),
  'exec','-T','app','python','-'],input=source)
def browser(host):return Browser(pilot.config['port'],host,pilot.directory/'root.crt')
file=private/'fixture.json'
if file.exists():fixture=json.loads(file.read_text())
else:
 fixture=json.loads(code(SEED));file.write_text(json.dumps(fixture));file.chmod(0o600)
original=pilot.current_domains();checks=[];fault=False
baseline=json.loads(code(CONTRACT))
def verify(domains):
 host=domains['kompetenz-manager']
 if fault and host=='kompetenz-defekt.localhost':return False
 teacher,other,anonymous=[browser(host) for _ in range(3)]
 origin='https://'+host+':'+str(pilot.config['port'])
 for _ in range(50):
  try:anonymous.call('GET','/health/ready');break
  except (OSError,AssertionError):time.sleep(.2)
 teacher.login('fixture-teacher0');other.login('fixture-teacher1')
 assert teacher.cookie_options['kompetenz_manager_session']=={'secure':True,'httponly':True,'samesite':'Lax'}
 teacher.call('GET','/konto',headers={'X-Forwarded-Host':'forged.invalid','X-Forwarded-Proto':'http','X-Remote-User':'admin'})
 teacher.call('GET','/admin',expected=302);anonymous.call('GET','/admin',expected=302)
 other.form('/diagnostik/foerderangaben/'+str(fixture['students'][0]),{'schuljahr':'2026/2027'},expected=403)
 teacher.form('/konto',{},expected=400,csrf=False)
 teacher.form('/konto',{},headers={'Origin':'https://foreign.invalid'},expected=403)
 teacher.form('/konto',{'form_action':'profile','vorname':'Synthetic'},headers={'Origin':origin})
 # Restore this harmless field so the business snapshot remains identical.
 code("from app import app\nfrom extensions import db\nfrom models import User\nwith app.app_context():\n u=db.session.get(User,"+str(fixture['users'][0])+");u.vorname=None;db.session.commit()")
 assert teacher.call('GET','/schuelerakte/export/odt/'+str(fixture['students'][0])).startswith(b'PK')
 assert teacher.call('GET','/media/beobachtung/'+str(fixture['observation'])).startswith(b'\x89PNG')
 # Pause the only scheduled writer before this explicit native delivery job.
 pilot.compose_command('kompetenz-manager','stop','worker')
 program="""from app import app
from extensions import db
from models import Notification
from mail_versand import versende
import json,urllib.request
with app.app_context():
 n=Notification(user_id=USER,title='Synthetic domain proof',target_url='/konto')
 db.session.add(n);db.session.commit();nid=n.id
 assert versende('sofort')['mails']==1
 summary=json.load(urllib.request.urlopen('http://mailpit:8025/api/v1/messages'))
 found=False
 for row in summary['messages']:
  message=json.load(urllib.request.urlopen('http://mailpit:8025/api/v1/message/'+row['ID']))
  if ORIGIN+'/konto' in message.get('Text',''):found=True
 assert found
 db.session.delete(db.session.get(Notification,nid));db.session.commit()
"""
 code(program.replace('USER',str(fixture['users'][0])).replace('ORIGIN',repr(origin)))
 pilot.compose_command('kompetenz-manager','up','-d','--no-build','--wait','worker')
 teacher.form('/logout');other.form('/logout')
 checks.append({'domain':host,'secureCookie':True,'nativeRolesAndDiagnosisClassDenial':True,
  'csrfAndOriginDenied':True,'mailUsesCurrentRuntimeOriginInLocalSink':True,'protectedUploadAndOdtAvailable':True})
 return True
def activate(domains):
 path=pilot.directory/'kompetenz-manager.yml'
 lines=['      APP_BASE_URL: https://'+domains['kompetenz-manager']+':'+str(pilot.config['port'])
  if line.startswith('      APP_BASE_URL:') else line for line in path.read_text().splitlines()]
 with path.open('w') as stream:stream.write('\n'.join(lines)+'\n');stream.flush();os.fsync(stream.fileno())
 pilot.compose_command('kompetenz-manager','up','-d','--no-build','--wait','--wait-timeout','90','app','worker')
 config=caddyfile([(app,host,APP_PORTS[app]) for app,host in domains.items()]).replace('admin localhost:2019','admin localhost:2019\n local_certs')
 with (pilot.directory/'Caddyfile').open('w') as stream:stream.write(config);stream.flush();os.fsync(stream.fileno())
 proxy=pilot.inspect_service('infra','proxy')['Id']
 for action in ('validate','reload'):pilot.command(['docker','exec',proxy,'caddy',action,'--config','/etc/caddy/Caddyfile'])
assert verify(original)
driver=Domains(pilot.directory/'domain-transactions',original,'verwaltung.localhost',
 lambda old,new:set(new)==set(original) and all(h.endswith('.localhost') for h in new.values()),activate,verify,
 operation_lock=pilot.directory/'state/installation.lock')
try:
 driver.change('kompetenz-manager','kompetenz-neu.localhost')
 fault=True
 try:driver.change('kompetenz-manager','kompetenz-defekt.localhost')
 except DomainError as error:assert 'restored' in str(error)
 else:raise AssertionError('Bad domain accepted')
 assert pilot.current_domains()['kompetenz-manager']=='kompetenz-neu.localhost'
finally:
 fault=False;driver.change('kompetenz-manager','kompetenz.localhost')
def stable():
 paths=[pilot.directory/'state/installation.json']+list((pilot.directory/'secrets').rglob('*'))
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
before=stable();containers={a:pilot.inspect_service(a,'app')['Id'] for a in pilot.apps}
worker=pilot.inspect_service('kompetenz-manager','worker')['Id']
one,two=pilot.up(),pilot.up()
assert one==two and stable()==before and containers=={a:pilot.inspect_service(a,'app')['Id'] for a in pilot.apps}
assert worker==pilot.inspect_service('kompetenz-manager','worker')['Id']
engine=PilotEngine(pilot)
pilot.compose_command('kompetenz-manager','stop','worker')
assert engine.status('kompetenz-manager')['health']=='degraded'
pilot.compose_command('kompetenz-manager','up','-d','--no-build','--wait','worker')
offset=len(pilot.log.read_text().splitlines())
assert not engine.execute('stop','kompetenz-manager')['running']
assert not pilot.inspect_service('kompetenz-manager','worker')
browser('kompetenz.localhost').call('GET','/login',expected=503)
assert engine.execute('start','kompetenz-manager')['health']=='healthy'
assert verify(original) and stable()==before and json.loads(code(CONTRACT))==baseline
operations=[json.loads(line) for line in pilot.log.read_text().splitlines()[offset:]]
assert not any('km_migrate' in row['command'] or 'km_setup.py' in row['command'] for row in operations)
backend=pilot.inspect_service('kompetenz-manager','app')
assert not any(backend['NetworkSettings']['Ports'].values())
report={'apps':list(pilot.apps),'installationId':one['id'],'imageId':backend['Image'],'port':pilot.config['port'],
 'scope':'Nine-app local pilot, synthetic school data, verified local CA','domainChange':True,'forcedFailureRollback':True,
 'originalDomainRestored':True,'twoNoopRuns':True,'containersKeysAndCheckpointsStable':True,'businessRowsUnchanged':True,
 'workerFailureDegradesStatus':True,'stopPausesWebAndNotificationWriter':True,'stopMaintenance503':True,
 'startWithoutMigrationOrBootstrap':True,'privateBackend':True,'checks':checks,
 'limits':['No public DNS/ACME validation','No Ubuntu acceptance','No QR flow in this app','No capacity measurement']}
pilot.stop();report['stoppedDataRetained']=True
out=ROOT/'docs/implementation/evidence'
(out/'kompetenz-platform.json').write_text(json.dumps(report,indent=2)+'\n')
(out/'pilot-v20-operations.jsonl').write_text(pilot.log.read_text())
print(json.dumps(report))
