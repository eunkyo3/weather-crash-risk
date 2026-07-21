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

from src.analysis.accidents import accident_months, load_accidents, zone_weather_counts
from src.analysis.dashboard import build_dashboard
from src.analysis.exposure import (
    exposure_hours,
    load_weather,
    short_months,
    weather_coverage,
)
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


def _month_seq(start: str, end: str) -> list[str]:
    """`YYYY-MM` 두 값 사이의 모든 달(양끝 포함). 연말→연초 넘어감을 처리한다."""
    y, m = int(start[:4]), int(start[5:7])
    y1, m1 = int(end[:4]), int(end[5:7])
    out: list[str] = []
    while (y, m) <= (y1, m1):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def period_alignment(acc_months: list[str], exp_months: list[str]) -> dict:
    """분자(사고)와 분모(노출)의 기간이 어긋난 달을 찾는다.

    상대위험은 `사고건수 ÷ 노출시간` 이라 두 기간이 다르면 **에러 없이 틀린 값**이 나온다.
    사고율(시간당)은 곧바로 왜곡되고, RR도 두 기간의 기상 구성이 다른 만큼 편향된다.
    `exposure.load_weather()` 는 디렉토리의 모든 파일을 읽을 뿐 기간 필터가 없으므로,
    파일 구성이 곧 분모 기간이 된다 — 그래서 로드 직후 여기서 검사한다.

    기준은 사고의 **구간**(최초~최종 발생월)이지 사고가 실제로 있는 달의 집합이 아니다.
    사고 0건인 달도 노출시간은 분모에 정당하게 들어가야 하기 때문이다 — 정확집합을 쓰면
    그 달의 ASOS가 '과대'로 찍혀 삭제를 유도하고, 그러면 사고율이 위로 편향된다.

    반환:
        required — 사고 기간을 채우는 데 필요한 달 전체
        missing  — 그중 ASOS가 없는 달 (분모 결손 → 사고율 과대)
        unused   — 사고 기간 밖인데 ASOS만 있는 달 (분모 과대 → 사고율 과소)
        acc_gaps — 구간 안인데 사고가 한 건도 없는 달. 구간 기준 판정의 사각지대를
                   드러내기 위한 것 — 사고 파일을 통째로 빠뜨리면(예: 연도 하나 누락)
                   구간이 줄지 않아 missing/unused 로는 잡히지 않는다.
    """
    acc = sorted(set(acc_months))
    exp = set(exp_months)
    if not acc:
        return {"required": [], "missing": [], "unused": sorted(exp), "acc_gaps": []}
    required = _month_seq(acc[0], acc[-1])
    return {
        "required": required,
        "missing": sorted(set(required) - exp),
        "unused": sorted(exp - set(required)),
        "acc_gaps": sorted(set(required) - set(acc)),
    }


def _fmt_months(months: list[str], limit: int = 6) -> str:
    head = ", ".join(months[:limit])
    return head + (f" … 외 {len(months) - limit}개" if len(months) > limit else "")


def check_period_alignment(acc_months: list[str], exp_months: list[str]) -> dict:
    """기간 정합성을 검사하고, 어긋나면 분석을 진행하지 않고 중단한다."""
    align = period_alignment(acc_months, exp_months)
    missing, unused, gaps = align["missing"], align["unused"], align["acc_gaps"]

    acc_sorted = sorted(acc_months)
    acc_span = f"{acc_sorted[0]} ~ {acc_sorted[-1]}" if acc_sorted else "(없음)"
    exp_span = f"{min(exp_months)} ~ {max(exp_months)}" if exp_months else "(없음)"
    print(f"[기간] 사고 {acc_span} ({len(align['required'])}개월) / ASOS {exp_span} ({len(exp_months)}개월)")

    # 사고 구간 내부 공백은 중단 사유가 아니다(0건인 달은 통계적으로 정상). 다만 서울 25개
    # 자치구 사망+중상은 월 수백 건 규모라, 사고 0건인 달은 사실상 파일 결손 신호다.
    if gaps:
        print(
            f"[경고] 사고 구간 안에 사고가 0건인 달이 {len(gaps)}개 있습니다 "
            f"— 사고 파일 누락 가능성: {_fmt_months(gaps)}\n"
            "        (구간 기준 판정이라 이 경우 분모는 정상으로 보입니다. "
            "해당 연도 엑셀이 빠지지 않았는지 확인하세요.)"
        )

    if not missing and not unused:
        print("[기간] 분자·분모 기간 일치")
        return align

    lines = ["[기간 불일치] 사고 기간과 ASOS 노출 기간이 어긋납니다 — 사고율·상대위험이 틀어집니다."]
    if missing:
        lines.append(
            f"  · 분모 결손 {len(missing)}개월 (사고는 있는데 ASOS 없음 → 사고율 과대): "
            f"{_fmt_months(missing)}"
        )
    if unused:
        lines.append(
            f"  · 분모 과대 {len(unused)}개월 (사고 기간 밖 ASOS → 사고율 과소): "
            f"{_fmt_months(unused)}"
        )
    lines.append(
        "  조치: .env 의 START_YEAR/END_YEAR 를 사고 데이터 기간에 맞춘 뒤 "
        "`python -m src.collect.fetch_weather` 로 누락 월을 수집하거나, "
        f"기간 밖 파일을 {WX_DIR} 에서 옮기세요."
    )
    raise SystemExit("\n".join(lines))


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

    # 월 파일이 잘려 있어도 '존재'로는 통과하므로 시간수까지 본다(임계값 기반 → 경고).
    shorts = short_months(wx)
    if shorts:
        preview = ", ".join(f"{ym}({o}/{e}h)" for ym, o, e in shorts[:5])
        more = " …" if len(shorts) > 5 else ""
        print(
            f"[경고] 관측시간이 기대치에 크게 못 미치는 달 {len(shorts)}개 — {preview}{more}\n"
            "        해당 월을 지우고 `python -m src.collect.fetch_weather` 로 다시 받으세요."
        )

    # 분자·분모 기간 정합성 — 어긋나면 여기서 중단한다(산출물을 건드리기 전에).
    acc_months = accident_months(acc)
    check_period_alignment(acc_months, cov["months"])
    # 대시보드 배너·출처 표기는 이 실측 기간을 쓴다(하드코딩 금지 — 분석 창을 바꿨을 때
    # 화면에만 옛 기간이 남는 사고를 막는다).
    period = f"{acc_months[0][:4]}~{acc_months[-1][:4]}" if acc_months else None

    exp = exposure_hours(wx)

    print(f"[사고] {len(acc):,}건 / [노출] {int(exp.sum()):,}시간")
    for c in RISK_CATEGORIES:
        print(f"   {c}: 노출 {int(exp.get(c, 0)):,}h")

    risk = zone_weather_risk(zone_weather_counts(acc), exp)
    RISK_CSV.parent.mkdir(parents=True, exist_ok=True)
    risk.to_csv(RISK_CSV, index=False, encoding="utf-8-sig")
    print(f"[저장] {RISK_CSV}")

    build_dashboard(risk, GEOJSON, DASHBOARD, period=period)
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
