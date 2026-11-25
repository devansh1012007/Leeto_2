"""runner_gateway: bridges API ↔ runner over the pull protocol (02 §10).

Serves /runner/claim, /runner/jobs/{id}/heartbeat, /runner/jobs/{id}/result on the
internal network only. Validates every result as untrusted data (RUN-05).
"""
from __future__ import annotations

from core.errors import ApiError
from core.middleware import RequestContextMiddleware
from fastapi import Depends, FastAPI, Header
from runner.gateway import RunnerGateway, validate_job_result

app = FastAPI(title="Runner Gateway", docs_url=None, redoc_url=None)
app.add_middleware(RequestContextMiddleware)
gw = RunnerGateway()


async def runner_token(x_runner_token: str = Header(alias="X-Runner-Token")) -> str:
    if not x_runner_token or len(x_runner_token) < 8:
        raise ApiError("AUTH_FORBIDDEN")
    return x_runner_token


@app.post("/runner/claim")
async def claim(body: dict, token: str = Depends(runner_token)) -> dict:
    spec = gw.claim(runner_id=str(body.get("runner_id", "unknown")), capacity=int(body.get("capacity", 1)))
    if spec is None:
        return {"job": None}
    return {"job": spec}


@app.post("/runner/jobs/{job_id}/heartbeat")
async def heartbeat(job_id: str, body: dict, token: str = Depends(runner_token)) -> dict:
    return gw.heartbeat(job_id=job_id, state=str(body.get("state", "running")))


@app.post("/runner/jobs/{job_id}/result", status_code=202)
async def result(job_id: str, body: dict, token: str = Depends(runner_token)) -> dict:
    validated = validate_job_result(body)
    gw.result(job_id=job_id, payload=body)
    return {"accepted": True, "state": validated["state"]}
