"""Decode a screenshot of the native child QR without exposing its capability."""
import base64,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def verify_qr(pilot,host,account,play_code):
 origin="https://"+host+":"+str(pilot.config["port"])
 program="const fixture="+json.dumps(account|{"origin":origin,"playCode":play_code})+";\n"+r"""
const {createRequire}=await import('node:module');
const require=createRequire('/app/apps/server/package.json');
const {chromium}=require('playwright');
const browser=await chromium.launch({args:['--disable-dev-shm-usage']});
try{
 const context=await browser.newContext({ignoreHTTPSErrors:true,deviceScaleFactor:2});
 const page=await context.newPage();page.setDefaultTimeout(15000);
 await page.goto(fixture.origin);
 await page.getByLabel('E-Mail',{exact:true}).fill(fixture.email);
 await page.getByLabel('Passwort',{exact:true}).fill(fixture.password);
 await page.getByRole('button',{name:'Anmelden',exact:true}).click();
 await page.locator('.document-card').first().click();
 await page.getByLabel('Gemeinsam bearbeiten',{exact:true}).check();
 await page.locator('.collab-bar[data-status="verbunden"]').waitFor();
 await page.getByRole('button',{name:'Teilen',exact:true}).click();
 const qr=page.getByRole('img',{name:'QR-Code für '+fixture.origin+'/play/'+fixture.playCode,exact:true});
 await qr.waitFor();
 await qr.evaluate(node=>{node.style.width='300px';node.style.height='300px'});
 process.stdout.write((await qr.screenshot()).toString('base64'));
}finally{await browser.close();}
"""
 cmd=["docker","run","--rm","--init","--read-only","--network","host","--add-host",host+":127.0.0.1",
  "--cap-drop","ALL","--security-opt","no-new-privileges:true","--memory","768m","--cpus","2","--pids-limit","256",
  "--tmpfs","/tmp:size=128m,mode=1777","--tmpfs","/home/abgen:size=32m,uid=10001,gid=10001,mode=700",
  "-e","XDG_CACHE_HOME=/tmp/cache","-e","XDG_CONFIG_HOME=/tmp/config",
  "-i","abgen-pdf:0.1.0-dev","node","--input-type=module","-"]
 result=subprocess.run(cmd,input=program,capture_output=True,text=True,timeout=90)
 if result.returncode:
  (pilot.directory/"abgen-fixtures/qr-failure.private.log").write_text(result.stderr)
  raise AssertionError("Native QR browser capture failed; private diagnostic retained")
 png=base64.b64decode(result.stdout,validate=True)
 decoder="from PIL import Image;from pyzbar.pyzbar import decode;import io,sys,json;print(json.dumps([row.data.decode() for row in decode(Image.open(io.BytesIO(sys.stdin.buffer.read())))]))"
 result=subprocess.run(["docker","run","--rm","--read-only","--network","none","--cap-drop","ALL",
  "--security-opt","no-new-privileges:true","--memory","256m","--pids-limit","64",
  "-i","fahrradausbildung-browser-tests:0.1.0-dev","python","-c",decoder],
  input=png,capture_output=True,timeout=30)
 assert result.returncode==0,"QR decoder failed"
 assert json.loads(result.stdout)==[origin+"/play/"+play_code],"Decoded QR must use current domain and preserved child code"
 return True
