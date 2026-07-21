# data/ 디렉토리

실제 데이터 파일은 저장소에 포함되지 않습니다(`.gitignore`). 아래 구조로 수집됩니다.

```
data/
├── raw/
│   ├── accidents/               # 교통사고 데이터 (수동 다운로드 필요)
│   │   └── 사고분석-YYYY.xlsx   # TAAS 사고분석 엑셀 (사망+중상, 2014~2023)
│   ├── weather/                 # ASOS 시간자료 JSON (API 자동 수집)
│   │   └── asos_108_YYYYMM.json
│   └── boundaries/              # 서울시 자치구 경계 (선택, 기본 내장)
│       └── seoul_districts.geojson
├── processed/                   # 분석 결과 (자동 생성)
│   └── zone_weather_risk.csv    # 자치구×기상 상대위험 테이블
└── cache/                       # 중간 캐시 (gitignore)
```

## 데이터 출처 및 수집 방법

상세 정보는 [`docs/data-provenance.md`](../docs/data-provenance.md) 참조.

### 1. 교통사고 데이터 (분자)

**TAAS 사고분석 시스템** — 도로교통공단 교통사고분석시스템 GIS 조회로 다운로드

- **출처**: https://taas.koroad.or.kr/gis → 조건검색 → 목록보기 → **엑셀 다운로드**
- **데이터셋**: 공공데이터포털 15075668 (교통사고 GIS정보)
- **선택 조건**: 도시=서울, 심각도=**사망 + 중상**, 연도=2014~2023 (각 연도별 별도 다운로드)
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
- **기간**: 2014~2023 (사고 데이터와 동일)
- **인증**: `.env` 의 `DATA_GO_KR_SERVICE_KEY` 필요

### 3. 자치구 경계 (선택 사항)

저장소에 미포함된 경우 외부 소스로 보충:

```bash
# 예: github.com/southkorea/seoul-maps 또는 통계청 지형 DB
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
#      (2014~2023 각 연도별 사고분석-YYYY.xlsx)
# 2-2. 기상 데이터: 자동 수집
python -m src.collect.fetch_weather

# 3. 분석 및 대시보드 생성
python -m src.analysis.pipeline        # 상대위험 산출 → dashboard.html 생성
```

## 파일 명명 규칙

| 파일 | 내용 |
|---|---|
| `data/raw/accidents/사고분석-YYYY.xlsx` | TAAS 엑셀 (연도별) |
| `data/raw/weather/asos_108_YYYYMM.json` | ASOS 시간자료 (월별 API 응답) |
| `data/processed/zone_weather_risk.csv` | 최종 분석 결과 (자치구×기상×RR) |

---

> 상세한 데이터셋 ID, 수집 일자, 요청 파라미터, 저작권 표시는 [`docs/data-provenance.md`](../docs/data-provenance.md) 및 [`docs/methodology.md`](../docs/methodology.md) 참조.
