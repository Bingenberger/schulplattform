"""Dashboard administration pages for domains, certificates, mail, backups, updates and lifecycle."""
import base64
import re

import pytest

from schulplattform.dashboard import create_app
from schulplattform.dashboard_auth import AdminStore, otp

SEED = base64.b32encode(b"12345678901234567890").decode()
PASSWORD = "synthetic-password-123"


class Backend:
    def __init__(self):
        self.calls = []
        self.fail = set()

    def execute(self, action, app, params=None):
        self.calls.append((action, app, params))
        if action in self.fail:
            raise ValueError("synthetic-private-detail")
        if action == "overview":
            return {
                "release": "0.1.0", "management": {"hostname": "verwaltung.schule.example", "phase": "aktiv"},
                "apps": {"gswb": {"installed": True, "health": "healthy", "hostname": "woerterbuch.schule.example",
                                  "phase": "aktiv", "certificate": {"valid": True, "notAfter": "2027-01-30T00:00:00",
                                                                    "daysLeft": 80, "issuer": "CN=R11"}},
                         "schulwissen": {"installed": True, "health": "healthy", "hostname": "wissen.schule.example",
                                         "phase": "dns-ausstehend", "reason": "Kein A-/AAAA-Eintrag vorhanden"}},
                "smtp": {"mode": "relay", "host": "smtp.provider.example", "port": 587, "security": "starttls",
                         "username": "schule", "sender": "noreply@schule.example", "passwordSet": True},
                "backups": {"gswb": {"lastSuccess": "20261104T023000Z", "size": 1048576, "offsite": {"status": "ok"}}},
                "backupConfig": {"schedule": "02:30", "retention_days": 14},
                "openAcceptanceItems": [["gswb", "licenses", "A0 open"]],
                "updates": {"installed": "0.1.0", "available": []}}
        return {"ok": True, "detail": "Vom Anbieter angenommen."}


@pytest.fixture
def ui(tmp_path):
    clock = [1234567890]
    store = AdminStore(tmp_path / "state", clock=lambda: clock[0], initialize=True)
    store.create_admin("synthetic.operator", PASSWORD, SEED)
    backend = Backend()
    catalogue = {"gswb": {"name": "Wörterbuch", "description": "", "url": "https://woerterbuch.schule.example",
                          "public": True},
                 "schulwissen": {"name": "Schulwissen", "description": "", "url": "https://wissen.schule.example",
                                 "public": False}}
    app = create_app(tmp_path / "state", catalogue=catalogue, client=backend, store=store,
                     test_config={"TESTING": True, "SESSION_COOKIE_SECURE": False})
    client = app.test_client()
    token = re.search(r'name="csrf" value="([^"]+)"', client.get("/login").text)[1]
    client.post("/login", data={"csrf": token, "username": "synthetic.operator", "password": PASSWORD,
                                "otp": otp(SEED, clock[0] // 30)})
    return client, backend, store


def csrf(client, path):
    return re.search(r'name="csrf" value="([^"]+)"', client.get(path).text)[1]


def changes(backend):
    return [call for call in backend.calls if call[0] not in ("overview", "status")]


def test_pages_render_without_secrets(ui):
    client, backend, store = ui
    for path in ("/admin", "/admin/domains", "/admin/certificates", "/admin/mail", "/admin/backups", "/admin/updates"):
        page = client.get(path)
        assert page.status_code == 200, path
        assert SEED not in page.text and PASSWORD not in page.text
    assert "Kein A-/AAAA-Eintrag vorhanden" in client.get("/admin/domains").text
    assert "DNS ausstehend" in client.get("/admin").text
    assert "80" in client.get("/admin/certificates").text
    assert not changes(backend)


def test_domain_change_needs_preview_confirmation_and_valid_hostname(ui):
    client, backend, store = ui
    preview = client.get("/admin/domains/schulwissen?hostname=neu.schule.example")
    assert "SW_OEFFENTLICHE_URL" in preview.text and "https://neu.schule.example" in preview.text
    assert not changes(backend)
    token = csrf(client, "/admin")
    client.post("/admin/domains/schulwissen", data={"csrf": token, "hostname": "neu.schule.example"})
    assert not changes(backend)  # no confirmation, no change
    bad = client.post("/admin/domains/schulwissen", data={"csrf": token, "hostname": "x;rm -rf /", "confirmed": "1"})
    assert "Kein gültiger Hostname" in bad.text and not changes(backend)
    assert client.post("/admin/domains/schulwissen", data={"csrf": token, "hostname": "neu.schule.example",
                                                           "confirmed": "1"}).status_code == 302
    assert changes(backend) == [("domain-change", "schulwissen", {"hostname": "neu.schule.example"})]
    backend.fail.add("domain-change")
    failed = client.post("/admin/domains/schulwissen", data={"csrf": token, "hostname": "neu2.schule.example",
                                                             "confirmed": "1"})
    assert failed.status_code == 409 and "bisherige Konfiguration" in failed.text
    assert "synthetic-private-detail" not in failed.text
    assert client.post("/admin/domains/schulwissen", data={"hostname": "a.example", "confirmed": "1"}).status_code == 403


def test_mail_password_is_write_only_and_inputs_validated(ui):
    client, backend, store = ui
    token = csrf(client, "/admin/mail")
    client.post("/admin/mail", data={"csrf": token, "form": "password", "password": "Very-Secret-Relay-Password"})
    assert ("smtp-password", "_platform", {"password": "Very-Secret-Relay-Password"}) in backend.calls
    page = client.get("/admin/mail")
    assert "Very-Secret-Relay-Password" not in page.text and "gesetzt" in page.text
    before = len(changes(backend))
    client.post("/admin/mail", data={"csrf": token, "form": "test", "recipient": "a@b.example\nBcc: x@y.example"})
    client.post("/admin/mail", data={"csrf": token, "form": "settings", "host": "smtp.example", "port": "99999",
                                     "security": "tls", "username": "", "sender": "a@b.example", "sender_name": "x"})
    assert len(changes(backend)) == before
    result = client.post("/admin/mail", data={"csrf": token, "form": "test", "recipient": "lehrer@schule.example"})
    assert "Vom Anbieter angenommen." in result.text


def test_lifecycle_purge_requires_typed_confirmation_and_tiles_can_be_hidden(ui):
    client, backend, store = ui
    token = csrf(client, "/admin")
    assert "Wörterbuch" in client.get("/").text
    client.post("/admin/apps/gswb/hide", data={"csrf": token})
    assert "Wörterbuch" not in client.get("/").text
    client.post("/admin/apps/gswb/show", data={"csrf": token})
    assert "Wörterbuch" in client.get("/").text
    assert client.post("/admin/apps/gswb/purge", data={"csrf": token, "confirm": "GSWB!"}).status_code == 400
    assert not [c for c in changes(backend) if c[0] == "purge"]
    client.post("/admin/apps/gswb/purge", data={"csrf": token, "confirm": "gswb"})
    assert ("purge", "gswb", {"confirm": "gswb"}) in backend.calls
    assert client.post("/admin/apps/gswb/format-disk", data={"csrf": token}).status_code == 404
    with store.connect() as db:
        actions = [row[0] for row in db.execute("SELECT action FROM audit")]
    assert "tile-hide" in actions and "purge" in actions
