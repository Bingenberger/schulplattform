"""Chromium/WebKit over the local TLS proxy, with the ten-app pilot running."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from schulplattform.pilot import Pilot
from abgen_fixture import Browser
pilot=Pilot(ROOT/".work/pilot-v21")
private=pilot.directory/"abgen-fixtures"
account=json.loads((private/"account.json").read_text())
host=pilot.current_domains()["abgen"]
origin="https://"+host+":"+str(pilot.config["port"])
pilot.start()
try:
 # Verify the CA and hostname using the strict Python TLS client first.
 Browser(pilot.config["port"],host,pilot.directory/"root.crt").call("GET","/api/health/ready")
 source=(ROOT/".work/apps/abgen/contract_tests/browser.mjs").read_text()
 source=source.replace("browser.newContext()","browser.newContext({ignoreHTTPSErrors:true})")
 source=source.replace(" await page.locator('.document-card').first().waitFor();",
  """ await page.locator('.document-card').first().waitFor();
 const session=(await context.cookies()).find(cookie=>cookie.name==='abgen_session');
 assert.ok(session&&session.secure&&session.httpOnly&&session.sameSite==='Lax','secure browser session');
 assert.ok(!(await page.evaluate(()=>document.cookie)).includes('abgen_session='),'HttpOnly browser session');""")
 program="const fixture="+json.dumps(account|{"origin":origin})+";\n"+source
 cmd=["docker","run","--rm","--init","--read-only","--network","host","--add-host",host+":127.0.0.1",
  "--cap-drop","ALL","--security-opt","no-new-privileges:true","--memory","1536m","--cpus","2","--pids-limit","384",
  "--tmpfs","/tmp:size=256m,mode=1777","--tmpfs","/home/abgen:size=32m,uid=10001,gid=10001,mode=700",
  "-e","XDG_CACHE_HOME=/tmp/cache","-e","XDG_CONFIG_HOME=/tmp/config",
  "-i","abgen-pdf:0.1.0-dev","node","--input-type=module","-"]
 result=subprocess.run(cmd,input=program,capture_output=True,text=True,timeout=180)
 target=ROOT/("docs/implementation/evidence/abgen-platform-browser.log" if result.returncode==0 else ".work/abgen-platform-browser-failure.private.log")
 target.write_text("CA and hostname verified with strict Python TLS client; browser uses local CA exception.\n"+
  result.stdout+result.stderr+"\nexit_code="+str(result.returncode)+"\n")
 print(result.stdout,flush=True)
 assert result.returncode==0,"Browser acceptance failed; private diagnostic retained"
finally:
 pilot.stop()
 (ROOT/"docs/implementation/evidence/pilot-v21-operations.jsonl").write_text(pilot.log.read_text())
print("Real TLS browser editor/collaboration checks passed; all ten apps stopped with data retained")
