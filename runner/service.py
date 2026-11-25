#!/usr/bin/env python3
"""Runner service: real sandboxed execution + the Phase 3 stub (A7; R-02/R-24/D.2/B9).

Sandbox (per run): user+network namespace via `unshare -rn` (no egress; loopback only),
temporary workspace dir, resource limits via preexec_fn, wall-clock kill of the process
tree, output cap with truncation marker, workspace scrub after. In prod the runner runs
on a SEPARATE VM with no internet route; the namespace here is defense in depth.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

UNSHARE = Path("/usr/bin/unshare")
_USE_NS = UNSHARE.exists()

DEFAULT_LIMITS = {"cpu_ms": 5000, "wall_s": 10, "mem_mb": 512, "pids": 128, "out_bytes": 65536, "disk_mb": 256}


@dataclass
class RunOutcome:
    state: str                 # finished | timed_out | killed | failed
    exit_code: int | None
    stdout: str
    stderr: str
    truncated: bool
    killed_reason: str | None = None


def _limit_process(limits: dict[str, int]) -> None:  # pragma: no cover — runs in child
    os.setsid()
    try:
        import resource

        cpu_s = max(1, limits.get("cpu_ms", 5000) // 1000)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 1))
        mem = limits.get("mem_mb", 512) * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_NPROC, (limits.get("pids", 128), limits.get("pids", 128)))
        resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
    except OSError:  # best-effort limits on kernels without rlimits; wall-clock kill still applies
        pass


def execute_sandboxed(*, argv: list[str], files: dict[str, str] | None = None,
                      stdin_data: str | None = None, limits: dict[str, int] | None = None,
                      env_allow: dict[str, str] | None = None) -> RunOutcome:
    """Run argv in a throwaway workspace with hard limits; scrub the workspace after (GAP-03).

    argv comes ONLY from the server-side command_id table (B9) — participants never send argv.
    """
    limits = {**DEFAULT_LIMITS, **(limits or {})}
    workdir = tempfile.mkdtemp(prefix="bhctf-run-")
    out_cap = int(limits.get("out_bytes", 65536))
    truncated = False
    try:
        for rel, content in (files or {}).items():
            # path traversal defense (SEC-03): no absolute paths, no ..
            if os.path.isabs(rel) or ".." in rel.split("/"):
                return RunOutcome("failed", None, "", "rejected: unsafe path", True, "unsafe_path")
            dest = os.path.join(workdir, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(content)

        env = {"PATH": "/usr/bin:/bin", "HOME": workdir, "LC_ALL": "C", "TZ": "UTC"}
        env.update(env_allow or {})
        # user+net namespace: no egress, loopback only (escape tests #1/#2). Falls back to
        # plain execution only when user namespaces are unavailable (VM isolation covers it).
        run_argv = [str(UNSHARE), "-rn", "--", *argv] if _USE_NS else list(argv)
        proc = subprocess.Popen(
            run_argv, cwd=workdir, env=env,
            stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=lambda: _limit_process(limits),  # noqa: PLW1509 — runner is single-threaded
        )
        wall_s = float(limits.get("wall_s", 10))
        start = time.monotonic()
        try:
            out_b, err_b = proc.communicate(
                input=stdin_data.encode() if stdin_data is not None else None, timeout=wall_s
            )
        except subprocess.TimeoutExpired:
            # kill the whole process tree (setsid → group kill)
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                proc.kill()
            out_b, err_b = proc.communicate()
            return RunOutcome("timed_out", None, out_b[:out_cap].decode("utf-8", "replace"),
                              err_b[:out_cap].decode("utf-8", "replace"), True, "wall_timeout")
        _ = start
        stdout = out_b.decode("utf-8", "replace")
        stderr = err_b.decode("utf-8", "replace")
        if len(out_b) > out_cap:
            truncated = True
            stdout = stdout[:out_cap] + "\n…[truncated]"
        if len(err_b) > out_cap:
            truncated = True
            stderr = stderr[:out_cap] + "\n…[truncated]"
        state = "finished" if proc.returncode == 0 else ("failed" if proc.returncode and proc.returncode < 0 else "finished")
        return RunOutcome(state, proc.returncode, stdout, stderr, truncated)
    except Exception as exc:  # noqa: BLE001
        return RunOutcome("failed", None, "", f"sandbox fault: {exc}", False, "sandbox_fault")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)   # scrub between runs (GAP-03)


class StubRunner:
    """Phase 3 stub (T-3.0): deterministic delay + canned results; refuses prod."""

    FIXTURE_DIGESTS: ClassVar[dict[str, bool]] = {"sha256:stub-python-3.12": True, "sha256:stub-node-22": True}

    def __init__(self, *, env: str = "dev", delay_s: float = 0.05) -> None:
        if env == "prod":
            raise RuntimeError("RUNNER_MODE=stub refuses to start in ENV=prod (R-02/D.2)")
        self.delay_s = delay_s
        self._jobs: dict[str, dict[str, Any]] = {}

    def claim(self, spec: dict[str, Any]) -> dict[str, Any]:
        digest = spec.get("image_digest", "")
        if digest not in self.FIXTURE_DIGESTS:
            return {"error": "IMAGE_NOT_ALLOWED", "detail": digest}
        job_id = spec["job_id"]
        self._jobs[job_id] = {"spec": spec, "claimed_at": time.time()}
        return {"accepted": True, "job_id": job_id, "delay_s": self.delay_s}

    def result(self, job_id: str) -> dict[str, Any]:
        job = self._jobs.get(job_id)
        if not job:
            return {"error": "UNKNOWN_JOB"}
        canned = "stub-output: " + hashlib.sha256(job_id.encode()).hexdigest()[:16]
        return {
            "state": "finished", "exit_code": 0,
            "stdout": canned, "stderr": "",
            "usage": {"cpu_ms": 10, "mem_mb": 16, "wall_s": self.delay_s},
            "started_at": job["claimed_at"], "finished_at": time.time(),
            "sandbox_fault": None,
        }


def compare_output(actual: str, expected: str, mode: str = "exact") -> bool:
    """Official runs: the EVALUATOR compares, never the runner (02 §9.3)."""
    if mode == "exact":
        return actual == expected
    if mode == "trimmed":
        return "\n".join(x.strip() for x in actual.strip().splitlines()) == \
               "\n".join(x.strip() for x in expected.strip().splitlines())
    if mode == "json_structured":
        import json

        try:
            return json.loads(actual) == json.loads(expected)
        except Exception:  # noqa: BLE001
            return False
    if mode == "regex":
        import re

        return re.fullmatch(expected, actual) is not None
    raise ValueError(f"unknown comparison mode {mode}")
