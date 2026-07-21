"""pipeline.py의 BH(FDR) 유의 상승 판정(_bh_significant_elevated_gu) 테스트."""
import pandas as pd

from src.analysis.pipeline import _bh_significant_elevated_gu, _norm_sf


def _row(gu: str, rr: float, lo: float, hi: float) -> dict:
    return {"구": gu, "기상범주": "비", "상대위험": rr, "CI하한": lo, "CI상한": hi}


def test_norm_sf_basic():
    assert abs(_norm_sf(0.0) - 0.5) < 1e-9
    assert _norm_sf(1.96) < 0.03  # 표준정규 우측꼬리 ≈ 0.025


def test_bh_counts_clearly_significant_gu():
    # 세 구 모두 RR>1이고 CI가 좁아 명백히 유의 → 3개 모두 카운트
    cand = pd.DataFrame([
        _row("A", 2.0, 1.5, 2.667),
        _row("B", 1.8, 1.4, 2.31),
        _row("C", 2.5, 1.9, 3.29),
    ])
    assert _bh_significant_elevated_gu(cand) == 3


def test_bh_excludes_nonsignificant():
    # RR≈1, CI가 1을 포함 → 비유의 → 0
    cand = pd.DataFrame([_row("A", 1.05, 0.8, 1.38)])
    assert _bh_significant_elevated_gu(cand) == 0


def test_bh_excludes_protective_rr_below_1():
    # 유의하지만 RR<1(보호효과) → "위험 상승"이 아니므로 제외 → 0
    cand = pd.DataFrame([_row("A", 0.5, 0.4, 0.625)])
    assert _bh_significant_elevated_gu(cand) == 0


def test_bh_skips_nan_degenerate():
    cand = pd.DataFrame([
        {"구": "A", "기상범주": "눈", "상대위험": float("nan"),
         "CI하한": float("nan"), "CI상한": float("nan")},
    ])
    assert _bh_significant_elevated_gu(cand) == 0
