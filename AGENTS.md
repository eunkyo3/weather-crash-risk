<!-- Generated: 2026-07-21 | Updated: 2026-07-21 -->

# weather-crash-risk

## Purpose
서울시 **자치구 25개**를 단위로, 심각(사망·중상) 교통사고와 기상청 ASOS 시간자료를 결합해 **한 자치구 내부에서 기상조건(맑음/비/눈)별 사고 위험이 얼마나 달라지는지**를 노출시간 보정 상대위험(RR)으로 산출하고 folium/Leaflet 지도 대시보드로 시각화하는 대학 빅데이터 기획 PBL 프로젝트.

수집 → 분석 → 대시보드 → 자동검증까지 **전 구간이 구현되어 동작**한다. 산출물 `outputs/dashboard.html` 은 저장소에 커밋되어 있어 원천 데이터 없이도 바로 띄울 수 있다.

> ⚠️ **설계가 한 번 크게 바뀐 프로젝트다.** 원계획(다발지역 폴리곤 × 개별 사망사고, 위경도+발생시각 기반)은 원천 데이터셋 `15070340` 이 파기되면서 폐기됐고, 2026-07-14에 TAAS 집계본 기반 **자치구 단위 / 사망+중상 / 경찰기록 기상상태** 설계로 전환됐다. `docs/implementation-plan.md` 는 **전환 이전 계획**이라 현행과 어긋나는 서술이 있다 — 현행 사양은 `docs/methodology.md` 와 `docs/decisions-log.md` 하단(데이터 소스 변경)이 기준이다.

## Key Files
| File | Description |
|------|-------------|
| `README.md` | 프로젝트 개요, 데이터 출처, 실행 순서(환경준비 → 인증키 → 수집) |
| `requirements.txt` | Python 의존성. Phase별 주석(수집 / 공간분석 / PostGIS 적재)으로 구분 |
| `.env.example` | 환경변수 템플릿. 복사해 `.env` 생성. 인증키·대상지역·수집동작·PostGIS 설정 |
| `.gitignore` | 비밀값(`.env`), 수집 원본(`data/raw/`, `*.csv`, `*.geojson`), `.omc/` 제외 |
| `LICENSE` | MIT (코드 한정. 공공데이터는 저장소 미포함) |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `config/` | 환경변수 → 타입 지정 설정 객체 (see `config/AGENTS.md`) |
| `src/` | Python 소스 패키지 (see `src/AGENTS.md`) |
| `data/` | 수집 데이터 저장 위치. 내용물은 gitignore (see `data/AGENTS.md`) |
| `docs/` | 요구사항 스펙·구현 계획·결정 로그 (see `docs/AGENTS.md`) |
| `.omc/` | OMC 툴 운영 상태. gitignore 대상 — **문서화·수정하지 않는다** |

## For AI Agents

### Working In This Directory
- **문서 언어는 한국어**다. 코드 주석·docstring·`print` 로그·커밋 메시지 모두 한국어로 작성한다. 식별자(변수·함수·파일명)만 영어.
- **설계 결정을 임의로 바꾸지 않는다.** 지표 정의, 기상 범주 규칙, 분석 기간 같은 항목은 `docs/decisions-log.md` 에 합의된 상태다. 변경이 필요하면 먼저 그 문서를 확인하고, 바꿀 경우 결정 로그도 함께 갱신한다.
- **핵심 제약**: 이 프로젝트의 지표는 "구역 간 공간 gradient"가 아니라 **"한 구역 내부의 기상조건별 시간층화 상대위험"** 이다. 서울 ASOS 관측소가 소수라 구역 간 기상이 사실상 동일하기 때문. 코드·문서·UI 문구가 이 구분을 흐리지 않게 한다.
- **시간축은 KST 고정**. 사고 발생시각(시 0~23)과 ASOS 관측시각(`tm`)을 모두 로컬시각으로 다룬다. UTC 변환을 끼워넣지 않는다.
- 실행은 항상 패키지 모듈 형태: `python -m src.collect.fetch_hotspots`. 스크립트 직접 경로 실행(`python src/collect/...`)은 `config` 임포트가 깨진다.
- 비밀값을 코드에 하드코딩하지 않는다. 모든 인증키는 `.env` → `config.settings` 경유.

### Testing Requirements
- `pytest` 로 실행한다 (`tests/`, 합성 데이터 기반 결정론적 테스트). CI는 `.github/workflows/ci.yml` 에서 `ruff check src` + `pytest` 를 돌린다.
- **`pyproject.toml` 의 `[tool.pytest.ini_options] pythonpath = ["."]` 를 지우지 말 것.** 이게 없으면 bare `pytest`(CI가 쓰는 방식)에서 `src` 임포트가 깨져 로컬 `python -m pytest` 만 통과하는 위장 그린 상태가 된다.
- 수집 스크립트를 고쳤다면 좁은 범위로 실제 호출해 확인한다 (예: `.env` 의 `START_YEAR=END_YEAR` 를 한 해로 좁혀 실행 → `data/raw/**` 에 JSON 생성 및 항목 수 확인).
- 대시보드를 고쳤다면 산출 HTML을 파싱해 레이어·feature 수·범례를 확인한다. 데이터 없이 재생성하려면 커밋된 `data/processed/zone_weather_risk.csv` 를 입력으로 `build_dashboard()` 를 직접 호출하면 된다.
- 테스트를 새로 추가할 때는 네트워크 호출을 목(mock)한다. 실제 API를 때리는 테스트는 일 호출한도를 소모한다.

### Common Patterns
- 설정은 전부 `from config.settings import settings` 싱글턴 경유. 모듈 안에서 `os.getenv` 를 직접 부르지 않는다.
- API 호출은 `src/collect/common.py` 의 `get_json` / `extract_items` / `total_count` / `save_json` 를 재사용한다. `requests` 를 새로 직접 호출하지 않는다.
- 수집 루프는 "단위(연/월)별 try/except → 실패는 `print` 후 `continue`" 패턴. 한 구간 실패가 전체 수집을 중단시키지 않는다.
- 진행 상황은 로깅 프레임워크 없이 `print` 로 출력한다 (`  {단위} p{page}: +{n} (누적 {got}/{total})`).

## Dependencies

### External
- `requests` — 공공데이터포털 API 호출
- `python-dotenv` — `.env` 로드
- `pandas` — 표 데이터 처리 (분석 전 구간)
- `openpyxl` — TAAS 사고 엑셀(.xlsx) 읽기
- `folium` / `mapclassify` — 자치구 choropleth + 레이어 토글, 분위수 구간화
- `geopandas` / `shapely` / PostGIS 계열은 `requirements.txt` 에 **주석 처리**되어 있다. 현 설계는 구 라벨 기반이라 좌표 공간조인이 없어 불필요하다 — 좌표 데이터를 다시 확보하지 않는 한 되살리지 말 것.

### Vendored
- `assets/vendor/` — Leaflet 1.9.3 CSS/JS + layers 아이콘 (BSD-2-Clause 고지 포함). 대시보드를 오프라인에서 열기 위해 `dashboard._use_offline_assets()` 가 head에 인라인한다. 발표장 네트워크 장애 대비이므로 CDN 링크로 되돌리지 말 것.

### External Services
- 공공데이터포털(data.go.kr) — 기상청 ASOS 시간자료(15057210)
- 도로교통공단 TAAS(taas.koroad.or.kr/gis) — 사고분석 엑셀. **API 없음, 수동 다운로드** (`data/README.md`)
- ~~사망교통사고 정보(15070340)~~ — 2026-07-14 기준 **파기됨**. 되살리려 하지 말 것.

<!-- MANUAL: 이 줄 아래에 직접 추가한 메모는 재생성 시 보존됩니다 -->
