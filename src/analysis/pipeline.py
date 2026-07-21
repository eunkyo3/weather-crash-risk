"""전체 분석 파이프라인: 사고+노출 → 상대위험 → 대시보드 → 자동검증.

실행:
    python -m src.analysis.pipeline
산출물:
    data/processed/zone_weather_risk.csv   구×기상 상대위험 테이블
    outputs/dashboard.html                 자치구 choropleth + 기상필터 토글
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

from src.analysis.accidents import load_accidents, zone_weather_counts
from src.analysis.dashboard import build_dashboard
from src.analysis.exposure import exposure_hours, load_weather, weather_coverage
from src.analysis.risk import RISK_CATEGORIES, Z, zone_weather_risk

MIN_COVERAGE_RATIO = 0.8  # 기대 관측시간 대비 이 미만이면 커버리지 경고(#7)

ROOT = Path(__file__).resolve().parents[2]
ACC_DIR = ROOT / "data" / "raw" / "accidents"
WX_DIR = ROOT / "data" / "raw" / "weather"
GEOJSON = ROOT / "data" / "raw" / "boundaries" / "seoul_gu.geojson"
RISK_CSV = ROOT / "data" / "processed" / "zone_weather_risk.csv"
DASHBOARD = ROOT / "outputs" / "dashboard.html"

# Windows 콘솔(cp949) 등에서 한글·em-dash 출력 시 UnicodeEncodeError 방지
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


def run() -> pd.DataFrame:
    acc = load_accidents(ACC_DIR)
    wx = load_weather(WX_DIR)

    cov = weather_coverage(wx)
    print(
        f"[ASOS 커버리지] {len(cov['months'])}개월 관측 "
        f"({cov['start']:%Y-%m-%d %H:%M} ~ {cov['end']:%Y-%m-%d %H:%M})"
    )
    print(
        f"   관측시간 {cov['observed_hours']:,} / 기대시간(관측기간 기준) {cov['expected_hours']:,} "
        f"({cov['coverage_ratio'] * 100:.1f}%)"
    )
    if cov["coverage_ratio"] < MIN_COVERAGE_RATIO:
        print(
            f"[경고] ASOS 노출시간이 기대치의 {MIN_COVERAGE_RATIO * 100:.0f}% 미만입니다 "
            "— 원본 파일 누락/결측 가능성을 확인하세요"
        )

    exp = exposure_hours(wx)

    print(f"[사고] {len(acc):,}건 / [노출] {int(exp.sum()):,}시간")
    for c in RISK_CATEGORIES:
        print(f"   {c}: 노출 {int(exp.get(c, 0)):,}h")

    risk = zone_weather_risk(zone_weather_counts(acc), exp)
    RISK_CSV.parent.mkdir(parents=True, exist_ok=True)
    risk.to_csv(RISK_CSV, index=False, encoding="utf-8-sig")
    print(f"[저장] {RISK_CSV}")

    build_dashboard(risk, GEOJSON, DASHBOARD)
    print(f"[저장] {DASHBOARD}")

    verify(risk)
    return risk


def _norm_sf(z: float) -> float:
    """표준정규 생존함수 P(Z>z). scipy 미의존(stdlib math.erfc만 사용)."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def _bh_significant_elevated_gu(cand: pd.DataFrame, alpha: float = 0.05) -> int:
    """Benjamini-Hochberg(FDR) 보정 후에도 유의하게 위험 상승(RR>1)인 구 수(#4).

    risk.py가 산출한 로그척도 CI(상대위험, CI하한, CI상한)에서 표준오차를 근사
    역산해 양측 p-value를 구하고, cand의 모든 비교(구×범주)를 모집단으로 BH
    절차를 적용한다. risk.py의 CI는 Byar+MOVER 비대칭이지만, 유의에 도달하는
    셀은 표본이 커 CI가 거의 대칭이므로 se≈log(hi/lo)/(2Z) 근사가 타당하다
    (소표본·비대칭 셀은 애초에 유의판정에 도달하지 않는다). 다중비교
    (25구×2범주=50회) 미보정을 완화하는 탐색적 보정이며, risk.py의 CI 계산
    방식 자체는 바꾸지 않는다.
    """
    pvals = []
    rows = []
    for _, r in cand.iterrows():
        rr, lo, hi = r["상대위험"], r["CI하한"], r["CI상한"]
        if any(math.isnan(v) for v in (rr, lo, hi)) or rr <= 0 or lo <= 0:
            continue
        se = math.log(hi / lo) / (2 * Z)
        if se <= 0:
            continue
        z_stat = math.log(rr) / se
        pvals.append(2 * _norm_sf(abs(z_stat)))
        rows.append(r)

    m = len(pvals)
    if m == 0:
        return 0

    order = sorted(range(m), key=lambda i: pvals[i])
    max_rank = 0
    for rank, i in enumerate(order, start=1):
        if pvals[i] <= (rank / m) * alpha:
            max_rank = rank

    significant_gu = {
        rows[i]["구"] for i in order[:max_rank] if rows[i]["상대위험"] > 1.0
    }
    return len(significant_gu)


def verify(risk: pd.DataFrame, min_distinct_gu: int = 3) -> None:
    """AC7 자동검증: 기상 전환 시 구별 상대위험이 실제로 달라지는가."""
    problems = []

    # 1) 각 범주 레이어가 비어있지 않은지(색칠 가능 구 수)
    for cat in RISK_CATEGORIES:
        sub = risk[(risk["기상범주"] == cat) & (risk["사고건수"] > 0)]
        if len(sub) < min_distinct_gu:
            problems.append(f"{cat} 범주 색칠가능 구 {len(sub)}개 < {min_distinct_gu}")

    # 2) 비 vs 눈 상대위험이 최소 K개 구에서 값이 다른가 (NaN은 상이로 세지 않음)
    piv = risk.pivot_table(index="구", columns="기상범주", values="상대위험")
    if {"비", "눈"}.issubset(piv.columns):
        both = piv[["비", "눈"]].dropna()
        diff = int((both["비"].round(3) != both["눈"].round(3)).sum())
        if diff < min_distinct_gu:
            problems.append(f"비 vs 눈 RR 상이 구 {diff}개 < {min_distinct_gu}")
        print(f"[검증] 비 vs 눈 상대위험 상이 구: {diff}개")

    # 3) 위험이 "실제로" 상승했는가 — 비/눈 CI하한 > 1.0(맑음보다 유의하게 위험)인 구 수
    #    주의(#4): 이 판정은 25구×2범주=50회 비교다. 다중비교 미보정 상태이므로
    #    아래 카운트는 탐색적 분석 참고용이며, 통과 조건도 그 전제로 유지한다.
    #    같은 후보 집합에 대해 BH(FDR) 보정치도 함께 출력해 참고할 수 있게 한다.
    cand = risk[risk["기상범주"].isin(["비", "눈"])]
    elevated = cand[cand["CI하한"] > 1.0]["구"].nunique()
    print(
        f"[검증] 맑음보다 유의하게 위험 상승한 구(CI하한>1, 다중비교 미보정·참고용): {elevated}개"
    )
    if elevated < min_distinct_gu:
        problems.append(f"유의 상승 구 {elevated}개 < {min_distinct_gu}")

    elevated_fdr = _bh_significant_elevated_gu(cand)
    print(f"[검증] BH(FDR) 보정 후에도 유의한 위험 상승 구(q<0.05): {elevated_fdr}개")

    # 4) 산출물 존재
    for p in (RISK_CSV, DASHBOARD, GEOJSON):
        if not Path(p).exists():
            problems.append(f"산출물 없음: {p}")

    if problems:
        print("[검증 실패]")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)
    print("[검증 통과] AC7 충족 — 기상 전환 시 위험 분포가 실제로 달라짐")


if __name__ == "__main__":
    sys.exit(0 if run() is not None else 1)
