# weather-crash-risk

교통사고 다발지역과 기상 데이터를 융합해 **기상조건별 사고 위험의 시간층화(temporal stratification) 분석**을 수행하고, 지도 대시보드로 시각화하는 프로젝트입니다. (대학 빅데이터 기획 PBL)

## 무엇을 하는가
서울시 교통사고 다발지역에서 발생한 **사망교통사고 건별 발생 시각**을 기준으로 기상 관측 데이터와 결합하여, **"같은 구역 안에서 맑음 대비 비/눈 시간대에 사고율이 얼마나 높아지는가"** 를 노출시간으로 보정한 상대위험으로 산출합니다.

> ⚠️ 이 지표는 "기상이 어느 *구역*을 더 위험하게 만드는가"(공간 gradient)가 아니라, **한 구역 내부의 기상조건별 상대위험**(시간층화)입니다. 도심 관측소 밀도가 낮아 구역 간 기상이 사실상 동일하기 때문입니다.

## 데이터 출처
- 도로교통공단_사망교통사고정보 (건별, 발생 시각·위경도) — 공공데이터포털
- 도로교통공단_교통사고다발지역 (폴리곤) — 공공데이터포털
- 기상청 종관기상관측(ASOS) 시간자료 (+ AWS 보조) — 기상자료개방포털

## 기술 스택
- **분석**: Python (pandas, geopandas — `sjoin_nearest`, `merge_asof`), 시간축 KST 고정
- **저장/실행**: PostgreSQL + PostGIS (**Docker Compose** — `docker compose up`)
- **시각화**: Leaflet + 카테고리별 정적 GeoJSON (기상 필터 토글)

## 프로젝트 문서
- 요구사항 스펙: [`docs/requirements-spec.md`](docs/requirements-spec.md)
- 구현 계획 (Planner/Architect/Critic 합의): [`docs/implementation-plan.md`](docs/implementation-plan.md)
- 결정 로그 (deep-interview + grill): [`docs/decisions-log.md`](docs/decisions-log.md)

## 주요 한계 (정직성)
- 사망사고 한정 표본 → 소표본 셀은 신뢰구간·경고 표기
- 노출편향(통행량 미보정) → 노출시간 정규화로 부분 완화
- 눈(적설)은 ASOS 관측소 의존

## 시작하기

### 1. 환경 준비
```bash
python -m venv .venv
./.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # macOS/Linux
```

### 2. 인증키 설정
```bash
cp .env.example .env
# .env 의 DATA_GO_KR_SERVICE_KEY 에 공공데이터포털 디코딩 인증키 입력
# (기상청 ASOS 15057210 + 도로교통공단 다발지역 15057467/15105289 활용신청 필요)
```

### 3. 데이터 수집
```bash
python -m src.collect.fetch_hotspots   # 다발지역 폴리곤 → data/raw/hotspots/
python -m src.collect.fetch_weather    # ASOS 시간자료  → data/raw/weather/
# 사망사고 건별 CSV 는 수동 다운로드 (data/README.md 참고)
```

> 이후 단계(Phase 0 타당성 스파이크 → PostGIS 적재 → 대시보드)는
> [`docs/implementation-plan.md`](docs/implementation-plan.md) 참고.

## 라이선스
코드는 [MIT](LICENSE). 교통사고·기상 데이터는 저장소에 포함되지 않으며 공공데이터 이용범위(출처표시)를 준수합니다.
