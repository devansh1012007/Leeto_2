"""Append-only hash-chained audit + verification (02 §9.5, T-10.9).

The chain is per-event serialized; checkpoints are exported off-DB (05). Verify walks
prev_hash links and recomputes hashes.
"""
from __future__ import annotations

import hashlib
import json
import secrets


def entry_hash(prev_hash: bytes | None, *, actor_id: str | None, action: str,
               target_type: str | None, target_id: str | None, details_json: str) -> bytes:
    blob = json.dumps(
        {
            "prev": (prev_hash or b"").hex(),
            "actor": actor_id,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "details": details_json,
        },
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).digest()


def new_chain_head() -> bytes:
    return secrets.token_bytes(32)


def verify_chain(entries: list[dict]) -> dict:
    """entries: [{id, actor_id, action, target_type, target_id, prev_hash(hex), hash(hex), details}]
    Returns {ok, first_break_id, verified_count}."""
    prev: bytes | None = None
    verified = 0
    for e in entries:
        if e.get("prev_hash") and prev is not None and bytes.fromhex(e["prev_hash"]) != prev:
            return {"ok": False, "first_break_id": e["id"], "verified_count": verified}
        recomputed = entry_hash(
            bytes.fromhex(e["prev_hash"]) if e.get("prev_hash") else None,
            actor_id=e.get("actor_id"), action=e["action"], target_type=e.get("target_type"),
            target_id=e.get("target_id"), details_json=e.get("details") or "{}",
        )
        if e.get("hash") and bytes.fromhex(e["hash"]) != recomputed:
            return {"ok": False, "first_break_id": e["id"], "verified_count": verified}
        prev = bytes.fromhex(e["hash"]) if e.get("hash") else recomputed
        verified += 1
    return {"ok": True, "first_break_id": None, "verified_count": verified}
