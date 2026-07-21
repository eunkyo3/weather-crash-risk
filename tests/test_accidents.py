"""src.analysis.accidents.weather_category / _gu / check_severity 테스트."""
from __future__ import annotations

import pandas as pd

from src.analysis.accidents import _gu, check_severity, weather_category


def test_weather_category_clear_stays_clear():
    assert weather_category("맑음") == "맑음"


def test_weather_category_cloudy_maps_to_clear():
    # 비강수(흐림)는 맑음 기준선에 통합
    assert weather_category("흐림") == "맑음"


def test_weather_category_rain():
    assert weather_category("비") == "비"


def test_weather_category_snow():
    assert weather_category("눈") == "눈"


def test_weather_category_fog_maps_to_other():
    assert weather_category("안개") == "기타"


def test_weather_category_unknown_maps_to_other():
    assert weather_category("기타") == "기타"


def test_gu_extracts_last_token():
    assert _gu("서울특별시 강동구") == "강동구"


def _df(contents: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"사고내용": contents})


def test_check_severity_accepts_fatal_and_serious():
    # 분석 범위(사망+중상)만 있으면 경고 대상 없음
    assert check_severity(_df(["사망사고", "중상사고", "중상사고"])) == {}


def test_check_severity_flags_out_of_scope_records():
    # 경상/부상신고가 섞이면 분자가 과대집계되므로 라벨·건수를 돌려준다
    result = check_severity(_df(["사망사고", "경상사고", "경상사고", "부상신고사고"]))
    assert result == {"경상사고": 2, "부상신고사고": 1}


def test_check_severity_tolerates_missing_column():
    # 라벨 스키마가 바뀌어도 파이프라인을 죽이지 않는다(경고만)
    assert check_severity(pd.DataFrame({"시군구": ["서울특별시 중구"]})) == {}
