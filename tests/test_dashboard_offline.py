"""오프라인 보장(M1/S1)과 원자적 저장 회귀 테스트.

리뷰어 지적: M1 수정이 수동 검증에만 의존해서, `_use_offline_assets()` 호출을
`m.save()` 아래로 되돌려도 테스트가 전부 초록으로 통과했다. 여기서 그 경로를 고정한다.
"""
from __future__ import annotations

import json
import os
import stat
import sys

import folium
import pandas as pd
import pytest

from src.analysis import dashboard as dash

# 최소 입력: 구 3개 × 기상 3범주 + 사각형 폴리곤 3개
_ZONES = ["가구", "나구", "다구"]


@pytest.fixture
def risk() -> pd.DataFrame:
    rows = []
    for i, gu in enumerate(_ZONES):
        for cat, n, exp, rr in [("맑음", 100 + i, 8000, 1.0), ("비", 20 + i, 800, 1.2 + i * 0.1),
                                ("눈", 5 + i, 100, 1.8 + i * 0.2)]:
            rows.append({
                "구": gu, "기상범주": cat, "사고건수": n, "노출시간": exp,
                "사고율_시간당": n / exp, "상대위험": rr,
                "CI하한": rr * 0.8, "CI상한": rr * 1.2,
                "소표본경고": cat == "눈",
            })
    return pd.DataFrame(rows)


@pytest.fixture
def geojson(tmp_path):
    feats = []
    for i, gu in enumerate(_ZONES):
        x = 127.0 + i * 0.1
        feats.append({
            "type": "Feature",
            "properties": {"name": gu},
            "geometry": {"type": "Polygon", "coordinates": [[
                [x, 37.5], [x + 0.08, 37.5], [x + 0.08, 37.58], [x, 37.58], [x, 37.5]]]},
        })
    p = tmp_path / "zones.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    return p


def _external_refs(html: str) -> list[str]:
    return dash._EXTERNAL_ASSET_RE.findall(html)


def test_generated_dashboard_has_no_external_asset_references(risk, geojson, tmp_path):
    out = dash.build_dashboard(risk, geojson, tmp_path / "d.html", period=None)
    html = out.read_text(encoding="utf-8")
    assert _external_refs(html) == []
    # leaflet 이 실제로 인라인되어 있어야 한다 — 참조만 지우면 지도가 빈 채로 뜬다.
    # 임의의 크기 임계값 대신 벤더 원본이 통째로 들어갔는지를 확인한다.
    leaflet_js = (dash._VENDOR / "leaflet.js").read_text(encoding="utf-8")
    assert leaflet_js in html, "leaflet.js 본문이 인라인되지 않았다"
    assert ".leaflet-container" in html, "leaflet.css 가 인라인되지 않았다"

    # 순서: 라이브러리가 지도 생성 코드보다 먼저 나와야 한다. 위치 무관 단언만 두면
    # 인라인을 figure.script 로 옮겨도 초록이 유지되면서 지도는 온·오프라인 모두 깨진다
    # (_LegendSwitcher docstring 이 기록한 그 버그).
    assert html.index(leaflet_js) < html.index("var map_"), "leaflet 이 지도 생성보다 뒤에 있다"

    # CSS 안의 상대 이미지 경로는 data URI 로 치환돼야 한다. 이건 태그 속성이 아니라
    # CSS url() 이라 _EXTERNAL_ASSET_RE 가 구조적으로 잡지 못하는 누수 경로다.
    assert "url(images/" not in html, "leaflet.css 의 상대 이미지 경로가 남아 있다"
    assert "url(data:image" in html, "이미지가 data URI 로 인라인되지 않았다"


def test_period_must_be_passed_explicitly(risk, geojson, tmp_path):
    """기간을 빠뜨린 호출이 조용히 '기간 없는 대시보드'를 만들면 안 된다.

    실제로 겪은 사고다 — 하드코딩을 걷어낸 뒤 검증 스크립트가 period 없이 재생성해서
    커밋된 산출물의 배너·출처에서 기간이 사라졌다. 기본값을 없애 TypeError 로 만든다.
    """
    with pytest.raises(TypeError, match="period"):
        dash.build_dashboard(risk, geojson, tmp_path / "d.html")  # type: ignore[call-arg]


def test_period_is_rendered_in_banner_and_source_line(risk, geojson, tmp_path):
    out = dash.build_dashboard(risk, geojson, tmp_path / "d.html", period="2007~2025")
    html = out.read_text(encoding="utf-8")
    assert "기준=맑음 · 2007~2025 사망·중상" in html      # 배너
    assert "ASOS(기상), 2007~2025" in html               # 범례 출처


def test_period_none_omits_the_text_entirely(risk, geojson, tmp_path):
    """명시적 None 은 허용 — 다만 어정쩡한 빈 기간 문구를 남기지 않는다."""
    out = dash.build_dashboard(risk, geojson, tmp_path / "d.html", period=None)
    html = out.read_text(encoding="utf-8")
    assert "기준=맑음 · 사망·중상" in html
    assert "ASOS(기상)</div>" in html


def test_use_offline_assets_clears_folium_cdn_lists():
    m = folium.Map()
    assert m.default_js and m.default_css, "folium 기본값이 비어 있으면 이 테스트는 무의미"
    dash._use_offline_assets(m)
    assert m.default_js == []
    assert m.default_css == []


def test_missing_vendor_fails_before_touching_existing_output(
    risk, geojson, tmp_path, monkeypatch
):
    """M1 핵심 회귀 — 벤더 자산이 없으면 기존 산출물을 건드리지 않고 실패해야 한다.

    `_use_offline_assets()` 를 `m.save()` 아래로 옮기면 이 테스트가 깨진다
    (기존 파일이 CDN 참조본으로 덮여쓰인 뒤 예외가 나므로).
    """
    out = tmp_path / "d.html"
    dash.build_dashboard(risk, geojson, out, period=None)          # 정상 산출물 1회 생성
    good_bytes = out.read_bytes()
    assert _external_refs(good_bytes.decode("utf-8")) == []

    monkeypatch.setattr(dash, "_VENDOR", tmp_path / "__no_vendor__")
    with pytest.raises(FileNotFoundError):
        dash.build_dashboard(risk, geojson, out, period=None)

    assert out.read_bytes() == good_bytes, "실패한 재생성이 기존 대시보드를 훼손했다"
    assert _external_refs(out.read_text(encoding="utf-8")) == []
    leftovers = [p.name for p in tmp_path.iterdir() if p.name not in {"d.html", "zones.geojson"}]
    assert leftovers == [], f"임시 파일이 남았다: {leftovers}"


def test_save_atomic_rejects_external_refs_and_keeps_original(tmp_path, monkeypatch):
    """S1 — 외부 참조가 남으면 RuntimeError, 기존 파일은 보존."""
    out = tmp_path / "d.html"
    out.write_text("<html>기존 산출물</html>", encoding="utf-8")

    m = folium.Map()
    # 오프라인 처리를 생략해 CDN 태그가 남은 상태를 만든다
    with pytest.raises(RuntimeError, match="오프라인 보장 실패"):
        dash._save_atomic(m, out)

    assert out.read_text(encoding="utf-8") == "<html>기존 산출물</html>"
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "d.html"]
    assert leftovers == [], f"임시 파일이 남았다: {leftovers}"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX 권한 비트가 의미 있는 환경에서만")
def test_saved_dashboard_is_world_readable(risk, geojson, tmp_path):
    """R3 — mkstemp 의 0600 이 그대로 굳으면 재생성 계정 외에는 못 읽는다."""
    out = dash.build_dashboard(risk, geojson, tmp_path / "d.html", period=None)
    mode = stat.S_IMODE(os.stat(out).st_mode)
    assert mode & stat.S_IRGRP, f"그룹 읽기 권한 없음: {oct(mode)}"
    assert mode & stat.S_IROTH, f"기타 사용자 읽기 권한 없음: {oct(mode)}"
