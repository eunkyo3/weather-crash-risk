<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-07-21 | Updated: 2026-07-21 -->

# collect

## Purpose
공공데이터포털(data.go.kr) OpenAPI를 호출해 원본 데이터를 `data/raw/` 아래에 JSON으로 내려받는 수집 계층. 호출 공통 로직(`common.py`)과 데이터셋별 수집기(`fetch_hotspots.py`, `fetch_weather.py`)로 나뉜다. 파이프라인 Phase 1에 해당하며, 여기서 저장된 원본이 이후 모든 분석의 입력이다.

## Key Files
| File | Description |
|------|-------------|
| `common.py` | API 호출 공통 유틸. 재시도·rate-limit·XML 오류 방어·표준 응답 파싱(`get_json`, `extract_items`, `total_count`, `save_json`) |
| `fetch_hotspots.py` | KOROAD 사고다발지역(B552061) 폴리곤을 연도별 수집 → `data/raw/hotspots/{op}_{siDo}_{year}.json` |
| `fetch_weather.py` | 기상청 ASOS 시간자료를 월 단위 수집 → `data/raw/weather/asos_{stn}_{YYYYMM}.json` |
| `__init__.py` | 빈 파일. 패키지 마커 |

## Subdirectories
없음.

## For AI Agents

### Working In This Directory
- **`requests` 를 직접 부르지 않는다.** 모든 호출은 `common.get_json` 을 거친다. 인증키 주입, 재시도, rate-limit sleep, XML 오류 감지가 여기 한 곳에 있다.
- **data.go.kr 특성**: 오류를 JSON이 아닌 XML 바디(`<OpenAPI_ServiceResponse>`)로 돌려준다. `get_json` 은 응답이 `<` 로 시작하면 예외로 올린다. 새 엔드포인트를 붙일 때 이 방어를 우회하지 않는다.
- 인증키는 **디코딩(일반) 키**를 `.env` 에 넣는다. `requests` 가 인코딩하므로 인코딩 키를 넣으면 이중 인코딩되어 `SERVICE_KEY_IS_NOT_REGISTERED` 가 난다.
- **API 호출은 일 한도(개발계정 10,000회)를 소모한다.** 반복 실행으로 디버깅하지 말고, 검증할 때는 `.env` 의 `START_YEAR`/`END_YEAR` 를 한 해로 좁혀 실행한다. `RATE_LIMIT_SLEEP` 기본 0.34초(≈초당 3회)를 임의로 낮추지 않는다.
- `fetch_hotspots.py` 의 `GUGUN_CODES` 는 기본 빈 리스트다. 일부 KOROAD 오퍼레이션이 `siDo` 만으로 오류를 낼 때 서울 시군구 코드를 채우면 구별로 순회 호출한다 — 오류 원인을 확인한 뒤에만 채운다.
- 핫스팟 유형(지자체별 ↔ 보행자)은 코드가 아니라 `.env` 의 `KOROAD_HOTSPOT_OP` 로 전환한다. `settings.koroad_url` 이 `getRest{Op}` 접미사를 조립한다. 정확한 op 이름은 데이터셋 상세페이지의 "요청주소"에서 확인한다.
- 수집 시각은 **KST(관측 로컬시각)** 그대로 저장한다. 수집 단계에서 시간대 변환·정규화를 하지 않는다 — 원본 보존이 원칙이고, 변환은 이후 단계 책임이다.
- 저장 포맷은 API 응답 항목의 리스트를 그대로 담은 JSON이다. 수집 단계에서 컬럼을 고르거나 이름을 바꾸지 않는다.

### Testing Requirements
- 좁은 범위 실제 실행이 기본 검증이다: `.env` 를 한 해(또는 한 달)로 좁히고 `python -m src.collect.fetch_weather` → `data/raw/weather/` 에 파일이 생기고, `print` 의 `누적 N/총계` 가 일치하는지 본다.
- 페이지네이션 수정 시에는 **총계와 누적이 정확히 맞아떨어지는지**를 반드시 확인한다. `fetch_weather` 는 `numOfRows=999`, `fetch_hotspots` 는 `100` 을 쓰며, 누적 계산식(`(page-1)*페이지크기 + len(batch)`)이 이 값과 짝을 이룬다 — 한쪽만 바꾸면 조용히 조기 종료하거나 무한루프가 된다.
- 인증키가 없는 환경에서는 `require_key()` 예외 경로까지만 확인한다.

### Common Patterns
- **페이지네이션 루프**: `while True` 로 `pageNo` 를 증가시키며 `extract_items` 로 배치를 모으고, `batch` 가 비었거나 누적이 `totalCount` 이상이면 종료.
- **단위별 격리 실패**: `main()` 은 연/월 단위로 `try/except` 하고, 실패하면 `print(f"  ! {단위} 수집 실패: {e}")` 후 `continue`. 한 구간 오류가 전체 수집을 중단시키지 않는다.
- **빈 결과는 저장하지 않는다** (`fetch_weather` 의 `if items:`). 빈 JSON 파일이 "수집 완료"로 오인되는 것을 막는다.
- **재시도 백오프**: `get_json` 은 `rate_limit_sleep * 2**attempt` 로 대기하며 `max_retries` 까지 반복하고, 소진되면 마지막 오류를 담아 예외를 올린다.
- 모듈 docstring에 산출 경로·실행 명령·주의사항을 한국어로 명시한다.

## Dependencies

### Internal
- `config.settings` — 인증키, 대상 시도/관측소, 연도 범위, 엔드포인트 URL, 저장 경로, 재시도·rate-limit 값
- `data/raw/hotspots/`, `data/raw/weather/` — 산출 위치 (see `../../data/AGENTS.md`)

### External
- `requests` — HTTP 호출. 모듈 수준 `SESSION` 하나를 재사용한다 (커넥션 재사용 + 고정 User-Agent)

### External APIs
- 기상청 지상(종관, ASOS) 시간자료 조회서비스 — `http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList` (데이터셋 15057210). 주요 항목: `tm`(관측시각), `ta`(기온), `rn`(강수량), `hr3Fhsc`(3시간 신적설), `dsnw`(적설), `ws`(풍속)
- KOROAD 교통사고 다발지역 — `http://apis.data.go.kr/B552061/{op}/getRest{Op}` (데이터셋 15057467 / 15105289)

<!-- MANUAL: -->
