"""src.analysis.exposure 테스트 — classify_hour 경계값과 월별 결손 탐지."""
from __future__ import annotations

import pandas as pd

from src.analysis.exposure import classify_hour, short_months


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


def test_classify_hour_always_returns_a_risk_category():
    """'기타' 버킷은 존재하지 않는다 — 결측도 맑음으로 떨어진다(문서화된 동작).

    ASOS는 '강수 없음'과 '관측 결측'을 모두 빈 문자열로 보내 구분이 불가능하다.
    이 테스트는 그 설계 결정을 고정한다. 바꾸려면 methodology.md 한계 절과
    exposure.py 모듈 docstring을 함께 갱신해야 한다.
    """
    for args in [("", "", ""), (None, None, None), ("결측", "결측", "결측")]:
        assert classify_hour(*args) in {"맑음", "비", "눈"}
    # 완전 결측은 구체적으로 '맑음'(무강수와 동일 취급)
    assert classify_hour(None, None, None) == "맑음"


# --- short_months: 기간 정합성 검사가 못 보는 '잘린 월' 탐지 ---

def _hours(ym: str, n: int) -> list[str]:
    start = pd.Timestamp(f"{ym}-01")
    return [(start + pd.Timedelta(hours=i)).strftime("%Y-%m-%d %H:%M") for i in range(n)]


def test_complete_months_are_not_flagged():
    df = pd.DataFrame({"tm": _hours("2021-01", 744) + _hours("2021-04", 720)})
    assert short_months(df) == []


def test_truncated_month_is_flagged():
    """월 파일이 잘려도 '달 존재'로는 통과하므로 여기서 잡아야 한다."""
    df = pd.DataFrame({"tm": _hours("2021-01", 744) + _hours("2021-02", 100)})
    assert short_months(df) == [("2021-02", 100, 672)]


def test_leap_february_expects_696_hours():
    # 2020-02 는 29일 = 696시간. 윤년을 놓치면 정상 데이터를 결손으로 오탐한다.
    assert short_months(pd.DataFrame({"tm": _hours("2020-02", 696)})) == []
    assert short_months(pd.DataFrame({"tm": _hours("2020-02", 600)})) == [("2020-02", 600, 696)]


def test_threshold_tolerates_small_gaps():
    """실측 최저치(719/720 = 99.86%)처럼 한두 시간 빠진 달은 정상으로 본다."""
    assert short_months(pd.DataFrame({"tm": _hours("2012-11", 719)})) == []
    # 90% 미만이면 이상 신호
    assert short_months(pd.DataFrame({"tm": _hours("2012-11", 600)})) == [("2012-11", 600, 720)]
