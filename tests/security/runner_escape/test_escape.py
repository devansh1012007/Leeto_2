"""The 8 runner escape tests (06 §5 / T-8.4). These run the REAL sandbox in-process."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

from service import execute_sandboxed

LIMITS = {"wall_s": 8, "mem_mb": 512, "out_bytes": 65536}


def test_1_no_egress():
    out = execute_sandboxed(argv=["/usr/bin/curl", "-sS", "--max-time", "3", "https://example.com"], limits=LIMITS)
    assert out.state in ("failed", "timed_out") or "Example Domain" not in out.stdout


def test_2_no_ping():
    out = execute_sandboxed(argv=["/bin/ping", "-c", "1", "-W", "2", "8.8.8.8"], limits=LIMITS)
    assert out.exit_code != 0 or out.state != "finished"


def test_3_passwd_not_readable_from_workspace():
    out = execute_sandboxed(argv=["/bin/cat", "/etc/shadow"], limits=LIMITS)
    assert "root:" not in out.stdout


def test_4_fork_bomb_contained():
    out = execute_sandboxed(argv=["/bin/sh", "-c", "i=0; while true; do sleep 100 & i=$((i+1)); done"],
                            limits={"wall_s": 4, "pids": 64, "out_bytes": 4096})
    assert out.state in ("timed_out", "failed", "killed")


def test_5_huge_stdout_truncated():
    out = execute_sandboxed(argv=["/bin/sh", "-c", "yes x | head -c 1000000"],
                            limits={"wall_s": 5, "out_bytes": 8192})
    assert out.truncated and len(out.stdout) < 20_000


def test_6_infinite_loop_killed_at_wall_timeout():
    out = execute_sandboxed(argv=["/bin/sh", "-c", "while :; do :; done"], limits={"wall_s": 2})
    assert out.state == "timed_out" and out.killed_reason == "wall_timeout"


def test_7_proc_read_unavailable():
    out = execute_sandboxed(argv=["/bin/cat", "/proc/1/environ"], limits=LIMITS)
    assert "PATH=" not in out.stdout


def test_8_workspace_scrubbed():
    """Workspace dir is removed after the run (GAP-03 tmpfs scrub)."""
    import glob
    import tempfile

    before = set(glob.glob(tempfile.gettempdir() + "/bhctf-run-*"))
    execute_sandboxed(argv=["/bin/true"], limits=LIMITS)
    after = set(glob.glob(tempfile.gettempdir() + "/bhctf-run-*"))
    assert after == before, f"leaked workspaces: {after - before}"
