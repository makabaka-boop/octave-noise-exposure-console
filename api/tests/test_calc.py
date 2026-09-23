"""Core calculation checks.

The expected values are recomputed here straight from the defining
formulas (independent of app.calc's helper structure):

    E_band  = 10 ** ((L_band + A_band) / 10)
    LAeq,T  = 10 * log10( sum_p T_p * sum_b E_band(p, b) / sum_p T_p )
"""
import math

import pytest

from app.calc import (
    A_WEIGHTING_DB,
    FREQUENCIES_HZ,
    dominant_source,
    period_laeq,
    round1,
    total_laeq,
)


def expected_period_laeq(levels):
    energy = sum(10 ** ((l + a) / 10) for l, a in zip(levels, A_WEIGHTING_DB))
    return 10 * math.log10(energy)


def expected_total_laeq(durations, all_levels):
    energy = sum(
        d * sum(10 ** ((l + a) / 10) for l, a in zip(levels, A_WEIGHTING_DB))
        for d, levels in zip(durations, all_levels)
    )
    return 10 * math.log10(energy / sum(durations))


def test_single_period_all_bands_equal():
    levels = [94.0] * 8
    assert period_laeq(levels) == pytest.approx(expected_period_laeq(levels), abs=1e-12)
    # sanity anchor: 94 dB in every band A-weights to ~100.99 dB(A)
    assert period_laeq(levels) == pytest.approx(100.99, abs=0.01)


def test_single_dominant_band_recovers_its_level():
    # Only the 1000 Hz band (A-correction 0) carries energy; the remaining
    # bands sit at 0 dB and contribute a negligible floor.
    levels = [0, 0, 0, 0, 85.0, 0, 0, 0]
    assert period_laeq(levels) == pytest.approx(85.0, abs=1e-6)


def test_total_laeq_is_duration_weighted_energy_average():
    durations = [100, 3600, 7]
    all_levels = [
        [70, 72, 74, 76, 78, 80, 82, 84],
        [88.5, 80, 75, 70, 65, 60, 55, 50],
        [140, 0, 0, 0, 0, 0, 0, 0],
    ]
    assert total_laeq(durations, all_levels) == pytest.approx(
        expected_total_laeq(durations, all_levels), abs=1e-12
    )


def test_identical_periods_collapse_to_single_period_value():
    levels = [80, 81, 82, 83, 84, 85, 86, 87]
    assert total_laeq([1, 3600, 537], [levels, levels, levels]) == pytest.approx(
        period_laeq(levels), abs=1e-12
    )


def test_total_laeq_lies_between_extreme_periods():
    quiet = [60.0] * 8
    loud = [100.0] * 8
    total = total_laeq([900, 300], [quiet, loud])
    assert period_laeq(quiet) < total < period_laeq(loud)


def test_dominant_source_picks_highest_energy_band():
    durations = [1200, 600]
    all_levels = [
        [78, 80, 82, 84, 85, 83, 80, 75],
        [85, 88, 90, 92, 94, 95, 90, 84],
    ]
    idx, freq, energy = dominant_source(durations, all_levels)
    assert (idx, freq) == (1, 2000)
    assert energy == pytest.approx(600 * 10 ** ((95 + 1.2) / 10), rel=1e-12)


def test_dominant_source_tie_breaks_to_earliest_period():
    # Period energies for the 1000 Hz band are exactly equal
    # (100 s * 10 dB  ==  10 s * 20 dB); everything else is a low floor.
    durations = [100, 10]
    all_levels = [
        [0, 0, 0, 0, 10.0, 0, 0, 0],
        [0, 0, 0, 0, 20.0, 0, 0, 0],
    ]
    idx, freq, _ = dominant_source(durations, all_levels)
    assert (idx, freq) == (0, 1000)


def test_dominant_source_tie_breaks_to_lowest_frequency():
    # 36.2 dB at 63 Hz and 10 dB at 1000 Hz have identical A-weighted
    # energy (10.0), safely above the 0 dB floor of the other bands.
    levels = [36.2, 0, 0, 0, 10.0, 0, 0, 0]
    idx, freq, _ = dominant_source([60], [levels])
    assert (idx, freq) == (0, 63)


@pytest.mark.parametrize(
    "value,expected",
    [
        (85.04, 85.0),
        (85.05, 85.1),  # half rounds up, not banker's rounding
        (84.96, 85.0),
        (0.049, 0.0),
        (99.95, 100.0),
    ],
)
def test_round1_is_half_up_display_rounding(value, expected):
    assert round1(value) == expected
