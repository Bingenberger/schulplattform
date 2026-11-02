"""Durable installation checkpoints, serialized across processes.

Every action must be idempotent for a given installation ID. A probe must verify
the actual side effect, not merely the existence of this journal. A process may
die after an action succeeds but before its receipt is committed.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import uuid

from .storage import atomic_json, exclusive


class StateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Step:
    name: str
    apply: object
    probe: object


def plan_digest(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


class Installation:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / "installation.json"

    def run(self, plan, steps):
        names = [step.name for step in steps]
        if not names or len(set(names)) != len(names) or any(
                not re.fullmatch("[a-z][a-z0-9-]{0,40}", name) for name in names):
            raise StateError("Invalid installation steps")
        digest = plan_digest(plan)
        with exclusive(self.directory / "installation.lock"):
            if self.path.is_symlink():
                raise StateError("Symlink state is not permitted")
            if self.path.exists():
                try:
                    state = json.loads(self.path.read_text())
                    valid = (
                        set(state) == {"schemaVersion", "id", "planDigest", "steps", "completed", "running", "status", "events"}
                        and state["schemaVersion"] == 1
                        and state["planDigest"] == digest and state["steps"] == names
                        and isinstance(state["completed"], list)
                        and state["completed"] == names[:len(state["completed"])]
                        and state["running"] in (None, *names)
                        and state["status"] in ("running", "failed", "completed")
                        and isinstance(state["events"], list)
                    )
                    uuid.UUID(state["id"])
                    if not valid:
                        raise ValueError()
                    next_name = names[len(state["completed"])] if len(state["completed"]) < len(names) else None
                    if state["running"] not in (None, next_name):
                        raise ValueError()
                    if state["status"] == "completed" and (next_name is not None or state["running"] is not None):
                        raise ValueError()
                except (ValueError, KeyError, TypeError, AttributeError):
                    raise StateError("State invalid or plan changed; explicit recovery/upgrade required") from None
            else:
                state = dict(schemaVersion=1, id=str(uuid.uuid4()), planDigest=digest,
                             steps=names, completed=[], running=None, status="running", events=[])
                atomic_json(self.path, state)
            if state["status"] == "completed":
                return state  # no filesystem writes and no actions on repeated installation

            def event(step, outcome):
                state["events"].append(dict(step=step, outcome=outcome,
                    at=datetime.now(timezone.utc).isoformat()))
                atomic_json(self.path, state)

            for step in steps[len(state["completed"]):]:
                recovering = state["running"] == step.name
                state.update(running=step.name, status="running")
                event(step.name, "resuming" if recovering else "started")
                try:
                    if not (recovering and step.probe(state["id"]) is True):
                        step.apply(state["id"])
                    if step.probe(state["id"]) is not True:
                        raise StateError("Step verification failed")
                except BaseException:
                    state["status"] = "failed"
                    event(step.name, "failed")  # never persist exception text or credentials
                    raise
                state["completed"].append(step.name)
                state["running"] = None
                event(step.name, "verified")
            state["status"] = "completed"
            event("completed", "verified")
            return state
