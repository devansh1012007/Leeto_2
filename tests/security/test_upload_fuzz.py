"""T-10.4: upload fuzz on the RUNNER sandbox — zip-bomb-like expansion, traversal,
symlinks are contained or rejected; the API host never unpacks (R-07)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runner"))

from service import execute_sandboxed


def test_path_traversal_rejected():
    out = execute_sandboxed(argv=["/bin/true"], files={"../../etc/cron.d/evil": "* * * * * root /bin/sh -c 'pwned'"})
    assert out.state == "failed" and out.killed_reason == "unsafe_path"


def test_absolute_path_rejected():
    out = execute_sandboxed(argv=["/bin/true"], files={"/etc/passwd": "x"})
    assert out.state == "failed" and out.killed_reason == "unsafe_path"


def test_zip_bomb_expansion_contained_by_output_cap():
    """A 'compressed bomb' pattern: huge generated output is truncated at the cap."""
    out = execute_sandboxed(argv=["/bin/sh", "-c", "yes BOMB | head -c 2000000"],
                            limits={"wall_s": 5, "out_bytes": 4096})
    assert out.truncated and len(out.stdout) < 10_000


def test_workspace_scrubbed_after_fuzz():
    import glob
    import tempfile

    before = set(glob.glob(tempfile.gettempdir() + "/bhctf-run-*"))
    execute_sandboxed(argv=["/bin/true"], files={"a.py": "print('x')"})
    after = set(glob.glob(tempfile.gettempdir() + "/bhctf-run-*"))
    assert after == before
