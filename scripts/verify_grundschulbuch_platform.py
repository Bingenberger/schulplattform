"""Plattform-Abnahme des Grundschulbuchs mit dem echten Override aus catalogue.py.

Leeres Volume, Migration als Job (zweimal), `up --wait`, Container-Vertrag (kein Host-Port,
UID 10001, schreibgeschütztes Root-Dateisystem), Prüf-URLs des Katalogs, Erstzugang nur auf
einem Terminal (pty), Einlösen des Einmalcodes mit PIN, angemeldeter Zugriff, Herkunftsprüfung,
Betreiberverzeichnis und Galerie-Token im Container. Danach Neustart: Daten und Sitzung bleiben.

Aufruf: .venv/bin/python scripts/verify_grundschulbuch_platform.py [--image grundschulbuch:0.1.0-dev]
Keine Einmalcodes, PINs oder Schlüssel im Bericht.
"""
import argparse
import json
import os
import pty
import re
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schulplattform.catalogue import APPS  # noqa: E402
from schulplattform.stack import Layout, Stack, proxy_network  # noqa: E402

APP = ROOT / ".work/apps/grundschulbuch"
OUT = ROOT / "docs/implementation/evidence"
COMPOSE = (str(ROOT / ".work/docker-compose"),)
HOST = "buch.schule.test"
ORIGIN = f"https://{HOST}"


class LocalRelease:
    def __init__(self, image, commit):
        self.version, self.local_image, self.commit = "0.0.0-local", image, commit

    def image(self, name):
        return self.local_image if name == "grundschulbuch" else f"unused/{name}:0"

    def install_compose(self, app_id, target):
        target.mkdir(parents=True, exist_ok=True)
        data = subprocess.run(["git", "show", f"{self.commit}:docker-compose.yml"], cwd=APP, check=True,
                              capture_output=True).stdout
        (target / "docker-compose.yml").write_bytes(data)


def config():
    apps = {app: {"enabled": app in ("grundschulbuch", "bildergalerie", "gswb"), "hostname": f"{app}.schule.test"}
            for app in APPS}
    apps["grundschulbuch"]["hostname"] = HOST
    return {"schema": 1, "platform": {"management_domain": "verwaltung.schule.test", "acme_email": "it@schule.test",
                                      "acme_environment": "custom", "public_ipv4": "10.0.0.1"},
            "smtp": {"mode": "none"}, "backup": {"schedule": "02:30", "retention_days": 14}, "apps": apps}


def fetch(stack, path, method="GET", headers=None, body=None):
    """HTTP from a throwaway container on the app's proxy network (like Caddy would)."""
    script = ("const [u,m,h,b]=process.argv.slice(1);fetch(u,{method:m,headers:JSON.parse(h),redirect:'manual',"
              "body:b||undefined}).then(async r=>{console.log(JSON.stringify({status:r.status,"
              "cookie:r.headers.getSetCookie().join('\\n'),location:r.headers.get('location')||'',"
              "body:(await r.text()).slice(0,400)}))}).catch(e=>{console.log(JSON.stringify({status:0,body:String(e)}));})")
    out = subprocess.run(["docker", "run", "--rm", "--network", proxy_network("grundschulbuch"), "--user", "10001",
                          "--entrypoint", "node", stack.release.local_image, "-e", script,
                          f"http://grundschulbuch:3000{path}", method, json.dumps(headers or {}), body or ""],
                         check=True, capture_output=True, text=True, timeout=60).stdout
    return json.loads(out.strip().splitlines()[-1])


def bootstrap_on_tty(stack, name):
    """Run the documented first access in a real pseudo terminal; return the one-time code."""
    argv = [*COMPOSE, "-p", "sp-grundschulbuch", "--project-directory", str(stack.layout.apps / "grundschulbuch"),
            "-f", str(stack.layout.apps / "grundschulbuch/docker-compose.yml"),
            "-f", str(stack.layout.generated / "grundschulbuch.yml"),
            "exec", "app", "node", "scripts/bootstrap.mjs", name, "--admin"]
    pid, fd = pty.fork()
    if pid == 0:
        os.execvpe(argv[0], argv, stack.environment())
    output = b""
    while True:
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        output += chunk
    _, status = os.waitpid(pid, 0)
    text = output.decode(errors="replace")
    match = re.search(r"Einmalcode:\s*(\S+)", text)
    if os.waitstatus_to_exitcode(status) != 0 or not match:
        raise SystemExit("bootstrap on the terminal failed")
    return match[1], "angelegt" in text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="grundschulbuch:0.1.0-dev")
    parser.add_argument("--commit", default="HEAD")
    args = parser.parse_args()
    commit = subprocess.run(["git", "rev-parse", args.commit], cwd=APP, check=True, capture_output=True,
                            text=True).stdout.strip()
    report = {"app": "grundschulbuch", "commit": commit, "image": args.image,
              "imageId": subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", args.image], check=True,
                                        capture_output=True, text=True).stdout.strip(),
              "compose": subprocess.run([*COMPOSE, "version", "--short"], capture_output=True,
                                        text=True).stdout.strip(), "checks": {}}
    checks = report["checks"]
    with tempfile.TemporaryDirectory(prefix="sp-buch-") as tmp:
        layout = Layout(Path(tmp) / "root")
        stack = Stack(layout, config(), LocalRelease(args.image, commit), compose=COMPOSE)
        stack.apps = ("grundschulbuch",)
        layout.secrets.mkdir(parents=True, mode=0o700)
        layout.prepare()
        stack.materialize_secrets()
        stack.render_apps({"grundschulbuch": HOST})
        network = proxy_network("grundschulbuch")
        subprocess.run(["docker", "network", "create", "--internal", network], check=True, capture_output=True)
        try:
            for attempt in (1, 2):
                stack.compose("grundschulbuch", "run", "--rm", "--no-deps", "app", "node", "scripts/migrate.mjs")
                checks[f"migrationJob{attempt}"] = "ok"
            stack.compose("grundschulbuch", "up", "-d", "--wait", "app", timeout=300)
            container = stack.container("grundschulbuch", "app")
            assert not any(container["NetworkSettings"]["Ports"].values()), "host port published"
            assert container["Config"]["User"] == "10001:10001" and container["HostConfig"]["ReadonlyRootfs"]
            assert container["HostConfig"]["CapDrop"] == ["ALL"]
            checks["containerContract"] = {"user": container["Config"]["User"], "readOnlyRootfs": True,
                                           "publishedPorts": 0, "capDrop": "ALL",
                                           "networks": sorted(container["NetworkSettings"]["Networks"])}
            mounts = {m["Destination"]: m["RW"] for m in container["Mounts"]}
            assert mounts["/assets"] is False and mounts["/run/secrets/gallery-token"] is False
            assert mounts["/run/secrets/session-key"] is False and mounts["/data"] is True
            checks["mounts"] = mounts
            env = dict(item.split("=", 1) for item in container["Config"]["Env"])
            checks["environment"] = {key: env.get(key) for key in ("BASE_URL", "GALLERY_ORIGIN", "GALLERY_TOKEN_FILE",
                                                                  "WOERTERBUCH_ORIGIN", "GRUNDSCHULBUCH_ASSET_DIR")}
            for path, expected in (("/health/live", 200), ("/health/ready", 200), ("/anmelden", 200),
                                   ("/verwaltung", 307)):
                result = fetch(stack, path)
                assert result["status"] == expected, (path, result["status"])
                checks[f"GET {path}"] = result["status"]
            for check in APPS["grundschulbuch"].checks:
                result = fetch(stack, check.path, check.method, dict(check.headers))
                assert result["status"] == check.expected, (check.path, result)
                checks[f"{check.method} {check.path}"] = result["status"]
            # Without a terminal the code is refused (never ends up in logs).
            no_tty = subprocess.run([*COMPOSE, "-p", "sp-grundschulbuch", "--project-directory",
                                     str(layout.apps / "grundschulbuch"),
                                     "-f", str(layout.apps / "grundschulbuch/docker-compose.yml"),
                                     "-f", str(layout.generated / "grundschulbuch.yml"), "exec", "-T", "app", "node",
                                     "scripts/bootstrap.mjs", "Frau Prüfung"], env=stack.environment(),
                                    capture_output=True, text=True, stdin=subprocess.DEVNULL)
            assert no_tty.returncode == 2 and "Einmalcode:" not in no_tty.stdout
            checks["bootstrapWithoutTerminalRefused"] = {"exitCode": no_tty.returncode}
            code, created = bootstrap_on_tty(stack, "Frau Prüfung")
            checks["bootstrapOnTerminal"] = {"created": created}
            pin = f"{secrets.randbelow(900000) + 100000}"
            body = json.dumps({"name": "Frau Prüfung", "code": code, "pin": pin})
            foreign = fetch(stack, "/api/erstzugang", "POST", {"Origin": "https://evil.example",
                                                              "Content-Type": "application/json"}, body)
            assert foreign["status"] == 403
            checks["firstAccessForeignOrigin"] = 403
            redeemed = fetch(stack, "/api/erstzugang", "POST", {"Origin": ORIGIN, "Content-Type": "application/json"},
                             body)
            assert redeemed["status"] == 200, redeemed["status"]
            session = next(line for line in redeemed["cookie"].split("\n") if line.startswith("gsb_sitzung="))
            cookie = session.split(";")[0]
            attributes = session.lower()
            assert "httponly" in attributes and "secure" in attributes and "samesite=strict" in attributes
            checks["firstAccess"] = {"status": 200, "cookie": "HttpOnly; Secure; SameSite=Strict"}
            again = fetch(stack, "/api/erstzugang", "POST", {"Origin": ORIGIN, "Content-Type": "application/json"},
                          body)
            assert again["status"] == 401
            checks["codeSingleUse"] = 401
            classes = fetch(stack, "/verwaltung", headers={"Cookie": cookie})
            assert classes["status"] == 200, {k: classes[k] for k in ("status", "location")}
            checks["authenticatedGET /verwaltung"] = 200
            overview = fetch(stack, "/api/verwaltung", "POST", {"Origin": ORIGIN, "Cookie": cookie,
                                                               "Content-Type": "application/json"},
                             json.dumps({"action": "overview"}))
            assert overview["status"] == 200
            checks["adminOverview"] = 200
            inside = stack.compose("grundschulbuch", "exec", "-T", "app", "node", "-e",
                                   "const fs=require('fs');console.log(JSON.stringify({token:fs.readFileSync("
                                   "'/run/secrets/gallery-token','utf8').trim().length>=32,assets:fs.readdirSync("
                                   "'/assets').length,writeRoot:(()=>{try{fs.writeFileSync('/app/x','');return true}"
                                   "catch{return false}})(),data:fs.statSync('/data').mode.toString(8)}))")
            checks["insideContainer"] = json.loads(inside.strip().splitlines()[-1])
            assert checks["insideContainer"]["token"] and not checks["insideContainer"]["writeRoot"]
            stack.compose("grundschulbuch", "up", "-d", "--force-recreate", "--wait", "app", timeout=300)
            after = fetch(stack, "/verwaltung", headers={"Cookie": cookie})
            assert after["status"] == 200
            login = fetch(stack, "/api/anmelden", "POST", {"Origin": ORIGIN, "Content-Type": "application/json"},
                          json.dumps({"name": "Frau Prüfung", "pin": pin}))
            assert login["status"] == 200
            checks["afterRecreate"] = {"session": 200, "pinLogin": 200}
            report["result"] = "passed"
        finally:
            stack.compose("grundschulbuch", "down", "-v", "--timeout", "30", check=False)
            subprocess.run(["docker", "network", "rm", network], capture_output=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "grundschulbuch-platform.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
