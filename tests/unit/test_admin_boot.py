"""B10 boot assertion: shared_secret refuses staging/prod; stub runner refuses prod."""
from __future__ import annotations

import pytest


def _settings(monkeypatch, env: str, **kw):
    monkeypatch.setenv("ENV", env)
    for k, v in kw.items():
        monkeypatch.setenv(k, v)
    from core.config import Settings

    return Settings()


def test_shared_secret_refused_in_staging(monkeypatch):
    from core.config import ConfigError

    s = _settings(monkeypatch, "staging", ADMIN_AUTH_MODE="shared_secret")
    with pytest.raises(ConfigError, match="shared_secret"):
        s.assert_boot_invariants()


def test_shared_secret_refused_in_prod(monkeypatch):
    from core.config import ConfigError

    s = _settings(monkeypatch, "prod", ADMIN_AUTH_MODE="shared_secret", JWT_SECRET="x" * 32)
    with pytest.raises(ConfigError, match="shared_secret"):
        s.assert_boot_invariants()


def test_access_mode_ok_in_prod(monkeypatch):
    s = _settings(monkeypatch, "prod", ADMIN_AUTH_MODE="access", RUNNER_MODE="off",
                  JWT_SECRET="x" * 32, AI_KIND="off")
    assert s.assert_boot_invariants() == []


def test_stub_runner_refused_in_prod(monkeypatch):
    from core.config import ConfigError

    s = _settings(monkeypatch, "prod", ADMIN_AUTH_MODE="access", RUNNER_MODE="stub",
                  JWT_SECRET="x" * 32, AI_KIND="off")
    with pytest.raises(ConfigError, match="RUNNER_MODE=stub"):
        s.assert_boot_invariants()


def test_remote_ai_requires_privacy_bump(monkeypatch):
    from core.config import ConfigError

    s = _settings(monkeypatch, "prod", ADMIN_AUTH_MODE="access", RUNNER_MODE="off",
                  JWT_SECRET="x" * 32, AI_KIND="remote")
    with pytest.raises(ConfigError, match="privacy_notice"):
        s.assert_boot_invariants()
