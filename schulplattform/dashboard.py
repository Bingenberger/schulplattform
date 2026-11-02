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
from .deployment import APPS, ACTIONS, Client, DeploymentBusy
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
        entries = [(app_id, entry) for app_id, entry in catalogue.items()
                   if entry.get("public") is True or app_id in grants]
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

    @app.get("/admin")
    @administrator
    def admin():
        services = []
        for app_id in sorted(catalogue):
            try:
                status = client.execute("status", app_id)
            except (OSError, ValueError):
                status = {"running": False, "health": "unbekannt", "image": None}
            services.append((app_id, catalogue[app_id], status))
        with store.connect() as db:
            audit = db.execute("""SELECT a.at,COALESCE(u.username,a.actor) AS actor,a.action,a.app_id,a.outcome
                                  FROM audit a LEFT JOIN admins u ON u.id=a.actor ORDER BY a.id DESC LIMIT 50""").fetchall()
        return render_template("admin.html", services=services, audit=audit)

    @app.post("/admin/actions/<app_id>/<action>")
    @administrator
    def action(app_id, action):
        if app_id not in catalogue or action not in ("start", "stop"):
            abort(404)
        identity = g.admin["id"]
        store.audit(identity, action, app_id, "accepted")
        try:
            client.execute(action, app_id)
        except DeploymentBusy:
            store.audit(identity, action, app_id, "blocked")
            return render_template("operation_failed.html", busy=True), 409
        except (OSError, ValueError):
            store.audit(identity, action, app_id, "failed")
            return render_template("operation_failed.html"), 503
        store.audit(identity, action, app_id, "completed")
        return redirect(url_for("admin"))

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
