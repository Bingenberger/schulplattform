"""Chromium tablet smoke for native local login, navigation, logout and local assets."""
import json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
private=Path((ROOT/'.work/kompetenz-latest-fixture').read_text());fixture=json.loads((private/'fixture.json').read_text())
origin='http://localhost:'+str(fixture['port'])
env=os.environ|{'KM_SECRET_FILE':fixture['secretFile'],'KM_PORT':str(fixture['port']),'APP_BASE_URL':origin,'SESSION_COOKIE_SECURE':'0','MAIL_SERVER':''}
base=[str(ROOT/'.work/docker-compose'),'-p',fixture['project'],'-f',str(ROOT/'.work/apps/kompetenz-manager/docker-compose.yml')]
file=private/'browser-input.json';file.write_text(json.dumps({'origin':origin,'student':fixture['students'][0]}));file.chmod(0o444)
program=r'''
from pathlib import Path
from urllib.parse import urlsplit
import json
from playwright.sync_api import sync_playwright,expect
data=json.loads(Path('/run/fixture.json').read_text());origin=data['origin'];requests=[]
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 context=browser.new_context(viewport={'width':1024,'height':768},is_mobile=True,has_touch=True)
 page=context.new_page();page.on('request',lambda request:requests.append(request.url))
 page.goto(origin+'/login')
 page.locator('input[name="username"]').fill('fixture-teacher0')
 page.locator('input[name="password"]').fill('new-synthetic-teacher-123')
 page.locator('button[type="submit"]').click()
 page.wait_for_url(origin+'/')
 page.goto(origin+'/konto');expect(page.locator('input[name="vorname"]')).to_be_visible()
 cookies=context.cookies()
 assert any(c['name']=='kompetenz_manager_session' and c['httpOnly'] and c['sameSite']=='Lax' for c in cookies)
 assert 'kompetenz_manager_session' not in page.evaluate('document.cookie')
 page.goto(origin+'/schuelerakte?schueler_id='+str(data['student']))
 assert 'Synthetic' in page.inner_text('body')
 page.goto(origin+'/admin');page.wait_for_url(origin+'/')
 assert 'Zugriff verweigert' in page.inner_text('body')
 page.goto(origin+'/konto')
 assert page.evaluate("""async()=>{let token=document.querySelector('meta[name="csrf-token"]').content;
 return (await fetch('/logout',{method:'POST',headers:{'X-CSRF-Token':token}})).status}""")==200
 page.goto(origin+'/konto');assert urlsplit(page.url).path=='/login'
 assert all(urlsplit(url).hostname in ('localhost','127.0.0.1',None) for url in requests)
 context.close();browser.close()
print(json.dumps({'nativeTeacherUiLogin':True,'tabletAccountAndStudentNavigation':True,'adminRedirectDenial':True,
 'httpOnlyCookie':True,'logoutRequiresNewLogin':True,'noThirdPartyRequestsObserved':True,
 'scope':'Chromium tablet emulation; no complete visual/export interaction acceptance'}))
'''
image=json.loads(subprocess.check_output(['docker','image','inspect','fahrradausbildung-browser-tests:0.1.0-dev'],text=True))[0]['Id']
command=['docker','run','--rm','--init','--network','host','--read-only','--cap-drop','ALL',
 '--security-opt','no-new-privileges:true','--memory','1024m','--cpus','1','--pids-limit','512',
 '--tmpfs','/tmp:size=128m,mode=1777','-v',str(file)+':/run/fixture.json:ro','-i',image,'python','-']
try:
 subprocess.run(base+['up','-d','--no-build','--wait','app'],env=env,capture_output=True,check=True)
 result=subprocess.run(command,input=program,capture_output=True,text=True,timeout=180)
 if result.returncode:
  (private/'browser-error.private.log').write_text(result.stdout+result.stderr)
  raise RuntimeError('Browser proof failed; raw failure retained privately')
 report=json.loads(result.stdout);report['browserImage']=image
 cid=subprocess.check_output(base+['ps','-q','app'],env=env,text=True).strip()
 report['imageId']=json.loads(subprocess.check_output(['docker','inspect',cid],text=True))[0]['Image']
 (ROOT/'docs/implementation/evidence/kompetenz-browser.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report))
finally:subprocess.run(base+['stop'],env=env,capture_output=True,check=True)
