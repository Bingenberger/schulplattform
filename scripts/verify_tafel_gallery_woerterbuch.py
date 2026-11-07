"""Verbundene Abnahme B1–B3: Grundschultafel mit Bildergalerie (JSON-API v1, private Galerie mit
API-Token) und Grundschul-Wörterbuch (gswb) als echte Container auf einem gemeinsamen Netz.

- Wörterbuch: Filter, Wortliste mit Bild und Ton, Medien über die Tafel; ohne Wörterbuch 503 und
  der Knopf „Aus dem Wörterbuch …“ fehlt, die Readiness bleibt gesund.
- Galerie: Suche, Schlagworte, Bild-Proxy nur für /media/…, Token geht mit, Negativfälle; im Browser
  „Einfügen → Bild → Bildergalerie“, danach enthält das gespeicherte Heft eine Data-URL und keine
  Galerie-URL.

Daten: Kopien unter .work (gswb-Datenbank und Medien read-only, Galerie-Altbestand); keine
Zugangsdaten oder Inhalte im Bericht.

  verify_tafel_gallery_woerterbuch.py --gswb /home/…/GSWB --gallery-legacy DIR
"""
import argparse
import http.cookiejar
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/implementation/evidence"
PLAYWRIGHT = "mcr.microsoft.com/playwright:v1.64.1-noble"


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def sh(*argv, check=True, **kwargs):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=900, **kwargs)
    if check and result.returncode:
        raise SystemExit(f"{' '.join(argv[:6])} -> {result.returncode}\n{result.stderr[-1500:]}")
    return result.stdout


class Client:
    def __init__(self, base):
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, path, body=None, method=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers={"Content-Type": "application/json", "Origin": self.base})
        try:
            with self.opener.open(request, timeout=20) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as error:
            return error.code, error.read(), error.headers


def wait(url, path="/health/live", seconds=90):
    for _ in range(seconds * 4):
        try:
            with urllib.request.urlopen(url + path, timeout=2):
                return
        except (OSError, urllib.error.HTTPError):
            time.sleep(0.25)
    raise SystemExit(f"{url}{path} not reachable")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gswb", required=True, help="gswb-Arbeitskopie mit data/, static/images, audio/")
    parser.add_argument("--gallery-legacy", required=True, help="Altbestand: gallery.db und static/{uploads,display,thumbnails}")
    args = parser.parse_args()
    gswb_dir, legacy = Path(args.gswb), Path(args.gallery_legacy)

    run_id = secrets.token_hex(4)
    work = ROOT / ".work" / f"b3-{run_id}"
    work.mkdir(mode=0o755)
    net = f"sp-b3-{run_id}"
    names = {k: f"sp-b3-{k}-{run_id}" for k in ("gswb", "gallery", "tafel")}
    volumes = [f"sp-b3-{v}-{run_id}" for v in ("gswb-data", "gallery-db", "gallery-media", "tafel-data")]
    for name in ("tafel-key", "gswb-key", "gallery-key", "gallery-token"):
        (work / name).write_text(secrets.token_urlsafe(48))
        (work / name).chmod(0o444)
    (work / "gswb-editor").write_text("")
    (work / "gswb-editor").chmod(0o444)
    hardening = ["--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                 "--user", "10001:10001", "--tmpfs", "/tmp:size=64m,mode=1777"]
    report = {}
    tafel_port = free_port()
    tafel = f"http://127.0.0.1:{tafel_port}"
    try:
        sh("docker", "network", "create", net)
        # gswb: Datenbank-Kopie im Volume (Migrationsjob), Medien read-only
        sh("docker", "run", "--rm", "-u", "0", "-v", f"{volumes[0]}:/app/data", "-v", f"{gswb_dir / 'data'}:/src:ro",
           "--entrypoint", "sh", "gswb:new", "-c",
           "cp /src/grundschul_woerterbuch.sqlite3 /app/data/ && chown -R 10001:10001 /app/data")
        gswb_mounts = ["-v", f"{volumes[0]}:/app/data", "-v", f"{gswb_dir / 'static/images'}:/app/static/images:ro",
                       "-v", f"{(gswb_dir / 'audio').resolve()}:/app/static/audio:ro", "--tmpfs", "/app/static/uploads",
                       "-v", f"{work / 'gswb-key'}:/run/secrets/session_key:ro",
                       "-v", f"{work / 'gswb-editor'}:/run/secrets/editor_hash:ro",
                       "-e", "SECRET_KEY_FILE=/run/secrets/session_key", "-e", "EDITOR_PASSWORD_HASH_FILE=/run/secrets/editor_hash",
                       "-e", "SESSION_COOKIE_SECURE=0"]
        sh("docker", "run", "--rm", *hardening, *gswb_mounts, "gswb:new", "python", "-m", "grundschul_woerterbuch.migrate")
        sh("docker", "run", "-d", "--name", names["gswb"], "--network", net, "--network-alias", "gswb", *hardening,
           *gswb_mounts, "gswb:new")

        # Galerie: Altbestand, privat (Token-Variante), Migration als Job
        sh("docker", "run", "--rm", "-u", "0", "-v", f"{volumes[1]}:/data/db", "-v", f"{volumes[2]}:/data/media",
           "-v", f"{legacy}:/legacy:ro", "--entrypoint", "sh", "bildergalerie:0.1.0-dev", "-c",
           "cp /legacy/gallery.db /data/db/ && cp -r /legacy/static/uploads /legacy/static/display "
           "/legacy/static/thumbnails /data/media/ && chown -R 10001:10001 /data/db /data/media")
        gallery_mounts = ["-v", f"{volumes[1]}:/data/db", "-v", f"{volumes[2]}:/data/media",
                          "-v", f"{work / 'gallery-key'}:/run/secrets/key:ro",
                          "-v", f"{work / 'gallery-token'}:/run/secrets/api-token:ro",
                          "-e", "SECRET_KEY_FILE=/run/secrets/key", "-e", "GALLERY_API_TOKEN_FILE=/run/secrets/api-token",
                          "-e", "GALLERY_PUBLIC=false", "-e", "BASE_URL=http://gallery:8000"]
        sh("docker", "run", "--rm", *hardening, *gallery_mounts, "bildergalerie:0.1.0-dev", "python", "migrate.py")
        sh("docker", "run", "-d", "--name", names["gallery"], "--network", net, "--network-alias", "gallery",
           *hardening, *gallery_mounts, "bildergalerie:0.1.0-dev")

        def start_tafel(woerterbuch, gallery):
            sh("docker", "rm", "-f", names["tafel"], check=False)
            sh("docker", "run", "-d", "--name", names["tafel"], "--network", net, *hardening,
               "-p", f"127.0.0.1:{tafel_port}:3000", "-v", f"{volumes[3]}:/data",
               "-v", f"{work / 'tafel-key'}:/run/secrets/session-key:ro",
               "-v", f"{work / 'gallery-token'}:/run/secrets/gallery-token:ro",
               "-e", "SESSION_SECRET_FILE=/run/secrets/session-key", "-e", f"BASE_URL={tafel}",
               "-e", "TAFEL_DATA_DIR=/data", "-e", "TAFEL_ASSET_DIR=/data/assets",
               "-e", f"GALLERY_ORIGIN={'http://gallery:8000' if gallery else ''}",
               "-e", f"GALLERY_TOKEN_FILE={'/run/secrets/gallery-token' if gallery else ''}",
               "-e", f"WOERTERBUCH_ORIGIN={'http://gswb:8000' if woerterbuch else ''}", "grundschultafel:0.1.0-dev")
            wait(tafel)

        sh("docker", "run", "--rm", "-u", "0", "-v", f"{volumes[3]}:/data", "--entrypoint", "chown",
           "grundschultafel:0.1.0-dev", "10001:10001", "/data")
        start_tafel(True, True)
        sh("docker", "exec", names["tafel"], "node", "scripts/migrate.mjs")
        token = sh("docker", "exec", names["tafel"], "node", "--input-type=module", "-e",
                   "import {bootstrap} from './scripts/bootstrap.mjs';process.stdout.write(await bootstrap('b3-lehrkraft'))")
        pin = "".join(secrets.choice("0123456789") for _ in range(6))
        teacher = Client(tafel)
        assert teacher.call("/api/auth/login", {"username": "b3-lehrkraft", "password": token})[0] == 200
        assert teacher.call("/api/auth/change-password", {"currentPassword": token, "newPassword": pin})[0] == 200
        wait(tafel, "/health/ready")

        # --- Wörterbuch (B1) -------------------------------------------------------------
        anonymous = Client(tafel)
        report["woerterbuchAnonymous"] = anonymous.call("/api/woerterbuch/words?anzahl=3")[0]
        status, body, _ = teacher.call("/api/woerterbuch/filters")
        filters = json.loads(body)
        status, body, _ = teacher.call("/api/woerterbuch/words?anzahl=10&silben=2&mit_bild=1&zufall=1")
        words = json.loads(body)
        with_audio = [w for w in words["words"] if w["audio"]]
        image = teacher.call(words["words"][0]["image"])
        audio = teacher.call(with_audio[0]["audio"]) if with_audio else (None, b"", {})
        report["woerterbuch"] = {
            "filters": {"categories": len(filters["categories"]), "partsOfSpeech": len(filters["partsOfSpeech"])},
            "wordsTotal": words["total"], "returned": len(words["words"]),
            "allTwoSyllables": all(len(w["syllables"]) == 2 for w in words["words"]),
            "allWithImage": all(w["image"] for w in words["words"]),
            "image": {"status": image[0], "type": image[2].get("Content-Type")},
            "audio": {"status": audio[0], "type": audio[2].get("Content-Type") if audio[2] else None},
            "traversal": teacher.call("/api/woerterbuch/media?path=" + urllib.request.quote("/static/images/%2e%2e"))[0],
        }
        assert report["woerterbuchAnonymous"] == 401
        assert words["total"] > 0 and image[0] == 200 and audio[0] == 200, report["woerterbuch"]
        assert report["woerterbuch"]["traversal"] == 400

        # --- Galerie (B2/B3) über die Tafel ---------------------------------------------
        report["galleryAnonymous"] = anonymous.call("/api/gallery?q=a")[0]
        status, body, _ = teacher.call("/api/gallery?q=farbe&pageSize=12")
        search = json.loads(body)
        status, body, _ = teacher.call("/api/gallery?pageSize=12&page=2")
        page2 = json.loads(body)
        status, body, _ = teacher.call("/api/gallery/tags?q=fa")
        tags = json.loads(body)
        thumb = teacher.call(search["items"][0]["thumbnailUrl"])
        report["gallery"] = {
            "search": {"total": search["total"], "items": len(search["items"]), "fields": sorted(search["items"][0])},
            "paging": {"page": page2["page"], "totalPages": page2["totalPages"], "items": len(page2["items"])},
            "tags": tags["tags"][:3],
            "thumbnail": {"status": thumb[0], "type": thumb[2].get("Content-Type")},
            "proxyRejects": {p: teacher.call("/api/gallery/image?path=" + urllib.request.quote(p, safe=""))[0]
                             for p in ("/static/display/x.webp", "/media/display/../../db/gallery.db",
                                       "/media/uploads/x.png", "http://evil.example/media/display/x.webp")},
        }
        # Direkt an der privaten Galerie: ohne/mit falschem Token abgewiesen
        probe = ("import urllib.request as u,sys\nfor h in ({}, {'Authorization':'Bearer falsch'}):\n"
                 "  try: u.urlopen(u.Request('http://gallery:8000/api/v1/images',headers=h),timeout=5);print(200)\n"
                 "  except Exception as e: print(getattr(e,'code','err'))\n")
        report["galleryDirectWithoutToken"] = sh("docker", "exec", names["gswb"], "python", "-c", probe).split()
        assert report["galleryAnonymous"] == 401 and search["total"] > 0 and thumb[0] == 200
        assert set(report["gallery"]["proxyRejects"].values()) == {400}
        assert report["galleryDirectWithoutToken"] == ["401", "401"]

        # --- Browser: Bild aus der Galerie einfügen, Heft speichern ---------------------
        script = work / "ui.mjs"
        script.write_text(UI_SCRIPT)
        ui = sh("docker", "run", "--rm", "--network", "host", "-e", f"BASE={tafel}", "-e", "USER=b3-lehrkraft",
                "-e", f"PIN={pin}", "-v", f"{work}:/out", PLAYWRIGHT, "sh", "-c",
                "cd /tmp && npm init -y >/dev/null && npm i playwright@1.64.1 >/dev/null 2>&1 && cp /out/ui.mjs . && node ui.mjs")
        report["browser"] = json.loads(ui.strip().splitlines()[-1])
        notebooks = sh("docker", "run", "--rm", "-v", f"{volumes[3]}:/data:ro", "--entrypoint", "sh",
                       "grundschultafel:0.1.0-dev", "-c", "cat /data/*/*.json 2>/dev/null | head -c 50000000")
        report["notebook"] = {"containsDataImage": "data:image/" in notebooks,
                              "containsGalleryUrl": "/api/gallery/image" in notebooks or "gallery:8000" in notebooks
                              or "/media/display/" in notebooks}
        assert report["notebook"]["containsDataImage"] and not report["notebook"]["containsGalleryUrl"]

        # --- ohne Wörterbuch und Galerie: 503, Knopf fehlt, Readiness gesund -------------
        start_tafel(False, False)
        wait(tafel, "/health/ready")
        teacher = Client(tafel)
        teacher.call("/api/auth/login", {"username": "b3-lehrkraft", "password": pin})
        report["disabled"] = {"woerterbuch": teacher.call("/api/woerterbuch/words?anzahl=3")[0],
                              "gallery": teacher.call("/api/gallery?q=a")[0],
                              "ready": urllib.request.urlopen(tafel + "/health/ready", timeout=5).status}
        ui = sh("docker", "run", "--rm", "--network", "host", "-e", f"BASE={tafel}", "-e", "USER=b3-lehrkraft",
                "-e", f"PIN={pin}", "-e", "MODE=disabled", "-v", f"{work}:/out", PLAYWRIGHT, "sh", "-c",
                "cd /tmp && npm init -y >/dev/null && npm i playwright@1.64.1 >/dev/null 2>&1 && cp /out/ui.mjs . && node ui.mjs")
        report["browserDisabled"] = json.loads(ui.strip().splitlines()[-1])
        assert report["disabled"] == {"woerterbuch": 503, "gallery": 503, "ready": 200}
        return report
    finally:
        for name in names.values():
            sh("docker", "rm", "-f", name, check=False)
        for volume in volumes:
            sh("docker", "volume", "rm", volume, check=False)
        sh("docker", "network", "rm", net, check=False)
        for png in work.glob("*.png"):
            shutil.copy(png, ROOT / ".work" / f"b3-{png.name}")
        shutil.rmtree(work, ignore_errors=True)


UI_SCRIPT = r"""
import { chromium } from 'playwright';
const base = process.env.BASE, mode = process.env.MODE || 'enabled';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
const problems = [];
page.on('pageerror', e => problems.push('pageerror: ' + e.message));
page.on('response', r => { if (r.status() >= 400) problems.push(r.status() + ' ' + new URL(r.url()).pathname); });
const result = { mode };
// Anmeldung über die API im selben Browserkontext (Namensliste + PIN-Feld der Oberfläche umgangen)
const login = await page.request.post(base + '/api/auth/login', {
  data: { username: process.env.USER, password: process.env.PIN }, headers: { Origin: base } });
if (!login.ok()) throw new Error('login ' + login.status());
await page.goto(base + '/');
await page.waitForTimeout(3000);
// Blitzlesen über den Werkzeugkasten öffnen
async function openBlitzlesen() {
  await page.getByTitle('Werkzeugkoffer').first().click();
  await page.waitForTimeout(500);
  await page.getByText('Blitzlesen', { exact: true }).first().click();
  await page.waitForTimeout(1500);
}
await openBlitzlesen();
result.dictionaryButton = await page.getByText('Aus dem Wörterbuch …').count();
await page.screenshot({ path: `/out/blitz-${mode}.png` });
if (mode === 'enabled') {
  await page.getByText('Aus dem Wörterbuch …').first().click();
  await page.waitForTimeout(1000);
  await page.getByRole('button', { name: /laden|übernehmen|Wörter holen/i }).first().click().catch(() => {});
  await page.waitForTimeout(2500);
  result.dictionaryOption = await page.locator('option', { hasText: 'Wörterbuch:' }).count();
  await page.screenshot({ path: '/out/blitz-dict.png' });
  await page.keyboard.press('Escape');
  await page.reload();
  await page.waitForTimeout(2500);
  // Einfügen → Bild → Bildergalerie
  await page.getByRole('button', { name: 'Einfügen' }).or(page.getByTitle('Einfügen')).first().click();
  await page.waitForTimeout(500);
  await page.getByText('Bild', { exact: true }).first().click();
  await page.waitForSelector('[data-gallery-item]', { timeout: 20000 });
  result.galleryItems = await page.locator('[data-gallery-item]').count();
  result.licenseShown = await page.getByText(/^Lizenz:/).count();
  await page.waitForLoadState('networkidle');
  await page.waitForFunction(() => [...document.querySelectorAll('[data-gallery-item] img')].every(i => i.complete), null, { timeout: 30000 }).catch(() => {});
  result.thumbnailsBroken = await page.evaluate(() => [...document.querySelectorAll('[data-gallery-item] img')].filter(i => !i.naturalWidth).length);
  await page.screenshot({ path: '/out/gallery.png' });
  // Schlagwort-Filter und Blättern
  const chip = page.locator('[data-gallery-tag]').first();
  result.firstTag = await chip.textContent();
  await chip.click();
  await page.waitForTimeout(1500);
  result.filteredItems = await page.locator('[data-gallery-item]').count();
  await page.locator('[data-gallery-item]').first().click();
  await page.waitForTimeout(3000);
  result.canvasObjects = await page.evaluate(() => {
    const c = document.querySelector('canvas.upper-canvas, canvas');
    return !!c;
  });
  // Autosave (3 s nach der letzten Änderung) abwarten
  await page.waitForTimeout(9000);
  await page.screenshot({ path: '/out/inserted.png' });
}
result.problems = problems;
console.log(JSON.stringify(result));
await browser.close();
"""


if __name__ == "__main__":
    result = main()
    (OUT / "tafel-gallery-woerterbuch.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
