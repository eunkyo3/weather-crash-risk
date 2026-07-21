"""src.analysis.risk.zone_weather_risk / _unstable 테스트 — 합성 데이터로 결정론적 검증."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from src.analysis.risk import MIN_STABLE_N, _unstable, zone_weather_risk

EXPECTED_COLUMNS = [
    "구",
    "기상범주",
    "사고건수",
    "노출시간",
    "사고율_시간당",
    "상대위험",
    "CI하한",
    "CI상한",
    "소표본경고",
]

# 합성 입력: 맑음(대표본) / 비(대표본) / 눈(소표본, n<10 → 불안정)
COUNTS = pd.DataFrame(
    {
        "구": ["테스트구"] * 3,
        "기상범주": ["맑음", "비", "눈"],
        "사고건수": [1000, 300, 5],
    }
)
EXPOSURE = pd.Series({"맑음": 8000.0, "비": 800.0, "눈": 50.0})


@pytest.fixture
def result() -> pd.DataFrame:
    return zone_weather_risk(COUNTS, EXPOSURE)


def _row(df: pd.DataFrame, category: str) -> pd.Series:
    matches = df[df["기상범주"] == category]
    assert len(matches) == 1
    return matches.iloc[0]


def test_result_has_expected_columns(result):
    assert list(result.columns) == EXPECTED_COLUMNS


def test_baseline_relative_risk_is_one(result):
    row = _row(result, "맑음")
    assert row["상대위험"] == 1.0
    assert row["CI하한"] == 1.0
    assert row["CI상한"] == 1.0


def test_relative_risk_matches_manual_formula(result):
    # RR(범주) = (사고건수/노출시간) / (맑음 사고건수/맑음 노출시간)
    base_rate = 1000 / 8000.0

    rain_row = _row(result, "비")
    expected_rain_rr = (300 / 800.0) / base_rate
    assert rain_row["사고율_시간당"] == pytest.approx(300 / 800.0)
    assert rain_row["상대위험"] == pytest.approx(expected_rain_rr)

    snow_row = _row(result, "눈")
    expected_snow_rr = (5 / 50.0) / base_rate
    assert snow_row["사고율_시간당"] == pytest.approx(5 / 50.0)
    assert snow_row["상대위험"] == pytest.approx(expected_snow_rr)


def test_small_sample_ci_is_wider_than_large_sample_ci(result):
    rain_row = _row(result, "비")
    snow_row = _row(result, "눈")
    rain_width = rain_row["CI상한"] - rain_row["CI하한"]
    snow_width = snow_row["CI상한"] - snow_row["CI하한"]
    assert snow_width > rain_width


def test_ci_bounds_bracket_relative_risk_for_normal_cells(result):
    for cat in ["비", "눈"]:
        row = _row(result, cat)
        assert row["CI하한"] < row["상대위험"] < row["CI상한"]


def test_small_sample_warning_flag(result):
    # 눈 사고건수(5) < MIN_STABLE_N(10) → 소표본경고 True
    # (pandas는 bool 컬럼값을 numpy.bool_로 반환하므로 bool()로 캐스팅 후 비교)
    snow_row = _row(result, "눈")
    assert snow_row["사고건수"] < MIN_STABLE_N
    assert bool(snow_row["소표본경고"]) is True

    # 비는 대표본이라 소표본경고 False
    rain_row = _row(result, "비")
    assert bool(rain_row["소표본경고"]) is False

    # 맑음(기준선)은 정의상 경고 대상이 아님
    base_row = _row(result, "맑음")
    assert bool(base_row["소표본경고"]) is False


def test_unstable_flags_small_count():
    assert _unstable(MIN_STABLE_N - 1, 0.5, 1.5) is True
    assert _unstable(MIN_STABLE_N, 0.5, 1.5) is False


def test_unstable_flags_wide_ci_ratio():
    # hi/lo > MAX_CI_RATIO(3.0) → 불안정, n은 충분해도 마찬가지
    assert _unstable(50, 1.0, 4.0) is True
    assert _unstable(50, 1.0, 3.0) is False


def test_unstable_ignores_degenerate_nan_ci_when_n_sufficient():
    assert _unstable(50, math.nan, math.nan) is False
