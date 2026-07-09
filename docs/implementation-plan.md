# Work Plan: 교통사고 다발지역 × 기상 융합 시간층화 위험분석 대시보드

> Source spec: `.omc/specs/deep-interview-traffic-accident-weather-risk.md` (Ambiguity 14.5%)
> Status: **PENDING APPROVAL** — 합의 도달 (Architect: SOUND-WITH-CHANGES / Critic iter1: REJECT → iter2: **APPROVE**, MF1~MF7 해결 + 비차단 개선 4건 반영). 실행은 별도 명시 승인 필요.

## Requirements Summary
서울특별시의 교통사고 다발지역에서 발생한 사망교통사고 건별 발생 시각을 기준으로 기상 관측 데이터와 결합하여, **"같은 구역 안에서 기상조건(맑음/비/눈)에 따라 사고 위험이 어떻게 달라지는가"를 노출시간으로 보정한 시간층화 상대위험**으로 산출하고, 기상 필터 토글로 위험 분포 변화를 보여주는 지도 대시보드를 만든다. (대학 빅데이터 기획 PBL — 산출물: 동작 프로토타입 + 기획 문서)

> **⚠️ 핵심 재정의 (MF1):** 이 지표는 "기상이 어느 *구역*을 더 위험하게 만드는가"(공간 gradient)가 **아니다**. 서울 도심 ASOS 관측소가 소수여서 구역 간 기상은 거의 동일하다. 따라서 정당하게 말할 수 있는 것은 **"한 구역 내부에서, 비/눈 시간대에 발생한 사고율이 맑은 시간대 대비 얼마나 높은가"(시간층화)** 이다. 지도 색은 이 구역별 시간층화 상대위험을 표현하며, 구역 간 절대 비교가 아님을 문서·범례에 명시한다.

## RALPLAN-DR Summary (short mode)

### Principles
1. **통계적 정직성 우선** — 표본이 작으면 화려한 지수보다 한계 명시가 신뢰를 만든다.
2. **데이터 가용성이 설계를 지배한다** — 확보 가능한 데이터 형태 + 실측된 신호량에 아키텍처를 맞춘다.
3. **MVP 우선** — 지도+기상필터 토글이 동작하면 성공. 나머지는 부가.
4. **기획 PBL 이중 산출물** — 코드와 기획 문서를 함께 낸다.
5. **재현 가능성** — 데이터셋 ID·엔드포인트·분류규칙을 명시하고 배치 스크립트로 자동화.

### Decision Drivers (top 3)
1. 사망사고 건별 표본이 작다 → **신호 존재를 스키마 전에 검증**하는 것이 최우선
2. ASOS 관측소 저밀도 → 공간 gradient 불가 → 시간층화로 재정의
3. 산출물이 동작 대시보드 → 필터 토글이 실제로 갱신되어야 함

### Viable Options (재탐색 — MF6)
**Option A — 배치 ETL을 SQL로 + PostGIS + FastAPI + Leaflet 3층**
- Pros: 공간SQL 포트폴리오, 서빙 계층 명확
- Cons: 정적·소량 데이터에 3층 write-path 과설계, MVP 우선 원칙과 긴장

**Option B — Python/geopandas 분석 + folium/kepler.gl 정적 지도**
- Pros: 구현 부담 최소. `sjoin_nearest`(최근접), `merge_asof`(시간+결측 tolerance 동시 해결), groupby 집계가 PostGIS 연산을 그대로 대체. **folium LayerControl / kepler.gl 필터로 AC7 토글을 백엔드 없이 충족**
- Cons: 공간SQL 산출물이 약함(포트폴리오 관점)

**선택: Option C — 합의 시너지 (Architect·Critic 권장)**
> **Python/geopandas 분석 엔진** → 결과를 **PostGIS 평문 테이블**로 적재(공간SQL 산출물 보존) → **카테고리별 정적 GeoJSON** 서빙(Leaflet). 무거운 write-path를 제거하면서 동작 대시보드와 공간SQL 산출물을 모두 확보. matview 미사용.

*Option A 무효화 근거:* 데이터가 정적·소량(백만 행 미만, 메모리 적재 가능)이고 데모 시점 동적 쿼리가 없어 SQL ETL의 이점이 없음. Option B 단독 무효화 근거: 공간SQL 학습·포트폴리오 요건(사용자 원 구상)을 버리게 됨. → C가 양쪽 흡수.

## Phase 0 — 타당성 스파이크 (스키마 전 필수 게이트, MF2/MF5)
1. **대상 도시 확정: 서울특별시.** 선정 기준: (a) 전국 최다 사망사고 표본, (b) 도심 ASOS 지점(지점번호 108 서울) + 다수 AWS 존재, (c) 다발지역 데이터 밀집. 스파이크 결과가 기준 미달이면 부산으로 대체 검토.
2. **겹침 카운트 스파이크**: 서울 사망사고 건별 ∩ 다발지역 폴리곤 ∩ {맑음/비/눈} 셀별 건수를 실측(파이썬, 스키마 없이 CSV로).
3. **게이트 판정 (임계값 명시)**:
   - 각 기상범주 × 구역 셀의 비어있지 않은 셀 수, 특히 **눈 범주 총 사고건수 < 30** 이면 → **1차 분석단위를 다발지역 폴리곤 → 시군구/도로유형 집계**로 승격(폴리곤은 표시 오버레이로 강등). 
   - 5~10년 누적 창이 데이터셋 보존기간에 실제 존재하는지 확인(사망사고 건별 피드 시작연도 체크).
4. 확정된 단위·기간·도시를 기획 문서 "데이터 근거"에 기록.

## Acceptance Criteria (testable)
- [ ] AC1: 서울 다발지역(또는 게이트 후 시군구/도로유형) + 사망사고 건별이 PostGIS에 적재, `count(*)` 확인
- [ ] AC2: 각 사망사고 레코드에 **사고점 기준** 최근접 관측소 ID가 채워짐(시간 매칭용); 각 구역에 **중심점 기준** 대표 관측소 ID가 채워짐(노출 분모용) — 둘은 분리 (MF1/finding5)
- [ ] AC3: 각 사망사고 시각(KST)에 관측소 정시 기상이 매핑됨. 결측 시 ±1h tolerance 우선, 그래도 없으면 `데이터없음` 범주로 **라벨**(NULL 아님) — 데이터갭은 실패가 아니라 명시 버킷 (MF4)
- [ ] AC4: 기상범주별 노출시간이 **구역 대표 관측소** 기준으로 계산됨 (분자·분모 동일 분류규칙 사용)
- [ ] AC5: 구역 × 기상범주 시간층화 상대위험 = (사고건수 ÷ 노출시간) 산출. **"같은 구역 내 범주 간 비교"** 로 문서화 (MF1)
- [ ] AC6: 지도에서 구역 위험도가 색 표시, 클릭 시 건수·표본수·상대위험·신뢰구간 표시
- [ ] AC7 (MVP 핵심, 자동검증): 기상 필터 {맑음/비/눈} 전환 시 각 레이어가 비어있지 않고(**K≥3 색칠 구역**, 시군구 승격 시 K는 단위 수에 맞춰 재설정), **1차 게이트 = 범주 간 구역별 상대위험 *값*이 ≥K개 구역에서 달라짐**(스펙 요건 "위험 분포가 실제로 바뀜"을 직접 충족). 2차(nice-to-have) = 순위 변화. GeoJSON/API 출력 자동 assert + 스크린샷 (MF7). *순위 강제는 데이터 왜곡 유인이 되므로 값 변화가 우선 기준.*
- [ ] AC8: 셀당 표본수 n 표시, 소표본(n<임계) 경고. n=0~1 셀은 CI degenerate 처리 명시. **색칠됐지만 n≤1인 구역은 소표본 경고 스타일(빗금/투명도)로 렌더** — Phase 0 눈≥30이 구역별 비어있지 않음을 보장하지 않으므로 (critic opt#4)
- [ ] AC9: 기획 문서에 문제정의·데이터셋ID·방법·분류규칙·한계(공간gradient아님/노출편향/표본)·기대효과 포함

## Implementation Steps

### Phase 1 — 데이터 수집 (배치, KST 고정)
5. 공공데이터포털 API 키 발급. 사용 데이터셋 ID 기록: 도로교통공단_사망교통사고정보, 도로교통공단_교통사고다발지역, 기상청 ASOS 시간자료(+AWS 보조).
6. 사망사고 건별 수집 → CSV. 발생일시를 **KST(Asia/Seoul)로 명시 파싱**, timestamptz 저장 시 오프셋 고정.
7. 다발지역 폴리곤/좌표 → GeoJSON.
8. 사고 시각 목록 추출 → 필요한 기상 조회 기간/지점 산출.
9. ASOS 시간자료 수집(서울 지점 + AWS 보조). 호출 최적화: 지점×기간 배치, rate-limit 재시도, 로컬 캐시. 원천 시간축 KST 명시.

### Phase 2 — 분석 엔진 (Python/geopandas, MF6 Option C)
10. **분류 규칙 함수(단일 정의, 분자·분모 공유, MF3)**:
    - `눈`: 신적설 > 0 또는 (강수량>0 & 기온 ≤ 0℃)
    - `비`: 강수량 ≥ 0.1mm & 위 눈 조건 아님
    - `맑음`: 그 외(강수 0)
    - `데이터없음`: 관측 결측(±1h tolerance 실패)
    - 눈·비 동시 성립 시 눈 우선. 이 규칙을 사고시각 분류(numerator)와 노출시간 집계(denominator)에 **동일 적용**.
11. 최근접 관측소: 사고점→`sjoin_nearest`(시간매칭용 station_id), 구역중심점→`sjoin_nearest`(노출분모용 대표 station_id). 분리 저장 (MF1/finding5). **눈 노출 계산용 대표 관측소는 반드시 ASOS(적설 관측)** 로 제한 — AWS가 최근접이어도 눈 분모는 최근접 ASOS를 사용하거나 해당 구역을 적설-불가로 플래그(critic opt#3).
12. 시간 매칭: 사고 occurred_at(KST) 정시 라운딩 → `merge_asof(tolerance=1h, direction=nearest)` 로 관측 결합 → 분류규칙 적용 (MF4 결측 흡수).
13. 노출시간: 구역 대표 관측소의 기상범주별 시간수 집계.
14. 시간층화 상대위험: 구역×범주 (사고건수 ÷ 노출시간). **Poisson exact / Byar 근사 CI**(MF opt) 산출, n=0~1 degenerate 처리.

### Phase 3 — 적재 & 서빙 (PostGIS 평문 테이블, 정적 GeoJSON)
15. 스키마 DDL (평문 테이블, matview 미사용, 제네릭 geometry — MF opt / finding7,8):
    - `hotspot_zone(id, name, geom geometry(Geometry,4326), centroid geometry(Point,4326), accident_count, rep_station_id)`
    - `fatal_accident(id, occurred_at timestamptz, geom geometry(Point,4326), accident_type, zone_id, match_station_id, weather_category)`
    - `weather_station(id, name, kind, geom geometry(Point,4326))`
    - `zone_weather_risk(zone_id, weather_category, accident_count, exposure_hours, relative_risk, sample_n, ci_low, ci_high)` — **평문 테이블**
    - 공간 인덱스 `GIST(geom)`. 거리는 순위용(4326 `<->`)만 사용; 미터 거리 필요 시 EPSG:5179 변환 명시 (finding6).
16. 분석 결과 적재. 카테고리별 정적 GeoJSON(`zones_clear.geojson` 등) 생성.

### Phase 4 — 대시보드
17. 프론트: Leaflet + 카테고리별 GeoJSON 로드 + 기상 필터 토글(LayerControl) + choropleth 색상.
18. 클릭 팝업: 건수·표본수·상대위험·CI·소표본 경고.
19. (선택) 읽기전용 `/zones?weather=` GeoJSON 엔드포인트(FastAPI) — 정적 서빙으로 데모 리스크 제거 가능.

### Phase 5 — 기획 문서 & 검증
20. 기획 문서(문제정의·데이터셋ID·방법·분류규칙·한계·기대효과).
21. 검증: 아래 Verification Steps 전 항목.

## Risks and Mitigations
| Risk | Mitigation |
|---|---|
| **노출 분모가 구역 간 상수 → 공간 무의미 (MF1)** | 지표를 시간층화로 재정의, 문서·범례에 "구역 간 비교 아님" 명시. AWS 다지점으로 비/기온은 부분적 공간변이 복원 시도(눈은 ASOS 의존) |
| **사망∩다발∩눈 셀 공백 → 데모 깨짐 (MF2)** | Phase 0 스파이크 게이트: 눈 총 사고<30이면 시군구/도로유형 단위로 승격 |
| 기상 분류 임계 모호 → 지표 편향 (MF3) | 단일 분류 함수, 분자·분모 동일 적용, 규칙 문서화 |
| KST 오프셋/결측 → 9h 오배정·NULL (MF4) | KST 고정, merge_asof ±1h, 결측은 `데이터없음` 라벨 |
| 표본 부족 | 10년 누적, 소표본 경고, Poisson CI |
| API rate limit | 배치·캐시·재시도, 선별 호출 |
| SRID 불일치 | 4326 통일, 순위 외 거리는 5179 변환 |

## Verification Steps
1. TZ 일관성: 사고·기상 timestamptz가 KST 기준으로 저장됐는지 샘플 교차확인 (MF4)
2. `SELECT count(*) FROM fatal_accident WHERE match_station_id IS NULL;` → 0 (AC2)
3. `weather_category` 분포 조회: `데이터없음` 비율이 과도하지 않은지 확인 (AC3, NULL 아님)
4. `zone_weather_risk` 샘플로 relative_risk·sample_n·CI 확인 (AC5, AC8)
5. **AC7 자동검증**: 각 카테고리 GeoJSON이 ≥K개 색칠 구역 포함 & 최소 두 범주 간 구역 순위 상이함을 스크립트로 assert + 토글 스크린샷 (MF7)
6. 기획 문서 체크리스트 (AC9)

## ADR (Architecture Decision Record)
- **Decision:** Python/geopandas 분석 엔진 → PostGIS 평문 테이블 → 카테고리별 정적 GeoJSON + Leaflet 토글 (Option C). 지표는 시간층화 상대위험.
- **Drivers:** 소량·정적 데이터 / 표본 신호 불확실(스파이크 선행) / 동작 대시보드 산출물 / 공간SQL 포트폴리오 보존.
- **Alternatives considered:** A(SQL ETL 3층 — 과설계로 기각), B(정적지도 단독 — 공간SQL 산출물 상실로 기각).
- **Why chosen:** C가 MVP·통계정직성·포트폴리오를 동시 충족하며 write-path 부담 최소.
- **Consequences:** 공간 gradient 주장을 포기(시간층화로 한정). matview·동적쿼리 미사용. Phase 0 게이트가 아키텍처를 바꿀 수 있음(폴리곤→시군구).
- **Follow-ups:** 스파이크 결과에 따른 단위 확정; AWS 공간변이 복원 실험; CI 방법 최종화.

## Changelog (consensus iteration 2)
- MF1: 지표를 시간층화로 재정의, 노출 분모를 구역 대표 관측소 granularity로, Goal/AC5 문구 수정
- MF2: Phase 0 겹침 스파이크 + 임계 게이트(눈<30 → 시군구 승격) 추가
- MF3: 기상 분류 규칙 명시(단일 함수, 분자·분모 공유)
- MF4: KST 고정 + merge_asof ±1h + `데이터없음` 라벨, AC3/검증 현실화
- MF5: 대상 도시 서울 확정 + 선정기준
- MF6: Option B 공정 재탐색 + Architect 시너지(Option C) 채택, matview 제거
- MF7: AC7 자동검증(순위 상이 assert) 조작화
- Opt: Poisson/Byar CI 명시, 평문 테이블, 데이터셋 ID 기록, 4326/5179 거리 주석, AWS 공간변이 복원 아이디어
