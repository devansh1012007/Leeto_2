"""T-8.x: official runs are deterministic — 3 repeats give identical results (DAT-05)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

from service import compare_output, execute_sandboxed


def test_official_run_three_repeats_identical():
    code = "for i in range(10):\n    print(i * i)\n"
    outs = []
    for _ in range(3):
        out = execute_sandboxed(
            argv=["/usr/bin/python3", "-c", code],
            limits={"wall_s": 5, "out_bytes": 65536},
        )
        assert out.state == "finished" and out.exit_code == 0
        outs.append(out.stdout)
    assert outs[0] == outs[1] == outs[2]


def test_comparison_modes_deterministic():
    assert compare_output("a\nb\n", "a\nb\n", "trimmed")
    assert not compare_output("a\nb\n", "b\na\n", "trimmed")
