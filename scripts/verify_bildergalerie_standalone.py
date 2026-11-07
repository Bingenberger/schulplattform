"""Standalone-Abnahme der Bildergalerie: leere Volumes, Migration als Job, Erstzugang auf dem
Terminal, Upload, Freigabe, danach liefert die JSON-API v1 das Bild. Optional: Übernahme einer
Altdatenbank (--legacy DIR mit gallery.db und static/{uploads,display,thumbnails}).

Keine Zugangsdaten, Tokens oder Bildinhalte im Bericht.
"""
import argparse
import http.cookiejar
import io
import json
import os
import pty
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / ".work/apps/bildergalerie"
OUT = ROOT / "docs/implementation/evidence"


class Client:
    def __init__(self, base):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), NoRedirect)

    def request(self, path, data=None, headers=None, method=None):
        request = urllib.request.Request(self.base + path, data=data, headers=headers or {}, method=method)
        try:
            with self.opener.open(request, timeout=15) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as error:
            return error.code, error.read(), error.headers

    def csrf(self, path="/login"):
        return re.search(rb'name="csrf-token" content="([^"]+)"', self.request(path)[1])[1].decode()

    def form(self, path, fields, csrf_from="/login"):
        fields = {**fields, "csrf_token": self.csrf(csrf_from)}
        body = urllib.parse.urlencode(fields).encode()
        return self.request(path, body, {"Content-Type": "application/x-www-form-urlencoded"})


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def png(size=(320, 240)):
    """Einfarbiges PNG ohne Pillow (Host-Umgebung)."""
    import struct
    import zlib
    width, height = size
    raw = b"".join(b"\x00" + b"\xdc\x28\x28" * width for _ in range(height))
    chunk = lambda kind, data: (struct.pack(">I", len(data)) + kind + data
                                + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def multipart(name, data, boundary):
    return (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            "Content-Type: image/png\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy", help="Verzeichnis mit Altdaten (gallery.db, static/…)")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()

    project = "sp-galerie-standalone-" + secrets.token_hex(4)
    work = ROOT / ".work" / project
    work.mkdir(mode=0o700)
    key = work / "session-key"
    key.write_text(secrets.token_urlsafe(48))
    key.chmod(0o444)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = os.environ | {"GALLERY_PORT": str(port), "GALLERY_SECRET_FILE": str(key),
                        "GALLERY_BASE_URL": f"http://127.0.0.1:{port}"}
    compose = [str(ROOT / ".work/docker-compose"), "-p", project, "-f", str(APP / "docker-compose.yml")]
    report = {"operations": []}

    def run(*argv, expected=0, **kwargs):
        result = subprocess.run([*compose, *argv], env=env, capture_output=True, text=True, timeout=600, **kwargs)
        report["operations"].append({"command": " ".join(argv[:4]), "exitCode": result.returncode})
        if result.returncode != expected:
            raise SystemExit(f"{' '.join(argv)} -> {result.returncode}\n{result.stderr[-2000:]}")
        return result.stdout

    def bootstrap(name):
        """Einmal-Passwort über ein echtes Terminal (bootstrap.py schreibt nur nach /dev/tty)."""
        master, slave = pty.openpty()
        process = subprocess.Popen([*compose, "exec", "app", "python", "bootstrap.py", name], env=env,
                                   stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        output = b""
        while True:
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            output += chunk
        process.wait(timeout=60)
        os.close(master)
        match = re.search(rb"g\xc3\xbcltig:\r?\n([A-Za-z0-9_-]{20,})", output)
        return process.returncode, match[1].decode() if match else None

    client = Client(f"http://127.0.0.1:{port}")
    try:
        if not args.no_build:
            subprocess.run(["docker", "build", "-q", "--target", "final", "-t", "bildergalerie:0.1.0-dev", str(APP)],
                           check=True, capture_output=True, timeout=900)
        run("up", "-d", "--no-build")
        for _ in range(100):
            try:
                if client.request("/health/live")[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(0.2)
        status, body, _ = client.request("/health/ready")
        report["readyBeforeMigration"] = status
        assert status == 503 and json.loads(body)["status"] == "migration-required"

        if args.legacy:
            legacy = Path(args.legacy)
            # Altdaten in die Volumes kopieren (wie der Plattform-Import), danach migrieren
            container = run("ps", "-q", "app").strip()
            subprocess.run(["docker", "cp", str(legacy / "gallery.db"), f"{container}:/data/db/gallery.db"], check=True)
            for kind in ("uploads", "display", "thumbnails"):
                subprocess.run(["docker", "cp", str(legacy / "static" / kind), f"{container}:/data/media/"], check=True)
            subprocess.run(["docker", "run", "--rm", "--network", "none", "-u", "0", "-v", f"{project}_db:/data/db",
                            "-v", f"{project}_media:/data/media", "--entrypoint", "chown", "bildergalerie:0.1.0-dev",
                            "-R", "10001:10001", "/data/db", "/data/media"], check=True)
        migration = run("run", "--rm", "--no-deps", "-T", "app", "python", "migrate.py")
        report["migration"] = [line for line in migration.splitlines() if line]
        assert client.request("/health/ready")[0] == 200

        if args.legacy:
            api = json.loads(client.request("/api/v1/images?per_page=60")[1])
            report["legacyApiTotal"] = api["total"]
            sample = api["items"][0]
            report["legacyMedia"] = [client.request(sample["thumbnail_url"])[0], client.request(sample["display_url"])[0]]
            code, token = bootstrap("galerie-admin")
            report["bootstrapWithExistingAccounts"] = code
            assert code != 0 and token is None
            return report

        code, token = bootstrap("galerie-admin")
        report["bootstrap"] = code
        assert code == 0 and token
        code, again = bootstrap("zweites-konto")
        report["secondBootstrapRefused"] = code != 0 and again is None
        assert report["secondBootstrapRefused"]

        status, _, headers = client.form("/login", {"username": "galerie-admin", "password": token})
        assert status == 302 and headers["Location"].endswith("/change_password")
        new_password = secrets.token_urlsafe(18)
        status, _, _ = client.form("/change_password", {"old_password": token, "new_password": new_password,
                                                        "confirm_password": new_password}, "/change_password")
        assert status == 302
        report["passwordChanged"] = True

        boundary = secrets.token_hex(8)
        csrf = client.csrf("/upload")
        status, body, _ = client.request("/upload", multipart("Roter Apfel.png", png(), boundary),
                                         {"Content-Type": f"multipart/form-data; boundary={boundary}",
                                          "X-CSRF-Token": csrf})
        assert status == 200, body
        image_id = json.loads(body)["image_id"]
        anonymous = Client(client.base)
        report["apiBeforeReview"] = json.loads(anonymous.request("/api/v1/images?q=apfel")[1])["total"]
        assert report["apiBeforeReview"] == 0

        tags = json.dumps([{"value": "apfel"}, {"value": "obst"}])
        status, _, _ = client.form("/upload_review", {"image_ids": str(image_id), f"tags_{image_id}": tags,
                                                       f"style_{image_id}": "aquarell",
                                                       f"description_{image_id}": "Ein roter Apfel",
                                                       f"ai_tool_{image_id}": "", f"prompt_{image_id}": ""},
                                   "/upload_review")
        assert status == 302
        api = json.loads(anonymous.request("/api/v1/images?q=apfel")[1])
        item = api["items"][0]
        report["apiAfterReview"] = {"total": api["total"], "id": item["id"] == image_id, "tags": item["tags"],
                                    "style": item["style"], "size": [item["width"], item["height"]]}
        assert api["total"] == 1 and item["tags"] == ["apfel", "obst"]
        status, data, headers = anonymous.request(item["display_url"])
        report["display"] = {"status": status, "type": headers["Content-Type"], "nosniff": headers["X-Content-Type-Options"]}
        assert status == 200 and headers["Content-Type"] == "image/webp"
        report["tagsApi"] = json.loads(anonymous.request("/api/v1/tags?q=ap")[1])
        report["traversal"] = anonymous.request("/media/display/..%2F..%2Fdb%2Fgallery.db")[0]
        assert report["traversal"] == 404

        inspect = json.loads(subprocess.check_output(["docker", "inspect", run("ps", "-q", "app").strip()]))[0]
        report["container"] = {"user": inspect["Config"]["User"], "readOnly": inspect["HostConfig"]["ReadonlyRootfs"],
                               "capDrop": inspect["HostConfig"]["CapDrop"],
                               "ports": inspect["HostConfig"]["PortBindings"]}
        assert report["container"]["readOnly"] and report["container"]["user"] == "10001:10001"
        return report
    finally:
        subprocess.run([*compose, "down", "-v", "--remove-orphans"], env=env, capture_output=True, timeout=120)
        for path in work.iterdir():
            path.unlink()
        work.rmdir()


if __name__ == "__main__":
    import urllib.parse  # noqa: F401  (für Client.form)
    result = main()
    name = "bildergalerie-standalone-legacy.json" if "--legacy" in sys.argv else "bildergalerie-standalone.json"
    (OUT / name).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
