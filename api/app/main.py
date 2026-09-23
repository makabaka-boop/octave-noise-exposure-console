"""FastAPI entrypoint. A single POST /api/assessments call performs one
energy calculation; the per-period LAeq, total LAeq, pass/fail verdict and
dominant source in the response all derive from that same computation.
"""
from __future__ import annotations

import math
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .calc import (
    FREQUENCIES_HZ,
    dominant_source,
    laeq_from_energy,
    period_laeq,
    round1,
    total_energy,
)
from .models import (
    AssessmentRequest,
    AssessmentResponse,
    DominantSource,
    PeriodResult,
)

app = FastAPI(title="Noise Exposure Workbench API")

# The production deployment serves the SPA behind an nginx reverse proxy on
# the same origin, so CORS is only a convenience for local dev servers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _sanitize_non_finite(obj: Any) -> Any:
    """Replace non-finite floats so the 422 body stays valid JSON.

    A NaN/Infinity band value is rejected by the schema, but the default
    error handler echoes the offending input verbatim and then fails to
    serialize it — the client would get a 500 instead of the 422.
    """
    if isinstance(obj, float) and not math.isfinite(obj):
        return str(obj)
    if isinstance(obj, dict):
        return {key: _sanitize_non_finite(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_non_finite(value) for value in obj]
    return obj


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_sanitize_non_finite(jsonable_encoder({"detail": exc.errors()})),
    )


@app.post("/api/assessments", response_model=AssessmentResponse)
def assess(request: AssessmentRequest) -> AssessmentResponse:
    durations = [p.duration for p in request.periods]
    levels = [[p.bands[str(f)] for f in FREQUENCIES_HZ] for p in request.periods]

    energy_total = total_energy(durations, levels)
    laeq_total = laeq_from_energy(energy_total / sum(durations))
    period_idx, frequency, source_energy = dominant_source(durations, levels)

    return AssessmentResponse(
        limit_db=request.limit,
        total_duration_s=sum(durations),
        laeq_total_db=round1(laeq_total),
        passed=laeq_total <= request.limit,  # unrounded comparison
        periods=[
            PeriodResult(
                index=i + 1,
                duration=duration,
                laeq_db=round1(period_laeq(band_levels)),
            )
            for i, (duration, band_levels) in enumerate(zip(durations, levels))
        ],
        dominant_source=DominantSource(
            period_index=period_idx + 1,
            frequency_hz=frequency,
            energy_share_percent=round1(100.0 * source_energy / energy_total),
        ),
    )
