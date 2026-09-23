"""API boundary and contract tests. Every invalid payload must fail the
WHOLE request with 422; valid boundary values must pass validation.
"""
import json
import math

import pytest
from fastapi.testclient import TestClient

from app.calc import A_WEIGHTING_DB
from app.main import app

client = TestClient(app)

FREQS = ["63", "125", "250", "500", "1000", "2000", "4000", "8000"]


def make_period(duration=600, level=80.0, **band_overrides):
    bands = {f: level for f in FREQS}
    bands.update({str(k): v for k, v in band_overrides.items()})
    return {"duration": duration, "bands": bands}


def make_payload(**overrides):
    payload = {"limit": 85.0, "periods": [make_period()]}
    payload.update(overrides)
    return payload


def post(payload):
    return client.post("/api/assessments", json=payload)


def post_raw(body):
    return client.post(
        "/api/assessments", content=body, headers={"Content-Type": "application/json"}
    )


# ---------------------------------------------------------------- happy path


def test_happy_path_single_energy_calculation():
    payload = make_payload(
        periods=[
            make_period(duration=1200, **{"63": 78, "125": 80, "250": 82, "500": 84,
                                          "1000": 85, "2000": 83, "4000": 80, "8000": 75}),
            make_period(duration=600, **{"63": 85, "125": 88, "250": 90, "500": 92,
                                         "1000": 94, "2000": 95, "4000": 90, "8000": 84}),
        ]
    )
    res = post(payload)
    assert res.status_code == 200
    body = res.json()

    # independent recomputation from the defining formula
    def period_energy(period):
        return sum(
            10 ** ((period["bands"][str(f)] + a) / 10)
            for f, a in zip([63, 125, 250, 500, 1000, 2000, 4000, 8000], A_WEIGHTING_DB)
        )

    energies = [period_energy(p) for p in payload["periods"]]
    durations = [p["duration"] for p in payload["periods"]]
    expected_total = 10 * math.log10(
        sum(d * e for d, e in zip(durations, energies)) / sum(durations)
    )

    assert body["laeq_total_db"] == pytest.approx(round(expected_total, 1), abs=0.051)
    assert body["passed"] is False  # ~95.5 dB(A) against an 85 dB limit
    assert body["total_duration_s"] == 1800
    assert [p["index"] for p in body["periods"]] == [1, 2]
    assert body["periods"][0]["laeq_db"] == pytest.approx(
        round(10 * math.log10(energies[0]), 1), abs=0.051
    )
    # dominant source: period 2, 2000 Hz — from the same energy sum
    assert body["dominant_source"]["period_index"] == 2
    assert body["dominant_source"]["frequency_hz"] == 2000
    expected_share = 100.0 * durations[1] * 10 ** ((95 + 1.2) / 10) / sum(
        d * e for d, e in zip(durations, energies)
    )
    assert body["dominant_source"]["energy_share_percent"] == pytest.approx(
        expected_share, abs=0.05
    )


# ------------------------------------------------- verdict uses unrounded LAeq


def test_verdict_uses_unrounded_value_fail():
    # LAeq ~ 85.04 -> displays as 85.0 but exceeds the 85.0 limit unrounded.
    res = post(make_payload(limit=85.0, periods=[make_period(**{"1000": 85.04}, level=0)]))
    assert res.status_code == 200
    body = res.json()
    assert body["laeq_total_db"] == 85.0
    assert body["passed"] is False


def test_verdict_uses_unrounded_value_pass():
    # LAeq ~ 84.96 -> also displays as 85.0 and passes unrounded.
    res = post(make_payload(limit=85.0, periods=[make_period(**{"1000": 84.96}, level=0)]))
    assert res.status_code == 200
    body = res.json()
    assert body["laeq_total_db"] == 85.0
    assert body["passed"] is True


def test_verdict_exactly_at_limit_passes():
    # The comparison is "<=": an unrounded LAeq exactly equal to the limit
    # passes. (The 0 dB floor of the other bands nudges LAeq a hair above
    # 85.0, so the exact float is used as the limit.)
    from app.calc import total_laeq

    levels = [0, 0, 0, 0, 85.0, 0, 0, 0]
    laeq = total_laeq([600], [levels])
    res = post(make_payload(limit=laeq, periods=[make_period(**{"1000": 85.0}, level=0)]))
    assert res.json()["passed"] is True


# ------------------------------------------------------------- boundary values


@pytest.mark.parametrize("duration", [1, 3600])
def test_duration_boundaries_ok(duration):
    assert post(make_payload(periods=[make_period(duration=duration)])).status_code == 200


@pytest.mark.parametrize("duration", [0, -1, 3601])
def test_duration_out_of_range_422(duration):
    assert post(make_payload(periods=[make_period(duration=duration)])).status_code == 422


@pytest.mark.parametrize("duration", [10.5, "600", True, None])
def test_duration_non_integer_422(duration):
    assert post(make_payload(periods=[make_period(duration=duration)])).status_code == 422


@pytest.mark.parametrize("level", [0, 140])
def test_band_boundaries_ok(level):
    assert post(make_payload(periods=[make_period(level=level)])).status_code == 200


@pytest.mark.parametrize("level", [-0.1, 140.1, -500])
def test_band_out_of_range_422(level):
    assert post(make_payload(periods=[make_period(level=level)])).status_code == 422


def test_band_nan_422():
    body = json.dumps(make_payload()).replace('"500": 80.0', '"500": NaN')
    assert post_raw(body).status_code == 422


def test_band_infinity_422():
    body = json.dumps(make_payload()).replace('"500": 80.0', '"500": Infinity')
    assert post_raw(body).status_code == 422


@pytest.mark.parametrize("limit", [40, 100])
def test_limit_boundaries_ok(limit):
    assert post(make_payload(limit=limit)).status_code == 200


@pytest.mark.parametrize("limit", [39.9, 100.1])
def test_limit_out_of_range_422(limit):
    assert post(make_payload(limit=limit)).status_code == 422


def test_period_count_boundaries():
    assert post(make_payload(periods=[make_period()])).status_code == 200
    assert post(make_payload(periods=[make_period()] * 24)).status_code == 200
    assert post(make_payload(periods=[])).status_code == 422
    assert post(make_payload(periods=[make_period()] * 25)).status_code == 422


# ----------------------------------------------------- structural validation


def test_missing_band_422():
    payload = make_payload()
    del payload["periods"][0]["bands"]["63"]
    assert post(payload).status_code == 422


def test_extra_band_422():
    payload = make_payload()
    payload["periods"][0]["bands"]["16000"] = 50
    assert post(payload).status_code == 422


def test_missing_duration_422():
    payload = make_payload()
    del payload["periods"][0]["duration"]
    assert post(payload).status_code == 422


def test_missing_limit_422():
    payload = make_payload()
    del payload["limit"]
    assert post(payload).status_code == 422


def test_extra_period_field_422():
    payload = make_payload()
    payload["periods"][0]["la"] = 91.2
    assert post(payload).status_code == 422


def test_extra_top_level_field_422():
    payload = make_payload()
    payload["workshop"] = " stamping "
    assert post(payload).status_code == 422


def test_single_invalid_period_fails_whole_request():
    payload = make_payload(periods=[make_period(), make_period(duration=0)])
    assert post(payload).status_code == 422
