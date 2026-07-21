<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-07-21 | Updated: 2026-07-21 -->

# analysis

## Purpose
프로젝트의 분석 엔진. TAAS 사고 엑셀과 ASOS 시간자료를 읽어 **자치구 × 기상범주 시간층화 상대위험(RR)** 을 산출하고, folium 대시보드를 생성한 뒤 수용기준(AC7)을 자동검증한다. 원천 데이터가 없어도 커밋된 `data/processed/zone_weather_risk.csv` 로 대시보드만 재생성할 수 있다.

## Key Files
| File | Description |
|------|-------------|
| `pipeline.py` | 전 구간 오케스트레이션 + AC7 자동검증. **유일한 실행 진입점** (`python -m src.analysis.pipeline`) |
| `risk.py` | RR 산출 + 신뢰구간(Byar 포아송 근사 → 로그척도 MOVER 결합) + 소표본 판정 |
| `accidents.py` | TAAS 엑셀 로더. 구명 정규화, 기상상태 매핑, 중복 제거, 심각도 검증(`check_severity`) |
| `exposure.py` | ASOS JSON 로더. 시간별 기상 분류(`classify_hour`)와 노출시간 집계, 커버리지 진단 |
| `dashboard.py` | folium choropleth 생성. 레이어별 분위수 색상, 범례 교체 스크립트, 오프라인 자산 인라인 |
| `surface_check.py` | 노면상태 × 기상상태 교차검증. **읽기전용 진단** — 파이프라인 산출물을 바꾸지 않는다 |

## Subdirectories
없음.

## For AI Agents

### Working In This Directory

- **분자·분모의 기간이 같아야 한다.** `exposure.load_weather()` 는 디렉토리의 모든 파일을 읽을 뿐 기간 필터가 없어, `data/raw/weather/` 의 파일 구성이 곧 분모 기간이 된다. `pipeline.check_period_alignment()` 가 월 단위로 대조해 어긋나면 `SystemExit(1)` 로 멈춘다 — **이 가드를 우회하거나 경고로 낮추지 말 것.** 기간 불일치는 에러 없이 사고율을 왜곡시키는 부류라, 멈추지 않으면 아무도 알아채지 못한다.
- **분자와 분모의 출처가 다르다.** 사고의 기상범주는 경찰 정성 기록(TAAS `기상상태`), 노출시간은 ASOS 정량 관측이다. 이 비대칭은 알려진 한계이며 `methodology.md` 에 편향 방향까지 문서화되어 있다. 두 분류 규칙 중 한쪽만 바꾸면 대칭이 깨지므로 반드시 함께 검토한다.
- **통계 방법을 바꾸면 근거를 docstring에 남긴다.** `risk.py` 는 Katz 로그근사를 왜 Byar+MOVER로 교체했는지(소표본 CI 과신 보정), `pipeline.py` 는 BH(FDR) 보정을 왜 참고용으로만 출력하는지를 적어 두었다. 이 저장소는 "무엇을 했나"보다 "왜 그렇게 했나"를 남기는 쪽을 택했다.
- **scipy를 도입하지 말 것.** CI 계산은 의도적으로 `math` 만으로 구현되어 있다(Byar 근사가 닫힌형이라 특수함수가 필요 없다). 의존성을 늘리면 Docker 이미지와 CI 설치 시간이 함께 늘어난다.
- **`RISK_CATEGORIES` 와 `BASELINE` 의 단일 출처는 `risk.py`** 다. `accidents.py` 와 `dashboard.py` 가 거기서 임포트한다 — 복제본을 다시 만들지 말 것. 범주를 바꾸면 `accidents._WEATHER_MAP`(TAAS 라벨 접기)과 `exposure.classify_hour`(ASOS 분류)도 **함께** 고쳐야 분자·분모가 대칭을 유지한다.
- `exposure.classify_hour` 는 **항상 맑음/비/눈 중 하나를 반환**한다. 결측과 무강수를 ASOS가 구분하지 않아 '기타' 버킷이 없으며, 이 동작은 테스트로 고정되어 있다. 바꾸려면 `methodology.md` 한계 6번도 함께 갱신한다.
- `dashboard.py` 의 후처리 JS는 **`MacroElement` 로 감싸야 한다.** `Figure.script` 에 직접 붙이면 folium의 지도 생성 코드보다 먼저 렌더되어 `map_xxx` 가 undefined 인 채 실행된다(실제로 겪은 버그).

### Testing Requirements
- `pytest`(루트에서) — 합성 데이터 기반이라 원천 데이터나 네트워크 없이 돌아간다.
- 대시보드를 고쳤다면 **산출 HTML을 파싱해 검증**한다: GeoJSON 레이어 3개, feature 25×3, 범례 패널 3개, 외부 `script src`/`link href` 0건.
- 색상·레이어 로직을 바꿨다면 브라우저 렌더까지 확인하는 것이 안전하다. JS 에러는 정적 검사로 잡히지 않으며, 지도가 통째로 비어도 HTML은 정상으로 보인다.
- `pipeline.verify()` 는 기준 미달 시 `SystemExit(1)` 을 던진다 — 이게 AC7 게이트다. 통과시키려고 임계값(`min_distinct_gu`)을 낮추지 말 것.

### Common Patterns
- 컬럼명은 한글을 그대로 쓴다(`구`, `기상범주`, `사고건수`, `상대위험`, `CI하한`). 산출 CSV가 발표·보고서에 그대로 실리기 때문이다.
- CSV는 `utf-8-sig` 로 쓴다(엑셀에서 한글이 깨지지 않도록).
- **검사의 severity 는 오탐 가능성으로 가른다.**
  - **중단(`SystemExit`)** — 판정이 결정론적이고 오탐이 없으며, 통과시키면 지표가 곧바로 틀어지는 것. 기간 정합성(월 집합 비교), AC7 게이트, 오프라인 보장이 여기 속한다.
  - **경고(`print`)** — 휴리스틱이거나 임계값이 자의적이어서 오탐이 가능한 것. 심각도 라벨 검사(`check_severity`, 연도별 표기 변동 가능), ASOS 커버리지 0.8, 사고 구간 내부 공백(0건인 달은 통계적으로 정상)이 여기 속한다.
  - 경고는 예외가 아니라 `print` 로 알린다 — 데이터 품질 문제로 파이프라인 전체를 죽이지 않되 사용자가 반드시 보게 한다.

## Dependencies

### Internal
- `data/raw/accidents/`, `data/raw/weather/`, `data/raw/boundaries/seoul_gu.geojson` — 입력
- `data/processed/zone_weather_risk.csv`, `outputs/dashboard.html` — 산출
- `assets/vendor/` — Leaflet 오프라인 자산 (`dashboard._use_offline_assets`)

### External
- `pandas` — 전 모듈 / `openpyxl` — 엑셀 읽기
- `folium` + `branca` — 지도 생성, `MacroElement`/`Template`

<!-- MANUAL: -->
