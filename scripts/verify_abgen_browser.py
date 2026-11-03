"""Real Chromium/WebKit editor smoke; no browser screenshots or credentials in evidence."""
import json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/".work/apps/abgen"
directory=Path((ROOT/".work/abgen-latest-fixture").read_text())
meta=json.loads((directory/"meta.json").read_text())
account=json.loads((directory/"account.json").read_text())
base=[str(ROOT/".work/docker-compose"),"-p",meta["project"],"-f",str(APP/"docker-compose.yml")]
env=os.environ|meta["env"]
def compose(args):
 r=subprocess.run(base+args,env=env,capture_output=True,text=True,timeout=180)
 assert r.returncode==0,"Browser fixture lifecycle failed"
try:
 compose(["up","-d","--no-build","--wait","--wait-timeout","90"])
 program="const fixture="+json.dumps(account|{"origin":meta["env"]["WEB_ORIGIN"]})+";\n"+(APP/"contract_tests/browser.mjs").read_text()
 result=subprocess.run(["docker","run","--rm","--init","--read-only","--network","host","--cap-drop","ALL",
  "--security-opt","no-new-privileges:true","--memory","1536m","--cpus","2","--pids-limit","384",
  "--tmpfs","/tmp:size=256m,mode=1777","--tmpfs","/home/abgen:size=32m,uid=10001,gid=10001,mode=700",
  "-e","XDG_CACHE_HOME=/tmp/cache","-e","XDG_CONFIG_HOME=/tmp/config",
  "-i","abgen-pdf:0.1.0-dev","node","--input-type=module","-"],input=program,capture_output=True,text=True,timeout=180)
 target=ROOT/("docs/implementation/evidence/abgen-browser.log" if result.returncode==0 else ".work/abgen-browser-failure.private.log")
 target.write_text(result.stdout+result.stderr+"\nexit_code="+str(result.returncode)+"\n")
 print(result.stdout,flush=True)
 if result.returncode:print("Browser check failed; private diagnostic retained")
 else:print("Chromium and WebKit passed; fixture stopped with all data preserved")
finally:compose(["stop"])
raise SystemExit(result.returncode)
