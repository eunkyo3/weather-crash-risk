"""ASOS 시간자료 → 기상범주 분류 및 노출시간(분모) 집계.

노출시간 = "서울에서 맑음/비/눈이 실제로 몇 시간이었나". 상대위험의 분모다.
분류 규칙은 사고 기상범주(맑음/비/눈)와 대칭이 되도록 정의한다(결정로그 기준):

    눈  : 신적설(hr3Fhsc) > 0  또는 (강수량 > 0 & 기온 <= 0℃)
    비  : 강수량 >= 0.1mm  &  위 눈 조건 아님
    맑음: 그 외(강수 없음) — 흐림 포함(비강수)

ASOS 수치 필드는 무강수/무적설 시 빈 문자열('')로 온다 → 0으로 해석.
기온(ta)만 결측 시 NaN 처리(눈 판정의 기온 조건에서 보수적으로 제외).

**결측 처리(중요):** ASOS는 "강수 없음"과 "관측 결측"을 모두 빈 문자열로 보내므로 둘을
구분할 수 없다. 따라서 분류는 **결측 시간을 '맑음'에 포함**시킨다 — 즉 `classify_hour`는
항상 맑음/비/눈 중 하나를 반환하며 '기타' 버킷은 없다. 이는 맑음 분모를 과대추정해
모든 RR을 상향시킬 수 있는 방향의 편향이나, 관측 커버리지가 100.00%(2007~2025 = 6,940일
× 24h = 기대 166,560h, 실측 관측 166,559h)라 실질 영향은 미미하다.
누락 자체는 `weather_coverage()`가 행 단위로
감시하며, 이 한계는 methodology.md 한계 절에 명시되어 있다.
"""
from __future__ import annotations

import calendar
import glob
import math
from pathlib import Path

import pandas as pd

RAIN_MM_THRESHOLD = 0.1


def _num(value: object) -> float:
    """ASOS 수치 문자열 → float. 빈값/파싱실패 → 0.0 (무강수·무적설 규약)."""
    try:
        s = str(value).strip()
        return float(s) if s else 0.0
    except (TypeError, ValueError):
        return 0.0


def _temp(value: object) -> float:
    """기온 → float, 결측이면 NaN(눈 판정에서 보수적 제외용)."""
    try:
        s = str(value).strip()
        return float(s) if s else math.nan
    except (TypeError, ValueError):
        return math.nan


def classify_hour(rn: object, hr3Fhsc: object, ta: object) -> str:
    """한 시간의 ASOS 관측을 기상범주로 분류. 항상 맑음/비/눈 중 하나를 반환한다.

    결측(빈 문자열)은 ASOS 규약상 무강수와 구분되지 않으므로 '맑음'으로 떨어진다
    (모듈 docstring의 '결측 처리' 참조).
    """
    rain = _num(rn)
    fresh_snow = _num(hr3Fhsc)
    temp = _temp(ta)

    if fresh_snow > 0 or (rain > 0 and not math.isnan(temp) and temp <= 0):
        return "눈"
    if rain >= RAIN_MM_THRESHOLD:
        return "비"
    return "맑음"


def load_weather(src_dir: str | Path) -> pd.DataFrame:
    """월별 ASOS JSON을 모두 읽어 시간별 DataFrame으로 반환(+기상범주 컬럼)."""
    files = sorted(glob.glob(str(Path(src_dir) / "asos_*.json")))
    if not files:
        raise FileNotFoundError(f"ASOS JSON을 찾을 수 없습니다: {src_dir}")

    frames = [pd.read_json(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset="tm").reset_index(drop=True)
    df["기상범주"] = [
        classify_hour(r, s, t)
        for r, s, t in zip(df.get("rn", ""), df.get("hr3Fhsc", ""), df.get("ta", ""))
    ]
    return df


def exposure_hours(df: pd.DataFrame) -> pd.Series:
    """기상범주별 노출시간(시간수) = 각 범주로 분류된 관측 시간의 개수."""
    return df["기상범주"].value_counts()


def weather_coverage(df: pd.DataFrame) -> dict:
    """ASOS 수집 커버리지 요약 — 관측 월 목록, 총 노출시간, 관측기간(min~max).

    원본 JSON 파일 누락이나 대량 결측을 조기에 드러내기 위한 진단용 리포트다.
    classify_hour의 분류 로직에는 영향을 주지 않는다(#7).
    기대시간은 관측기간(min~max)을 시간 단위로 채웠을 때의 슬롯 수 —
    실제 관측시간이 이보다 크게 적으면 파일 누락/결측 가능성을 의미한다.
    """
    tm = pd.to_datetime(df["tm"])
    start, end = tm.min(), tm.max()
    expected_hours = int((end - start).total_seconds() // 3600) + 1
    observed_hours = len(df)
    return {
        "months": sorted(tm.dt.strftime("%Y-%m").unique().tolist()),
        "start": start,
        "end": end,
        "observed_hours": observed_hours,
        "expected_hours": expected_hours,
        "coverage_ratio": observed_hours / expected_hours if expected_hours else math.nan,
    }


MIN_MONTH_RATIO = 0.9  # 실측(2007~2025) 최저 충족률 99.86% — 이보다 한참 아래면 이상 신호


def short_months(df: pd.DataFrame, min_ratio: float = MIN_MONTH_RATIO) -> list[tuple[str, int, int]]:
    """관측 시간수가 그 달의 기대치에 크게 못 미치는 달을 찾는다.

    기간 정합성 검사는 달의 **존재**만 보므로, API 부분응답 등으로 잘린 월 파일은
    그대로 통과한다. 전체 커버리지 비율도 228개월 중 한 달이 비어야 0.4%p 움직일 뿐이라
    잡히지 않는다. 그 사각지대를 월 단위로 메운다.

    반환: (YYYY-MM, 관측시간, 기대시간) 목록 — 비어 있으면 정상.
    """
    tm = pd.to_datetime(df["tm"])
    counts = tm.dt.strftime("%Y-%m").value_counts()
    short: list[tuple[str, int, int]] = []
    for ym, observed in counts.items():
        year, month = int(ym[:4]), int(ym[5:7])
        expected = calendar.monthrange(year, month)[1] * 24
        if observed < expected * min_ratio:
            short.append((ym, int(observed), expected))
    return sorted(short)


if __name__ == "__main__":
    import sys

    src = sys.argv[1] if len(sys.argv) > 1 else "data/raw/weather"
    df = load_weather(src)
    exp = exposure_hours(df)
    total = int(exp.sum())
    print(f"[노출] {src} → 총 {total:,}시간 ({total/24/365:.1f}년치)")
    print(f"관측기간: {df['tm'].min()} ~ {df['tm'].max()}")
    for cat in ["맑음", "비", "눈"]:
        h = int(exp.get(cat, 0))
        print(f"  {cat}: {h:,}시간 ({h/total*100:.2f}%)")
