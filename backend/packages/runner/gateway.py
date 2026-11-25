"""Runner gateway client + job protocol (A7; 02 §10, corrections R-02/R-08/B9).

The runner PULLS jobs (claim/heartbeat/result); it has no inbound ports, no DB, no secrets.
The gateway relays; files move via short-lived signed URLs, never credentials.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.errors import ApiError

PROTOCOL_VERSION = "1.0.0"  # drift between phases is a BLOCKER (T-8.6)


@dataclass
class JobSpec:
    job_id: str
    kind: str                       # run_practice | run_official | upload_validate
    image_digest: str
    argv: list[str]
    env: dict[str, str] = field(default_factory=dict)
    limits: dict[str, int] = field(default_factory=lambda: {
        "cpu_ms": 5000, "wall_s": 10, "mem_mb": 512, "pids": 128, "out_bytes": 65536, "disk_mb": 256,
    })
    files: list[dict[str, str]] = field(default_factory=list)   # signed URLs, short-lived
    stdin_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id, "kind": self.kind, "image_digest": self.image_digest,
            "argv": self.argv, "env": self.env, "limits": self.limits, "files": self.files,
            "stdin_ref": self.stdin_ref, "protocol": PROTOCOL_VERSION,
        }


def validate_job_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Gateway treats everything from the runner as UNTRUSTED: schema + size validation (02 §10.4)."""
    allowed_states = {"finished", "timed_out", "killed", "failed"}
    if payload.get("state") not in allowed_states:
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "state", "problem": f"one of {sorted(allowed_states)}"}]})
    stdout = payload.get("stdout", "") or ""
    stderr = payload.get("stderr", "") or ""
    if len(stdout.encode()) > 262144 or len(stderr.encode()) > 262144:
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "stdout|stderr", "problem": "over 256 KB"}]})
    exit_code = payload.get("exit_code")
    if exit_code is not None and not isinstance(exit_code, int):
        raise ApiError("VALIDATION_ERROR", details={"fields": [{"field": "exit_code", "problem": "int"}]})
    return {
        "state": payload["state"],
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "usage": payload.get("usage", {}),
        "sandbox_fault": payload.get("sandbox_fault"),
    }


def sign_url(*, job_id: str, path: str, secret: str, ttl_s: int = 120) -> str:
    """Short-lived signed URL; the runner never receives storage credentials (T-8.2)."""
    expires = int(time.time()) + ttl_s
    sig = hashlib.sha256(f"{job_id}:{path}:{expires}:{secret}".encode()).hexdigest()[:32]
    return f"/internal/files/{path}?job={job_id}&expires={expires}&sig={sig}"


class RunnerGateway:
    """Admission control (02 §10.5): global queue cap, official > practice priority,
    round-robin per team, one concurrent per participant, kill switch stops handouts."""

    def __init__(self, *, runner_enabled: bool = True, max_queue_depth: int = 50,
                 max_concurrent_per_participant: int = 1, secret: str = "dev-secret"):
        self.runner_enabled = runner_enabled
        self.max_queue_depth = max_queue_depth
        self.max_concurrent = max_concurrent_per_participant
        self.secret = secret
        self._queue: list[dict[str, Any]] = []
        self._running: dict[str, dict[str, Any]] = {}      # participant_id -> job
        self._in_flight: set[str] = set()                   # queued OR running participants
        self._results: dict[str, dict[str, Any]] = {}
        self._cancelled: set[str] = set()             # job_ids cancelled via the API
        self._known: set[str] = set()                 # every job_id ever submitted
        self._last_team: str | None = None
        self._kill_switch_at: float | None = None

    def kill_switch(self) -> None:
        self._kill_switch_at = time.time()
        self.runner_enabled = False

    def submit(self, *, participant_id: str, team_id: str | None, kind: str, command_argv: list[str],
               image_digest: str, files: list[dict[str, str]] | None = None,
               stdin_ref: str | None = None) -> str:
        if not self.runner_enabled:
            raise ApiError("RUNNER_UNAVAILABLE")
        if len(self._queue) >= self.max_queue_depth:
            raise ApiError("RUN_RATE_LIMITED", details={"estimated_wait": f"{len(self._queue)} jobs"})
        if participant_id in self._in_flight:
            raise ApiError("RUN_RATE_LIMITED", details={"estimated_wait": "one concurrent run per participant"})
        job_id = str(uuid.uuid4())
        self._known.add(job_id)
        self._in_flight.add(participant_id)
        self._queue.append({
            "spec": JobSpec(job_id=job_id, kind=kind, image_digest=image_digest, argv=command_argv,
                            files=files or [], stdin_ref=stdin_ref).to_dict(),
            "participant_id": participant_id,
            "team_id": team_id,
            "priority": 0 if kind == "run_official" else 1,
            "enqueued_at": time.time(),
        })
        return job_id

    def claim(self, *, runner_id: str, capacity: int = 1) -> dict[str, Any] | None:
        """Runner pulls. Official jobs first; round-robin per team; kill switch stops handouts."""
        if not self.runner_enabled and not self._queue:
            return None
        if not self.runner_enabled:
            return None
        self._queue.sort(key=lambda j: (j["priority"], j["enqueued_at"]))
        picked = None
        for i, job in enumerate(self._queue):
            if job["team_id"] != self._last_team or len(self._queue) == 1:
                picked = self._queue.pop(i)
                break
        if picked is None and self._queue:
            picked = self._queue.pop(0)
        if picked is None:
            return None
        self._last_team = picked["team_id"]
        self._running[picked["participant_id"]] = picked
        return picked["spec"]

    def _release(self, participant_id: str) -> None:
        self._running.pop(participant_id, None)
        self._in_flight.discard(participant_id)

    def heartbeat(self, *, job_id: str, state: str) -> dict[str, Any]:
        # pull protocol: the runner learns about cancellation on its next heartbeat
        return {"cancel": not self.runner_enabled or job_id in self._cancelled}

    def cancel(self, job_id: str) -> None:
        """Best-effort cancel: mark the job; the runner stops on its next heartbeat."""
        self._cancelled.add(job_id)
        for pid, job in list(self._running.items()):
            if job["spec"]["job_id"] == job_id:
                self._release(pid)

    def result(self, *, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        validated = validate_job_result(payload)
        for pid, job in list(self._running.items()):
            if job["spec"]["job_id"] == job_id:
                self._release(pid)
        self._results[job_id] = validated
        return validated

    def get_result(self, job_id: str) -> dict[str, Any] | None:
        if job_id in self._results:
            return self._results[job_id]
        if job_id in self._cancelled:
            return {"state": "cancelling", "exit_code": None, "stdout": "", "stderr": ""}
        if job_id in self._known:
            return {"state": "queued", "exit_code": None, "stdout": "", "stderr": ""}
        return None
