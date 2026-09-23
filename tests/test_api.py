"""pytest：用独立公式核对后端计算，并用边界样例卡校验与判定。

参考公式与生产代码相互独立地直接书写，不调用 service 的中间函数。
"""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.schemas import BAND_FREQS

client = TestClient(app)

A_CORR = {
    63: -26.2,
    125: -16.1,
    250: -8.6,
    500: -3.2,
    1000: 0.0,
    2000: 1.2,
    4000: 1.0,
    8000: -1.1,
}


def ref_period_laeq(levels: dict[int, float]) -> float:
    return 10 * math.log10(
        sum(10 ** ((levels[f] + A_CORR[f]) / 10) for f in BAND_FREQS)
    )


def ref_total(periods: list[dict]) -> float:
    num = sum(p["duration"] * 10 ** (ref_period_laeq(p["levels"]) / 10) for p in periods)
    den = sum(p["duration"] for p in periods)
    return 10 * math.log10(num / den)


def ref_share(periods, i, freq):
    total = 0.0
    for p in periods:
        for f in BAND_FREQS:
            total += p["duration"] * 10 ** ((p["levels"][f] + A_CORR[f]) / 10)
    p = periods[i]
    return p["duration"] * 10 ** ((p["levels"][freq] + A_CORR[freq]) / 10) / total


def make_payload(periods, limit=85.0):
    return {
        "limit": limit,
        "periods": [
            {
                "duration": p["duration"],
                "levels": {str(f): p["levels"][f] for f in BAND_FREQS},
            }
            for p in periods
        ],
    }


def quiet_levels(freq=None, value=80.0, base=0.0):
    """除 freq 外全部给 base，freq 给 value。"""
    return {f: (value if f == freq else base) for f in BAND_FREQS}


# ---------------------------------------------------------------- 数值核对

def test_single_period_1khz_only():
    periods = [{"duration": 600, "levels": quiet_levels(1000, 80.0, 0.0)}]
    r = client.post("/api/exposure", json=make_payload(periods))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["periods"][0]["laeq_display"] == "80.0"
    assert body["total_laeq_display"] == "80.0"
    assert body["dominant"] == {
        "period_index": 1,
        "frequency": 1000,
        "energy_share": pytest.approx(1.0, abs=1e-7),
        "energy": pytest.approx(1e8, rel=1e-9),
    }
    assert body["compliant"] is True


def test_two_equal_periods_plus_3db():
    levels_a = quiet_levels(1000, 70.0)
    levels_b = quiet_levels(1000, 73.0)
    periods = [
        {"duration": 100, "levels": levels_a},
        {"duration": 100, "levels": levels_b},
    ]
    r = client.post("/api/exposure", json=make_payload(periods))
    body = r.json()
    # 独立参考公式为基准；73.0 严格比 70 高 3 dB（能量 1.9953 倍），
    # 合并值 = 70 + 10log10((1+10^0.3)/2) ≈ 71.754（精确的 2 倍能量需 +3.01 dB）
    assert body["total_laeq"] == pytest.approx(ref_total(periods), abs=1e-12)
    assert body["total_laeq"] == pytest.approx(
        70 + 10 * math.log10((1 + 10 ** 0.3) / 2), abs=1e-5
    )
    assert body["total_laeq_display"] == "71.8"
    assert body["dominant"]["period_index"] == 2
    assert body["dominant"]["frequency"] == 1000


def test_duration_weighting_matches_reference():
    periods = [
        {"duration": 1, "levels": quiet_levels(500, 90.0)},
        {"duration": 3599, "levels": quiet_levels(2000, 60.0)},
    ]
    r = client.post("/api/exposure", json=make_payload(periods, limit=70))
    body = r.json()
    assert body["total_laeq"] == pytest.approx(ref_total(periods), abs=1e-12)
    for i, p in enumerate(body["periods"]):
        assert p["laeq"] == pytest.approx(ref_period_laeq(periods[i]["levels"]), abs=1e-12)
    assert body["dominant"]["period_index"] == 2
    assert body["dominant"]["frequency"] == 2000
    assert body["dominant"]["energy_share"] == pytest.approx(ref_share(periods, 1, 2000), abs=1e-15)


def test_all_bands_and_a_weightings():
    levels = {f: 90.0 for f in BAND_FREQS}
    periods = [{"duration": 30, "levels": levels}]
    r = client.post("/api/exposure", json=make_payload(periods))
    body = r.json()
    expected = ref_period_laeq(levels)
    assert body["total_laeq"] == pytest.approx(expected, abs=1e-12)
    # 八个频带中 2000Hz 修正最高(+1.2)，为主导频带
    assert body["dominant"]["frequency"] == 2000
    # 能量占比之和为 1
    total_share = sum(b["energy_share"] for b in body["periods"][0]["bands"])
    assert total_share == pytest.approx(1.0, abs=1e-12)


def test_shares_sum_to_one_across_periods():
    periods = [
        {"duration": 250, "levels": {f: 55.0 + (f % 7) * 4 for f in BAND_FREQS}},
        {"duration": 1777, "levels": {f: 48.0 + (f % 5) * 6 for f in BAND_FREQS}},
        {"duration": 90, "levels": {f: 70.0 - (f % 3) * 5 for f in BAND_FREQS}},
    ]
    body = client.post("/api/exposure", json=make_payload(periods)).json()
    shares = [b["energy_share"] for p in body["periods"] for b in p["bands"]]
    assert sum(shares) == pytest.approx(1.0, abs=1e-12)
    assert body["total_laeq"] == pytest.approx(ref_total(periods), abs=1e-12)


# ------------------------------------------------------ 并列打破规则

def test_tie_breaks_earliest_period():
    # 两个时段所有输入完全相同 => 主导取最早时段
    levels = quiet_levels(1000, 75.0)
    periods = [
        {"duration": 100, "levels": levels},
        {"duration": 100, "levels": levels},
    ]
    body = client.post("/api/exposure", json=make_payload(periods)).json()
    assert body["dominant"]["period_index"] == 1


def test_tie_breaks_lowest_frequency():
    # 让 250Hz(-8.6) 与 1000Hz(0) 能量相等：250 声级高 8.6 dB
    levels = quiet_levels(63, 0.0)
    levels[250] = 80.0
    levels[1000] = 71.4
    periods = [{"duration": 10, "levels": levels}]
    body = client.post("/api/exposure", json=make_payload(periods)).json()
    band_map = {b["frequency"]: b for b in body["periods"][0]["bands"]}
    assert band_map[250]["energy"] == pytest.approx(band_map[1000]["energy"], rel=1e-12)
    assert body["dominant"]["frequency"] == 250


def test_tie_different_durations_can_shift_dominance():
    # 相同时段内声级，但时长更短的高声级时段仍可能主导
    loud = quiet_levels(1000, 100.0)
    quiet = quiet_levels(1000, 70.0)
    periods = [
        {"duration": 3600, "levels": quiet},
        {"duration": 1, "levels": loud},
    ]
    body = client.post("/api/exposure", json=make_payload(periods)).json()
    # 1s 的 100dB 能量=1e10；3600s 的 70dB 能量=3600*1e7=3.6e10 => 时段1主导
    assert body["dominant"]["period_index"] == 1
    assert body["dominant"]["energy_share"] == pytest.approx(3.6 / 4.6, rel=1e-6)


# ------------------------------------------------------ 合格判定用未舍入值

def test_boundary_exactly_at_limit_compliant():
    # 限值取该工况的未舍入暴露值本身，验证判定边界为 <=（等于限值即合格）
    periods = [{"duration": 100, "levels": quiet_levels(1000, 85.0, base=0.0)}]
    exact = ref_total(periods)
    body = client.post("/api/exposure", json=make_payload(periods, limit=exact)).json()
    assert body["total_laeq"] == pytest.approx(exact, abs=1e-12)
    assert body["compliant"] is True
    # 限值比真实值低一点点即超标，证明用的是未舍入值而非 85.0 展示值
    body2 = client.post(
        "/api/exposure", json=make_payload(periods, limit=exact - 1e-9)
    ).json()
    assert body2["compliant"] is False


def test_unrounded_value_used_above_limit():
    # 构造未舍入值 85.04(+零底噪微扰) -> 展示 85.0，但仍判超标
    periods = [{"duration": 100, "levels": quiet_levels(1000, 85.04, base=0.0)}]
    body = client.post("/api/exposure", json=make_payload(periods, limit=85)).json()
    assert body["total_laeq"] == pytest.approx(85.04, abs=1e-6)
    assert body["total_laeq_display"] == "85.0"
    assert body["compliant"] is False


def test_unrounded_value_used_below_limit():
    # 84.95 -> 展示 85.0（HALF_UP），但未超 85 => 合格
    periods = [{"duration": 100, "levels": quiet_levels(1000, 84.95, base=0.0)}]
    body = client.post("/api/exposure", json=make_payload(periods, limit=85)).json()
    assert body["total_laeq_display"] == "85.0"
    assert body["compliant"] is True


def test_short_loud_not_diluted():
    # 60s@110dB + 3540s@80dB：算术平均声级仅 (60*110+3540*80)/3600 = 80.5，
    # 会被误判合格；能量合并应得 ≈ 92.5 dB，短时高声级不被稀释。
    periods = [
        {"duration": 60, "levels": quiet_levels(1000, 110.0)},
        {"duration": 3540, "levels": quiet_levels(1000, 80.0)},
    ]
    body = client.post("/api/exposure", json=make_payload(periods, limit=85)).json()
    assert body["total_laeq"] == pytest.approx(ref_total(periods), abs=1e-12)
    assert body["total_laeq"] == pytest.approx(92.5, abs=5e-2)
    assert body["compliant"] is False


# ------------------------------------------------------ 422 校验

VALID_LEVELS = {str(f): 80.0 for f in BAND_FREQS}


def post(raw):
    return client.post("/api/exposure", json=raw)


def test_422_missing_band():
    raw = make_payload([{"duration": 10, "levels": {f: 80.0 for f in BAND_FREQS}}])
    del raw["periods"][0]["levels"]["500"]
    assert post(raw).status_code == 422


def test_422_extra_band():
    raw = make_payload([{"duration": 10, "levels": {f: 80.0 for f in BAND_FREQS}}])
    raw["periods"][0]["levels"]["31"] = 70
    assert post(raw).status_code == 422


def test_422_missing_duration():
    raw = make_payload([{"duration": 10, "levels": {f: 80.0 for f in BAND_FREQS}}])
    del raw["periods"][0]["duration"]
    assert post(raw).status_code == 422


def test_422_missing_limit():
    raw = make_payload([{"duration": 10, "levels": {f: 80.0 for f in BAND_FREQS}}])
    del raw["limit"]
    assert post(raw).status_code == 422


def test_422_extra_top_field():
    raw = make_payload([{"duration": 10, "levels": {f: 80.0 for f in BAND_FREQS}}])
    raw["operator"] = "X"
    assert post(raw).status_code == 422


@pytest.mark.parametrize("duration", [0, -1, 3601, 1.5, "60", True, None])
def test_422_bad_duration(duration):
    raw = make_payload([{"duration": 10, "levels": {f: 80.0 for f in BAND_FREQS}}])
    raw["periods"][0]["duration"] = duration
    assert post(raw).status_code == 422


@pytest.mark.parametrize("level", [-0.1, 140.1, "80", True, False, None])
def test_422_bad_level(level):
    raw = make_payload([{"duration": 10, "levels": {f: 80.0 for f in BAND_FREQS}}])
    raw["periods"][0]["levels"]["1000"] = level
    assert post(raw).status_code == 422


@pytest.mark.parametrize("limit", [39.9, 100.1, 0, 140, "85", True, None])
def test_422_bad_limit(limit):
    raw = make_payload([{"duration": 10, "levels": {f: 80.0 for f in BAND_FREQS}}])
    raw["limit"] = limit
    assert post(raw).status_code == 422


@pytest.mark.parametrize("n", [0, 25])
def test_422_period_count(n):
    raw = make_payload(
        [{"duration": 10, "levels": {f: 80.0 for f in BAND_FREQS}} for _ in range(n)]
    )
    assert post(raw).status_code == 422


def test_422_level_boundary_values_accepted():
    raw = make_payload([{"duration": 1, "levels": {f: 0.0 for f in BAND_FREQS}}])
    assert post(raw).status_code == 200
    raw["periods"][0]["levels"] = {str(f): 140.0 for f in BAND_FREQS}
    assert post(raw).status_code == 200


def test_422_duration_boundaries_accepted():
    for d in (1, 3600):
        raw = make_payload([{"duration": d, "levels": {f: 80.0 for f in BAND_FREQS}}])
        assert post(raw).status_code == 200


def test_422_empty_body():
    assert client.post("/api/exposure", json={}).status_code == 422


def test_422_limit_boundaries_accepted():
    for limit in (40, 100):
        raw = make_payload(
            [{"duration": 1, "levels": {f: 50.0 for f in BAND_FREQS}}], limit=limit
        )
        assert post(raw).status_code == 200


# ------------------------------------------------------- 展示舍入

def test_display_half_up_rounding():
    # 1000Hz 单频带 84.95/85.05/85.15 的 HALF_UP 展示
    cases = {84.95: "85.0", 85.04: "85.0", 85.05: "85.1", 84.94: "84.9"}
    for value, expected in cases.items():
        periods = [{"duration": 5, "levels": quiet_levels(1000, value)}]
        body = client.post("/api/exposure", json=make_payload(periods)).json()
        assert body["total_laeq_display"] == expected
