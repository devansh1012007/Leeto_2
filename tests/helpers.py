"""Test helpers shared across unit/integration suites."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_app(app_name: str):
    """Load backend/apps/<app_name>/app/main.py under a unique module name.

    Both apps use `from X import ...` package imports; loading under distinct names
    avoids sys.modules collisions between api_participant and api_admin. The module is
    registered in sys.modules BEFORE exec so pydantic can resolve forward references.
    """
    path = ROOT / "backend" / "apps" / app_name / "app" / "main.py"
    mod_name = f"{app_name}_app_main"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        del sys.modules[mod_name]
        raise
    return module
