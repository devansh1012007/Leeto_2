#!/usr/bin/env python3
"""CI load-smoke: 100 req/s for 10 s against a stub endpoint (T-0.4)."""
from __future__ import annotations

import argparse
import asyncio
import sys
import time

import httpx


async def main(target: str, rate: int, duration: int) -> int:
    sent = ok = 0
    interval = 1.0 / rate
    start = time.monotonic()
    async with httpx.AsyncClient(base_url=target, timeout=5) as client:
        async def one():
            nonlocal sent, ok
            try:
                r = await client.get("/healthz")
                ok += int(r.status_code == 200)
            except Exception:  # noqa: BLE001 — load smoke counts failures, never crashes
                ok += 0
            sent += 1
        while time.monotonic() - start < duration:
            await asyncio.gather(*(one() for _ in range(rate)))
            await asyncio.sleep(max(0, interval))
    elapsed = time.monotonic() - start
    rps = sent / elapsed
    print(f"load-smoke: {sent} requests in {elapsed:.1f}s = {rps:.0f} req/s, {ok} ok")
    if rps < rate * 0.8:
        print("FAIL: could not sustain target rate")
        return 1
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="http://localhost:8000")
    ap.add_argument("--rate", type=int, default=100)
    ap.add_argument("--duration", type=int, default=10)
    a = ap.parse_args()
    sys.exit(asyncio.run(main(a.target, a.rate, a.duration)))
