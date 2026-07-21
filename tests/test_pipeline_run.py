"""pipeline.run() 배선 테스트.

`check_period_alignment` 함수 자체를 아무리 잘 테스트해도, `run()` 에서 그 호출을
빼버리면 게이트는 사라진다. 리뷰어가 실제로 지적한 구멍이다 — 호출부를 삭제해도
스위트 전체가 초록이었다. 여기서 **배선과 호출 순서**를 고정한다.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from src.analysis import pipeline

ZONES = ["가구", "나구", "다구", "라구", "마구"]


def _weather(months: list[str], clear: int = 1200, rain: int = 180, snow: int = 60):
    """월별 시간단위 관측. 앞에서부터 맑음/비/눈 순으로 범주를 배정한다."""
    stamps = []
    for ym in months:
        y, mo = int(ym[:4]), int(ym[5:7])
        start = pd.Timestamp(year=y, month=mo, day=1)
        end = start + pd.offsets.MonthBegin(1)
        stamps += list(pd.date_range(start, end, freq="h", inclusive="left"))
    cats = (["맑음"] * clear + ["비"] * rain + ["눈"] * snow)
    cats = (cats * (len(stamps) // max(len(cats), 1) + 1))[: len(stamps)]
    return pd.DataFrame({"tm": [s.strftime("%Y-%m-%d %H:%M") for s in stamps],
                         "기상범주": cats})


def _accidents(months: list[str]):
    """구 × 기상범주 사고. 비의 상대위험이 확실히 1보다 크도록 만든다."""
    rows = []
    for i, gu in enumerate(ZONES):
        for cat, n in [("맑음", 1000), ("비", 200 + i * 5), ("눈", 20 + i * 3)]:
            for k in range(n):
                rows.append({"발생년월": f"{months[k % len(months)][:4]}년 "
                                        f"{int(months[k % len(months)][5:7])}월",
                             "구": gu, "기상범주": cat})
    return pd.DataFrame(rows)


def _geojson(path, zones=ZONES):
    feats = []
    for i, gu in enumerate(zones):
        x = 127.0 + i * 0.1
        feats.append({"type": "Feature", "properties": {"name": gu},
                      "geometry": {"type": "Polygon", "coordinates": [[
                          [x, 37.5], [x + .08, 37.5], [x + .08, 37.58], [x, 37.58], [x, 37.5]]]}})
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}),
                    encoding="utf-8")
    return path


@pytest.fixture
def wired(monkeypatch, tmp_path):
    """run() 의 입출력 경로를 임시 디렉토리로 돌린다."""
    csv = tmp_path / "risk.csv"
    dash = tmp_path / "dashboard.html"
    monkeypatch.setattr(pipeline, "RISK_CSV", csv)
    monkeypatch.setattr(pipeline, "DASHBOARD", dash)
    monkeypatch.setattr(pipeline, "GEOJSON", _geojson(tmp_path / "z.geojson"))
    return csv, dash


def _patch_data(monkeypatch, acc_months, wx_months):
    monkeypatch.setattr(pipeline, "load_accidents", lambda _p: _accidents(acc_months))
    monkeypatch.setattr(pipeline, "load_weather", lambda _p: _weather(wx_months))


def test_run_aborts_on_period_mismatch_before_writing_anything(
    wired, monkeypatch, capsys
):
    """분모 결손 상태에서 run() 은 산출물을 만들지 않고 중단해야 한다.

    이 테스트가 잡는 회귀: pipeline.run() 에서 check_period_alignment 호출을 지우거나
    CSV 저장 뒤로 옮기는 것. 둘 다 산출물이 생겨 아래 단언이 깨진다.
    """
    csv, dash = wired
    _patch_data(monkeypatch, ["2020-01", "2020-02", "2020-03"], ["2020-01"])

    with pytest.raises(SystemExit) as e:
        pipeline.run()

    assert "기간 불일치" in str(e.value)
    assert "분모 결손" in str(e.value)
    assert not csv.exists(), "기간 불일치인데 상대위험 CSV가 기록됐다"
    assert not dash.exists(), "기간 불일치인데 대시보드가 기록됐다"


def test_run_aborts_when_exposure_extends_beyond_accidents(wired, monkeypatch):
    """분모 과대(사고 기간 밖 ASOS)도 동일하게 중단한다."""
    csv, dash = wired
    _patch_data(monkeypatch, ["2020-01"], ["2019-11", "2019-12", "2020-01"])

    with pytest.raises(SystemExit) as e:
        pipeline.run()
    assert "분모 과대" in str(e.value)
    assert not csv.exists() and not dash.exists()


def test_run_completes_and_writes_artifacts_when_aligned(wired, monkeypatch):
    """정합 상태에서는 기존 동작이 그대로 — 게이트가 정상 실행을 막지 않는다."""
    csv, dash = wired
    months = ["2020-01", "2020-02"]
    _patch_data(monkeypatch, months, months)

    risk = pipeline.run()

    assert csv.exists() and dash.exists()
    assert set(risk["구"]) == set(ZONES)
    assert set(risk["기상범주"]) == {"맑음", "비", "눈"}
    # 맑음은 정의상 기준선
    assert (risk[risk["기상범주"] == "맑음"]["상대위험"] == 1.0).all()


def test_run_passes_measured_period_to_dashboard(wired, monkeypatch):
    """배너·출처의 기간이 하드코딩이 아니라 실제 데이터에서 온다."""
    _csv, dash = wired
    _patch_data(monkeypatch, ["2020-01", "2020-02"], ["2020-01", "2020-02"])

    pipeline.run()

    html = dash.read_text(encoding="utf-8")
    assert "2020~2020" in html
    assert "2014~2023" not in html, "옛 기간이 하드코딩되어 남아 있다"


def test_run_warns_but_proceeds_on_internal_accident_gap(wired, monkeypatch, capsys):
    """사고 구간 내부 공백은 경고만 하고 계속 진행한다(0건인 달은 통계적으로 정상).

    다만 파일 누락 신호일 수 있으므로 반드시 화면에 드러나야 한다.
    """
    csv, _dash = wired
    # 사고는 2020-01 과 2020-03 만, 노출은 세 달 모두 → 2020-02 가 사고 공백
    _patch_data(monkeypatch, ["2020-01", "2020-03"], ["2020-01", "2020-02", "2020-03"])

    pipeline.run()

    out = capsys.readouterr().out
    assert "사고가 0건인 달" in out
    assert "2020-02" in out
    assert csv.exists(), "경고는 중단 사유가 아니다"
