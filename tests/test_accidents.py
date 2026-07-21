"""src.analysis.accidents.weather_category / _gu 테스트."""
from __future__ import annotations

from src.analysis.accidents import _gu, weather_category


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
