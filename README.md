# weather-crash-risk

서울시 자치구별 **심각(사망·중상) 교통사고**를 기상조건과 결합해 **기상조건별 사고 위험의 시간층화(temporal stratification) 분석**을 수행하고, 자치구 지도 대시보드로 시각화하는 프로젝트입니다. (대학 빅데이터 기획 PBL)

## 무엇을 하는가

서울시에서 발생한 **심각(사망·중상) 교통사고**를 사고 시점의 기상상태(맑음/비/눈)로 나누고, 각 기상의 **노출시간(ASOS 기준 실제로 맑음·비·눈이었던 시간수)** 으로 나눈 **노출보정 상대위험**을 자치구별로 산출합니다.

핵심 지표: **상대위험(RR) = (비/눈일 때 사고율) ÷ (맑을 때 사고율)** — "비/눈일 때 맑을 때보다 사고 위험이 몇 배인가".

> ⚠️ 이 지표는 "기상이 어느 *구역*을 더 위험하게 만드는가"(공간 gradient)가 아니라, **한 구역 내부의 기상조건별 상대위험**(시간층화)입니다. 도심 관측소 밀도가 낮아 구역 간 기상이 사실상 동일하기 때문입니다.

## 현재 상태

| 항목 | 상태 |
|---|---|
| 수집 → 분석 → 대시보드 → 자동검증 | ✅ 전 구간 동작 |
| 노출(ASOS) 2007~2025 | ✅ 228개월 수집 완료 (166,559h, 커버리지 100.00%) |
| 사고(TAAS) 2007~2025 | ⏳ 재수집 중 |
| 커밋된 `outputs/dashboard.html`·`zone_weather_risk.csv` | 이전 창(**2014~2023**) 산출물 — 재수집 후 갱신 |
| 테스트 / 린트 | 91 passed · ruff clean · GitHub Actions |

분석 기간을 **2014~2023 → 2007~2025(19년)** 로 확장했습니다. 눈 표본이 이 지표의 병목이었기 때문입니다(10년 기준 눈 사고 325건, 25개 구 중 16개가 소표본 경고). 근거와 이력은 [`docs/decisions-log.md`](docs/decisions-log.md) 참조.

## 데이터 출처 및 저작자 표시

본 프로젝트는 아래 공공데이터를 이용하며, 각 제공기관이 요구하는 **출처표시** 조건에 따라 저작자를 명시합니다. 원천 데이터 파일은 저장소에 포함하지 않습니다.

| 데이터 | 제공기관 (저작자) | 출처 | 이용조건 |
|---|---|---|---|
| 교통사고(사망·중상) 개별 정보 | **도로교통공단** | 교통사고분석시스템(TAAS), https://taas.koroad.or.kr — 공공데이터포털 데이터셋 `15075668`(교통사고 GIS정보)을 통해 개방 | 출처표시 |
| 지상(종관, ASOS) 시간자료 | **기상청** | 공공데이터포털 「기상청_지상(종관, ASOS) 시간자료 조회서비스」, 데이터셋 `15057210` | 출처표시 |
| 서울시 자치구 경계 | 통계청(통계지리정보) 기반 | `southkorea/seoul-maps` (KOSTAT 2013) | 출처표시 |

> 데이터 저작권은 각 제공기관에 있으며, 본 저장소는 공공데이터포털 및 각 기관의 **출처표시** 이용허락범위를 준수합니다.
> 상세 재현정보(데이터셋 ID·수집 조건·요청 파라미터)는 [`docs/data-provenance.md`](docs/data-provenance.md) 참조.

## 데이터 설계 요약 (실측 기반 확정)

- **분석 단위**: 서울 25개 자치구. 사고 개별 데이터에 위경도가 없어 자치구까지만 제공되므로, 다발지역 폴리곤 단위 대신 자치구 단위로 확정.
- **사고(분자)**: TAAS 사고분석 엑셀, 사망+중상, 2007~2025. 기상상태는 **경찰 기록값**을 사용.
- **노출(분모)**: 기상청 ASOS 서울(지점 108) 시간자료로 맑음/비/눈 노출시간 산출.
- **기상범주**: 맑음(맑음+흐림, 비강수) / 비 / 눈 / 기타(안개·결측 = 상대위험 제외).

## 기술 스택

- **분석**: Python (pandas) — 시간축 KST 고정, 신뢰구간은 Byar 근사 + 로그척도 MOVER (scipy 미사용)
- **시각화**: folium(Leaflet) 자치구 choropleth + 기상 필터 레이어 토글, **레이어별 분위수 색상**
- **품질 게이트**: pytest 91개 + ruff, GitHub Actions에서 실행
- **배포**: Docker (`docker compose up`) — 비루트 실행, 헬스체크 포함

## 프로젝트 문서

**현행 사양** (이 둘이 기준입니다)
- 분석 방법론: [`docs/methodology.md`](docs/methodology.md) — 지표 정의·분류규칙·CI·한계
- 데이터 재현정보: [`docs/data-provenance.md`](docs/data-provenance.md) — 데이터셋 ID·수집조건·단계별 재현·검증 목록
- 결정 로그: [`docs/decisions-log.md`](docs/decisions-log.md) — 무엇을 왜 그렇게 정했는가 (데이터 소스 변경·기간 확장 이력 포함)

**전환 이전 문서** (⚠️ 현행과 어긋나는 서술이 있습니다 — 위 문서가 우선)
- [`docs/implementation-plan.md`](docs/implementation-plan.md), [`docs/requirements-spec.md`](docs/requirements-spec.md)

## 주요 한계 (정직성)

- **공간 gradient 아님**: 지표는 구역 간 절대 비교가 아니라 구역 내부의 기상조건별 시간층화 상대위험.
- **기상 출처 이원화**: 사고의 기상분류는 경찰 정성 기록(TAAS), 노출시간은 ASOS 정량 관측 → 분류 기준이 완전히 동일하지 않아 **눈 RR이 상향 편향**될 수 있음.
- **눈 소표본**: 눈 노출은 19년간 477시간(전체의 0.29%)에 불과. 소표본 셀은 반투명·점선으로 표기하고 신뢰구간을 함께 제시.
- **노출편향**: 통행량 미보정 → 노출시간 정규화로 부분 완화.
- **결측이 맑음에 흡수됨**: ASOS가 "강수 없음"과 "관측 결측"을 구분하지 않아 결측 시간이 맑음 분모에 포함됨(커버리지 100%라 실질 영향은 미미).

## 조용히 틀리는 것을 막는 장치

이 지표는 `사고건수 ÷ 노출시간` 이라 입력이 어긋나도 **에러 없이 그럴듯한 숫자**가 나옵니다. 그래서 파이프라인이 실행 중 다음을 검사합니다 (상세: [`docs/data-provenance.md`](docs/data-provenance.md) §7.1).

| 검사 | 실패 시 |
|---|---|
| 사고 기간 ↔ ASOS 기간 월 단위 일치 | **중단** (산출물 미갱신) |
| 기상 필터 전환 시 위험 분포가 실제로 달라짐 (AC7) | **중단** |
| 대시보드에 외부 CDN 참조가 남았는지 | **중단** |
| 심각도 혼입(경상 등), ASOS 커버리지, 잘린 월 파일, 사고 구간 공백 | 경고 |

## 빠른 실행 (Docker)

가장 간단한 방법 — Docker만 있으면 대시보드가 바로 뜹니다.

```bash
docker compose up --build      # 이미지 빌드 + 실행
# 브라우저에서 http://localhost:8000 접속 → 자치구 위험 지도
```

중지: `docker compose down`. 포트를 바꾸려면 `docker-compose.yml`의 `8000:8000`을 수정하세요.

> 🔌 **오프라인 동작**: 대시보드는 Leaflet을 HTML에 인라인해 두어 **네트워크 없이도 열립니다**
> (배경 지도 타일만 비고 자치구 폴리곤·범례·구 이름·레이어 토글은 정상 표시). 발표장 네트워크
> 장애에 대비한 장치입니다. `outputs/dashboard.html` 을 브라우저로 직접 열어도 됩니다.

> 기본은 저장소에 포함된 대시보드를 서빙합니다. **원천 데이터에서 재생성**하려면
> `docker-compose.yml`의 `volumes`를 활성화하고 `RUN_PIPELINE=1 docker compose up`으로 실행하세요.

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

`.env` 의 `START_YEAR`/`END_YEAR`(기본 2007/2025)가 **ASOS 수집 범위 = 상대위험의 분모 기간**을 결정합니다. 사고 데이터 기간과 반드시 같게 두세요.

### 3. 데이터 준비
```bash
# 사고: TAAS(taas.koroad.or.kr/gis) → 사고분석 → 지역별
#   조건: 서울특별시 / 시군구=전체 / 심각도=사망+중상 / 2007~2025 각 연도
#   → data/raw/accidents/사고분석-YYYY.xlsx  (19개 파일)
python -m src.collect.fetch_weather    # ASOS 시간자료 → data/raw/weather/ (228개월, 20~40분)
```

> ⚠️ 시군구를 특정 구로 두면 **그 구만** 받아집니다(드롭다운 첫 항목이 기본 선택될 수 있음).
> 자치구 경계 GeoJSON은 저장소에 포함되어 있어 별도 조치가 필요 없습니다.

### 4. 입력 점검 (파이프라인 실행 전)
```bash
python -m src.analysis.accidents    # [구] 25개 / 사고내용이 사망·중상만인지 확인
python -m src.analysis.exposure     # 노출시간·관측기간 확인
```

### 5. 분석 & 대시보드
```bash
python -m src.analysis.pipeline        # 노출 분류 → 구×기상 상대위험 → 대시보드 + 자동검증
python -m src.serve                    # http://localhost:8000 에서 대시보드 서빙
```

## 개발

```bash
pytest                    # 91 tests
ruff check src tests
```

기여·수정 시 규약은 각 디렉토리의 `AGENTS.md` 를 참조하세요 (루트 → `src/` → `src/analysis/` 계층).

## 라이선스

코드는 [MIT](LICENSE). 교통사고·기상 데이터는 저장소에 포함되지 않으며, 각 제공기관(도로교통공단·기상청)의 공공데이터 이용범위(**출처표시**)를 준수합니다.
벤더링된 Leaflet은 BSD-2-Clause — [`assets/vendor/LICENSE-leaflet.txt`](assets/vendor/LICENSE-leaflet.txt).
