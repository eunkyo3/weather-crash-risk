<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-07-21 | Updated: 2026-07-21 -->

# src

## Purpose
프로젝트의 Python 소스 패키지 루트. **수집(`collect/`) → 분석·대시보드(`analysis/`) → 서빙(`serve.py`)** 전 구간이 구현되어 있다. 파이프라인 진입점은 `python -m src.analysis.pipeline` 하나이며, 이것이 사고·기상 로드부터 상대위험 산출·대시보드 생성·자동검증(AC7)까지 전부 수행한다.

## Key Files
| File | Description |
|------|-------------|
| `serve.py` | 표준 라이브러리 정적 서버. `/` → `outputs/dashboard.html`. Docker 컨테이너 기본 실행 대상 |
| `__init__.py` | 빈 파일. 패키지 마커 |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `collect/` | 공공데이터포털 API 수집 스크립트 (see `collect/AGENTS.md`) |
| `analysis/` | 사고·노출 로드, 상대위험 산출, 대시보드 생성, 자동검증 (see `analysis/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- 모든 모듈은 **프로젝트 루트에서 패키지 경로로 실행**된다: `python -m src.<pkg>.<module>`. 임포트도 루트 기준 절대경로(`from config.settings import settings`, `from src.analysis.risk import ...`)로 쓴다. 상대임포트(`from .risk import`)는 이 저장소 관례가 아니다.
- 각 모듈은 **CLI 진입점 형태**를 유지한다: `main()`(또는 `run()`) + `if __name__ == "__main__":`. 여러 모듈이 자기진단용 `__main__` 블록을 갖고 있어 단독 실행으로 중간 산출을 확인할 수 있다.
- 단계 간 데이터 전달은 **파일**(`data/raw/` → `data/processed/` → `outputs/`)로 한다. 각 단계를 따로 재실행할 수 있어야 재현성이 유지된다.
- 설정을 모듈에 하드코딩하지 않는다. 대상 지역·기간 등 바뀔 수 있는 값은 `config.settings` 를 거친다. 단 `analysis/` 는 경로 상수를 모듈 최상단에 두는 방식(`pipeline.py` 의 `ACC_DIR`/`GEOJSON` 등)을 쓴다.
- **`collect/fetch_hotspots.py` 는 구설계(다발지역 폴리곤) 잔재다.** 현행 자치구 기반 분석 경로에서는 호출되지 않는다. 파이프라인에 다시 엮으려 하지 말 것.

### Testing Requirements
- `pytest` 로 실행하며 테스트는 `tests/` 에 있다(합성 데이터 기반, 네트워크·원천데이터 불필요).
- 순수 함수부터 덮는다 — `risk.zone_weather_risk`, `exposure.classify_hour`, `accidents.weather_category`/`check_severity`, `pipeline._bh_significant_elevated_gu` 가 현재 커버 대상이다.
- 분류 규칙이나 결측 처리의 **동작을 바꾸면 문서도 함께 고친다**. `exposure` 의 결측→맑음 동작처럼 테스트가 설계 결정을 고정하고 있는 지점이 있다.

### Common Patterns
- 모든 모듈은 `from __future__ import annotations` 로 시작하고 타입 힌트를 붙인다 (`list[dict]`, `str | None`).
- 모듈 최상단 docstring에 **무엇을 입력받아 무엇을 산출하는지, 실행 명령, 주의사항**을 한국어로 적는다. 통계 방법을 바꿀 때는 근거(왜 Katz 대신 Byar+MOVER인지 등)를 docstring에 남기는 것이 이 저장소의 관례다.
- 진행 상황은 `print` 로 출력한다. 로깅 프레임워크는 도입되지 않았다.

## Dependencies

### Internal
- `config/` — `collect/` 가 `settings` 싱글턴에 의존
- `data/` — 입력(`raw/`)과 산출(`processed/`) 위치
- `assets/vendor/` — `analysis/dashboard.py` 가 오프라인 인라인에 사용

### External
- `collect/`: `requests`
- `analysis/`: `pandas`, `openpyxl`, `folium`, `branca`
- `serve.py`: 표준 라이브러리만

<!-- MANUAL: -->
