"""Request/response schemas. Any missing field, unexpected field, unknown
band, or out-of-range/non-finite value fails the whole request with 422.
"""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from .calc import FREQUENCIES_HZ

BAND_KEYS = frozenset(str(f) for f in FREQUENCIES_HZ)

BandLevel = Annotated[float, Field(ge=0.0, le=140.0, allow_inf_nan=False)]


class PeriodIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration: Annotated[StrictInt, Field(ge=1, le=3600)]
    bands: dict[str, BandLevel]

    @model_validator(mode="after")
    def _exact_band_set(self) -> "PeriodIn":
        keys = set(self.bands)
        if keys != BAND_KEYS:
            missing = sorted(BAND_KEYS - keys, key=float)
            extra = sorted(keys - BAND_KEYS)
            parts = []
            if missing:
                parts.append("missing bands: " + ", ".join(missing))
            if extra:
                parts.append("unexpected bands: " + ", ".join(extra))
            raise ValueError("; ".join(parts))
        return self


class AssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: Annotated[float, Field(ge=40.0, le=100.0, allow_inf_nan=False)]
    periods: Annotated[list[PeriodIn], Field(min_length=1, max_length=24)]


class PeriodResult(BaseModel):
    index: int  # 1-based, chronological order
    duration: int
    laeq_db: float  # rounded to 0.1 dB for display


class DominantSource(BaseModel):
    period_index: int  # 1-based
    frequency_hz: int
    energy_share_percent: float  # rounded to 0.1 % for display


class AssessmentResponse(BaseModel):
    limit_db: float
    total_duration_s: int
    laeq_total_db: float  # rounded to 0.1 dB for display
    passed: bool  # computed from the UNROUNDED total: laeq_total <= limit
    periods: list[PeriodResult]
    dominant_source: DominantSource
