"""구 × 기상범주 시간층화 상대위험(RR) 산출.

지표: 같은 구 안에서 "비/눈일 때 사고율"이 "맑을 때 사고율"의 몇 배인가.
    rate(구, 범주)  = 사고건수(구, 범주) / 노출시간(범주)     # 노출은 서울 전역 공통(ASOS 108)
    RR(구, 범주)    = rate(구, 범주) / rate(구, 맑음)          # 맑음 기준선 = 1

CI: 두 포아송률의 비에 대한 신뢰구간.
    기존에는 Katz 로그근사 ln(RR) ± 1.96·sqrt(1/n_범주 + 1/n_맑음)만 썼으나,
    이는 정규 대칭 근사라 사고건수가 작은 셀(눈: n≈4~34)에서 구간을 과신(너무 좁게)한다.
    개선: 각 범주 카운트에 **Byar 근사**(포아송 exact 구간의 닫힌형 세제곱근 근사)로
    비대칭 신뢰구간을 구한 뒤, 로그척도에서 **MOVER**(Method of Variance Estimates
    Recovery; Zou & Donner 2008)로 rate ratio 구간으로 결합한다.
      - 소표본 셀 → Byar 구간이 오른쪽으로 길어져 CI가 자연히 넓어진다(과신 보정).
      - 대표본 셀 → Byar이 대칭 정규로 수렴하고 MOVER가 곧 Katz 식이 되어 기존과 일치한다.
    특수함수(scipy)가 필요없어 math만으로 계산되며, 모든 셀을 같은 방법으로 일관 처리한다.
소표본(n<=1) 등 분자/기준이 0인 셀은 CI를 degenerate 처리하고 경고 플래그를 세운다.
"""
from __future__ import annotations

import math

import pandas as pd

RISK_CATEGORIES = ["맑음", "비", "눈"]
BASELINE = "맑음"
Z = 1.96

# 불안정(소표본) 판정 임계
MIN_STABLE_N = 10       # 카테고리 사고건수가 이 미만이면 포아송 추정 불안정
MAX_CI_RATIO = 3.0      # CI 상한/하한 배수가 이 초과면 사실상 정보량 부족


def _unstable(n: float, lo: float, hi: float) -> bool:
    """RR 셀이 불안정한가 — 소표본이거나 신뢰구간이 지나치게 넓은가."""
    if n < MIN_STABLE_N:
        return True
    if not (math.isnan(lo) or math.isnan(hi)) and lo > 0 and (hi / lo) > MAX_CI_RATIO:
        return True
    return False


def _byar_poisson_ci(n: float) -> tuple[float, float]:
    """관측 카운트 n(포아송)의 평균 μ에 대한 Byar 근사 신뢰구간 [하한, 상한].

    Byar(1978)의 세제곱근 정규근사 — 포아송 exact(Garwood) 구간에 매우 근접하며
    닫힌형이라 특수함수 없이 계산된다. 소표본에서 오른쪽으로 비대칭(상한이 더 김)이라
    Wald/Katz 대비 하한을 낮추고 상한을 높여 과신을 보정한다.
        L = n     · (1 - 1/(9n)     - Z/(3√n))³
        U = (n+1) · (1 - 1/(9(n+1)) + Z/(3√(n+1)))³
    """
    if n <= 0:
        return 0.0, 0.0
    lo = n * (1.0 - 1.0 / (9.0 * n) - Z / (3.0 * math.sqrt(n))) ** 3
    hi = (n + 1.0) * (1.0 - 1.0 / (9.0 * (n + 1.0)) + Z / (3.0 * math.sqrt(n + 1.0))) ** 3
    return max(lo, 0.0), hi


def _rate_ratio_ci(
    n_cat: float, exp_cat: float, n_base: float, exp_base: float
) -> tuple[float, float]:
    """rate ratio (범주/맑음)의 신뢰구간 — Byar 포아송 구간 + 로그척도 MOVER 결합.

    각 rate의 Byar 구간을 구한 뒤, ln RR = ln(rate_cat) - ln(rate_base) 를
    두 독립 구간의 차(MOVER)로 전파한다. 노출시간 T는 상수라 로그차에서 상쇄되지만
    명시적으로 유지한다. 대표본에서는 Katz(ln RR ± Z·sqrt(1/n_cat+1/n_base))로 수렴한다.
    호출부에서 n_cat>0, n_base>0, 두 노출>0을 보장한다(그래서 Byar 하한>0, log 안전).
    """
    r_cat = n_cat / exp_cat
    r_base = n_base / exp_base
    lc, uc = _byar_poisson_ci(n_cat)
    lb, ub = _byar_poisson_ci(n_base)

    x_cat, xl_cat, xu_cat = math.log(r_cat), math.log(lc / exp_cat), math.log(uc / exp_cat)
    x_base, xl_base, xu_base = math.log(r_base), math.log(lb / exp_base), math.log(ub / exp_base)

    d = x_cat - x_base
    lo = d - math.sqrt((x_cat - xl_cat) ** 2 + (xu_base - x_base) ** 2)
    hi = d + math.sqrt((xu_cat - x_cat) ** 2 + (x_base - xl_base) ** 2)
    return math.exp(lo), math.exp(hi)


def zone_weather_risk(
    counts: pd.DataFrame,
    exposure: pd.Series,
    baseline: str = BASELINE,
) -> pd.DataFrame:
    """구×기상범주 상대위험 테이블 산출.

    counts: [구, 기상범주, 사고건수] (src.analysis.accidents.zone_weather_counts)
    exposure: 기상범주 → 노출시간 (src.analysis.exposure.exposure_hours)
    """
    exp = {c: float(exposure.get(c, 0.0)) for c in RISK_CATEGORIES}

    mat = (
        counts[counts["기상범주"].isin(RISK_CATEGORIES)]
        .pivot_table(index="구", columns="기상범주", values="사고건수", aggfunc="sum", fill_value=0)
    )
    for c in RISK_CATEGORIES:
        if c not in mat.columns:
            mat[c] = 0

    rows = []
    for gu, r in mat.iterrows():
        base_n = float(r[baseline])
        base_rate = base_n / exp[baseline] if exp[baseline] > 0 else math.nan
        for cat in RISK_CATEGORIES:
            n = float(r[cat])
            exp_cat = exp[cat]
            rate = n / exp_cat if exp_cat > 0 else math.nan

            if cat == baseline:
                rr, lo, hi = 1.0, 1.0, 1.0
            elif base_n > 0 and n > 0 and exp_cat > 0 and exp[baseline] > 0:
                rr = rate / base_rate
                # Byar 근사 포아송 구간을 MOVER로 결합 → 소표본 셀 CI가 정직하게 넓어짐.
                lo, hi = _rate_ratio_ci(n, exp_cat, base_n, exp[baseline])
            else:
                # 분자 0 또는 기준 0 → RR 값은 두되 CI는 degenerate
                rr = (rate / base_rate) if (base_rate and not math.isnan(base_rate)) else math.nan
                lo, hi = math.nan, math.nan

            rows.append(
                {
                    "구": gu,
                    "기상범주": cat,
                    "사고건수": int(n),
                    "노출시간": int(exp_cat),
                    "사고율_시간당": rate,
                    "상대위험": rr,
                    "CI하한": lo,
                    "CI상한": hi,
                    # 불안정 셀: 카운트가 작거나(포아송 불안정) CI가 매우 넓을 때 경고.
                    # (n<=1만 보면 눈 n=4 셀도 '신뢰가능'처럼 보이는 문제를 보정)
                    "소표본경고": (cat != baseline) and _unstable(n, lo, hi),
                }
            )

    df = pd.DataFrame(rows)
    return df.sort_values(["구", "기상범주"]).reset_index(drop=True)


if __name__ == "__main__":
    # 최소 자기진단: 합성 카운트로 CI 방법이 동작하는지만 확인한다.
    # (실제 데이터 파이프라인 실행은 `python -m src.analysis.pipeline` 참조 — 중복 로직 제거)
    # 기대: 사고건수가 작은 '눈' 셀의 CI폭이 '비' 셀보다 넓어야 한다.
    demo_counts = pd.DataFrame(
        {
            "구": ["샘플구"] * 3,
            "기상범주": ["맑음", "비", "눈"],
            "사고건수": [1000, 200, 6],
        }
    )
    demo_exp = pd.Series({"맑음": 8000.0, "비": 700.0, "눈": 40.0})
    demo = zone_weather_risk(demo_counts, demo_exp)
    demo["CI폭"] = demo["CI상한"] - demo["CI하한"]
    print(demo.to_string(index=False))
