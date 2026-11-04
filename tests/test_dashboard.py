import base64
import re

import pytest
from schulplattform.dashboard import create_app
from schulplattform.dashboard_auth import AdminStore, otp

SEED = base64.b32encode(b"12345678901234567890").decode()


class Client:
    def __init__(self):
        self.calls = []
    def execute(self, action, app, params=None):
        self.calls.append((action, app))
        if action == "overview":
            raise ValueError("synthetic: overview not available in this fake")
        return {"running": action != "stop", "health": "healthy", "image": "sha256:synthetic"}


@pytest.fixture
def dashboard(tmp_path):
    clock = [1234567890]
    store = AdminStore(tmp_path / "state", clock=lambda: clock[0], initialize=True)
    identity = store.create_admin("synthetic.operator", "synthetic-password-123", SEED)
    backend = Client()
    catalogue = {
        "gswb": {"name": "Wörterbuch", "description": "Öffentliche Suche",
                 "url": "https://woerter.example.invalid", "public": True},
        "schulwissen": {"name": "Schulwissen", "description": "Nur freigegebene Konten",
                       "url": "https://wissen.example.invalid", "public": False}}
    app = create_app(tmp_path / "state", catalogue=catalogue, client=backend, store=store,
                     test_config={"TESTING": True, "SESSION_COOKIE_SECURE": False})
    return app, store, identity, backend, clock


def csrf(client, path="/login"):
    return re.search(r'name="csrf" value="([^"]+)"', client.get(path).text)[1]


def login(client, clock):
    return client.post("/login", data={"csrf": csrf(client), "username": "synthetic.operator",
        "password": "synthetic-password-123", "otp": otp(SEED, clock[0] // 30)})


def test_anonymous_admin_csrf_and_shell_inputs_denied(dashboard):
    app, store, identity, backend, clock = dashboard
    client = app.test_client()
    assert client.get("/admin").status_code == 302
    assert client.post("/admin/actions/gswb/start").status_code == 403
    assert client.post("/login", data={"csrf": "ü"}).status_code == 403
    assert not backend.calls
    assert login(client, clock).status_code == 302
    assert client.post("/admin/actions/gswb/shell", data={"csrf": csrf(client, "/admin")}).status_code == 404
    assert not any(action not in ("status", "overview") for action, app in backend.calls)


def test_tiles_require_public_route_or_confirmed_access_projection(dashboard):
    app, store, identity, backend, clock = dashboard
    client = app.test_client()
    assert "Wörterbuch" in client.get("/").text
    assert "https://wissen.example.invalid" not in client.get("/").text
    login(client, clock)
    assert "https://wissen.example.invalid" not in client.get("/").text
    store.confirm_access(identity, "schulwissen")
    assert "https://wissen.example.invalid" in client.get("/").text


def test_admin_actions_audited_logout_revokes_and_no_secrets_in_html(dashboard):
    app, store, identity, backend, clock = dashboard
    client = app.test_client()
    assert login(client, clock).status_code == 302
    page = client.get("/admin")
    assert page.status_code == 200
    assert SEED not in page.text
    assert "synthetic-password-123" not in page.text
    with client.session_transaction() as session:
        sid = session["sid"]
    assert sid not in page.text
    token = csrf(client, "/admin")
    assert client.post("/admin/actions/gswb/stop", data={"csrf": token}).status_code == 302
    assert ("stop", "gswb") in backend.calls
    with store.connect() as db:
        assert db.execute("SELECT outcome FROM audit ORDER BY id").fetchall()[1][0] == "completed"
    assert client.post("/logout", data={"csrf": token}).status_code == 302
    assert store.authenticate(sid) is None
    assert client.get("/admin").status_code == 302


def test_deployment_failure_is_generic_and_audited(dashboard):
    app, store, identity, backend, clock = dashboard
    client = app.test_client()
    login(client, clock)
    token = csrf(client, "/admin")
    def failure(action, app_id):
        raise ValueError("synthetic-sensitive-key")
    backend.execute = failure
    response = client.post("/admin/actions/gswb/start", data={"csrf": token})
    assert response.status_code == 503
    assert "synthetic-sensitive-key" not in response.text
    with store.connect() as db:
        assert db.execute("SELECT outcome FROM audit ORDER BY id DESC LIMIT 1").fetchone()[0] == "failed"


def test_busy_app_stop_explains_safe_next_step(dashboard):
    from schulplattform.deployment import DeploymentBusy
    app, store, identity, backend, clock = dashboard
    client = app.test_client()
    login(client, clock)
    token = csrf(client, "/admin")
    def busy(action, app_id):
        raise DeploymentBusy("synthetic-private-detail")
    backend.execute = busy
    response = client.post("/admin/actions/gswb/stop", data={"csrf": token})
    assert response.status_code == 409
    assert "Spiel abschließen" in response.text
    assert "synthetic-private-detail" not in response.text
    with store.connect() as db:
        assert db.execute("SELECT outcome FROM audit ORDER BY id DESC LIMIT 1").fetchone()[0] == "blocked"
