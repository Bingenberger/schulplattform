"""Real browser smoke for local teacher and child UI, no camera or real data."""
import json,os,subprocess,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
private=Path((ROOT/".work/leseflux-latest-fixture").read_text());fixture=json.loads((private/"fixture.json").read_text())
child=json.loads((private/"restore-child.json").read_text())
env=os.environ|{"LESEFLUX_SECRETS_DIR":fixture["secretDirectory"],"COOKIE_SECURE":"false"}
# The standalone origin is fixed in the compose container configuration; recover it without values from other env fields.
ids=subprocess.check_output(["docker","ps","-aq","--filter","label=com.docker.compose.project="+fixture["project"],
 "--filter","label=com.docker.compose.service=app"],text=True).strip()
if ids:
 info=json.loads(subprocess.check_output(["docker","inspect",ids],text=True))[0]
 origin=next(value.split("=",1)[1] for value in info["Config"]["Env"] if value.startswith("CORS_ORIGIN="))
else:
 with socket.socket() as listener:listener.bind(("127.0.0.1",0));origin="http://localhost:"+str(listener.getsockname()[1])
port=int(origin.rsplit(":",1)[1]);env|={"LESEFLUX_PORT":str(port),"CORS_ORIGIN":origin}
base=[str(ROOT/".work/docker-compose"),"-p",fixture["project"],"-f",str(ROOT/".work/apps/leseflux/docker-compose.yml")]
inputs={"origin":origin,"email":fixture["teacherEmail"],"password":fixture["teacherPassword"],
    "childCode":child["loginCode"],"childId":child["id"]}
file=private/"browser-input.json";file.write_text(json.dumps(inputs));file.chmod(0o444)
program=r"""
import json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(Path('/run/fixture.json').read_text())
requests=[]
with sync_playwright() as p:
 browser=p.chromium.launch()
 context=browser.new_context(viewport={'width':1024,'height':768})
 context.add_init_script("localStorage.setItem('leseflux-auth',JSON.stringify({state:{user:null,token:'obsolete-synthetic-token'},version:0}))")
 page=context.new_page();page.on('request',lambda request:requests.append(request.url))
 page.goto(fixture['origin']+'/login')
 page.locator('#email').fill(fixture['email']);page.locator('#password').fill(fixture['password'])
 page.get_by_role('button',name='Anmelden',exact=True).click()
 page.wait_for_url('**/teacher/dashboard')
 user=page.evaluate("async()=>await(await fetch('/api/auth/me')).json()")
 assert user['role']=='TEACHER' and user['email']==fixture['email']
 state=json.loads(page.evaluate("localStorage.getItem('leseflux-auth')"))
 assert 'token' not in state['state']
 cookies=context.cookies()
 assert any(cookie['name']=='token' and cookie['httpOnly'] and cookie['sameSite']=='Strict' for cookie in cookies)
 assert 'token=' not in page.evaluate('document.cookie')
 context.close()
 children=browser.new_context(viewport={'width':810,'height':1080},is_mobile=True,has_touch=True)
 page=children.new_page();page.on('request',lambda request:requests.append(request.url))
 page.goto(fixture['origin']+'/child/login')
 page.get_by_role('button',name='Code eingeben',exact=True).click()
 page.get_by_placeholder('z. B. AB3X7K').fill(fixture['childCode'])
 page.get_by_placeholder('z. B. AB3X7K').press('Enter')
 page.wait_for_url('**/child/home')
 user=page.evaluate("async()=>await(await fetch('/api/auth/me')).json()")
 assert user['role']=='CHILD' and user['id']==fixture['childId']
 assert page.evaluate("async()=>(await fetch('/api/admin/teachers')).status")==403
 state=json.loads(page.evaluate("localStorage.getItem('leseflux-auth')"))
 assert 'token' not in state['state']
 children.close();browser.close()
assert all(urlsplit(url).hostname in ('localhost','127.0.0.1',None) for url in requests)
print(json.dumps({'teacherUiLogin':True,'childCodeUiLogin':True,'legacyLocalStorageTokenRemoved':True,
 'cookieHttpOnlyAndStrict':True,'noJwtInLocalStorageOrDocumentCookie':True,'childAdminDenied':True,
 'noThirdPartyRequestsObserved':True,'cameraQrScan':'not exercised','browser':'Chromium tablet emulation'}))
"""
image=json.loads(subprocess.check_output(["docker","image","inspect","fahrradausbildung-browser-tests:0.1.0-dev"],text=True))[0]["Id"]
command=["docker","run","--rm","--init","--network","host","--read-only","--cap-drop","ALL","--security-opt","no-new-privileges:true",
 "--memory","1024m","--cpus","1","--pids-limit","512","--tmpfs","/tmp:size=128m,mode=1777",
 "-v",str(file)+":/run/fixture.json:ro","-i",image,"python","-"]
try:
 subprocess.run(base+["up","-d","--no-build","--wait","--wait-timeout","90"],env=env,capture_output=True,check=True)
 result=subprocess.run(command,input=program,capture_output=True,text=True,timeout=180)
 if result.returncode:
  (private/"browser-error.private.log").write_text(result.stdout+result.stderr)
  raise RuntimeError("Browser proof failed; raw failure retained privately")
 report=json.loads(result.stdout);report["browserImage"]=image
 cid=subprocess.check_output(base+["ps","-q","app"],env=env,text=True).strip()
 report["imageId"]=json.loads(subprocess.check_output(["docker","inspect",cid],text=True))[0]["Image"]
 (ROOT/"docs/implementation/evidence/leseflux-browser.json").write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps(report))
finally:subprocess.run(base+["stop"],env=env,capture_output=True,check=True)
