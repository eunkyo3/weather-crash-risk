"""src.analysis.dashboard 의 분위수 구간·색상 배정 테스트.

지도 렌더링은 검증하지 않는다. 여기서 고정하는 것은 "색이 실제로 갈리는가"와
"기준선(RR=1.0) 처리가 문서의 주장과 일치하는가" 두 가지다.
"""
from __future__ import annotations

import random

import pandas as pd
import pytest

from src.analysis.dashboard import (
    _EXTERNAL_ASSET_RE,
    _COOL,
    _MAX_BUCKETS,
    _WARM,
    _bucket,
    _legend_panel,
    _range_labels,
    _sample,
    bin_colors,
    quantile_bins,
)


def _scale(values: list[float], small: int = 0) -> dict:
    """_legend_panel 에 넘길 스케일 dict 를 실제 분포에서 만든다."""
    s = pd.Series(values, dtype=float)
    bins = quantile_bins(s)
    return {
        "bins": bins,
        "colors": bin_colors(bins, data_max=float(s.max())),
        "nd": 2,
        "small": small,
        "vmin": float(s.min()),
        "vmax": float(s.max()),
        "n": len(s),
        "zones": len(s),
    }


def test_anchor_included_when_baseline_inside_distribution():
    # 눈 레이어처럼 1.0 위아래가 모두 있으면 기준선이 구간 경계가 된다
    values = pd.Series([0.75, 0.9, 1.2, 1.9, 2.5, 3.8])
    assert 1.0 in quantile_bins(values)


def test_anchor_omitted_when_all_values_at_or_above_baseline():
    """비 레이어(전 구 RR>=1.0)에서는 1.0을 경계로 넣지 않는다.

    넣으면 아무 구도 속하지 않는 빈 구간이 생기고, 범례가 "1.00 = 기준선 경계"라고
    주장하게 되어 사용자에게 거짓이 된다. 범례는 대신 "전 구 RR>=1.00" 문장을 쓴다.
    """
    values = pd.Series([1.0021, 1.11, 1.17, 1.23, 1.28, 1.3928])
    assert 1.0 not in quantile_bins(values)


def test_bin_colors_length_matches_bucket_count():
    bins = [1.115, 1.165, 1.233, 1.281]
    assert len(bin_colors(bins)) == len(bins) + 1


def test_bin_colors_split_cool_below_and_warm_above_baseline():
    bins = [0.8, 1.0, 1.5]  # 버킷: <0.8, 0.8~1.0, 1.0~1.5, >=1.5
    colors = bin_colors(bins)
    assert colors[0] in _COOL and colors[1] in _COOL   # 1.0 미만 → 한색
    assert colors[2] in _WARM and colors[3] in _WARM   # 1.0 이상 → 난색


def test_all_protective_layer_is_entirely_cool():
    """전 구가 RR<1.0(맑을 때보다 안전)이면 최상단 구간까지 한색이어야 한다.

    최상단 버킷은 위로 열려 있어 경계만 보면 '기준선 이상'으로 오판된다. data_max를
    넘기지 않으면 안전한 구가 위험색(난색)으로 칠해진다 — 방향이 정반대인 표시다.
    """
    bins = [0.418, 0.534, 0.595, 0.671]      # 전 경계가 1.0 미만
    naive = bin_colors(bins)                  # data_max 없음 → 최상단이 난색(옛 버그)
    assert naive[-1] in _WARM

    fixed = bin_colors(bins, data_max=0.749)  # 실제 최대값도 1.0 미만
    assert all(c in _COOL for c in fixed), f"안전 레이어에 난색 혼입: {fixed}"


def test_color_direction_never_contradicts_value():
    """무작위 분포 전수 점검 — 값과 색의 방향이 어긋나는 셀이 하나도 없어야 한다."""
    rng = random.Random(20260721)
    violations = []
    for _ in range(2000):
        lo, hi = rng.choice([(0.1, 0.99), (1.0, 3.0), (0.2, 5.0), (0.95, 1.05)])
        vals = [rng.uniform(lo, hi) for _ in range(25)]
        s = pd.Series(vals)
        bins = quantile_bins(s)
        colors = bin_colors(bins, data_max=float(s.max()))
        for v in vals:
            idx = _bucket(v, bins)
            color = colors[idx]
            if v < 1.0 and color in _WARM:
                violations.append((round(v, 3), color, bins))
            if v >= 1.0 and color in _COOL:
                violations.append((round(v, 3), color, bins))
    assert not violations, f"{len(violations)}건 방향 위반, 예: {violations[:2]}"


def test_bin_colors_are_distinct_at_max_bucket_count():
    """인접 구간이 같은 색으로 뭉개지지 않아야 한다(램프 길이 부족 회귀 방지)."""
    bins = [0.6, 0.75, 0.9, 1.0, 1.4]  # 경계 5개 → 버킷 6개 = 최대치
    colors = bin_colors(bins)
    assert len(colors) == len(bins) + 1 == _MAX_BUCKETS
    assert len(set(colors)) == len(colors), f"색상 중복: {colors}"


def test_sample_raises_instead_of_silently_reusing_colors():
    with pytest.raises(ValueError, match="색상 램프가 부족"):
        _sample(["#111111", "#222222"], 3)


def test_single_bucket_uses_mid_ramp_not_the_palest_end():
    """구간이 하나뿐인 레이어가 거의 흰색으로 칠해지면 무데이터와 구분되지 않는다.

    눈 레이어의 RR<1.0 버킷이 실제로 이 경로를 탄다(강북·서대문·종로 3개 구).
    """
    assert _sample(_COOL, 1) == [_COOL[len(_COOL) // 2]]
    assert _sample(_COOL, 1) != [_COOL[-1]]   # 가장 옅은 끝이 아니어야
    assert _sample(_WARM, 1) != [_WARM[-1]]   # 가장 진한 빨강도 아니어야(위험 과장 방지)


def test_cool_ramp_stays_distinguishable_from_na_and_background():
    """한색 램프는 무채색(무데이터 #cccccc, 배경 #f4f4f2)과 구분되어야 한다.

    판정 기준은 밝기가 아니라 **채도**다 — #abd9e9 는 #cccccc 와 밝기가 비슷해도 뚜렷한
    파랑이라 구분되지만, 이전에 잘못 넣었던 #d1e5f0(채도 31)은 회색빛이라 구분되지 않았다.
    """
    def chroma(hex_color: str) -> int:
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        return max(r, g, b) - min(r, g, b)

    assert chroma("#cccccc") == 0            # 무데이터색은 완전 무채색
    for color in _COOL:
        assert chroma(color) >= 40, f"{color} 는 채도 {chroma(color)} 로 회색과 혼동된다"
    assert chroma("#d1e5f0") < 40            # 회귀 방지: 이 색은 다시 넣으면 안 된다


def test_range_labels_align_with_buckets():
    bins = [1.1, 1.2, 1.3]
    labels = _range_labels(bins)
    assert len(labels) == len(bins) + 1
    assert labels[0].startswith("<") and labels[-1].startswith("≥")


@pytest.mark.parametrize(
    "values",
    [
        [1.0] * 25,                          # 전부 동일
        [0.5] * 25,                          # 전부 기준선 미만, 동일
        [2.0] * 25,                          # 전부 기준선 초과, 동일
        list(range(1, 26)),                  # 전부 기준선 이상, 넓게 분포
        [i / 100 for i in range(1, 26)],     # 전부 기준선 미만
        [0.99] * 12 + [1.01] * 13,           # 기준선 바로 아래/위로 양분
        [0.1, 0.2, 0.3, 0.4, 1.0] + [5.0] * 20,
    ],
)
def test_color_ramps_cover_every_reachable_bucket_layout(values):
    """도달 가능한 어떤 분포에서도 램프가 모자라 예외가 나지 않아야 한다.

    한쪽 램프가 감당할 최대 버킷은 5개다(경계 최대 5개 → 버킷 6개인데, 그 경우는
    기준선이 경계에 포함된 때뿐이라 한색·난색으로 갈린다). _sample 의 ValueError 는
    N_BINS 를 늘렸을 때만 울리는 안전장치로 남는다.
    """
    bins = quantile_bins(pd.Series(values, dtype=float))
    colors = bin_colors(bins)  # 램프 부족이면 여기서 ValueError
    assert len(colors) == len(bins) + 1
    below = sum(1 for b in bins if b <= 1.0)
    assert below <= len(_COOL)
    assert (len(bins) + 1 - below) <= len(_WARM)


def test_quantile_bins_handles_empty_and_nan():
    assert quantile_bins(pd.Series([], dtype=float)) == []
    assert quantile_bins(pd.Series([float("nan"), float("nan")])) == []


def test_external_asset_regex_detects_cdn_tags_but_not_anchor_links():
    """오프라인 보장을 지키는 정규식 — 리소스 태그만 잡고 저작자표시 링크는 무시.

    folium이 판올림되며 쓸 수 있는 회피 형태(작은따옴표, 프로토콜 상대 URL)까지 덮는다.
    """
    assert _EXTERNAL_ASSET_RE.search('<script src="https://cdn.example/leaflet.js"></script>')
    assert _EXTERNAL_ASSET_RE.search('<link rel="stylesheet" href="http://cdn.example/a.css"/>')
    assert _EXTERNAL_ASSET_RE.search("<script src='https://cdn.example/x.js'></script>")
    assert _EXTERNAL_ASSET_RE.search('<script src="//cdn.example/x.js"></script>')
    assert _EXTERNAL_ASSET_RE.search("<link href='//cdn.example/a.css' rel='stylesheet'>")
    # 로드가 아닌 것들
    assert not _EXTERNAL_ASSET_RE.search('<a href="https://leafletjs.com">Leaflet</a>')
    assert not _EXTERNAL_ASSET_RE.search('<script>var t="https://tile/{z}.png";</script>')


# --- _legend_panel: M2/R1 이 살았던 자리. 세 가지 분포 모양을 모두 덮는다 ---

def test_legend_says_baseline_boundary_when_distribution_straddles_one():
    panel = _legend_panel("비", _scale([0.7, 0.9, 1.1, 1.4, 2.0]), "p", visible=True)
    assert "1.00 = 기준선 경계" in panel


def test_legend_says_all_dangerous_when_every_zone_at_or_above_one():
    panel = _legend_panel("비", _scale([1.0021, 1.11, 1.17, 1.23, 1.3928]), "p", visible=True)
    assert "모두 RR ≥ 1.00" in panel
    assert "전 구가 맑음보다 위험" in panel
    assert "전 구가 맑음보다 안전" not in panel


def test_legend_says_all_safe_when_every_zone_below_one():
    """R1 회귀 방지 — 전 구가 안전한데 '전 구가 맑음보다 위험'이라 말하면 안 된다.

    이 방향 오류는 `pedestrian_only=True`(결정로그가 명시한 다음 단계)에서 실제로
    도달 가능하다 — 비 오는 날 보행자 통행이 줄면 보행자 RR이 1.0 아래로 갈 수 있다.
    """
    panel = _legend_panel("비", _scale([0.55, 0.7, 0.85, 0.95, 0.99]), "p", visible=True)
    assert "모두 RR &lt; 1.00" in panel
    assert "전 구가 맑음보다 안전" in panel
    assert "전 구가 맑음보다 위험" not in panel


def test_legend_zone_count_comes_from_data_not_hardcoded():
    """구 수는 두 군데 나온다 — 'N개 구 모두'와 소표본 'k/N개 구'. 둘 다 데이터 기준이어야
    한다. 하나만 고치면 같은 범례가 '3개 구 모두 …' 옆에 '1/25개 구'를 띄워 자기모순이 된다.
    """
    panel = _legend_panel("비", _scale([1.1, 1.2, 1.3], small=1), "p", visible=True)
    assert "3개 구 모두" in panel
    assert "1/3개 구" in panel
    # 구 수가 나오는 두 자리 어디에도 25가 박혀 있으면 안 된다
    # ("25" 단독 검사는 CSS 의 max-width:250px 에 걸리므로 문맥까지 붙여 확인)
    assert "25개 구 모두" not in panel
    assert "/25개 구" not in panel


def test_baseline_layer_legend_warns_it_is_not_a_risk_comparison():
    scale = {"bins": [10.0, 20.0], "colors": ["#eff3ff", "#9ecae1", "#08519c"],
             "nd": 0, "small": 0, "vmin": None, "vmax": None, "n": 25, "zones": 25}
    panel = _legend_panel("맑음", scale, "p", visible=False)
    assert "위험 비교로 읽으면 안 됩니다" in panel


def test_snow_legend_keeps_bias_warning_and_small_sample_count():
    # 실데이터와 같은 모양: 25개 구, 그중 16개가 소표본 경고
    snow_rr = [0.75, 0.8, 0.97] + [1.0 + i * 0.18 for i in range(22)]
    panel = _legend_panel("눈", _scale(snow_rr, small=16), "p", visible=True)
    assert "16/25개 구" in panel
    assert "상향 편향" in panel
    assert "레이어마다 따로" in panel   # 레이어 간 색 비교 경고
