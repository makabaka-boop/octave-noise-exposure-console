"""请求 / 响应模型。

校验规则（任何一条不满足，整次请求返回 422）：
- 时段数 1 ~ 24；
- 每个时段 duration 为 1 ~ 3600 的整数；
- levels 必须且只能包含 63~8000 Hz 八个倍频带键；
- 每个声级为 0 ~ 140 的有限数（布尔值、NaN、Infinity 一律拒绝）；
- 顶层及各层均不允许额外字段。
"""
from __future__ import annotations

import math
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

BAND_FREQS = (63, 125, 250, 500, 1000, 2000, 4000, 8000)

def _check_int(v):
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError("必须是整数")
    if v < 1 or v > 3600:
        raise ValueError("duration 必须在 1 ~ 3600 秒之间")
    return v


Duration = Annotated[int, BeforeValidator(_check_int)]


def _check_level(v):
    # bool 是 int 的子类，必须显式拒绝；字符串等非数值类型直接拒绝（不做隐式转换）
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError("声级必须是数字")
    f = float(v)
    if not math.isfinite(f):
        raise ValueError("声级必须是有限数")
    if f < 0 or f > 140:
        raise ValueError("声级必须在 0 ~ 140 dB 之间")
    return f


Level = Annotated[float, BeforeValidator(_check_level)]


class PeriodIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration: Duration
    levels: dict[str, Level]

    @model_validator(mode="after")
    def _exact_bands(self) -> "PeriodIn":
        keys = set(self.levels.keys())
        expected = {str(f) for f in BAND_FREQS}
        if keys != expected:
            missing = sorted(expected - keys, key=lambda x: int(x))
            extra = sorted(keys - expected, key=lambda x: int(x) if x.lstrip("-").isdigit() else x)
            parts = []
            if missing:
                parts.append(f"缺失频带: {', '.join(missing)}")
            if extra:
                parts.append(f"额外频带: {', '.join(extra)}")
            raise ValueError("；".join(parts))
        return self


class ExposureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: Level = Field(..., description="职业接触限值，40 ~ 100 dB")
    periods: list[PeriodIn] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def _limit_range(self) -> "ExposureIn":
        if self.limit < 40 or self.limit > 100:
            raise ValueError("limit 必须在 40 ~ 100 dB 之间")
        return self


class BandOut(BaseModel):
    frequency: int
    level_db: float
    a_weighted_db: float
    energy: float
    energy_share: float  # 占全任务总能量的比例（0~1）


class PeriodOut(BaseModel):
    index: int
    duration_s: int
    laeq: float  # 未舍入 LAeq
    laeq_display: str  # 四舍五入到一位后的展示串
    bands: list[BandOut]


class DominantOut(BaseModel):
    period_index: int
    frequency: int
    energy: float
    energy_share: float


class ExposureOut(BaseModel):
    total_laeq: float
    total_laeq_display: str
    limit_db: float
    compliant: bool
    dominant: DominantOut
    periods: list[PeriodOut]
