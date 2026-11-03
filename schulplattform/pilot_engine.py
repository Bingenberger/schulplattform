"""Fixed selected-app pilot operations; production release control is separate."""
import json
from .deployment import APPS, ACTIONS, DeploymentBusy
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
        installed = self.installed() and app in self.pilot.apps
        backend = self.pilot.inspect_service(app, "app") if installed else None
        state = backend["State"] if backend else {}
        health=state.get("Health", {}).get("Status", "stopped")
        if app=="kompetenz-manager" and installed and state.get("Running"):
            worker=self.pilot.inspect_service(app,"worker")
            if not worker or not worker["State"]["Running"] or worker["State"].get("Health",{}).get("Status")!="healthy":
                health="degraded"
        return {"app": app, "installed": installed, "running": state.get("Running") is True,
                "health": health,
                "image": backend["Image"] if backend else None}

    def routes(self, maintenance):
        self.pilot.refresh_routes(maintenance)

    def execute(self, action, app):
        if action not in ACTIONS or app not in APPS:
            raise ValueError("Unknown deployment action or app")
        if action == "status":
            return self.status(app)
        if not self.installed() or app not in self.pilot.apps:
            raise StateError("Pilot must be installed first")
        if action == "start":
            self.pilot.up(check_running=False)  # rejects image changes; never a bootstrap
        with exclusive(self.pilot.directory / "state/installation.lock"):
            if action == "stop":
                if app == "zackboing" and self.status(app)["running"]:
                    pending = self.pilot.quiz_control("prepare-stop")
                    if pending["activeGames"]:
                        self.pilot.quiz_control("cancel-stop")
                        raise DeploymentBusy("Active games must finish before stop")
                self.routes({app})
                if app=="kompetenz-manager":
                    self.pilot.compose_command(app,"stop","--timeout","130","worker")
                self.pilot.compose_command(app, "stop", "--timeout", "130", "app")
            else:
                self.pilot.compose_command("infra", "up", "-d", "--no-build")
                if app == "schulwissen":
                    self.pilot.compose_command(app, "up", "-d", "--no-build", "--wait", "db")
                self.pilot.configure_proxy()
                services=["app","worker"] if app=="kompetenz-manager" else ["app"]
                self.pilot.compose_command(app, "up", "-d", "--no-build", "--wait", "--wait-timeout", "90", *services)
                if app == "zackboing":
                    self.pilot.quiz_control("cancel-stop")
                if self.status(app)["health"] != "healthy":
                    raise StateError("App failed readiness")
                self.routes(set())
            return self.status(app)
