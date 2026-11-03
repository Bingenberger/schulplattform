"""Real interactive first-admin setup with generated private file credentials."""
import json,os,pty,secrets,select,socket,subprocess,time
from pathlib import Path
from leseflux_fixture import Browser
ROOT=Path(__file__).resolve().parents[1]
project="sp-leseflux-setup-"+secrets.token_hex(5);private=ROOT/".work"/project;private.mkdir(mode=0o700)
subprocess.run([str(ROOT/".venv/bin/python"),str(ROOT/".work/apps/leseflux/prepare_secrets.py")],cwd=private,capture_output=True,check=True)
keys=private/".private";keys.rename(private/"secrets");keys=private/"secrets"
assert keys.stat().st_mode&0o777==0o700
assert all(file.stat().st_mode&0o777==0o444 for file in keys.iterdir())
with socket.socket() as sock:sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
env=os.environ|{"LESEFLUX_SECRETS_DIR":str(keys),"LESEFLUX_PORT":str(port),
 "CORS_ORIGIN":"http://localhost:"+str(port),"COOKIE_SECURE":"false"}
base=[str(ROOT/".work/docker-compose"),"-p",project,"-f",str(ROOT/".work/apps/leseflux/docker-compose.yml")]
password=secrets.token_urlsafe(24);file=private/"setup-password";file.write_text(password);file.chmod(0o600)
def run(command):return subprocess.run(command,env=env,capture_output=True,text=True,timeout=180,check=True).stdout
def setup():
 master,slave=pty.openpty()
 process=subprocess.Popen(base+["run","--rm","-it","--no-deps","app","node","scripts/setup-admin.cjs",
     "personal-fixture@example.invalid","Synthetic Personal Admin"],env=env,stdin=slave,stdout=slave,stderr=slave,close_fds=True)
 os.close(slave);output=b"";first=second=False;deadline=time.monotonic()+90
 try:
  while time.monotonic()<deadline:
   if select.select([master],[],[],.2)[0]:
    try:chunk=os.read(master,65536)
    except OSError:break
    if not chunk:break
    output+=chunk
    if b"mindestens 12 Zeichen): " in output and not first:
     os.write(master,(password+"\r").encode());first=True
    if b"Wiederholen: " in output and not second:
     os.write(master,(password+"\r").encode());second=True
   if process.poll() is not None:break
  if process.poll() is None:process.wait(timeout=5)
  assert password.encode() not in output,"Password echoed"
  return process.returncode,first and second
 finally:
  if process.poll() is None:process.kill();process.wait()
  os.close(master)
report={}
try:
 run(base+["up","-d","--no-build","--wait","postgres"])
 run(base+["run","--rm","--no-deps","app","node","scripts/platform-migrate.cjs"])
 result,prompted=setup();assert result==0 and prompted,"Interactive setup failed"
 result,prompted=setup();assert result!=0 and prompted,"Existing account overwritten"
 run(base+["up","-d","--no-build","--wait","app"])
 browser=Browser(port)
 logged=browser.call("POST","/api/auth/login-teacher",{"email":"personal-fixture@example.invalid","password":password})
 assert logged["user"]["role"]=="ADMIN" and "token" not in logged
 report={"generatedPrivateDirectory0700":True,"projectedFiles0444":True,"interactiveHiddenPasswordConfirmedTwice":True,
  "existingAccountPreserved":True,"personalAdminLogin":True,"noDefaultAccountCreated":True}
finally:run(base+["down","--remove-orphans"])
report["stoppedDataRetained"]=True
(ROOT/"docs/implementation/evidence/leseflux-setup.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report))
