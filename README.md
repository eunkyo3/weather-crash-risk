# weather-crash-risk

서울시 자치구별 **심각(사망·중상) 교통사고**를 기상조건과 결합해 **기상조건별 사고 위험의 시간층화(temporal stratification) 분석**을 수행하고, 자치구 지도 대시보드로 시각화하는 프로젝트입니다. (대학 빅데이터 기획 PBL)

## 무엇을 하는가

서울시에서 발생한 **심각(사망·중상) 교통사고**를 사고 시점의 기상상태(맑음/비/눈)로 나누고, 각 기상의 **노출시간(ASOS 기준 실제로 맑음·비·눈이었던 시간수)** 으로 나눈 **노출보정 상대위험**을 자치구별로 산출합니다.

핵심 지표: **상대위험(RR) = (비/눈일 때 사고율) ÷ (맑을 때 사고율)** — "비/눈일 때 맑을 때보다 사고 위험이 몇 배인가".

> ⚠️ 이 지표는 "기상이 어느 *구역*을 더 위험하게 만드는가"(공간 gradient)가 아니라, **한 구역 내부의 기상조건별 상대위험**(시간층화)입니다. 도심 관측소 밀도가 낮아 구역 간 기상이 사실상 동일하기 때문입니다.

## 데이터 출처 및 저작자 표시

본 프로젝트는 아래 공공데이터를 이용하며, 각 제공기관이 요구하는 **출처표시** 조건에 따라 저작자를 명시합니다. 원천 데이터 파일은 저장소에 포함하지 않습니다.

| 데이터 | 제공기관 (저작자) | 출처 | 이용조건 |
|---|---|---|---|
| 교통사고(사망·중상) 개별 정보 | **도로교통공단** | 교통사고분석시스템(TAAS), https://taas.koroad.or.kr — 공공데이터포털 데이터셋 `15075668`(교통사고 GIS정보)을 통해 개방 | 출처표시 |
| 지상(종관, ASOS) 시간자료 | **기상청** | 공공데이터포털 「기상청_지상(종관, ASOS) 시간자료 조회서비스」, 데이터셋 `15057210` | 출처표시 |
| 서울시 자치구 경계 | 통계청(통계지리정보) 기반 | `southkorea/seoul-maps` (KOSTAT 2013) | 출처표시 |
| (선택) 교통사고 다발지역 폴리곤 | 도로교통공단 | 공공데이터포털 데이터셋 `15057467` | 출처표시 |

> 데이터 저작권은 각 제공기관에 있으며, 본 저장소는 공공데이터포털 및 각 기관의 **출처표시** 이용허락범위를 준수합니다.
> 상세 수집 재현정보(데이터셋 ID·수집일·요청 파라미터)는 [`docs/decisions-log.md`](docs/decisions-log.md) 참조.

## 데이터 설계 요약 (실측 기반 확정)

- **분석 단위**: 서울 25개 자치구. (사고 개별 데이터에 위경도가 없어 자치구까지 제공 → 다발지역 폴리곤 단위 대신 자치구 단위)
- **사고(분자)**: TAAS 사고분석 엑셀, 사망+중상, 2014~2023 (약 80,000건). 기상상태는 경찰 기록값을 사용.
- **노출(분모)**: 기상청 ASOS 서울(지점 108) 시간자료로 맑음/비/눈 노출시간 산출.
- **기상범주**: 맑음(맑음+흐림, 비강수) / 비 / 눈 / 기타(안개·결측=상대위험 제외).

## 기술 스택

- **분석**: Python (pandas) — 시간축 KST 고정
- **시각화**: folium(Leaflet) 자치구 choropleth + 기상 필터 레이어 토글
- (선택) PostGIS 적재는 포트폴리오용 후순위 — MVP는 정적 산출물로 충분

## 프로젝트 문서

- 요구사항 스펙: [`docs/requirements-spec.md`](docs/requirements-spec.md)
- 구현 계획 (Planner/Architect/Critic 합의): [`docs/implementation-plan.md`](docs/implementation-plan.md)
- 결정 로그 (deep-interview + grill + 데이터 소스 변경): [`docs/decisions-log.md`](docs/decisions-log.md)

## 주요 한계 (정직성)

- **공간 gradient 아님**: 지표는 구역 간 절대 비교가 아니라 구역 내부의 기상조건별 시간층화 상대위험.
- **기상 출처 이원화**: 사고의 기상분류는 경찰 정성 기록(TAAS), 노출시간은 ASOS 정량 관측 → 분류 기준이 완전히 동일하지 않음(문서에 명시).
- **눈 소표본**: 눈 관련 사고는 표본이 작아 소표본 경고 스타일로 표기, 신뢰구간 함께 제시.
- **노출편향**: 통행량 미보정 → 노출시간 정규화로 부분 완화.

## 빠른 실행 (Docker)

가장 간단한 방법 — Docker만 있으면 대시보드가 바로 뜹니다.

```bash
docker compose up --build      # 이미지 빌드 + 실행
# 브라우저에서 http://localhost:8000 접속 → 자치구 위험 지도
```

중지: `docker compose down`. 포트를 바꾸려면 `docker-compose.yml`의 `8000:8000`을 수정하세요.

> 기본은 저장소에 포함된 대시보드를 서빙합니다. **원천 데이터에서 재생성**하려면
> `docker-compose.yml`의 `volumes`를 활성화하고 `RUN_PIPELINE=1 docker compose up`으로 실행하세요
> (사고 엑셀 `data/raw/accidents/` + `.env`의 `DATA_GO_KR_SERVICE_KEY` 필요).

## 시작하기 (로컬 Python)

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
# (기상청 ASOS 15057210 활용신청 필요)
```

### 3. 데이터 준비
```bash
# 사고 데이터: TAAS(taas.koroad.or.kr/gis)에서 서울 사망+중상 연도별 엑셀 다운로드
#   → data/raw/accidents/사고분석-YYYY.xlsx
python -m src.collect.fetch_weather    # ASOS 시간자료 → data/raw/weather/
```

### 4. 분석 & 대시보드
```bash
python -m src.analysis.pipeline        # 노출 분류 → 구×기상 상대위험 → 대시보드 HTML
python -m src.serve                    # http://localhost:8000 에서 대시보드 서빙
```

## 라이선스

코드는 [MIT](LICENSE). 교통사고·기상 데이터는 저장소에 포함되지 않으며, 각 제공기관(도로교통공단·기상청)의 공공데이터 이용범위(**출처표시**)를 준수합니다.
