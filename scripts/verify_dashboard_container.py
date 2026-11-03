"""Real dashboard container -> authenticated Unix service -> pilot app controls."""
import base64
from http.cookies import SimpleCookie
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import socket
import ssl
import subprocess
import sys
import threading
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schulplattform.dashboard_auth import otp
from schulplattform.deployment import Gate, Server
from schulplattform.pilot import Pilot, INFRASTRUCTURE
from schulplattform.pilot_engine import PilotEngine

import argparse
parser=argparse.ArgumentParser()
parser.add_argument("--state-dir", default=".work/pilot-v2")
args=parser.parse_args()
pilot = Pilot(ROOT / args.state_dir)
control_app = "grundschultafel" if "grundschultafel" in pilot.apps else "gswb"
directory = ROOT / ".work" / ("dashboard-test-" + secrets.token_hex(5))
directory.mkdir(mode=0o700)
sockets = directory / "sockets"
sockets.mkdir(mode=0o750)
key = secrets.token_urlsafe(48).encode()
key_path = directory / "client-key"
key_path.write_bytes(key)
key_path.chmod(0o444)  # parent 0700; only this file is projected into the container
password = secrets.token_urlsafe(32)
seed = base64.b32encode(secrets.token_bytes(20)).decode()
project = "sp-dashboard-" + secrets.token_hex(5)
state_volume = project + "-state"
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
catalogue = {
    "gswb": {"name": "Wörterbuch", "description": "Öffentliche Wörterbuchsuche",
             "url": "https://woerter.localhost:" + str(pilot.config["port"]), "public": True},
    "schulwissen": {"name": "Schulwissen", "description": "Schulinterne Inhalte",
                   "url": "https://wissen.localhost:" + str(pilot.config["port"]), "public": False}}
if "grundschultafel" in pilot.apps:
    catalogue["grundschultafel"]={"name":"Grundschultafel","description":"Persönliche Lehrertafel",
        "url":"https://tafel.localhost:"+str(pilot.config["port"]), "public":False}
(directory / "apps.json").write_text(json.dumps(catalogue))
(directory / "Caddyfile").write_text("{\n admin localhost:2019\n local_certs\n}\nverwaltung.localhost {\n reverse_proxy dashboard:8000\n}\n")
compose_data = {
    "services": {
        "dashboard": {
            "image": "schulplattform-dashboard:0.1.0-dev", "user": "10001:" + str(os.getgid()),
            "read_only": True, "cap_drop": ["ALL"], "security_opt": ["no-new-privileges:true"],
            "tmpfs": ["/tmp:size=64m,mode=1777"], "mem_limit": "384m", "cpus": 0.5, "pids_limit": 128,
            "volumes": [state_volume + ":/state", str(sockets) + ":/run/management:ro",
                        str(key_path) + ":/run/secrets/deployment-key:ro",
                        str(directory / "apps.json") + ":/config/apps.json:ro"],
            "environment": {"SP_DASHBOARD_STATE": "/state", "SP_DEPLOYMENT_SOCKET": "/run/management/deploy.sock",
                            "SP_DEPLOYMENT_KEY_FILE": "/run/secrets/deployment-key", "SP_APP_CATALOGUE": "/config/apps.json",
                            "SP_DASHBOARD_HOSTS": "verwaltung.localhost,localhost,127.0.0.1"},
            "networks": ["management"]},
        "proxy": {
            "image": INFRASTRUCTURE["caddy"], "ports": [f"127.0.0.1:{port}:443"],
            "volumes": [str(directory / "Caddyfile") + ":/etc/caddy/Caddyfile:ro", "tls-data:/data", "tls-config:/config"],
            "networks": ["edge", "management"], "mem_limit": "128m", "cpus": 0.5, "pids_limit": 128}
    },
    "networks": {"edge": {}, "management": {"internal": True}},
    "volumes": {state_volume: {"external": True}, "tls-data": {}, "tls-config": {}}
}
for service in compose_data["services"].values():
    service["logging"] = {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}}
(directory / "compose.json").write_text(json.dumps(compose_data))
base = [str(ROOT / ".work/docker-compose"), "-p", project, "-f", str(directory / "compose.json")]
operations = []

def run(argv, input=None):
    result = subprocess.run(argv, input=input, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    operations.append({"command": argv, "exitCode": result.returncode})
    if result.returncode:
        raise RuntimeError("Dashboard integration command failed; no potentially sensitive output emitted")
    return result.stdout

gate = Gate(directory / "deployment.sqlite3", key, PilotEngine(pilot))
cookies = {}
context = None

def request(path, method="GET", data=None):
    global context
    connection = http.client.HTTPSConnection("verwaltung.localhost", port, context=context, timeout=180)
    connection.sock = context.wrap_socket(socket.create_connection(("127.0.0.1", port), timeout=5),
                                          server_hostname="verwaltung.localhost")
    connection.sock.settimeout(180)
    headers = {"Cookie": "; ".join(name + "=" + value for name, value in cookies.items())}
    body = None
    if data is not None:
        body = urlencode(data)
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    html = response.read().decode()
    for name, value in response.getheaders():
        if name.lower() == "set-cookie":
            parsed = SimpleCookie()
            parsed.load(value)
            for key_name, morsel in parsed.items():
                if morsel.value:
                    cookies[key_name] = morsel.value
                else:
                    cookies.pop(key_name, None)
    status = response.status
    connection.close()
    return status, html

def token(html):
    return re.search(r'name="csrf" value="([^"]+)"', html)[1]

server = Server(sockets / "deploy.sock", gate, allowed_uid=10001)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
report = None
try:
    run(["docker", "volume", "create", state_volume])
    setup = """import json,sys; from schulplattform.dashboard_auth import AdminStore; data=json.load(sys.stdin); store=AdminStore('/state',initialize=True); store.create_admin(data['username'],data['password'],data['seed']); print('initialized')"""
    run(["docker", "run", "--rm", "-i", "--network", "none", "--user", "10001:" + str(os.getgid()),
         "-v", state_volume + ":/state", "schulplattform-dashboard:0.1.0-dev", "python", "-c", setup],
        input=json.dumps({"username": "synthetic.operator", "password": password, "seed": seed}))
    run(base + ["up", "-d", "--no-build", "--wait", "--wait-timeout", "90"])
    proxy = run(base + ["ps", "-q", "proxy"]).strip()
    run(["docker", "cp", proxy + ":/data/caddy/pki/authorities/local/root.crt", str(directory / "root.crt")])
    context = ssl.create_default_context(cafile=str(directory / "root.crt"))
    status, html = request("/")
    assert status == 200 and "Wörterbuch" in html
    assert catalogue["schulwissen"]["url"] not in html
    assert request("/admin")[0] == 302
    assert request("/admin/actions/"+control_app+"/start", "POST", {})[0] == 403
    status, html = request("/login")
    assert status == 200
    assert request("/login", "POST", {"csrf": token(html), "username": "synthetic.operator",
                                     "password": password, "otp": "invalid"})[0] == 401
    import time
    status, html = request("/login")
    assert request("/login", "POST", {"csrf": token(html), "username": "synthetic.operator",
                                     "password": password, "otp": otp(seed, int(time.time() // 30))})[0] == 302
    status, html = request("/admin")
    assert status == 200 and "Plattform verwalten" in html
    assert password not in html and seed not in html and key.decode() not in html
    csrf = token(html)
    assert request("/admin/actions/"+control_app+"/shell", "POST", {"csrf": csrf})[0] == 404
    assert request("/admin/actions/"+control_app+"/start", "POST", {"csrf": csrf})[0] == 302
    assert PilotEngine(pilot).status(control_app)["health"] == "healthy"
    assert request("/admin/actions/"+control_app+"/stop", "POST", {})[0] == 403
    assert PilotEngine(pilot).status(control_app)["running"]
    assert request("/admin/actions/"+control_app+"/stop", "POST", {"csrf": csrf})[0] == 302
    assert not PilotEngine(pilot).status(control_app)["running"]
    assert request("/logout", "POST", {"csrf": csrf})[0] == 302
    assert request("/admin")[0] == 302
    web = run(base + ["ps", "-q", "dashboard"]).strip()
    info = json.loads(run(["docker", "inspect", web]))[0]
    assert info["Config"]["User"].split(":")[0] == "10001"
    assert info["HostConfig"]["ReadonlyRootfs"]
    assert not any("docker.sock" in item["Source"] or "docker.sock" in item["Destination"] for item in info["Mounts"])
    assert key.decode() not in "\n".join(info["Config"]["Env"])
    report = {"scope": "synthetic admin, real dashboard container, real authenticated Unix service and pilot actions",
              "imageId": info["Image"],
              "tls": True, "totpRequired": True, "anonymousAdminDenied": True, "csrfEnforced": True,
              "unknownActionDenied": True, "appStartAndStop": True, "controlledApp": control_app, "logoutRevokes": True,
              "noDockerSocket": True, "nonRootReadOnly": True, "noCredentialsInHtmlOrEnv": True,
              "appAccessProjectionEnforced": True}
finally:
    try:
        run(base + ["down"])
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
        pilot.stop()
        out = ROOT / "docs/implementation/evidence"
        (out / "dashboard-container-operations.json").write_text(json.dumps(operations, indent=2) + "\n")
        if report is not None:
            report["stoppedAfterTest"] = True
            (out / "dashboard-container.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
