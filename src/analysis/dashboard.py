"""자치구 choropleth 대시보드(folium) — 기상범주 레이어 토글.

맑음/비/눈 3개 레이어를 만든다.
- **맑음**: 기준선(RR=1.0)이라 위험 색칠이 무정보이므로, 대신 **맑은 날씨 사고건수**를
  순차 파랑계열 choropleth로 색칠한다(구별 사고 규모 파악용).
- **비/눈**: 같은 구 안에서 맑음 대비 **상대위험(RR)** 을 RdYlBu 계열로 색칠한다.
LayerControl로 토글하면 기상별 위험 분포 변화가 보인다.
구 클릭 팝업에 사고건수·노출시간·시간당 사고율·상대위험·CI·소표본 경고를 표시한다.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import folium
import pandas as pd

CATEGORIES = ["맑음", "비", "눈"]
DEFAULT_LAYER = "비"
BASELINE = "맑음"

CLEAR_LAYER_NAME = "맑음 (사고건수·기준선)"

# 상대위험 색상 구간 (파랑=낮음 → 빨강=높음, RdYlBu 계열)
_BINS = [0.5, 0.8, 1.25, 2.0, 3.0]
_COLORS = ["#2c7bb6", "#abd9e9", "#ffffbf", "#fdae61", "#f46d43", "#d7191c"]
_NA_COLOR = "#cccccc"

# 맑음 사고건수 순차 색상 (연한 → 진한 파랑, ColorBrewer Blues)
_BLUE_COLORS = ["#eff3ff", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]


def _color(rr: float) -> str:
    if rr is None or (isinstance(rr, float) and math.isnan(rr)):
        return _NA_COLOR
    for i, b in enumerate(_BINS):
        if rr < b:
            return _COLORS[i]
    return _COLORS[-1]


def _blue_color(count: float, edges: list[float]) -> str:
    """맑음 사고건수 → 순차 파랑. edges는 오름차순 구간 경계(길이=색상수-1)."""
    if count is None or (isinstance(count, float) and math.isnan(count)):
        return _NA_COLOR
    for i, e in enumerate(edges):
        if count < e:
            return _BLUE_COLORS[i]
    return _BLUE_COLORS[-1]


def _blue_edges(counts: pd.Series) -> list[float]:
    """맑음 사고건수 분포의 분위수로 5개 구간 경계 산출(6색 → 경계 5개)."""
    vals = counts[counts > 0]
    if len(vals) == 0:
        return [1, 2, 3, 4, 5]
    qs = [vals.quantile(q) for q in (0.2, 0.4, 0.6, 0.8, 0.95)]
    # 경계가 중복되면 단조 증가하도록 살짝 벌린다.
    edges: list[float] = []
    for q in qs:
        v = float(q)
        if edges and v <= edges[-1]:
            v = edges[-1] + 1.0
        edges.append(v)
    return edges


def _fmt(x: object, nd: int = 2) -> str:
    try:
        f = float(x)
        return "—" if math.isnan(f) else f"{f:.{nd}f}"
    except (TypeError, ValueError):
        return "—"


def build_dashboard(
    risk: pd.DataFrame,
    geojson_path: str | Path,
    out_html: str | Path,
    name_prop: str = "name",
) -> Path:
    """상대위험 테이블 + 자치구 GeoJSON → folium HTML 대시보드 저장."""
    geo = json.loads(Path(geojson_path).read_text(encoding="utf-8"))

    # (구, 범주) → 지표 lookup
    idx: dict[tuple[str, str], dict] = {
        (row["구"], row["기상범주"]): row for _, row in risk.iterrows()
    }

    # 맑음 사고건수 분포 기반 파랑 색상 경계
    clear_counts = risk[risk["기상범주"] == BASELINE].set_index("구")["사고건수"]
    blue_edges = _blue_edges(clear_counts)

    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11, tiles="cartodbpositron")

    # 페이지 제목(<title>) 삽입
    m.get_root().header.add_child(
        folium.Element("<title>서울 자치구 기상별 교통사고 위험</title>")
    )

    for cat in CATEGORIES:
        is_clear = cat == BASELINE
        layer_name = CLEAR_LAYER_NAME if is_clear else f"{cat} (맑음 대비 상대위험)"
        fg = folium.FeatureGroup(name=layer_name, show=(cat == DEFAULT_LAYER))
        gj = copy.deepcopy(geo)
        for feat in gj["features"]:
            gu = feat["properties"].get(name_prop)
            rec = idx.get((gu, cat))
            if rec is not None:
                rr = rec["상대위험"]
                cnt = int(rec["사고건수"])
                feat["properties"].update(
                    {
                        "자치구": gu,
                        "기상": cat,
                        "상대위험": _fmt(rr),
                        "신뢰구간": f"[{_fmt(rec['CI하한'])}, {_fmt(rec['CI상한'])}]",
                        "사고건수": cnt,
                        "노출시간": f"{int(rec['노출시간']):,} h",
                        "사고율_시간당": _fmt(rec["사고율_시간당"], 5),
                        "불안정": "⚠ 소표본/불안정" if bool(rec["소표본경고"]) else "",
                        "_rr": None if (isinstance(rr, float) and math.isnan(rr)) else float(rr),
                        "_count": cnt,
                        "_small": bool(rec["소표본경고"]),
                    }
                )
            else:
                feat["properties"].update(
                    {"자치구": gu, "기상": cat, "상대위험": "—", "신뢰구간": "—",
                     "사고건수": 0, "노출시간": "—", "사고율_시간당": "—",
                     "불안정": "⚠ 표본없음", "_rr": None, "_count": 0, "_small": True}
                )

        def style_function(feature, _is_clear=is_clear, _edges=blue_edges):
            p = feature["properties"]
            if _is_clear:
                # 맑음: 사고건수 순차 파랑(기준선이라 위험 색칠은 무정보)
                fill = _blue_color(p.get("_count"), _edges)
            else:
                fill = _color(p.get("_rr"))
            return {
                "fillColor": fill,
                "color": "#666666",
                "weight": 1,
                # 소표본 구는 반투명 + 점선 테두리로 경고(맑음은 항상 안정)
                "fillOpacity": 0.35 if p.get("_small") else 0.75,
                "dashArray": "4,4" if p.get("_small") else None,
            }

        if is_clear:
            popup_fields = ["자치구", "기상", "사고건수", "노출시간", "사고율_시간당"]
            popup_aliases = ["자치구", "기상범주", "사고건수", "노출시간(ASOS)",
                             "시간당 사고율"]
            tooltip = folium.GeoJsonTooltip(
                fields=["자치구", "사고건수"], aliases=["", "맑음 사고건수 "]
            )
        else:
            popup_fields = ["자치구", "기상", "상대위험", "신뢰구간", "사고건수",
                            "노출시간", "사고율_시간당", "불안정"]
            popup_aliases = ["자치구", "기상범주", "상대위험(RR)", "95% CI",
                             "사고건수(표본 n)", "노출시간(ASOS)", "시간당 사고율", ""]
            tooltip = folium.GeoJsonTooltip(
                fields=["자치구", "상대위험"], aliases=["", "상대위험(RR) "]
            )

        folium.GeoJson(
            gj,
            style_function=style_function,
            highlight_function=lambda f: {"weight": 3, "color": "#000000"},
            popup=folium.GeoJsonPopup(
                fields=popup_fields,
                aliases=popup_aliases,
                localize=True,
            ),
            tooltip=tooltip,
        ).add_to(fg)
        fg.add_to(m)

    _add_gu_labels(m, geo, name_prop)
    folium.LayerControl(collapsed=False).add_to(m)
    _add_banner(m)
    _add_legend(m)

    out = Path(out_html)
    out.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(out))
    return out


def _centroid(geometry: dict) -> tuple[float, float] | None:
    """폴리곤/멀티폴리곤 좌표의 평균점(lat, lon) — 라벨 배치용(shapely 불필요)."""
    pts: list[tuple[float, float]] = []

    def walk(x: object) -> None:
        if isinstance(x, (list, tuple)):
            if len(x) == 2 and all(isinstance(v, (int, float)) for v in x):
                pts.append((x[0], x[1]))  # [lon, lat]
            else:
                for e in x:
                    walk(e)

    walk(geometry.get("coordinates"))
    if not pts:
        return None
    lon = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return lat, lon


def _add_gu_labels(m: folium.Map, geo: dict, name_prop: str) -> None:
    """각 자치구 중심에 구 이름을 상시 표시(마우스 오버 불필요). 레이어로 토글 가능."""
    fg = folium.FeatureGroup(name="구 이름", show=True)
    for feat in geo["features"]:
        name = feat["properties"].get(name_prop)
        c = _centroid(feat["geometry"])
        if not c or not name:
            continue
        folium.Marker(
            location=list(c),
            icon=folium.DivIcon(
                html=(
                    '<div style="font-size:11px;font-weight:700;color:#1a1a1a;'
                    'text-shadow:0 0 2px #fff,0 0 2px #fff,0 0 2px #fff;'
                    'white-space:nowrap;transform:translate(-50%,-50%)">'
                    f'{name}</div>'
                )
            ),
        ).add_to(fg)
    fg.add_to(m)


def _add_banner(m: folium.Map) -> None:
    """지도 상단 고정 배너: 제목 + 해석 주의 부제.

    배너가 leaflet 상단 컨트롤(좌:줌 / 우:레이어토글)을 가리지 않도록,
    상단 컨트롤을 배너 높이만큼 아래로 내리는 CSS를 함께 주입한다.
    """
    html = (
        '<style>.leaflet-top{top:62px !important;}</style>'
        '<div style="position:fixed;top:0;left:0;right:0;z-index:10000;'
        'background:rgba(33,37,41,.92);color:#fff;padding:8px 16px;'
        'font-family:sans-serif;box-shadow:0 1px 6px rgba(0,0,0,.3)">'
        '<div style="font-size:16px;font-weight:700">'
        '서울 자치구 기상별 교통사고 위험</div>'
        '<div style="font-size:11px;color:#cfd4da;margin-top:2px">'
        '기준=맑음 · 2014~2023 사망·중상 · '
        '⚠구역 내부 기상 비교(시간층화)이며 구역 간 절대비교가 아님</div>'
        '</div>'
    )
    m.get_root().html.add_child(folium.Element(html))


def _add_legend(m: folium.Map) -> None:
    items = "".join(
        f'<div><span style="background:{c};width:14px;height:14px;'
        f'display:inline-block;margin-right:6px;border:1px solid #999"></span>{lab}</div>'
        for c, lab in [
            (_COLORS[0], "< 0.5 (낮음)"),
            (_COLORS[1], "0.5–0.8"),
            (_COLORS[2], "0.8–1.25 (기준)"),
            (_COLORS[3], "1.25–2"),
            (_COLORS[4], "2–3"),
            (_COLORS[5], "≥ 3 (높음)"),
            (_NA_COLOR, "표본없음/소표본"),
        ]
    )
    blue = (
        f'<span style="background:{_BLUE_COLORS[0]};width:14px;height:14px;'
        f'display:inline-block;border:1px solid #999;vertical-align:middle"></span>'
        f'<span style="background:{_BLUE_COLORS[2]};width:14px;height:14px;'
        f'display:inline-block;border:1px solid #999;vertical-align:middle"></span>'
        f'<span style="background:{_BLUE_COLORS[5]};width:14px;height:14px;'
        f'display:inline-block;border:1px solid #999;vertical-align:middle"></span>'
    )
    html = (
        '<div style="position:fixed;bottom:24px;left:24px;z-index:9999;background:white;'
        'padding:10px 12px;border:1px solid #999;border-radius:6px;font-size:12px;'
        'font-family:sans-serif;box-shadow:0 1px 4px rgba(0,0,0,.2);max-width:230px">'
        '<b>비·눈: 맑음 대비 상대위험(RR)</b>'
        '<div style="color:#555;margin:2px 0 4px">'
        'RR = 맑을 때 대비 사고위험 배수 '
        '(1=같음, 2=2배 위험, 0.5=절반)</div>' + items +
        '<div style="margin-top:6px"><b>맑음: 사고건수</b> '
        f'{blue} <span style="color:#666">(연함→많음)</span></div>'
        '<div style="margin-top:4px;color:#666">점선/반투명 = 소표본·불안정(사고건수&lt;10 또는 CI 과대)</div>'
        '<div style="margin-top:2px;color:#a00">⚠ 눈 범주는 사고 표본(경찰 라벨)과 '
        '노출시간(ASOS) 분류 기준이 달라 RR이 상향 편향될 수 있고, 표시된 CI는 분류 불확실성을 '
        '반영하지 않습니다(실제 불확실성은 더 큼).</div>'
        '<div style="margin-top:6px;padding-top:6px;border-top:1px solid #ddd;color:#888;font-size:11px">'
        '출처: 도로교통공단 TAAS(사고) · 기상청 ASOS(기상), 2014~2023</div></div>'
    )
    m.get_root().html.add_child(folium.Element(html))
