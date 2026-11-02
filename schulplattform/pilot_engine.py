"""Fixed two-app pilot operations; production release control is separate."""
import json
from .deployment import APPS, ACTIONS
from .proxy import caddyfile
from .state import StateError
from .storage import exclusive


class PilotEngine:
    def __init__(self, pilot):
        self.pilot = pilot

    def installed(self):
        path = self.pilot.directory / "state/installation.json"
        return path.exists() and json.loads(path.read_text()).get("status") == "completed"

    def status(self, app):
        backend = self.pilot.inspect_service(app, "app") if self.installed() else None
        state = backend["State"] if backend else {}
        return {"app": app, "installed": self.installed(), "running": state.get("Running") is True,
                "health": state.get("Health", {}).get("Status", "stopped"),
                "image": backend["Image"] if backend else None}

    def routes(self, maintenance):
        self.pilot.refresh_routes(maintenance)

    def execute(self, action, app):
        if action not in ACTIONS or app not in APPS:
            raise ValueError("Unknown deployment action or app")
        if action == "status":
            return self.status(app)
        if not self.installed():
            raise StateError("Pilot must be installed first")
        if action == "start":
            self.pilot.up(check_running=False)  # rejects image changes; never a bootstrap
        with exclusive(self.pilot.directory / "state/installation.lock"):
            if action == "stop":
                self.routes({app})
                self.pilot.compose_command(app, "stop", "--timeout", "130", "app")
            else:
                self.pilot.compose_command("infra", "up", "-d", "--no-build")
                if app == "schulwissen":
                    self.pilot.compose_command(app, "up", "-d", "--no-build", "--wait", "db")
                    self.pilot.configure_proxy()
                self.pilot.compose_command(app, "up", "-d", "--no-build", "--wait", "--wait-timeout", "90", "app")
                if self.status(app)["health"] != "healthy":
                    raise StateError("App failed readiness")
                self.routes(set())
            return self.status(app)
