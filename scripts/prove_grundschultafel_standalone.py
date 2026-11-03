"""Synthetic standalone HTTP proof. Tokens stay in private fixtures, never report bodies."""
import base64, concurrent.futures, http.client, json, os
from http.cookies import SimpleCookie
from pathlib import Path
import secrets, subprocess, time, urllib.parse
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/".work/apps/grundschultafel"
project="sp-tafel-standalone-"+secrets.token_hex(5)
PRIVATE=ROOT/".work"/project
PRIVATE.mkdir(mode=0o700,exist_ok=True)
os.chmod(PRIVATE,0o700)
key=PRIVATE/"session-key"
if not key.exists():key.write_text(secrets.token_urlsafe(48))
os.chmod(key,0o444)
env=dict(os.environ,TAFEL_PORT="44961",BASE_URL="http://localhost:44961",TAFEL_SECRET_FILE=str(key))
compose=[str(ROOT/".work/docker-compose"),"-p",project,"-f",str(APP/"docker-compose.yml")]
report=[]
def docker(*args,input=None,check=True):
    return subprocess.run([*compose,*args],env=env,input=input,text=True,capture_output=True,check=check)
def note(message):report.append("PASS "+message);print(report[-1],flush=True)
class Client:
    def __init__(self):self.cookies={}
    def call(self,method,path,body=None,headers=None,expected=200):
        headers=dict(headers or {})
        if self.cookies:headers["Cookie"]="; ".join(k+"="+v for k,v in self.cookies.items())
        if body is not None and not isinstance(body,bytes):
            body=json.dumps(body).encode();headers["Content-Type"]="application/json"
        conn=http.client.HTTPConnection("127.0.0.1",44961,timeout=20)
        conn.request(method,path,body,headers);response=conn.getresponse()
        data=response.read()
        for name,value in response.getheaders():
            if name.lower()=="set-cookie":
                cookie=SimpleCookie();cookie.load(value)
                for key,value in cookie.items():
                    if value.value:self.cookies[key]=value.value
                    else:self.cookies.pop(key,None)
        status=response.status;conn.close()
        assert status==expected,f"{method} {path.split('?')[0]} returned {status}, expected {expected}"
        try:return json.loads(data)
        except ValueError:return data
anonymous=Client();admin=Client();teacher=Client();other=Client()
try:
    docker("up","-d","--no-build")
    for _ in range(60):
        try:anonymous.call("GET","/health/live");break
        except (OSError,AssertionError):time.sleep(1)
    else:raise RuntimeError("liveness failed")
    anonymous.call("GET","/health/ready",expected=503)
    anonymous.call("POST","/api/auth/login",{"username":"fixture-admin","password":"invalid"},expected=503)
    note("liveness independent of migration; readiness/login closed before explicit migration")
    docker("exec","-T","app","node","scripts/migrate.mjs")
    anonymous.call("GET","/health/ready")
    result=docker("exec","-T","app","node","scripts/bootstrap.mjs","fixture-admin",check=False)
    assert result.returncode!=0 and len(result.stdout)==0
    token=docker("exec","-T","app","node","--input-type=module","-e",
        "import {bootstrap} from './scripts/bootstrap.mjs';process.stdout.write(await bootstrap('fixture-admin'))").stdout
    (PRIVATE/"bootstrap-token").write_text(token);os.chmod(PRIVATE/"bootstrap-token",0o600)
    admin.call("POST","/api/auth/login",{"username":"fixture-admin","password":token})
    admin.call("GET","/api/admin/users",expected=403)
    admin.call("POST","/api/auth/change-password",{"currentPassword":token,"newPassword":"318642"})
    anonymous.call("POST","/api/auth/login",{"username":"fixture-admin","password":token},expected=401)
    note("headless CLI discloses no token; one-use bootstrap forces personal PIN replacement")
    def create(i):
        client=Client();client.cookies=admin.cookies.copy()
        return client.call("POST","/api/admin/users",{"username":f"fixture-teacher-{i}","password":f"52910{i}","role":"teacher"})["user"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:users=list(pool.map(create,range(4)))
    assert len(admin.call("GET","/api/admin/users"))==5
    teacher.call("POST","/api/auth/login",{"username":"fixture-teacher-0","password":"529100"})
    other.call("POST","/api/auth/login",{"username":"fixture-teacher-1","password":"529101"})
    teacher.call("GET","/api/admin/users",expected=403)
    teacher.call("POST","/api/admin/users",{"username":"forbidden","password":"123456"},expected=403)
    teacher.call("POST","/api/notebooks",{},expected=405)
    teacher.call("PUT","/api/notebooks/fixture-book",{"id":"fixture-book","name":"Synthetic notebook","pages":[]})
    saved=teacher.call("GET","/api/notebooks/fixture-book")
    assert saved["name"]=="Synthetic notebook"
    other.call("GET","/api/notebooks/fixture-book",expected=404)
    teacher.call("PUT","/api/notebooks/fixture-book",{},headers={"Origin":"https://foreign.invalid"},expected=403)
    note("concurrent personal accounts preserved; teacher/admin and notebook ownership and Origin denials enforced")
    copied=Client();copied.cookies={"session":teacher.cookies["session"]}
    copied.call("GET","/api/auth/me",expected=401)
    saved_cookies=teacher.cookies.copy()
    (PRIVATE/"teacher-cookies.json").write_text(json.dumps(saved_cookies));os.chmod(PRIVATE/"teacher-cookies.json",0o600)
    docker("restart","app")
    for _ in range(60):
        try:teacher.call("GET","/api/auth/me");break
        except (OSError,AssertionError):time.sleep(1)
    else:raise RuntimeError("session did not survive restart")
    note("copied JWT alone rejected; original two-cookie session survives restart")
    ticket=teacher.call("POST","/api/mobile-upload/session")
    token=urllib.parse.parse_qs(urllib.parse.urlsplit(ticket["url"]).query)["token"][0]
    assert ticket["url"].startswith("http://localhost:44961/upload?")
    (PRIVATE/"mobile-ticket").write_text(token);os.chmod(PRIVATE/"mobile-ticket",0o600)
    image=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")
    def upload(cap,expected):
        boundary="synthetic-boundary"
        body=(f"--{boundary}\r\nContent-Disposition: form-data; name=\"token\"\r\n\r\n{cap}\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"fixture.png\"\r\nContent-Type: image/png\r\n\r\n").encode()+image+f"\r\n--{boundary}--\r\n".encode()
        return anonymous.call("POST","/api/mobile-upload",body,{"Content-Type":"multipart/form-data; boundary="+boundary},expected=expected)
    upload(secrets.token_urlsafe(32),400)
    uploaded=upload(token,200)
    asset=teacher.call("GET",uploaded["url"]);assert asset==image
    other.call("GET",uploaded["url"],expected=404)
    anonymous.call("GET",uploaded["url"],expected=401)
    other.call("GET","/api/mobile-upload?token="+token,expected=404)
    anonymous.call("GET","/api/mobile-upload?token="+token,expected=401)
    assert teacher.call("GET","/api/mobile-upload?token="+token)["imageUrl"].startswith("data:image/png;base64,")
    assert teacher.call("GET","/api/mobile-upload?token="+token)["imageUrl"] is None
    upload(token,400)
    note("canonical QR URL; anonymous phone upload requires issued capability; asset/poll ownership and single-use enforced")
    teacher.call("GET","/api/gallery?q=fixture",expected=503)
    teacher.call("GET","/api/youtube?q=fixture",expected=503)
    anonymous.call("GET","/health/ready")
    note("optional external services disabled while readiness remains healthy")
    admin.call("PATCH","/api/admin/users",{"username":"fixture-teacher-0","newPassword":"729104"})
    teacher.call("GET","/api/auth/me",expected=401)
    teacher.call("POST","/api/auth/login",{"username":"fixture-teacher-0","password":"729104"})
    stale=Client();stale.cookies=teacher.cookies.copy()
    teacher.call("POST","/api/auth/logout")
    stale.call("GET","/api/auth/me",expected=401)
    admin.call("DELETE","/api/admin/users",{"username":"fixture-teacher-1"})
    other.call("GET","/api/auth/me",expected=401)
    note("PIN reset, account deletion and logout revoke existing server sessions")
    for i in range(5):anonymous.call("POST","/api/auth/login",{"username":"fixture-teacher-2","password":"invalid"},expected=401)
    anonymous.call("POST","/api/auth/login",{"username":"fixture-teacher-2","password":"529102"},expected=429)
    docker("restart","app")
    for _ in range(60):
        try:anonymous.call("GET","/health/ready");break
        except (OSError,AssertionError):time.sleep(1)
    anonymous.call("POST","/api/auth/login",{"username":"fixture-teacher-2","password":"529102"},expected=429)
    note("five failed PIN attempts lock account; lock survives restart")
    metadata=json.loads(docker("ps","--format","json").stdout)
    if isinstance(metadata,dict):metadata=[metadata]
    container=metadata[0]["ID"]
    inspection=json.loads(subprocess.check_output(["docker","inspect",container],text=True))[0]
    assert inspection["Config"]["User"]=="10001:10001"
    assert inspection["HostConfig"]["ReadonlyRootfs"] is True
    assert "SESSION_SECRET=" not in "\n".join(inspection["Config"]["Env"])
    note("UID 10001, read-only root and file-projected key verified on real standalone container")
    fixture={"project":project,"keyFile":str(key),"volume":next(m["Name"] for m in inspection["Mounts"] if m["Destination"]=="/data"),
             "asset":uploaded["url"],"users":[u["id"] for u in users],"teacher":users[0]["id"]}
    (PRIVATE/"fixture.json").write_text(json.dumps(fixture))
    (ROOT/".work/tafel-last-fixture").write_text(str(PRIVATE))

finally:
    docker("stop",check=False)
    (ROOT/"docs/implementation/evidence/grundschultafel-standalone.log").write_text(
        "$ .venv/bin/python scripts/prove_grundschultafel_standalone.py\n"+"\n".join(report)+"\n")
