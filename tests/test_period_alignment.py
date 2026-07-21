"""분자(사고)·분모(노출) 기간 정합성 가드 테스트.

이 가드가 막는 것은 "에러 없이 틀린 숫자"다. 사고 기간과 ASOS 기간이 어긋나면
사고율(사고건수÷노출시간)이 곧바로 왜곡되는데 파이프라인은 정상 종료한다.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.analysis.accidents import accident_months
from src.analysis.pipeline import (
    _month_seq,
    check_period_alignment,
    period_alignment,
)


def months(*pairs: tuple[int, int]) -> list[str]:
    return [f"{y:04d}-{m:02d}" for y, m in pairs]


# --- _month_seq ---

def test_month_seq_crosses_year_boundary():
    assert _month_seq("2023-11", "2024-02") == ["2023-11", "2023-12", "2024-01", "2024-02"]


def test_month_seq_single_month():
    assert _month_seq("2020-05", "2020-05") == ["2020-05"]


def test_month_seq_full_year():
    seq = _month_seq("2019-01", "2019-12")
    assert len(seq) == 12 and seq[0] == "2019-01" and seq[-1] == "2019-12"


def test_month_seq_multi_year_length():
    # 2007-01 ~ 2025-12 = 19년 × 12 = 228개월 (실제 분석 기간)
    assert len(_month_seq("2007-01", "2025-12")) == 228


# --- period_alignment: 4가지 경우 ---

def test_perfectly_aligned_reports_nothing():
    m = _month_seq("2014-01", "2015-12")
    a = period_alignment(m, m)
    assert a["missing"] == [] and a["unused"] == []
    assert len(a["required"]) == 24


def test_missing_exposure_is_detected():
    """사고는 있는데 ASOS가 없는 달 → 분모 결손(사고율 과대)."""
    acc = _month_seq("2014-01", "2014-06")
    exp = [x for x in acc if x not in ("2014-03", "2014-04")]
    a = period_alignment(acc, exp)
    assert a["missing"] == ["2014-03", "2014-04"]
    assert a["unused"] == []


def test_unused_exposure_is_detected():
    """사고 기간 밖 ASOS만 있는 달 → 분모 과대(사고율 과소).

    2014~2023 사고에 2007~2025 ASOS를 물리는 실수가 정확히 이 경우다.
    """
    acc = _month_seq("2014-01", "2014-03")
    exp = _month_seq("2013-11", "2014-05")
    a = period_alignment(acc, exp)
    assert a["missing"] == []
    assert a["unused"] == ["2013-11", "2013-12", "2014-04", "2014-05"]


def test_both_directions_at_once():
    acc = _month_seq("2020-01", "2020-04")
    exp = ["2019-12", "2020-01", "2020-04"]   # 02·03 없음, 2019-12 여분
    a = period_alignment(acc, exp)
    assert a["missing"] == ["2020-02", "2020-03"]
    assert a["unused"] == ["2019-12"]


def test_gap_inside_accident_span_counts_as_missing():
    """사고가 없는 달이라도 기간 안이면 노출이 있어야 한다(구간 기준 판정)."""
    acc = ["2021-01", "2021-04"]          # 02·03 에는 사고 없음
    exp = _month_seq("2021-01", "2021-04")
    a = period_alignment(acc, exp)
    assert a["required"] == _month_seq("2021-01", "2021-04")
    assert a["missing"] == [] and a["unused"] == []


def test_empty_accidents_flags_all_exposure_as_unused():
    a = period_alignment([], ["2020-01", "2020-02"])
    assert a["required"] == [] and a["missing"] == []
    assert a["unused"] == ["2020-01", "2020-02"]
    # 이름대로 '막는지'까지 확인 — 함수 반환값만 보면 게이트가 통과시켜도 초록이다
    with pytest.raises(SystemExit):
        check_period_alignment([], ["2020-01", "2020-02"])


def test_out_of_order_accident_months_still_report_correct_span(capsys):
    """입력이 정렬돼 있지 않아도 출력 구간이 뒤집히지 않아야 한다."""
    m = ["2020-12", "2020-01", "2020-06"]
    check_period_alignment(m, _month_seq("2020-01", "2020-12"))
    assert "2020-01 ~ 2020-12" in capsys.readouterr().out


# --- 파이프라인 게이트 ---

def test_gate_reports_alignment_and_returns_clean_result(capsys):
    m = _month_seq("2007-01", "2008-12")
    a = check_period_alignment(m, m)
    assert a["missing"] == [] and a["unused"] == [] and a["acc_gaps"] == []
    out = capsys.readouterr().out
    assert "분자·분모 기간 일치" in out
    assert "2007-01 ~ 2008-12" in out


def test_gate_raises_on_missing_exposure():
    acc = _month_seq("2014-01", "2014-06")
    exp = [x for x in acc if x != "2014-03"]
    with pytest.raises(SystemExit) as e:
        check_period_alignment(acc, exp)
    msg = str(e.value)
    assert "기간 불일치" in msg
    assert "분모 결손" in msg and "2014-03" in msg
    assert "START_YEAR" in msg          # 조치 안내


def test_gate_raises_on_unused_exposure():
    with pytest.raises(SystemExit) as e:
        check_period_alignment(_month_seq("2014-01", "2014-02"),
                               _month_seq("2007-01", "2014-02"))
    msg = str(e.value)
    assert "분모 과대" in msg
    assert "fetch_weather" in msg


def test_gate_message_truncates_long_month_lists():
    acc = _month_seq("2014-01", "2014-12")
    with pytest.raises(SystemExit) as e:
        check_period_alignment(acc, [])
    assert "외 6개" in str(e.value)      # 12개월 중 6개만 나열


# --- accidents.accident_months 파서 ---

def test_accident_months_parses_taas_format():
    df = pd.DataFrame({"발생년월": ["2023년 1월", "2023년 12월", "2007년 3월"]})
    assert accident_months(df) == ["2007-03", "2023-01", "2023-12"]


def test_accident_months_deduplicates_and_sorts():
    df = pd.DataFrame({"발생년월": ["2020년 5월"] * 3 + ["2020년 1월"]})
    assert accident_months(df) == ["2020-01", "2020-05"]


def test_accident_months_warns_about_unparsable_rows(capsys):
    """파싱 실패를 조용히 버리면 기간이 좁게 잡혀 정합성 검사가 오진단한다.

    ISO 표기(`2020-06`)처럼 사람 눈엔 멀쩡해 보이는 값도 거부되므로, 경고가 없으면
    기간이 조용히 좁아진다. (연도 컬럼도 같은 패턴 `_YEAR_MONTH_RE` 를 쓰므로 두 곳의
    파싱 강도가 어긋나지 않는다 — 예전엔 연도만 느슨해 같은 행이 다르게 취급됐다.)
    """
    df = pd.DataFrame({"발생년월": ["2020년 5월", "미상", "", "2020-06"]})
    assert accident_months(df) == ["2020-05"]
    out = capsys.readouterr().out
    assert "파싱 실패 3/4행" in out
    assert "2023년 1월" in out          # 기대 형식 안내
