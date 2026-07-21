"""사고 데이터(TAAS 사고분석-지역별 엑셀) 로더 및 정규화.

TAAS GIS "사고분석 → 지역별" 엑셀은 사망사고 개별 CSV(data.go.kr 15070340, 파기)의
대체 소스다. 좌표·발생시각은 없고 **시군구 + 기상상태**까지만 제공되므로, 분석 단위는
자치구(25개), 기상범주는 데이터에 기록된 `기상상태`를 그대로 쓴다(노출 분모만 ASOS).

확정 컬럼(2014~2023 동일):
    구분번호, 발생년월, 주야, 시군구, 사고내용, 사망자수, 중상자수, 경상자수,
    부상신고자수, 사고유형, 법규위반, 노면상태, 기상상태, 도로형태,
    가해운전자 차종/성별/연령대/상해정도, 피해운전자 차종/성별/연령대/상해정도

사용:
    from src.analysis.accidents import load_accidents, zone_weather_counts
    df = load_accidents("data/raw/accidents/사망중상")
"""
from __future__ import annotations

import glob
from pathlib import Path

import pandas as pd

# TAAS 기상상태 → 분석 기상범주.
# 노출 분모(ASOS)와 동일 규칙으로 맞춰야 하므로 비강수(맑음/흐림)는 '맑음'으로 통합.
# 눈>비 우선(원자료는 단일 라벨이라 실제 충돌은 없음).
_WEATHER_MAP = {
    "맑음": "맑음",
    "흐림": "맑음",  # 비강수 → 맑음(비강수) 기준선에 포함
    "비": "비",
    "눈": "눈",
}

# 표본이 극소한 참고 범주(안개/기타/결측)는 상대위험 계산에서 제외하고 '기타'로 라벨.
OTHER = "기타"

# 분석에서 상대위험을 산출하는 유효 범주(기준선 = 맑음)
RISK_CATEGORIES = ["맑음", "비", "눈"]


def weather_category(value: object) -> str:
    """TAAS 기상상태 문자열을 분석 기상범주로 매핑."""
    return _WEATHER_MAP.get(str(value).strip(), OTHER)


def _gu(sigungu: object) -> str:
    """'서울특별시 강동구' → '강동구'."""
    parts = str(sigungu).split()
    return parts[-1] if parts else str(sigungu)


def load_accidents(src_dir: str | Path) -> pd.DataFrame:
    """폴더의 모든 `*.xlsx`를 읽어 하나로 합치고 파생 컬럼을 붙인다.

    파생 컬럼: 연도(발생년월에서), 구(시군구 말단), 기상범주, 보행자여부.
    """
    files = sorted(glob.glob(str(Path(src_dir) / "*.xlsx")))
    if not files:
        raise FileNotFoundError(f"사고 엑셀을 찾을 수 없습니다: {src_dir}")

    frames = [pd.read_excel(f) for f in files]
    df = pd.concat(frames, ignore_index=True)

    # 연도는 파일명이 아니라 데이터(발생년월 '2023년 1월')에서 추출 — 신뢰 원천
    df["연도"] = df["발생년월"].astype(str).str.extract(r"(\d{4})").astype("Int64")
    df["구"] = df["시군구"].map(_gu)
    df["기상범주"] = df["기상상태"].map(weather_category)
    df["보행자여부"] = df["사고유형"].astype(str).str.startswith("차대사람")

    # 동일 구분번호 중복(파일 겹침) 방어
    before = len(df)
    df = df.drop_duplicates(subset="구분번호").reset_index(drop=True)
    if len(df) != before:
        print(f"  [주의] 중복 구분번호 {before - len(df)}건 제거")

    return df


def zone_weather_counts(df: pd.DataFrame, pedestrian_only: bool = False) -> pd.DataFrame:
    """구 × 기상범주 사고건수(상대위험 분자) 집계.

    pedestrian_only=True 이면 차대사람(보행자) 사고로 한정.
    """
    if pedestrian_only:
        df = df[df["보행자여부"]]
    counts = (
        df.groupby(["구", "기상범주"]).size().rename("사고건수").reset_index()
    )
    return counts


if __name__ == "__main__":
    import sys

    src = sys.argv[1] if len(sys.argv) > 1 else "data/raw/accidents/사망중상"
    df = load_accidents(src)
    print(f"[로드] {src}  →  {len(df):,}건, 연도 {sorted(df['연도'].dropna().unique().tolist())}")
    print("\n[사고내용]")
    print(df["사고내용"].value_counts().to_string())
    print("\n[기상범주]")
    print(df["기상범주"].value_counts().to_string())
    print(f"\n[구] {df['구'].nunique()}개, 보행자 {int(df['보행자여부'].sum()):,}건")
    print("\n[구 × 기상범주 — 눈 색칠가능 구 수]")
    counts = zone_weather_counts(df)
    piv = counts.pivot(index="구", columns="기상범주", values="사고건수").fillna(0).astype(int)
    for cat in RISK_CATEGORIES:
        if cat in piv.columns:
            print(f"  {cat}: 총 {int(piv[cat].sum()):,}건, ≥1건 구 {int((piv[cat] > 0).sum())}/25")
