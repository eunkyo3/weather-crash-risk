"""ASOS 시간자료 → 기상범주 분류 및 노출시간(분모) 집계.

노출시간 = "서울에서 맑음/비/눈이 실제로 몇 시간이었나". 상대위험의 분모다.
분류 규칙은 사고 기상범주(맑음/비/눈)와 대칭이 되도록 정의한다(결정로그 기준):

    눈  : 신적설(hr3Fhsc) > 0  또는 (강수량 > 0 & 기온 <= 0℃)
    비  : 강수량 >= 0.1mm  &  위 눈 조건 아님
    맑음: 그 외(강수 없음) — 흐림 포함(비강수)
    (관측 자체가 결측이면 '기타'로 제외)

ASOS 수치 필드는 무강수/무적설 시 빈 문자열('')로 온다 → 0으로 해석.
기온(ta)만 결측 시 NaN 처리(눈 판정의 기온 조건에서 보수적으로 제외).
"""
from __future__ import annotations

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
    """한 시간의 ASOS 관측을 기상범주로 분류."""
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
