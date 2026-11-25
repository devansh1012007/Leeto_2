"""Unit: emergency rails (08 §4.12), runner gateway protocol, auth limits, audit chain."""
from __future__ import annotations

import time

import emergency.service as em
import pytest
from audit.chain import entry_hash, verify_chain
from auth.tokens import LoginLimiter, hash_password, make_access_token, verify_password
from core.errors import ApiError
from runner.gateway import RunnerGateway, validate_job_result

# repo-root runner/ dir is on sys.path via conftest (backend `runner` package shadows it otherwise)
from service import StubRunner, compare_output, execute_sandboxed


# ---------------------------------------------------------------- emergency rails
def _req(**kw):
    base = {"action": "pause", "event_id": "e1", "actor_id": "admin-1",
            "reason": "platform fault requiring pause", "confirm": "7", "stepped_up_at": time.time()}
    base.update(kw)
    return em.EmergencyRequest(**base)


class TestEmergencyRails:
    def test_step_up_expiry_rejected(self):
        with pytest.raises(ApiError) as ei:
            em.check_rails(_req(stepped_up_at=time.time() - 400))
        assert ei.value.code == "AUTH_STEP_UP_REQUIRED"

    def test_destructive_needs_distinct_second_approver(self):
        with pytest.raises(ApiError) as ei:
            em.check_rails(_req(action="score_adjust"))
        assert ei.value.code == "ESCALATION_REQUIRED"
        with pytest.raises(ApiError) as ei:
            em.check_rails(_req(action="score_adjust", approver_id="admin-1"))
        assert ei.value.code == "ESCALATION_REQUIRED"

    def test_reason_min_20_chars(self):
        with pytest.raises(ApiError):
            em.check_rails(_req(reason="too short"))

    def test_typed_numeral_confirmation(self):
        with pytest.raises(ApiError):
            em.check_rails(_req(confirm="SEVEN"))
        with pytest.raises(ApiError):
            em.check_rails(_req(confirm="7 "))
        em.check_rails(_req(confirm="7"))

    def test_participant_copy_only_from_catalog(self):
        catalog = {"emergency.copy.pause": "The event is paused. The clock is stopped."}
        out = em.participant_copy("pause", catalog)
        assert out == "The event is paused. The clock is stopped."
        with pytest.raises(ApiError):
            em.participant_copy("nonexistent_action", catalog)

    def test_reversibility_catalog_covers_all_actions(self):
        for action in em._APPLY:
            assert action in em.REVERSIBILITY, f"{action} missing from reversibility catalog"


# ---------------------------------------------------------------- runner protocol
class TestRunnerGateway:
    def test_result_validation_rejects_unknown_state(self):
        with pytest.raises(ApiError):
            validate_job_result({"state": "exploded"})

    def test_result_validation_rejects_oversized_output(self):
        with pytest.raises(ApiError):
            validate_job_result({"state": "finished", "stdout": "x" * 300000})

    def test_one_concurrent_per_participant(self):
        gw = RunnerGateway()
        gw.submit(participant_id="p1", team_id="t1", kind="run_practice",
                  command_argv=["/usr/bin/test"], image_digest="sha256:x")
        with pytest.raises(ApiError) as ei:
            gw.submit(participant_id="p1", team_id="t1", kind="run_practice",
                      command_argv=["/usr/bin/test"], image_digest="sha256:x")
        assert ei.value.code == "RUN_RATE_LIMITED"

    def test_kill_switch_stops_handouts(self):
        gw = RunnerGateway()
        gw.submit(participant_id="p1", team_id="t1", kind="run_practice",
                  command_argv=["/usr/bin/test"], image_digest="sha256:x")
        gw.kill_switch()
        assert gw.claim(runner_id="r1") is None

    def test_official_priority_over_practice(self):
        gw = RunnerGateway()
        gw.submit(participant_id="p1", team_id="t1", kind="run_practice",
                  command_argv=["/usr/bin/build"], image_digest="sha256:x")
        gw.submit(participant_id="p2", team_id="t2", kind="run_official",
                  command_argv=["/usr/bin/test"], image_digest="sha256:x")
        job = gw.claim(runner_id="r1")
        assert job["kind"] == "run_official"


class TestStubRunner:
    def test_stub_refuses_prod(self):
        with pytest.raises(RuntimeError, match="refuses to start in ENV=prod"):
            StubRunner(env="prod")

    def test_stub_rejects_unknown_image_digest(self):
        stub = StubRunner()
        out = stub.claim({"job_id": "j1", "image_digest": "sha256:unknown"})
        assert out["error"] == "IMAGE_NOT_ALLOWED"

    def test_stub_result_deterministic(self):
        stub = StubRunner()
        stub.claim({"job_id": "j1", "image_digest": "sha256:stub-python-3.12", "argv": []})
        a = stub.result("j1")
        b = stub.result("j1")
        assert a["stdout"] == b["stdout"] and a["exit_code"] == 0


class TestSandbox:
    def test_finished_run(self):
        out = execute_sandboxed(argv=["/bin/echo", "hello"], limits={"wall_s": 5})
        assert out.state == "finished" and out.exit_code == 0
        assert "hello" in out.stdout

    def test_wall_timeout_kills(self):
        out = execute_sandboxed(argv=["/bin/sleep", "30"], limits={"wall_s": 1})
        assert out.state == "timed_out" and out.killed_reason == "wall_timeout"

    def test_output_truncated_with_marker(self):
        out = execute_sandboxed(argv=["/bin/sh", "-c", "head -c 200000 /dev/zero | tr '\\0' 'x'"],
                                limits={"wall_s": 5, "out_bytes": 1000})
        assert out.truncated and "truncated" in out.stdout

    def test_path_traversal_rejected(self):
        out = execute_sandboxed(argv=["/bin/true"], files={"../evil.sh": "x"})
        assert out.state == "failed" and out.killed_reason == "unsafe_path"

    def test_compare_output_modes(self):
        assert compare_output("ok", "ok", "exact")
        assert compare_output(" ok \n", "ok", "trimmed")
        assert compare_output('{"a":1}', '{"a":1}', "json_structured")
        assert compare_output("abc123", "abc\\d+", "regex")
        assert not compare_output("no", "ok", "exact")


# ---------------------------------------------------------------- auth
class TestAuth:
    def test_password_hash_roundtrip(self):
        h = hash_password("super-secret-password-1")
        assert verify_password(h, "super-secret-password-1")
        assert not verify_password(h, "wrong-password-1234")

    def test_short_password_rejected(self):
        with pytest.raises(ApiError):
            hash_password("short")

    def test_login_limiter_identifier_5_per_min(self):
        lim = LoginLimiter()
        for _ in range(5):
            lim.check(identifier="u@x.local", ip="1.2.3.4")
        with pytest.raises(ApiError) as ei:
            lim.check(identifier="u@x.local", ip="1.2.3.4")
        assert ei.value.code == "AUTH_RATE_LIMITED"

    def test_five_failures_add_60s_delay_no_hard_lockout(self):
        lim = LoginLimiter()
        for _ in range(5):
            lim.record_failure("u@x.local")
        with pytest.raises(ApiError) as ei:
            lim.check(identifier="u@x.local", ip="1.2.3.4")
        assert ei.value.details["retry_after"] <= 61
        # no hard lockout: another identifier on the same IP still works
        lim.check(identifier="other@x.local", ip="1.2.3.4")

    def test_ip_limit_120_per_min(self):
        lim = LoginLimiter()
        for i in range(120):
            lim.check(identifier=f"u{i}@x.local", ip="9.9.9.9")
        with pytest.raises(ApiError) as ei:
            lim.check(identifier="fresh@x.local", ip="9.9.9.9")
        assert ei.value.code == "AUTH_RATE_LIMITED"

    def test_jwt_roundtrip_and_alg_pinned(self):
        tok = make_access_token(secret="s", sub="p1", sid="s1", role="participant")
        claims = __import__("jwt").decode(tok, "s", algorithms=["HS256"], audience="participant", issuer="bhctf")
        assert claims["sub"] == "p1"


# ---------------------------------------------------------------- audit chain
class TestAuditChain:
    def test_chain_verifies(self):
        entries = []
        prev = None
        for i in range(5):
            h = entry_hash(prev, actor_id="a", action=f"act.{i}", target_type="t",
                           target_id=str(i), details_json="{}")
            entries.append({"id": i, "actor_id": "a", "action": f"act.{i}", "target_type": "t",
                            "target_id": str(i), "prev_hash": prev.hex() if prev else None,
                            "hash": h.hex(), "details": "{}"})
            prev = h
        result = verify_chain(entries)
        assert result["ok"] and result["verified_count"] == 5

    def test_chain_break_detected(self):
        entries = []
        prev = None
        for i in range(3):
            h = entry_hash(prev, actor_id="a", action=f"act.{i}", target_type="t",
                           target_id=str(i), details_json="{}")
            entries.append({"id": i, "actor_id": "a", "action": f"act.{i}", "target_type": "t",
                            "target_id": str(i), "prev_hash": prev.hex() if prev else None,
                            "hash": h.hex(), "details": "{}"})
            prev = h
        entries[2]["hash"] = "00" * 32  # tamper
        result = verify_chain(entries)
        assert not result["ok"] and result["first_break_id"] == 2
