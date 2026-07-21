"""사고 데이터(TAAS 사고분석-지역별 엑셀) 로더 및 정규화.

TAAS GIS "사고분석 → 지역별" 엑셀은 사망사고 개별 CSV(data.go.kr 15070340, 파기)의
대체 소스다. 좌표·발생시각은 없고 **시군구 + 기상상태**까지만 제공되므로, 분석 단위는
자치구(25개), 기상범주는 데이터에 기록된 `기상상태`를 그대로 쓴다(노출 분모만 ASOS).

확정 컬럼(2007~2025 전 연도 동일, 실측 확인):
    구분번호, 발생년월, 주야, 시군구, 사고내용, 사망자수, 중상자수, 경상자수,
    부상신고자수, 사고유형, 법규위반, 노면상태, 기상상태, 도로형태,
    가해운전자 차종/성별/연령대/상해정도, 피해운전자 차종/성별/연령대/상해정도

사용:
    from src.analysis.accidents import load_accidents, zone_weather_counts
    df = load_accidents("data/raw/accidents")
"""
from __future__ import annotations

import glob
from pathlib import Path

import pandas as pd

# 유효 범주(맑음/비/눈)의 단일 출처는 risk.py 다. 모듈마다 같은 리스트를 복제해 두면
# 범주를 바꿀 때 한 곳을 빠뜨려 분자·분모·색칠이 조용히 어긋난다.
from src.analysis.risk import RISK_CATEGORIES

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


# 분석 대상 심각도 — TAAS `사고내용` 이 이 키워드를 포함해야 한다(결정로그: 사망+중상).
# TAAS에서 "전체" 조건으로 내려받으면 경상·부상신고가 섞여 분자가 조용히 부풀려지므로
# 로드 시점에 분포를 검사해 경고한다.
EXPECTED_SEVERITY = ("사망", "중상")

# `발생년월` 파싱의 단일 출처. 연도와 월을 각각 다른 정규식으로 뽑으면 강도가 어긋나
# (예: `2020-06` 이 연도 추출은 통과하고 월 추출은 실패) 같은 행이 기간 계산과 연도
# 컬럼에서 다르게 취급된다. 한 패턴에서 둘 다 뽑는다.
_YEAR_MONTH_RE = r"(\d{4})년\s*(\d{1,2})월"


def accident_months(df: pd.DataFrame) -> list[str]:
    """사고가 발생한 달 목록을 `YYYY-MM` 오름차순으로 반환한다.

    TAAS `발생년월` 은 `2023년 1월` 형태다(2007~2025 전 연도 동일, 실측 확인).
    노출(ASOS) 기간과 맞추려면 연도가 아니라 **월** 해상도가 필요하다 —
    연 단위로 비교하면 연중 일부만 수집된 해를 놓친다.

    파싱 실패를 조용히 버리면 기간이 실제보다 좁게 잡혀 정합성 검사가 엉뚱한 곳을
    가리킨다(예: 전부 실패하면 "분모 과대"로 오진단). 그래서 실패 행이 있으면 경고한다.
    """
    raw = df["발생년월"].astype(str).str.strip()
    parsed = raw.str.extract(_YEAR_MONTH_RE).dropna()
    failed = len(raw) - len(parsed)
    if failed:
        examples = raw[~raw.index.isin(parsed.index)].unique()[:3].tolist()
        print(
            f"  [경고] `발생년월` 파싱 실패 {failed:,}/{len(raw):,}행 — 예시 {examples}\n"
            "         TAAS 표기가 바뀌었을 수 있습니다(기대 형식: '2023년 1월'). "
            "이대로 두면 분석 기간이 실제보다 좁게 잡힙니다."
        )
    return sorted({f"{int(y):04d}-{int(m):02d}" for y, m in parsed.values})


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

    # 연도는 파일명이 아니라 데이터(발생년월 '2023년 1월')에서 추출 — 신뢰 원천.
    # accident_months 와 같은 패턴을 써서 두 곳의 파싱 강도가 어긋나지 않게 한다.
    df["연도"] = (
        df["발생년월"].astype(str).str.strip().str.extract(_YEAR_MONTH_RE)[0].astype("Int64")
    )
    df["구"] = df["시군구"].map(_gu)
    df["기상범주"] = df["기상상태"].map(weather_category)
    df["보행자여부"] = df["사고유형"].astype(str).str.startswith("차대사람")

    # 동일 구분번호 중복(파일 겹침) 방어
    before = len(df)
    df = df.drop_duplicates(subset="구분번호").reset_index(drop=True)
    if len(df) != before:
        print(f"  [주의] 중복 구분번호 {before - len(df)}건 제거")

    check_severity(df)
    return df


def check_severity(df: pd.DataFrame) -> dict[str, int]:
    """`사고내용` 분포를 검사해 분석 범위(사망+중상) 밖 레코드를 경고한다.

    TAAS에서 심각도 조건을 "전체"로 내려받으면 경상·부상신고가 섞이는데, 그대로 두면
    분자만 커져 상대위험이 조용히 틀어진다. 라벨 표기가 연도별로 달라질 수 있어
    실패시키지 않고 분포를 출력하는 경고 방식으로 처리한다.

    반환: 범위 밖 라벨 → 건수 (없으면 빈 dict).
    """
    if "사고내용" not in df.columns:
        print("  [주의] '사고내용' 컬럼이 없어 심각도 검증을 건너뜁니다")
        return {}

    counts = df["사고내용"].astype(str).str.strip().value_counts()
    unexpected = {
        label: int(n)
        for label, n in counts.items()
        if not any(k in label for k in EXPECTED_SEVERITY)
    }
    if unexpected:
        total = sum(unexpected.values())
        print(
            f"  [경고] 분석 범위(사망+중상) 밖 사고 {total:,}건이 섞여 있습니다 "
            f"— {unexpected}\n"
            "         TAAS에서 심각도='사망 + 중상' 조건으로 다시 받으세요. "
            "이대로 진행하면 상대위험의 분자가 과대집계됩니다."
        )
    return unexpected


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

    src = sys.argv[1] if len(sys.argv) > 1 else "data/raw/accidents"
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
