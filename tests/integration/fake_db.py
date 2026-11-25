"""Shared fake DB connection for DB-backed service tests without Postgres.

Implements the minimal synchronous SQLAlchemy-like surface the services use
(execute/first/scalar_one), with a row-addressable store. This tests SERVICE
LOGIC (lock order, idempotency, protocol steps); real SQL behavior is covered
by the Postgres-gated integration suite.
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any


class Row(dict):
    """Attribute-accessible row that ALSO unpacks positionally like SQLAlchemy Row
    (dict insertion order defines the tuple order — construct with ordered kwargs)."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as e:  # pragma: no cover
            raise AttributeError(name) from e

    def __iter__(self):
        return iter(self.values())

    def __getitem__(self, key):
        if isinstance(key, int):  # SQLAlchemy Row positional indexing (r[0], r[1], …)
            return list(self.values())[key]
        return super().__getitem__(key)


class FakeConn:
    """Single-connection fake with lock tracking for the B6 lock-order tests."""

    def __init__(self, *, now: datetime | None = None, paused: bool = False,
                 exec_closes_at: datetime | None = None, exec_opens_at: datetime | None = None):
        self.tables: dict[str, list[dict]] = {}
        self.locks_taken: list[str] = []
        self.executed: list[tuple[str, dict]] = []
        # the pipeline treats clock_timestamp() as a datetime (isoformat, timedelta math)
        self.now = now or datetime(2026, 12, 5, 10, 0, 0, tzinfo=UTC)
        self.event_paused = paused
        self.exec_closes_at = exec_closes_at
        self.exec_opens_at = exec_opens_at
        self.fail_on = {}  # sql-substring -> exception
        self._idempotency_conflict = False
        self.quota_buckets: dict[str, dict] = {}
        self.fail_next_commit = False

    # ---- SQLAlchemy-like API -------------------------------------------------
    def execute(self, sql, params=None):
        self.executed.append((sql if isinstance(sql, str) else str(sql), params or {}))
        sql_s = str(sql)
        for needle, exc in self.fail_on.items():
            if needle in sql_s:
                raise exc
        if "clock_timestamp()" in sql_s:
            return _Scalar(self.now)
        if "SELECT paused" in sql_s or "paused, safe_mode" in sql_s:
            return _First(Row(paused=self.event_paused, safe_mode=False))
        if "FOR UPDATE" in sql_s and "participant_progress" in sql_s:
            self.locks_taken.append("progress")
            return _First(Row(node="L2_EXEC", sub_state="active", version=1))
        if "FROM app.quota" in sql_s and "FOR UPDATE" in sql_s:
            self.locks_taken.append("quota")
            return _First(Row(buckets=self.quota_buckets.get("p", {})))
        if "SELECT id, kind, exec_opens_at" in sql_s or "FROM app.stages" in sql_s and "stage_key = " in sql_s:
            return _First(Row(
                id="stage-1", kind="flags", exec_opens_at=self.exec_opens_at,
                exec_closes_at=self.exec_closes_at, caps={"max_span": 25, "grace_s": 3},
            ))
        if "SELECT response_status, response_body, payload_hash FROM app.idempotency" in sql_s:
            rows = self.tables.get("idempotency", [])
            for r in rows:
                if r.get("key") == (params or {}).get("k") and r.get("participant_id") == (params or {}).get("p"):
                    return _First(Row(response_status=r["response_status"],
                                      response_body=r["response_body"],
                                      payload_hash=r["payload_hash"]))
            return _First(None)
        if "SELECT receipt_code FROM app.submissions" in sql_s:
            for r in self.tables.get("submissions", []):
                if r.get("participant_id") == (params or {}).get("p") and r.get("stage_id") == (params or {}).get("s"):
                    return _First(Row(receipt_code=r["receipt_code"]))
            return _First(None)
        if "SELECT count(*) FROM app.stages" in sql_s:
            return _Scalar(0)
        if "FROM gt.answer_packs WHERE id" in sql_s:
            return _First(Row(event_id="e1", state=self.tables.get("_pack_state", ["draft"])[0]))
        if "INSERT INTO" in sql_s:
            table = sql_s.split("INSERT INTO ")[1].split(" ")[0].split("(")[0].strip()
            if "app.idempotency" in table:
                key = (params or {}).get("k")
                for r in self.tables.setdefault("idempotency", []):
                    if r.get("key") == key:
                        raise _conflict()
                # jsonb round-trip: a real jsonb column deserializes back to a dict
                import json as _json

                rb = params.get("rb")
                try:
                    rb = _json.loads(rb) if isinstance(rb, str) else rb
                except Exception:  # noqa: BLE001 — non-JSON stays as stored
                    _ = rb  # keep the original value
                self.tables["idempotency"].append({
                    "participant_id": params.get("p"), "key": key,
                    "payload_hash": params.get("ph"),
                    "response_status": 202, "response_body": rb,
                })
            elif "app.ledger" in table and "reversal_of" in sql_s:
                for r in self.tables.get("ledger", []):
                    if r.get("reversal_of") == (params or {}).get("rev"):
                        raise _conflict()
                self.tables.setdefault("ledger", []).append(dict(params or {}))
            else:
                self.tables.setdefault(table, []).append(dict(params or {}))
        elif "UPDATE" in sql_s:
            self.tables.setdefault("_updates", []).append((sql_s, dict(params or {})))
            if "app.stages SET exec_closes_at" in sql_s and "gt.answer_packs SET state = 'active'" in self.tables.get("_updates", [])[0][0]:
                pass
        return _First(None)

    # async-context compatibility: services call conn.execute synchronously inside
    # an async function; FastAPI tx() yields the conn — the fakes here are used
    # through a shim in tests.


class _First:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row

    def fetchall(self):
        return [self._row] if self._row else []

    def scalar_one(self):
        return self._row


class _Scalar(_First):
    pass


def _conflict() -> Exception:
    import psycopg  # noqa: F401 — placeholder if needed

    class UniqueViolation(Exception):
        pass

    return UniqueViolation("duplicate key")


class FakeTx:
    """async context manager yielding a FakeConn (with commit failure injection)."""

    def __init__(self, conn: FakeConn):
        self.conn = conn
        self._lock = threading.Lock()

    async def __aenter__(self) -> FakeConn:
        self._lock.acquire()
        return self.conn

    async def __aexit__(self, *exc) -> None:
        self._lock.release()
