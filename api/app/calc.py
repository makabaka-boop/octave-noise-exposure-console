"""A-weighted octave-band noise exposure calculations.

Every level is converted to mean-square-pressure energy first; all
combination (per-period totals, duration weighting, source ranking)
happens in the energy domain. Rounding to one decimal is a
presentation-only concern (see :func:`round1`) and is never applied
before the compliance comparison.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from math import log10
from typing import Sequence

FREQUENCIES_HZ: tuple[int, ...] = (63, 125, 250, 500, 1000, 2000, 4000, 8000)
A_WEIGHTING_DB: tuple[float, ...] = (-26.2, -16.1, -8.6, -3.2, 0.0, 1.2, 1.0, -1.1)


def band_energy(level_db: float, a_weighting_db: float) -> float:
    """A-weighted energy of a single band, in arbitrary linear units."""
    return 10.0 ** ((level_db + a_weighting_db) / 10.0)


def period_energy(band_levels: Sequence[float]) -> float:
    """Total A-weighted energy of one measurement period."""
    return sum(
        band_energy(level, a) for level, a in zip(band_levels, A_WEIGHTING_DB)
    )


def laeq_from_energy(energy: float) -> float:
    return 10.0 * log10(energy)


def period_laeq(band_levels: Sequence[float]) -> float:
    """LAeq of a single period (unrounded)."""
    return laeq_from_energy(period_energy(band_levels))


def total_energy(durations: Sequence[int], band_levels: Sequence[Sequence[float]]) -> float:
    """Duration-weighted total energy across all periods."""
    return sum(d * period_energy(b) for d, b in zip(durations, band_levels))


def total_laeq(durations: Sequence[int], band_levels: Sequence[Sequence[float]]) -> float:
    """Duration-weighted energetic average LAeq over all periods (unrounded)."""
    return laeq_from_energy(total_energy(durations, band_levels) / sum(durations))


def dominant_source(
    durations: Sequence[int], band_levels: Sequence[Sequence[float]]
) -> tuple[int, int, float]:
    """Largest single-band contribution to the total energy.

    Returns ``(period_index_zero_based, frequency_hz, energy)``. Ties are
    broken by earliest period, then by lowest frequency, because periods are
    scanned in chronological order and bands in ascending frequency with a
    strict-greater comparison.
    """
    best: tuple[int, int, float] | None = None
    for period_idx, (duration, levels) in enumerate(zip(durations, band_levels)):
        for freq, level, a in zip(FREQUENCIES_HZ, levels, A_WEIGHTING_DB):
            energy = duration * band_energy(level, a)
            if best is None or energy > best[2]:
                best = (period_idx, freq, energy)
    assert best is not None  # guaranteed: at least one period, eight bands
    return best


def round1(value: float) -> float:
    """Round half-up to one decimal. Presentation only — never feed back
    into energy math or the compliance decision."""
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
