"""核心数值计算。

能量定义（相对声压平方，参考声压在取对数后约去）：
    E_band = 10 ** ((L_band + A计权修正_band) / 10)
单时段 LAeq 由该时段八个频带能量求和得到；
总 LAeq 以各时段持续时间为权重合并：
    LAeq_total = 10 * log10( sum_i d_i * sum_j E_ij / sum_i d_i )

占比 = 某时段某频带的时长加权能量 d_i * E_ij 占全任务总能量的比例。
所有结论（单时段 LAeq、总 LAeq、超标来源）均来自同一组能量值。
"""
from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

from .schemas import BAND_FREQS

# 固定 A 计权修正（63,125,250,500,1000,2000,4000,8000 Hz）
A_WEIGHTINGS: dict[int, float] = {
    63: -26.2,
    125: -16.1,
    250: -8.6,
    500: -3.2,
    1000: 0.0,
    2000: 1.2,
    4000: 1.0,
    8000: -1.1,
}


def band_energy(level_db: float, freq: int) -> float:
    """单频带能量（相对声压平方）。"""
    weighted = level_db + A_WEIGHTINGS[freq]
    return 10.0 ** (weighted / 10.0)


def energy_to_db(energy: float) -> float:
    """能量和 -> A 计权声级。"""
    return 10.0 * math.log10(energy)


def round1(value: float) -> str:
    """展示用：四舍五入到一位小数（HALF_UP，非银行家舍入）。"""
    return str(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
