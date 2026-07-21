"""자치구 choropleth 대시보드(folium) — 기상범주 레이어 토글.

맑음/비/눈 3개 레이어를 만든다.
- **맑음**: 기준선(RR=1.0)이라 위험 색칠이 무정보이므로, 대신 **맑은 날씨 사고건수**를
  순차 파랑계열 choropleth로 색칠한다(구별 사고 규모 파악용).
- **비/눈**: 같은 구 안에서 맑음 대비 **상대위험(RR)** 을 발산형 색상으로 칠한다.
LayerControl로 토글하면 기상별 위험 분포 변화가 보인다.
구 클릭 팝업에 사고건수·노출시간·시간당 사고율·상대위험·CI·소표본 경고를 표시한다.

**색상 구간은 레이어별 분위수**다(decisions-log "분위수 5단계" 결정). 고정 절대구간을
쓰면 RR이 좁은 구간에 몰린 레이어(비: 1.00~1.39)가 두세 색으로 뭉개져 지도가 무정보가
된다. RR=1.0(맑음 기준선)이 그 레이어 분포 **안에 있으면** 구간 경계로 끼워 넣고, 1.0
미만은 한색·이상은 난색으로 칠해 방향성을 유지한다. 분포가 기준선 한쪽에만 몰려 있으면
(전 구가 위험 또는 전 구가 안전) 빈 구간을 만들지 않고, 대신 범례가 어느 쪽인지를 문장으로
알린다 — **두 꼬리를 한 문장으로 뭉뚱그리면 반대쪽에서 방향이 정반대인 거짓말이 된다.**

> ⚠️ 분위수는 레이어마다 다시 계산되므로 **같은 색이 레이어 간 같은 RR을 뜻하지 않는다.**
> 범례에 그 경고를 넣어 두었다. 레이어 간 비교는 색이 아니라 숫자로 해야 한다.

범례는 레이어마다 다른 경계값을 쓰므로 **레이어 전환 시 함께 바뀐다**. 각 패널은 실제
사용된 경계값과 해당 레이어의 소표본 구 수를 함께 보여준다.

외부 CDN 없이 열리도록 folium의 `default_js`/`default_css` 를 비우고 Leaflet 자산을
head에 인라인한다(`assets/vendor/`). 저장된 HTML을 후처리 문자열 치환으로 손대지 않으므로
folium이 판올림돼도 조용히 깨지지 않으며, 저장 직후 외부 참조가 남았는지 단언한다.
지도 타일만 네트워크가 필요하며, 오프라인에서는 배경 없이 폴리곤·범례·라벨이 렌더된다.
"""
from __future__ import annotations

import base64
import copy
import json
import math
import os
import re
import tempfile
from pathlib import Path

import folium
import pandas as pd
from branca.element import MacroElement, Template

# 기상범주와 기준선의 단일 출처는 risk.py 다. 같은 리스트를 모듈마다 복제해 두면
# 범주를 바꿀 때 한 곳을 빠뜨려 분자·분모·색칠이 조용히 어긋난다.
from src.analysis.risk import BASELINE, RISK_CATEGORIES

DEFAULT_LAYER = "비"

CLEAR_LAYER_NAME = "맑음 (사고건수 — 위험 비교용 아님)"
LABEL_LAYER_NAME = "구 이름"

N_BINS = 5  # decisions-log: 분위수 5단계

# 버킷은 최대 6개(분위수 4경계 + 기준선 1 = 5경계). 6개가 되는 것은 기준선이 경계로
# 들어갔을 때뿐이고 그때는 한색·난색으로 갈리므로 **한쪽 램프가 감당할 최대는 5개**다.
# (전 구가 기준선 한쪽에 몰리면 기준선이 경계에 안 들어가 5버킷이 되고, 그 5개가 모두
#  한쪽 램프로 간다 — 그래서 각 램프는 정확히 5색이면 충분하고 여유는 없다.)
# 모자라면 _sample 이 같은 색을 두 번 뽑아 인접 구간이 구분되지 않으므로 예외를 던진다.
_MAX_BUCKETS = N_BINS + 1
# RR < 1.0 (맑음보다 안전) — 진한 파랑 → 옅은 파랑.
# 무데이터색(#cccccc)·지도 배경(#f4f4f2)과 혼동되지 않도록 흰색에 가까운 색은 쓰지 않는다.
_COOL = ["#08519c", "#2c7bb6", "#4393c3", "#74add1", "#abd9e9"]
# RR >= 1.0 (맑음보다 위험) — 옅은 노랑 → 진한 빨강
_WARM = ["#ffffbf", "#fdae61", "#f46d43", "#d73027", "#a50026"]
# 맑음 사고건수 순차 파랑 (ColorBrewer Blues)
_BLUE = ["#eff3ff", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]
_NA_COLOR = "#cccccc"

_VENDOR = Path(__file__).resolve().parents[2] / "assets" / "vendor"


def _sample(ramp: list[str], k: int) -> list[str]:
    """색상 램프에서 k개를 균등 간격으로 뽑는다.

    k=1이면 램프의 **중간색**을 쓴다. 양 끝을 쓰면 한 구간뿐인 레이어가 가장 옅은 색
    (거의 흰색 → 무데이터와 혼동) 또는 가장 진한 색(위험을 과장)으로 칠해진다.
    k가 램프 길이를 넘으면 같은 색이 중복 선택되어 인접 구간이 구분되지 않으므로
    조용히 넘어가지 않고 실패시킨다(램프를 늘려야 한다는 신호).
    """
    if k <= 0:
        return []
    if k > len(ramp):
        raise ValueError(f"색상 램프가 부족합니다: {k}개 필요, {len(ramp)}개 보유")
    if k == 1:
        return [ramp[len(ramp) // 2]]
    step = (len(ramp) - 1) / (k - 1)
    return [ramp[round(i * step)] for i in range(k)]


def quantile_bins(values: pd.Series, n_bins: int = N_BINS, anchor: float = 1.0) -> list[float]:
    """RR 분포의 분위수 경계를 만든다. 기준선(anchor)은 분포를 실제로 가를 때만 넣는다.

    반환값은 내부 경계 리스트(오름차순, 중복 제거) — 버킷 수는 len(경계)+1.
    값이 anchor 한쪽에만 몰려 있으면(전 구가 안전 또는 전 구가 위험) anchor를 경계로
    넣어봐야 아무 구도 속하지 않는 빈 구간이 생기므로 넣지 않는다. 그 경우 방향은
    범례 문장과 `bin_colors(data_max=...)` 가 책임진다.
    """
    vals = pd.Series([v for v in values if v is not None and not math.isnan(v)], dtype=float)
    if vals.empty:
        return []

    qs = [vals.quantile(i / n_bins) for i in range(1, n_bins)]
    bins = {round(float(q), 3) for q in qs}
    if float(vals.min()) < anchor < float(vals.max()):
        bins.add(anchor)
    return sorted(bins)


def bin_colors(
    bins: list[float], anchor: float = 1.0, data_max: float | None = None
) -> list[str]:
    """경계 리스트에 대응하는 버킷 색상(길이 = len(bins)+1).

    anchor 미만 버킷은 한색, 이상 버킷은 난색으로 나눠 "맑음보다 안전/위험"을 유지한다.

    **최상단 버킷은 위로 열려 있다**는 점이 함정이다. 경계가 전부 anchor 이하이면
    (= 전 구가 anchor 미만인 레이어) 마지막 버킷도 내용물이 전부 anchor 미만인데
    경계만 보고 판단하면 난색으로 칠해져 "안전한 구를 위험색으로" 표시하게 된다.
    `data_max` 를 넘겨주면 그 경우를 잡아 전 구간을 한색으로 칠한다.
    """
    n_buckets = len(bins) + 1
    below = sum(1 for b in bins if b <= anchor)
    if below == len(bins) and data_max is not None and data_max < anchor:
        below = n_buckets  # 최상단 버킷의 내용물도 전부 anchor 미만 → 전부 한색
    return _sample(_COOL, below) + _sample(_WARM, n_buckets - below)


def _bucket(value: float | None, bins: list[float]) -> int | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    for i, b in enumerate(bins):
        if value < b:
            return i
    return len(bins)


def _color(value: float | None, bins: list[float], colors: list[str]) -> str:
    idx = _bucket(value, bins)
    return _NA_COLOR if idx is None else colors[idx]


def _fmt(x: object, nd: int = 2) -> str:
    try:
        f = float(x)
        return "—" if math.isnan(f) else f"{f:.{nd}f}"
    except (TypeError, ValueError):
        return "—"


def _range_labels(bins: list[float], nd: int = 2) -> list[str]:
    """경계 리스트 → 사람이 읽는 구간 라벨(버킷 수와 길이 동일)."""
    if not bins:
        return ["전체"]
    labels = [f"< {bins[0]:.{nd}f}"]
    labels += [f"{lo:.{nd}f} – {hi:.{nd}f}" for lo, hi in zip(bins, bins[1:])]
    labels.append(f"≥ {bins[-1]:.{nd}f}")
    return labels


def build_dashboard(
    risk: pd.DataFrame,
    geojson_path: str | Path,
    out_html: str | Path,
    name_prop: str = "name",
    *,
    period: str | None,
) -> Path:
    """상대위험 테이블 + 자치구 GeoJSON → folium HTML 대시보드 저장.

    `period` 는 배너·출처 표기에 쓰는 분석 기간 문자열(예: "2007~2025")이다.

    **하드코딩하지 말 것** — 분석 창을 바꿨는데 화면에 옛 기간이 찍히면 발표 산출물이
    거짓말을 하게 된다(실제로 2014~2023 이 박혀 있었다). 호출부가 데이터에서 파생해 넘긴다.

    **기본값 없는 키워드 전용 인자**인 이유: 기본값을 두었더니 기간을 빠뜨린 호출이
    조용히 '기간 없는 대시보드'를 만들어 커밋된 산출물을 덮어썼다(실제로 겪었다).
    하드코딩을 없앤 자리에 '조용한 누락'이 들어오면 남는 게 없으므로, 기간을 넣지 않을
    거면 `period=None` 을 명시하게 한다.
    """
    geo = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    idx: dict[tuple[str, str], dict] = {
        (row["구"], row["기상범주"]): row for _, row in risk.iterrows()
    }

    # 레이어별 분위수 경계/색상 — 맑음은 사고건수, 비·눈은 상대위험 기준
    scales: dict[str, dict] = {}
    for cat in RISK_CATEGORIES:
        sub = risk[risk["기상범주"] == cat]
        vmin = vmax = None
        if cat == BASELINE:
            bins = quantile_bins(sub["사고건수"].astype(float), anchor=math.inf)
            colors = _sample(_BLUE, len(bins) + 1)
            nd = 0
            n_valued = int(sub["사고건수"].notna().sum())
        else:
            rr = sub["상대위험"].astype(float).dropna()
            bins = quantile_bins(rr)
            # data_max 를 넘겨야 "전 구가 기준선 미만"인 레이어의 최상단 버킷이
            # 난색으로 잘못 칠해지지 않는다(위로 열린 버킷 문제).
            colors = bin_colors(bins, data_max=float(rr.max()) if len(rr) else None)
            nd = 2
            n_valued = int(len(rr))
            if len(rr):
                vmin, vmax = float(rr.min()), float(rr.max())
        scales[cat] = {
            "bins": bins,
            "colors": colors,
            "nd": nd,
            "small": int(sub["소표본경고"].sum()),
            "vmin": vmin,
            "vmax": vmax,
            "n": n_valued,          # RR이 유효한 구 수 — "전 구가 …" 문장의 분자
            "zones": int(len(sub)),  # 이 레이어의 전체 구 수 — 소표본 표기의 분모
        }

    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11, tiles="cartodbpositron")
    m.get_root().header.add_child(
        folium.Element("<title>서울 자치구 기상별 교통사고 위험</title>")
    )

    layer_names: dict[str, str] = {}
    for cat in RISK_CATEGORIES:
        is_clear = cat == BASELINE
        layer_name = CLEAR_LAYER_NAME if is_clear else f"{cat} (맑음 대비 상대위험)"
        layer_names[cat] = layer_name
        sc = scales[cat]

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

        def style_function(feature, _clear=is_clear, _sc=sc):
            p = feature["properties"]
            metric = p.get("_count") if _clear else p.get("_rr")
            return {
                "fillColor": _color(metric, _sc["bins"], _sc["colors"]),
                "color": "#666666",
                "weight": 1,
                # 소표본 구는 반투명 + 점선 테두리로 경고(맑음은 항상 안정)
                "fillOpacity": 0.35 if p.get("_small") else 0.78,
                "dashArray": "4,4" if p.get("_small") else None,
            }

        if is_clear:
            popup_fields = ["자치구", "기상", "사고건수", "노출시간", "사고율_시간당"]
            popup_aliases = ["자치구", "기상범주", "사고건수", "노출시간(ASOS)", "시간당 사고율"]
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
            popup=folium.GeoJsonPopup(fields=popup_fields, aliases=popup_aliases, localize=True),
            tooltip=tooltip,
        ).add_to(fg)
        fg.add_to(m)

    _add_gu_labels(m, geo, name_prop)
    folium.LayerControl(collapsed=False).add_to(m)
    _add_banner(m, period)
    _add_legends(m, scales, layer_names, period)
    # 저장 전에 호출한다 — 벤더 자산이 없으면 여기서 실패해 기존 산출물을 건드리지 않는다.
    _use_offline_assets(m)

    out = Path(out_html)
    out.parent.mkdir(parents=True, exist_ok=True)
    _save_atomic(m, out)
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
    fg = folium.FeatureGroup(name=LABEL_LAYER_NAME, show=True)
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


def _add_banner(m: folium.Map, period: str | None = None) -> None:
    """지도 상단 고정 배너: 제목 + 해석 주의 부제.

    배너가 leaflet 상단 컨트롤(좌:줌 / 우:레이어토글)을 가리지 않도록,
    상단 컨트롤을 배너 높이만큼 아래로 내리는 CSS를 함께 주입한다.
    타일 미로드(오프라인) 시에도 폴리곤이 또렷하도록 지도 배경색을 지정한다.
    """
    span = f"{period} " if period else ""
    html = (
        '<style>.leaflet-top{top:62px !important;}'
        '.leaflet-container{background:#f4f4f2;}</style>'
        '<div style="position:fixed;top:0;left:0;right:0;z-index:10000;'
        'background:rgba(33,37,41,.92);color:#fff;padding:8px 16px;'
        'font-family:sans-serif;box-shadow:0 1px 6px rgba(0,0,0,.3)">'
        '<div style="font-size:16px;font-weight:700">'
        '서울 자치구 기상별 교통사고 위험</div>'
        '<div style="font-size:11px;color:#cfd4da;margin-top:2px">'
        f'기준=맑음 · {span}사망·중상 · '
        '⚠구역 내부 기상 비교(시간층화)이며 구역 간 절대비교가 아님</div>'
        '</div>'
    )
    m.get_root().html.add_child(folium.Element(html))


def _legend_panel(
    cat: str, scale: dict, panel_id: str, visible: bool, period: str | None = None
) -> str:
    """한 레이어의 범례 패널 HTML — 실제 분위수 경계값과 소표본 구 수를 표시."""
    period_note = f", {period}" if period else ""
    swatches = "".join(
        f'<div style="display:flex;align-items:center;margin:1px 0">'
        f'<span style="background:{c};width:14px;height:14px;display:inline-block;'
        f'margin-right:6px;border:1px solid #999;flex:none"></span>'
        f'<span>{lab}</span></div>'
        for c, lab in zip(scale["colors"], _range_labels(scale["bins"], scale["nd"]))
    )

    if cat == BASELINE:
        head = "<b>맑음: 사고 <u>건수</u> (위험도 아님)</b>"
        note = ('<div style="color:#555;margin:2px 0 4px">'
                '기준선 레이어 — RR=1.0이라 위험 색칠이 무정보라 사고 규모를 대신 표시'
                '<br>구간 = 사고건수 분위수 5단계</div>')
        extra = (
            '<div style="margin-top:6px;color:#a00">⚠ 이 레이어만 <b>노출시간으로 보정되지 '
            '않은 원건수</b>입니다. 통행량·인구가 많은 구가 당연히 짙게 나오므로 '
            '<b>구 간 위험 비교로 읽으면 안 됩니다.</b> 위험 비교는 비/눈 레이어의 RR로 하세요.</div>'
        )
    else:
        head = f"<b>{cat}: 맑음 대비 상대위험(RR)</b>"
        # 분포 모양이 세 가지라 문구도 세 가지다. 두 가지로만 나누면 "전 구가 기준선
        # 한쪽에 몰린" 경우를 한 문장이 떠맡아, 반대쪽 꼬리(전 구가 맑음보다 안전)에서
        # 방향이 정반대인 거짓 진술이 된다. 구 수도 데이터에서 가져온다(하드코딩 금지).
        n_zones, vmin, vmax = scale["n"], scale["vmin"], scale["vmax"]
        if any(abs(b - 1.0) < 1e-9 for b in scale["bins"]):
            baseline_note = '구간 = 이 레이어 RR 분위수 (1.00 = 기준선 경계)'
        elif vmax is not None and vmax < 1.0:
            baseline_note = (
                '구간 = 이 레이어 RR 분위수'
                f'<br><b>이 레이어는 {n_zones}개 구 모두 RR &lt; 1.00</b> — 전 구가 맑음보다 안전'
            )
        elif vmin is not None and vmin >= 1.0:
            baseline_note = (
                '구간 = 이 레이어 RR 분위수'
                f'<br><b>이 레이어는 {n_zones}개 구 모두 RR ≥ 1.00</b> — 전 구가 맑음보다 위험'
            )
        else:
            baseline_note = '구간 = 이 레이어 RR 분위수'
        note = ('<div style="color:#555;margin:2px 0 4px">'
                'RR = 맑을 때 대비 사고위험 배수 (1=같음, 2=2배)'
                f'<br>{baseline_note}</div>')
        extra = (
            f'<div style="margin-top:6px;color:#666">'
            f'점선/반투명 = 소표본·불안정 — 이 레이어 '
            f'<b>{scale["small"]}/{scale["zones"]}개 구</b> '
            f'(사고건수&lt;10 또는 CI 과대)</div>'
            '<div style="margin-top:4px;color:#666">⚠ 색 구간은 <b>레이어마다 따로</b> '
            '계산됩니다 — 같은 색이라도 레이어가 다르면 RR이 다릅니다. '
            '레이어 간 비교는 색이 아니라 숫자로 하세요.</div>'
        )
        if cat == "눈":
            extra += (
                '<div style="margin-top:4px;color:#a00">⚠ 눈은 사고 표본(경찰 라벨)과 '
                '노출시간(ASOS) 분류 기준이 달라 RR이 상향 편향될 수 있고, 표시된 CI는 '
                '분류 불확실성을 반영하지 않습니다(실제 불확실성은 더 큼).</div>'
            )

    return (
        f'<div id="{panel_id}" class="wcr-legend" style="display:{"block" if visible else "none"};'
        'position:fixed;bottom:24px;left:24px;z-index:9999;background:white;'
        'padding:10px 12px;border:1px solid #999;border-radius:6px;font-size:12px;'
        'font-family:sans-serif;box-shadow:0 1px 4px rgba(0,0,0,.2);max-width:250px">'
        f'{head}{note}{swatches}{extra}'
        '<div style="margin-top:6px;padding-top:6px;border-top:1px solid #ddd;color:#888;'
        f'font-size:11px">출처: 도로교통공단 TAAS(사고) · 기상청 ASOS(기상){period_note}</div>'
        '</div>'
    )


class _LegendSwitcher(MacroElement):
    """레이어 전환(overlayadd)에 맞춰 범례 패널을 교체하는 스크립트.

    MacroElement로 감싸는 이유: `Figure.script` 에 직접 붙이면 folium이 지도를 생성하는
    코드보다 **먼저** 렌더되어 `map_xxx` 가 undefined 인 상태로 실행된다. MacroElement를
    지도의 자식으로 추가하면 지도 초기화 이후에 렌더되어 안전하다.
    """

    _template = Template("""
        {% macro script(this, kwargs) %}
            (function () {
                var panels = {{ this.panels_json }};
                // 켜져 있는 기상 레이어 스택 — 마지막에 켠 것의 범례를 보여준다.
                // overlayremove 도 처리해야 레이어를 끈 뒤에도 그 범례가 남는 모순이 없다.
                var active = [{{ this.default_json }}];
                function render() {
                    var current = active.length ? active[active.length - 1] : null;
                    Object.keys(panels).forEach(function (k) {
                        var el = document.getElementById(panels[k]);
                        if (el) el.style.display = (k === current) ? "block" : "none";
                    });
                }
                function drop(name) {
                    active = active.filter(function (n) { return n !== name; });
                }
                var map = {{ this._parent.get_name() }};
                map.on("overlayadd", function (e) {
                    if (!(e.name in panels)) return;   // '구 이름' 등 무관한 오버레이는 무시
                    drop(e.name); active.push(e.name); render();
                });
                map.on("overlayremove", function (e) {
                    if (!(e.name in panels)) return;
                    drop(e.name); render();
                });
                render();
            })();
        {% endmacro %}
    """)

    def __init__(self, panels: dict[str, str], default_name: str) -> None:
        super().__init__()
        self._name = "LegendSwitcher"
        self.panels_json = json.dumps(panels, ensure_ascii=False)
        self.default_json = json.dumps(default_name, ensure_ascii=False)


def _add_legends(
    m: folium.Map, scales: dict, layer_names: dict[str, str], period: str | None = None
) -> None:
    """레이어별 범례 패널 + 레이어 전환 시 패널을 바꾸는 스크립트를 주입."""
    panels = {layer_names[c]: f"wcr-legend-{i}" for i, c in enumerate(RISK_CATEGORIES)}

    for i, cat in enumerate(RISK_CATEGORIES):
        m.get_root().html.add_child(
            folium.Element(
                _legend_panel(
                    cat, scales[cat], f"wcr-legend-{i}",
                    visible=(cat == DEFAULT_LAYER), period=period,
                )
            )
        )

    _LegendSwitcher(panels, layer_names[DEFAULT_LAYER]).add_to(m)


def _vendored_leaflet_css() -> str:
    """벤더링된 leaflet.css — 참조 이미지를 data URI로 치환해 요청을 없앤다."""
    css = (_VENDOR / "leaflet.css").read_text(encoding="utf-8")
    for img in ("layers-2x.png", "layers.png"):
        b64 = base64.b64encode((_VENDOR / "images" / img).read_bytes()).decode()
        css = css.replace(f"url(images/{img})", f"url(data:image/png;base64,{b64})")
    # 기본 마커 아이콘은 미사용(구 라벨은 DivIcon) → 1px 투명 GIF로 대체해 요청 제거
    return css.replace(
        "url(images/marker-icon.png)",
        "url(data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=)",
    )


def _use_offline_assets(m: folium.Map) -> None:
    """CDN 의존을 제거하고 Leaflet을 head에 인라인한다 (folium 지원 API 사용).

    folium은 leaflet 외에 jQuery·부트스트랩·아이콘 폰트도 링크하지만 이 대시보드는
    쓰지 않는다(사용 API는 L.map/geoJson/marker/divIcon/control뿐). `default_js`/
    `default_css` 를 비우면 folium이 애초에 CDN 태그를 만들지 않으므로, 저장된 HTML을
    정규식으로 도려내는 후처리가 필요 없다 — 그 방식은 folium이 새 자산을 추가하거나
    태그 형식을 바꾸면 조용히 무력화되고, 플러그인이 정말 필요로 하는 스크립트까지
    지워 빈 지도를 만들 수 있다.

    **반드시 `m.save()` 이전에 호출한다.** 벤더 파일이 없으면 여기서 예외가 나므로
    기존 산출물(오프라인 대시보드)을 덮어쓰지 않고 실패한다.
    """
    css, js = _vendored_leaflet_css(), (_VENDOR / "leaflet.js").read_text(encoding="utf-8")

    m.default_js = []
    m.default_css = []
    header = m.get_root().header
    header.add_child(folium.Element(f"<style>{css}</style>"), name="leaflet_css_inline")
    header.add_child(folium.Element(f"<script>{js}</script>"), name="leaflet_js_inline")


# 리소스를 로드하는 태그만 잡는다(<a href>는 저작자 표시 링크라 대상 아님).
# 작은따옴표 속성과 프로토콜 상대 URL(`//cdn/...`)도 외부 로드이므로 함께 잡는다.
_EXTERNAL_ASSET_RE = re.compile(r"""<(?:script|link)[^>]*\s(?:src|href)=["'](?:https?:)?//""")


def _save_atomic(m: folium.Map, out: Path) -> None:
    """임시 파일에 렌더한 뒤 검증에 통과해야 목적지를 교체한다.

    렌더 도중 실패하거나 외부 자산 참조가 남으면 기존 대시보드는 그대로 유지된다.
    (`docker compose up` 의 RUN_PIPELINE=1 경로에서 재생성이 실패해도 커밋된 오프라인
    산출물로 계속 서빙할 수 있어야 하기 때문.)
    """
    fd, tmp_name = tempfile.mkstemp(dir=str(out.parent), suffix=".html")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        m.save(str(tmp))
        html = tmp.read_text(encoding="utf-8")
        found = _EXTERNAL_ASSET_RE.findall(html)
        if found:
            raise RuntimeError(
                f"오프라인 보장 실패 — 외부 자산 참조가 {len(found)}건 남았습니다: {found[:3]}\n"
                "folium 판올림으로 새 CDN 자산이 추가됐을 수 있습니다. "
                "_use_offline_assets() 를 확인하세요."
            )
        # mkstemp 는 0600으로 만든다. os.replace 가 그 권한을 그대로 옮기므로 명시적으로
        # 읽기 권한을 준다 — 그러지 않으면 재생성한 계정 외에는 대시보드를 못 읽는다
        # (docker-compose 의 볼륨 마운트, 재생성/서빙 계정 분리, 공유 체크아웃에서 깨짐).
        os.chmod(tmp, 0o644)
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)
