"""노면상태 × 기상상태 교차검증 (#12).

TAAS 사고 기록은 `기상상태`와 `노면상태`를 각각 별도로 입력받는다. 두 값은 인과관계가
있어야 하지만(비 → 습기, 눈 → 적설/결빙) 실제로는 경찰 현장 기록이라 라벨이 어긋나는
경우가 있다("비"인데 노면 "건조" 등). 이 모듈은 그 불일치 비율을 정량화해
methodology의 "기상 출처 이원화"(사고=TAAS 기상상태, 노출=ASOS) 한계를 뒷받침하는
보조 진단 자료로 쓴다.

읽기전용 진단: 파이프라인/산출물을 변경하지 않는다.

사용:
    from src.analysis.surface_check import surface_weather_crosstab, label_consistency
    df = load_accidents("data/raw/accidents")
    surface_weather_crosstab(df)
"""
from __future__ import annotations

import pandas as pd

from src.analysis.accidents import load_accidents

# 기상범주별로 "정상적으로 기대되는" 노면상태 집합.
# 맑음(비강수 포함)이면 건조가 기본, 비면 습기, 눈이면 적설/결빙이 기대값.
# TAAS는 2017년경 노면상태 라벨을 개편(습기→젖음/습기, 결빙→서리/결빙)했으므로
# 신구 라벨을 모두 동의어로 취급한다. 침수/해빙은 표본이 극소(전체 5건)이나
# 각각 강우·적설과 인과적으로 연결되는 라벨이라 기대값에 포함한다.
# 기타(안개 등)는 기대 노면이 불분명해 진단 대상에서 제외.
_EXPECTED_SURFACE = {
    "맑음": {"건조"},
    "비": {"습기", "젖음/습기", "침수"},
    "눈": {"적설", "결빙", "서리/결빙", "해빙"},
}


def surface_weather_crosstab(df: pd.DataFrame) -> pd.DataFrame:
    """기상범주 × 노면상태 교차표(건수)."""
    return pd.crosstab(df["기상범주"], df["노면상태"])


def label_consistency(df: pd.DataFrame) -> dict:
    """기상범주별 "예상 노면과 불일치" 건수·비율.

    비/눈 범주는 노면 "건조" 비율도 함께 보고한다(전형적 불일치 패턴:
    "비"인데 노면 "건조", "눈"인데 노면 "건조").
    """
    result: dict = {}
    for category, expected in _EXPECTED_SURFACE.items():
        sub = df[df["기상범주"] == category]
        n = len(sub)
        if n == 0:
            continue
        mismatch = sub[~sub["노면상태"].isin(expected)]
        entry = {
            "건수": n,
            "불일치_건수": len(mismatch),
            "불일치_비율": len(mismatch) / n,
        }
        if category in ("비", "눈"):
            dry = sub[sub["노면상태"] == "건조"]
            entry["건조_건수"] = len(dry)
            entry["건조_비율"] = len(dry) / n
        result[category] = entry
    return result


if __name__ == "__main__":
    import sys

    src = sys.argv[1] if len(sys.argv) > 1 else "data/raw/accidents"
    df = load_accidents(src)

    print(f"[로드] {src}  →  {len(df):,}건")

    print("\n[기상범주 × 노면상태 교차표]")
    crosstab = surface_weather_crosstab(df)
    print(crosstab.to_string())

    print("\n[라벨 불일치 진단]")
    consistency = label_consistency(df)
    for category, stats in consistency.items():
        line = (
            f"  {category}: {stats['건수']:,}건 중 예상 노면 불일치 "
            f"{stats['불일치_건수']:,}건 ({stats['불일치_비율']:.1%})"
        )
        if "건조_비율" in stats:
            line += f" — 건조 기록 {stats['건조_건수']:,}건 ({stats['건조_비율']:.1%})"
        print(line)
