"""把校验后的请求组装为暴露结论。"""
from __future__ import annotations

from .calculations import A_WEIGHTINGS, band_energy, energy_to_db, round1
from .schemas import BAND_FREQS, ExposureIn, ExposureOut


def compute_exposure(payload: ExposureIn) -> ExposureOut:
    # 每格能量：periods[ i ].bands[ j ] = d_i * E_ij
    period_band_energies: list[list[float]] = []
    period_energy_sums: list[float] = []  # sum_j E_ij（未乘时长）
    total_duration = 0
    total_weighted_energy = 0.0  # sum_i d_i * sum_j E_ij

    for p in payload.periods:
        row: list[float] = []
        e_sum = 0.0
        for f in BAND_FREQS:
            e = band_energy(p.levels[str(f)], f)
            row.append(e)
            e_sum += e
        period_band_energies.append(row)
        period_energy_sums.append(e_sum)
        total_duration += p.duration
        total_weighted_energy += p.duration * e_sum

    total_laeq = energy_to_db(total_weighted_energy / total_duration)

    # 能量占比最高的时段与频带：按时段先后、频率从低到高打破并列
    dom_i = dom_j = 0
    dom_val = -1.0
    for i, row in enumerate(period_band_energies):
        d = payload.periods[i].duration
        for j, e in enumerate(row):
            val = d * e
            if val > dom_val:
                dom_val, dom_i, dom_j = val, i, j
    dominant_freq = BAND_FREQS[dom_j]
    dominant_share = dom_val / total_weighted_energy

    periods_out = []
    for i, p in enumerate(payload.periods):
        laeq = energy_to_db(period_energy_sums[i])
        d = p.duration
        bands = [
            {
                "frequency": f,
                "level_db": p.levels[str(f)],
                "a_weighted_db": p.levels[str(f)] + A_WEIGHTINGS[f],
                "energy": period_band_energies[i][j],
                "energy_share": d
                * period_band_energies[i][j]
                / total_weighted_energy,
            }
            for j, f in enumerate(BAND_FREQS)
        ]
        periods_out.append(
            {
                "index": i + 1,
                "duration_s": p.duration,
                "laeq": laeq,
                "laeq_display": round1(laeq),
                "bands": bands,
            }
        )

    # 合格判定用未舍入值；展示值仅用于页面
    return ExposureOut(
        total_laeq=total_laeq,
        total_laeq_display=round1(total_laeq),
        limit_db=payload.limit,
        compliant=total_laeq <= payload.limit,
        dominant={
            "period_index": dom_i + 1,
            "frequency": dominant_freq,
            "energy": dom_val / payload.periods[dom_i].duration,
            "energy_share": dominant_share,
        },
        periods=periods_out,
    )
