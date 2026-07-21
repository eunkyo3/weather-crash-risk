<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-07-21 | Updated: 2026-07-21 -->

# data

## Purpose
데이터가 놓이는 위치. **원천 데이터는 저장소에 커밋되지 않는다** — `.gitignore` 가 `data/raw/accidents/`, `data/raw/weather/`, `data/cache/`, `*.csv`, `*.geojson`, `*.parquet` 를 제외한다. 다만 하단 negation 규칙으로 **`raw/boundaries/seoul_gu.geojson` 과 `processed/zone_weather_risk.csv` 두 개만 예외로 커밋**된다(clone 직후 Docker 데모가 동작해야 하므로). 나머지는 수집 스크립트 실행 또는 수동 다운로드로 각자 재현한다.

## Key Files
| File | Description |
|------|-------------|
| `README.md` | 디렉토리 구조도, ASOS 자동 수집 실행법, TAAS 엑셀 수동 다운로드 절차와 필수 컬럼 |

## Subdirectories
대부분 런타임 생성이라 git에 추적되지 않는다 — AGENTS.md를 두지 않는다. 단 아래 표의
✅ 두 파일은 예외로 커밋된다.

| Directory | Purpose |
|-----------|---------|
| `raw/accidents/` | TAAS 사고분석 엑셀(`사고분석-YYYY.xlsx`, 사망+중상). **수동 다운로드** |
| `raw/weather/` | ASOS 시간자료 JSON. `fetch_weather.py` 자동 생성 |
| `raw/boundaries/` | ✅ `seoul_gu.geojson` — 자치구 경계. 파이프라인 필수 입력, **커밋됨** |
| `processed/` | ✅ `zone_weather_risk.csv` — 구×기상 상대위험 테이블. **커밋됨** |
| `raw/hotspots/` | (구설계 잔재) KOROAD 다발지역 폴리곤. 현행 분석 경로에서는 미사용 |
| `cache/` | 단계 간 중간 산출물 |

## For AI Agents

### Working In This Directory
- **원천 데이터를 커밋하지 않는다.** 사고 엑셀·ASOS JSON은 `.gitignore` 제외 규칙을 우회하거나 `git add -f` 하지 않는다. 공공데이터 재배포 문제와 저장소 비대화를 피하기 위한 결정이다.
- **예외 2건은 의도적으로 커밋된다** — `raw/boundaries/seoul_gu.geojson`(재배포 가능한 공개 경계 데이터, 파이프라인 필수 입력)과 `processed/zone_weather_risk.csv`(원천이 아닌 분석 산출물). clone 직후 `docker compose up` 이 동작하려면 둘 다 필요하다. `.gitignore` 하단의 negation 규칙으로 허용되어 있으니 지우지 말 것.
- 디렉토리가 비어 있는 것은 정상이다. 파일이 없다고 수집이 실패했다고 단정하지 말고, `.env` 인증키 설정 여부부터 확인한다.
- 경로를 코드에 문자열로 박지 않는다. `settings.raw_dir` / `settings.cache_dir` 를 쓰면 `.env` 의 `RAW_DIR`/`CACHE_DIR` 로 재배치할 수 있다.
- 파일명 규약을 유지한다 — 자동 수집물은 `{데이터셋}_{식별자}_{기간}.json` 형태다 (`frequentzoneLg_11_2023.json`, `asos_108_202301.json`). 이후 단계가 파일명에서 연도·관측소를 읽는다.
- 새 데이터 종류를 추가하면 `README.md` 의 구조도와 `.gitignore` 규칙을 함께 갱신한다.
- **사고 데이터는 API가 없다.** 자동 수집 코드를 만들려 하지 말고 `README.md` 의 수동 절차를 따른다 (TAAS GIS → 조건검색 → 엑셀 다운로드, 연도별 파일). 연도별로 컬럼 라벨이 다를 수 있으니 로더는 방어적으로 쓴다.
- ⚠️ **`data.go.kr 15070340`(개별 사망사고 CSV)을 되살리려 하지 말 것.** 2026-07-14 기준 **파기**되어 페이지 자체가 열리지 않는다. 이 프로젝트가 자치구 단위로 설계된 이유가 바로 그것이며, 대체 소스(TAAS 집계본)에는 **위경도와 발생시각이 없다**. 근거: `docs/decisions-log.md` "데이터 소스 변경".

### Testing Requirements
- 수집 검증은 파일 존재 + 항목 수 확인으로 한다. 예: `python -c "import json,glob; [print(p, len(json.load(open(p,encoding='utf-8')))) for p in glob.glob('data/raw/weather/*.json')]"`
- 한 달치 ASOS는 시간당 1행이므로 약 672~744행이 정상이다. 크게 모자라면 페이지네이션이 조기 종료된 것이다.
- TAAS 사고 엑셀은 필수 컬럼(**발생년월**, **시군구**, **기상상태**, 사고내용, 사고유형, 구분번호)이 있는지부터 확인한다. **위경도·발생시각(시)은 이 소스에 없다** — 그래서 분석 단위가 자치구이고 사고의 기상은 경찰 기록값을 쓴다.
- 심각도가 섞이면 분자가 조용히 부풀려진다. `load_accidents()` 가 `check_severity()` 로 `사고내용` 분포를 검사해 경고하니 그 출력을 확인한다.

### Common Patterns
- 수집물은 API 응답 그대로의 JSON 배열이다. 원본을 손대지 않고 보존하며, 정제는 이후 단계에서 별도 파일로 만든다.
- 인코딩은 UTF-8 고정 (`save_json` 이 `ensure_ascii=False`, `encoding="utf-8"` 로 기록). 산출 CSV는 엑셀 호환을 위해 `utf-8-sig` 로 쓴다.

## Dependencies

### Internal
- `src/collect/` — `raw/weather/` 에 쓰는 주체 (see `../src/collect/AGENTS.md`)
- `src/analysis/` — `raw/` 를 읽고 `processed/` 에 쓰는 주체 (see `../src/analysis/AGENTS.md`)
- `config/settings.py` — `raw_dir`, `cache_dir` 경로 결정

### External
- 기상청 ASOS 시간자료 — 공공데이터포털 `15057210` (API)
- 도로교통공단 TAAS 사고분석 — `taas.koroad.or.kr/gis` (수동 엑셀), 포털 등재 `15075668`
- 자치구 경계 — `southkorea/seoul-maps` (KOSTAT 2013)
- ~~`15070340`(개별 사망사고)~~ — **파기됨**. ~~`15057467`/`15105289`(다발지역)~~ — 현행 분석 경로에서 미사용

<!-- MANUAL: -->
