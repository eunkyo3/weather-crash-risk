# data/ 디렉토리

원천 데이터(사고 엑셀·ASOS JSON)는 저장소에 포함되지 않습니다(`.gitignore`). 다만 **자치구 경계
GeoJSON과 분석 결과 CSV는 예외로 커밋**되어 있어, clone 직후 `docker compose up` 만으로
대시보드를 띄울 수 있습니다. 아래 구조로 수집됩니다.

```
data/
├── raw/
│   ├── accidents/               # 교통사고 데이터 (수동 다운로드 필요)
│   │   └── 사고분석-YYYY.xlsx   # TAAS 사고분석 엑셀 (사망+중상, 2007~2025)
│   ├── weather/                 # ASOS 시간자료 JSON (API 자동 수집)
│   │   └── asos_108_YYYYMM.json
│   └── boundaries/              # 서울시 자치구 경계 (필수, 저장소에 포함됨)
│       └── seoul_gu.geojson     # ✅ 커밋되어 있음 — 별도 다운로드 불필요
├── processed/                   # 분석 결과 (파이프라인 생성)
│   └── zone_weather_risk.csv    # 자치구×기상 상대위험 테이블 (✅ 커밋되어 있음)
└── cache/                       # 중간 캐시 (gitignore)
```

## 데이터 출처 및 수집 방법

상세 정보는 [`docs/data-provenance.md`](../docs/data-provenance.md) 참조.

### 1. 교통사고 데이터 (분자)

**TAAS 사고분석 시스템** — 도로교통공단 교통사고분석시스템 GIS 조회로 다운로드

- **출처**: https://taas.koroad.or.kr/gis → 조건검색 → 목록보기 → **엑셀 다운로드**
- **데이터셋**: 공공데이터포털 15075668 (교통사고 GIS정보)
- **선택 조건**: 도시=서울, **시군구=전체**, 심각도=**사망 + 중상**, 연도=2007~2025 (각 연도별 별도 다운로드, 19개 파일)
  - ⚠️ 시군구를 특정 구로 두면 그 구만 받아진다(드롭다운 첫 항목이 기본 선택될 수 있음). 받은 뒤 `시군구` 고유값이 25개인지 확인할 것
- **필수 컬럼**: 발생년월, 시군구(자치구명), 기상상태(경찰 기록값)
- **비포함**: 위도, 경도, 발생 시각 (지점 좌표 없음 → 분석 단위 자치구로 확정)
- **저장**: `data/raw/accidents/사고분석-YYYY.xlsx` (예: 2023년은 `사고분석-2023.xlsx`)

> ⚠️ **구 데이터 소스 변경**: 개별 사고 CSV (data.go.kr 15070340)는 2026-07-14 기준 폐기됨. 좌표·시각이 있어 초기 폴리곤 기반 설계를 지향했으나, 현행은 자치구 단위로 확정됨.

### 2. 기상 데이터 (분모)

**ASOS 서울(지점 108) 시간자료** — 기상청 공공데이터 API

다음 명령어로 자동 수집:

```bash
python -m src.collect.fetch_weather    # ASOS → data/raw/weather/
```

- **데이터셋**: 공공데이터포털 15057210 「기상청_지상(종관, ASOS) 시간자료 조회서비스」
- **지점**: 서울(108) 주 관측소
- **필수**: 기온, 강수량, 신적설 (눈/비/맑음 분류용)
- **기간**: 2007~2025 (사고 데이터와 **동일해야 함** — 어긋나면 파이프라인이 중단)
- **인증**: `.env` 의 `DATA_GO_KR_SERVICE_KEY` 필요

### 3. 자치구 경계 (필수 — 저장소에 포함됨)

`data/raw/boundaries/seoul_gu.geojson` 은 **커밋되어 있으므로 별도 조치가 필요 없습니다.**
`src/analysis/pipeline.py` 가 이 경로를 필수 입력으로 읽습니다(없으면 대시보드 생성 실패).

- **출처**: [github.com/southkorea/seoul-maps](https://github.com/southkorea/seoul-maps) — KOSTAT 2013 기반 `seoul_municipalities_geo_simple.json`
- **이용조건**: 출처표시
- **필수 속성**: `properties.name` = 자치구명(한글), 25개 feature

실수로 삭제했거나 갱신이 필요하면 아래로 재취득합니다:

```bash
mkdir -p data/raw/boundaries
curl -o data/raw/boundaries/seoul_gu.geojson \
  https://raw.githubusercontent.com/southkorea/seoul-maps/master/kostat/2013/json/seoul_municipalities_geo_simple.json
```

## 재현 절차 요약

```bash
# 0. 환경 준비
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1. 인증키 설정
cp .env.example .env
# .env의 DATA_GO_KR_SERVICE_KEY에 공공데이터포털 인증키 입력

# 2. 데이터 수집
# 2-1. 사고 데이터: TAAS에서 수동 다운로드 후 data/raw/accidents/ 저장
#      (2007~2025 각 연도별 사고분석-YYYY.xlsx, 시군구=전체, 심각도=사망+중상)
# 2-2. 기상 데이터: 자동 수집
python -m src.collect.fetch_weather
# 2-3. 자치구 경계: 이미 커밋되어 있음 (data/raw/boundaries/seoul_gu.geojson) — 조치 불필요

# 3. 분석 및 대시보드 생성
python -m src.analysis.pipeline        # 상대위험 산출 → dashboard.html 생성
```

> 원천 데이터 없이 **대시보드만 확인**하려면 수집 단계를 건너뛰고 `docker compose up --build`
> 또는 `python -m src.serve` 로 커밋된 `outputs/dashboard.html` 을 바로 띄울 수 있습니다.

## 파일 명명 규칙

| 파일 | 내용 |
|---|---|
| `data/raw/accidents/사고분석-YYYY.xlsx` | TAAS 엑셀 (연도별) |
| `data/raw/weather/asos_108_YYYYMM.json` | ASOS 시간자료 (월별 API 응답) |
| `data/processed/zone_weather_risk.csv` | 최종 분석 결과 (자치구×기상×RR) |

---

> 상세한 데이터셋 ID, 수집 일자, 요청 파라미터, 저작권 표시는 [`docs/data-provenance.md`](../docs/data-provenance.md) 및 [`docs/methodology.md`](../docs/methodology.md) 참조.
