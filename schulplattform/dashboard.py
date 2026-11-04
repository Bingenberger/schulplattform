"""Server-rendered platform administration; never connects to the Docker socket."""
import argparse
from functools import wraps
import getpass
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from flask import Flask, abort, g, redirect, render_template, request, session, url_for

from .dashboard_auth import AdminStore, matching_counter
from .catalogue import DOMAIN_VARIABLES
from .deployment import APPS, ACTIONS, Client, DeploymentBusy, PLATFORM, valid_params
from .proxy import hostname


def create_app(state_dir, socket_path=None, key_file=None, catalogue=None, client=None, store=None, test_config=None, trusted_hosts=None):
    app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1] / "templates/dashboard"))
    store = store or AdminStore(state_dir)
    catalogue = catalogue or {}
    for app_id, entry in catalogue.items():
        origin = urlsplit(entry["url"])
        if (app_id not in APPS or origin.scheme != "https" or origin.username or origin.password or
                origin.path not in ("", "/") or origin.query or origin.fragment):
            raise ValueError("Invalid app catalogue")
        hostname(origin.hostname)
    if client is None:
        key = Path(key_file).read_bytes().strip()
        client = Client(socket_path, key)
    app.config.update(SECRET_KEY=store.cookie_key, SESSION_COOKIE_NAME="sp_admin",
                      TRUSTED_HOSTS=trusted_hosts or ["localhost", "127.0.0.1"],
                      SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE="Strict", MAX_CONTENT_LENGTH=16384)
    if test_config:
        app.config.update(test_config)
    app.extensions.update(admin_store=store, deployment_client=client)

    def csrf():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]
    app.jinja_env.globals["csrf"] = csrf
    from datetime import datetime, timezone
    app.jinja_env.filters["stamp"] = lambda value: datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    @app.before_request
    def authenticate_and_check_csrf():
        g.admin = store.authenticate(session.get("sid"))
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            expected, supplied = session.get("csrf", ""), request.form.get("csrf", "")
            if not expected or not supplied.isascii() or not secrets.compare_digest(expected, supplied):
                abort(403)

    @app.after_request
    def private_responses(response):
        response.headers.update({
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "same-origin",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        })
        return response

    def administrator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not g.admin:
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    @app.get("/")
    def tiles():
        grants = store.access(g.admin["id"]) if g.admin else set()
        concealed = hidden()
        entries = [(app_id, entry) for app_id, entry in catalogue.items()
                   if (entry.get("public") is True or app_id in grants) and app_id not in concealed]
        return render_template("tiles.html", entries=entries)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            token = store.login(request.form.get("username", ""), request.form.get("password", ""),
                                request.form.get("otp", ""))
            if token:
                session.clear()
                session["sid"] = token
                return redirect(url_for("admin"))
            error = "Anmeldung fehlgeschlagen oder vorübergehend gesperrt."
        return render_template("login.html", error=error), (401 if error else 200)

    @app.post("/logout")
    @administrator
    def logout():
        store.logout(session.get("sid"))
        session.clear()
        return redirect(url_for("tiles"))

    def hidden():
        with store.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS hidden_tiles(app_id TEXT PRIMARY KEY)")
            return {row[0] for row in db.execute("SELECT app_id FROM hidden_tiles")}

    def overview():
        try:
            data = client.execute("overview", PLATFORM, {})
            data["available"] = True
            return data
        except Exception:
            apps = {}
            for app_id in sorted(catalogue):
                try:
                    apps[app_id] = client.execute("status", app_id)
                except (OSError, ValueError):
                    apps[app_id] = {"running": False, "health": "unbekannt", "image": None}
            return {"available": False, "apps": apps}

    def audit_rows():
        with store.connect() as db:
            return db.execute("""SELECT a.at,COALESCE(u.username,a.actor) AS actor,a.action,a.app_id,a.outcome
                                 FROM audit a LEFT JOIN admins u ON u.id=a.actor ORDER BY a.id DESC LIMIT 50""").fetchall()

    def run(action, app_id, params=None, label=None):
        """Execute one fixed action with audit; returns (ok, result_or_status_code)."""
        identity = g.admin["id"]
        name = label or action
        store.audit(identity, name, app_id, "accepted")
        try:
            result = client.execute(action, app_id, params) if params is not None else client.execute(action, app_id)
        except DeploymentBusy:
            store.audit(identity, name, app_id, "blocked")
            return False, 409
        except (OSError, ValueError, RuntimeError):
            store.audit(identity, name, app_id, "failed")
            return False, 503
        store.audit(identity, name, app_id, "completed")
        return True, result

    def failed(code):
        return render_template("operation_failed.html", busy=code == 409), code

    @app.get("/admin")
    @administrator
    def admin():
        data = overview()
        services = [(app_id, catalogue[app_id], data["apps"].get(app_id, {})) for app_id in sorted(catalogue)]
        return render_template("admin.html", services=services, audit=audit_rows(), data=data, hidden=hidden())

    @app.post("/admin/actions/<app_id>/<action>")
    @administrator
    def action(app_id, action):
        if app_id not in catalogue or action not in ("start", "stop"):
            abort(404)
        ok, result = run(action, app_id)
        return redirect(url_for("admin")) if ok else failed(result)

    @app.post("/admin/apps/<app_id>/<operation>")
    @administrator
    def app_operation(app_id, operation):
        if app_id not in APPS:
            abort(404)
        if operation == "hide" or operation == "show":
            if app_id not in catalogue:
                abort(404)
            hidden()
            with store.connect() as db:
                if operation == "hide":
                    db.execute("INSERT OR IGNORE INTO hidden_tiles VALUES(?)", (app_id,))
                else:
                    db.execute("DELETE FROM hidden_tiles WHERE app_id=?", (app_id,))
            store.audit(g.admin["id"], "tile-" + operation, app_id, "completed")
            return redirect(url_for("admin"))
        params = {"dns-recheck": {}, "backup-now": {}, "uninstall": {}, "enable": {},
                  "maintenance-on": {"enabled": True}, "maintenance-off": {"enabled": False}}
        if operation == "purge":
            params["purge"] = {"confirm": request.form.get("confirm", "")}
        if operation not in params:
            abort(404)
        action_name = "maintenance" if operation.startswith("maintenance") else operation
        if not valid_params(action_name, app_id, params[operation]):
            abort(400)
        ok, result = run(action_name, app_id, params[operation], label=operation)
        if not ok:
            return failed(result)
        return redirect(url_for("backups") if operation == "backup-now" else url_for("admin"))

    @app.post("/admin/dns-recheck")
    @administrator
    def dns_recheck_all():
        ok, result = run("dns-recheck", PLATFORM, {})
        return redirect(url_for("domains")) if ok else failed(result)

    @app.get("/admin/domains")
    @administrator
    def domains():
        data = overview()
        return render_template("domains.html", data=data, catalogue=catalogue)

    @app.route("/admin/domains/<app_id>", methods=["GET", "POST"])
    @administrator
    def domain_change(app_id):
        if app_id not in catalogue:
            abort(404)
        data = overview()
        current = data["apps"].get(app_id, {}).get("hostname") or urlsplit(catalogue[app_id]["url"]).hostname
        candidate = request.values.get("hostname", "").strip().lower()
        error = None
        if candidate:
            try:
                hostname(candidate)
            except ValueError:
                error = "Kein gültiger Hostname."
        if request.method == "POST" and request.form.get("confirmed") == "1" and candidate and not error:
            ok, result = run("domain-change", app_id, {"hostname": candidate})
            if ok:
                return redirect(url_for("domains"))
            return render_template("domain_change.html", app_id=app_id, entry=catalogue[app_id], current=current,
                                   candidate=candidate, variables=DOMAIN_VARIABLES.get(app_id, ()),
                                   error="Der Wechsel wurde nicht übernommen; die bisherige Konfiguration gilt "
                                         "weiter. Häufigste Ursache: DNS-Eintrag zeigt noch nicht auf den Server."), 409
        return render_template("domain_change.html", app_id=app_id, entry=catalogue[app_id], current=current,
                               candidate=candidate if not error else "", variables=DOMAIN_VARIABLES.get(app_id, ()),
                               error=error, ip=data.get("management", {}).get("A"))

    @app.get("/admin/certificates")
    @administrator
    def certificates():
        return render_template("certificates.html", data=overview(), catalogue=catalogue)

    @app.get("/admin/backups")
    @administrator
    def backups():
        return render_template("backups.html", data=overview(), catalogue=catalogue)

    @app.get("/admin/updates")
    @administrator
    def updates():
        return render_template("updates.html", data=overview())

    @app.route("/admin/mail", methods=["GET", "POST"])
    @administrator
    def mail():
        message = None
        if request.method == "POST":
            kind = request.form.get("form")
            if kind == "settings":
                try:
                    port = int(request.form.get("port", ""))
                except ValueError:
                    port = 0
                params = {k: request.form.get(k, "").strip() for k in
                          ("host", "security", "username", "sender", "sender_name")}
                params["port"] = port
                if not valid_params("smtp-update", PLATFORM, params):
                    message = ("error", "Eingaben unvollständig oder ungültig; nichts geändert.")
                else:
                    ok, result = run("smtp-update", PLATFORM, params)
                    message = ("ok", "Einstellungen gespeichert, Relay neu gestartet.") if ok else \
                        ("error", "Speichern fehlgeschlagen; bisherige Einstellungen gelten.")
            elif kind == "password":
                params = {"password": request.form.get("password", "")}
                if not valid_params("smtp-password", PLATFORM, params):
                    message = ("error", "Passwort leer oder zu lang; nichts geändert.")
                else:
                    ok, _ = run("smtp-password", PLATFORM, params)
                    message = ("ok", "Passwort gespeichert.") if ok else ("error", "Speichern fehlgeschlagen.")
            elif kind == "test":
                params = {"recipient": request.form.get("recipient", "").strip()}
                if not valid_params("smtp-test", PLATFORM, params):
                    message = ("error", "Ungültige Empfängeradresse.")
                else:
                    ok, result = run("smtp-test", PLATFORM, params)
                    message = ("ok", result.get("detail", "Übergeben.")) if ok else \
                        ("error", "Testversand fehlgeschlagen; Relay-Zustand prüfen.")
            else:
                abort(400)
        return render_template("mail.html", data=overview(), message=message)

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready():
        import sqlite3
        try:
            with store.connect() as db:
                if db.execute("PRAGMA user_version").fetchone()[0] != 1:
                    return {"status": "not-ready"}, 503
        except sqlite3.Error:
            return {"status": "not-ready"}, 503
        return {"status": "ready"}

    return app


def setup_admin(directory, username):
    import base64
    import time
    with open("/dev/tty", "r+") as tty:
        password = getpass.getpass("Passwort (mindestens 12 Zeichen): ", stream=tty)
        confirmation = getpass.getpass("Passwort wiederholen: ", stream=tty)
        if password != confirmation:
            raise ValueError("Passwords do not match")
        seed = base64.b32encode(secrets.token_bytes(20)).decode()
        tty.write("TOTP-Schlüssel nur in die eigene Authenticator-App übernehmen:\n" + seed + "\n")
        tty.write("Aktuellen sechsstelligen Code eingeben: ")
        tty.flush()
        code = tty.readline().strip()
        if matching_counter(seed, code, time.time()) is None:
            raise ValueError("TOTP verification failed")
    store = AdminStore(directory, initialize=True)
    store.create_admin(username, password, seed)
    print("Plattform-Administrationskonto eingerichtet.")



def from_env():
    import json
    directory = os.environ["SP_DASHBOARD_STATE"]
    return create_app(directory, os.environ["SP_DEPLOYMENT_SOCKET"], os.environ["SP_DEPLOYMENT_KEY_FILE"],
                      json.loads(Path(os.environ["SP_APP_CATALOGUE"]).read_text()),
                      trusted_hosts=os.environ["SP_DASHBOARD_HOSTS"].split(","))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "serve"])
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--username")
    parser.add_argument("--socket", type=Path)
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--catalogue", type=Path)
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    if args.action == "setup":
        if not args.username:
            parser.error("--username is required")
        setup_admin(args.state_dir, args.username)
    else:
        import json
        if not args.socket or not args.key_file or not args.catalogue:
            parser.error("--socket, --key-file and --catalogue are required")
        app = create_app(args.state_dir, args.socket, args.key_file, json.loads(args.catalogue.read_text()))
        # Local diagnostic server only. Production uses gunicorn behind TLS.
        app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
