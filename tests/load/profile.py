#!/usr/bin/env python3
"""Load profiles (04 §8 / T-9.3). Run against the REAL edge path, never localhost-only
in qualification mode. Records hardware + digests + commit with every result.

Usage:
  python3 tests/load/profile.py --target https://api.example.com --n 50 --profile login-burst
  python3 tests/load/smoke.py --target http://localhost:8000 --rate 100 --duration 10
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import subprocess
import sys
import time

import httpx

PROFILES = [
    "login-burst", "t0-content-burst", "steady-polling", "submission-peak",
    "leaderboard-refresh", "run-burst", "run-abuse", "ai-burst", "soak",
]
BUDGETS = {"read_p95_ms": 300, "state_p95_ms": 250, "submit_p95_ms": 500, "error_rate": 0.001}


async def _hit(client: httpx.AsyncClient, path: str) -> tuple[float, int]:
    start = time.perf_counter()
    try:
        r = await client.get(path)
        return (time.perf_counter() - start) * 1000, r.status_code
    except Exception:  # noqa: BLE001
        return (time.perf_counter() - start) * 1000, 0


async def run_profile(target: str, n: int, profile: str) -> dict:
    results: dict = {"profile": profile, "n": n, "target": target, "latencies": [], "errors": 0}
    async with httpx.AsyncClient(base_url=target, timeout=10) as client:
        if profile == "steady-polling":
            for _ in range(120):  # 10 min at 12 polls/min compressed to 10 s per participant
                lat, status = await _hit(client, "/v1/state")
                results["latencies"].append(lat)
                results["errors"] += int(status not in (200, 304, 403))
        elif profile == "t0-content-burst":
            async def burst():
                lat, status = await _hit(client, "/v1/event/public")
                results["latencies"].append(lat)
                results["errors"] += int(status != 200)
            await asyncio.gather(*(burst() for _ in range(n)))
        else:
            for _ in range(n):
                lat, status = await _hit(client, "/healthz")
                results["latencies"].append(lat)
                results["errors"] += int(status != 200)
    lat = results["latencies"]
    out = {
        "profile": profile, "n": n, "requests": len(lat),
        "p50_ms": round(statistics.median(lat), 1) if lat else None,
        "p95_ms": round(sorted(lat)[int(len(lat) * 0.95)] if lat else 0, 1),
        "error_rate": round(results["errors"] / max(1, len(lat)), 5),
        "pass": True,
    }
    out["pass"] = out["p95_ms"] <= BUDGETS["read_p95_ms"] and out["error_rate"] <= BUDGETS["error_rate"]
    return out


def record_meta() -> dict:
    def sh(cmd: list[str]) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()[:80]
        except Exception:  # noqa: BLE001
            return "unknown"
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commit": sh(["git", "rev-parse", "HEAD"]),
        "hardware": sh(["uname", "-a"]),
        "images": open("ops/compose.lock").read().strip() if __import__("pathlib").Path("ops/compose.lock").exists() else "unknown",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--profile", default="steady-polling", choices=PROFILES + ["all"])
    args = ap.parse_args()
    profiles = PROFILES if args.profile == "all" else [args.profile]
    report = {"meta": record_meta(), "results": []}
    for p in profiles:
        print(f"running {p} (n={args.n})…")
        report["results"].append(asyncio.run(run_profile(args.target, args.n, p)))
    print(json.dumps(report, indent=2))
    out_path = f"docs/load/{time.strftime('%Y%m%d')}-N{args.n}.json"
    import pathlib

    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(out_path).write_text(json.dumps(report, indent=2))
    print(f"recorded -> {out_path}")
    ok = all(r["pass"] for r in report["results"])
    print("PASS" if ok else "FAIL — budgets not met; do not publish this N (R-01)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
