"""src.analysis.exposure.classify_hour 경계값 테스트."""
from __future__ import annotations

from src.analysis.exposure import classify_hour


def test_light_rain_below_threshold_is_clear():
    # 강수 0.05mm(RAIN_MM_THRESHOLD=0.1 미만) & 기온 5도 → 맑음
    assert classify_hour(0.05, 0, 5) == "맑음"


def test_rain_at_threshold_is_rain():
    # 강수 0.1mm(임계값) & 기온 5도 → 비
    assert classify_hour(0.1, 0, 5) == "비"


def test_freezing_rain_is_snow():
    # 강수>0 & 기온<=0 → 눈
    assert classify_hour(0.5, 0, -1) == "눈"


def test_fresh_snow_present_is_snow_even_without_rain():
    # 신적설>0 이면 강수가 0이어도 눈
    assert classify_hour(0, 0.2, 5) == "눈"


def test_all_empty_strings_treated_as_zero_is_clear():
    # ASOS 무강수/무적설 관측은 빈 문자열로 옴 → 0 처리 → 맑음
    assert classify_hour("", "", "") == "맑음"


def test_missing_temperature_with_rain_is_rain_not_snow():
    # 기온 결측('')이면 눈 판정의 기온조건에서 보수적으로 제외 → 강수>=0.1이면 비
    assert classify_hour(0.5, 0, "") == "비"
