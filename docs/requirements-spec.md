# Deep Interview Spec: 교통사고 다발지역 × 기상 융합 위험지수 대시보드

## Metadata
- Interview ID: deep-interview (greenfield)
- Rounds: 5
- Final Ambiguity Score: 14.5%
- Type: greenfield
- Generated: 2026-07-09
- Threshold: 0.2 (20%)
- Threshold Source: default
- Initial Context Summarized: no
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.90 | 0.40 | 0.36 |
| Constraint Clarity | 0.80 | 0.30 | 0.24 |
| Success Criteria | 0.85 | 0.30 | 0.255 |
| **Total Clarity** | | | **0.855** |
| **Ambiguity** | | | **0.145** |

## Topology
| Component | Status | Description | Coverage / Deferral Note |
|-----------|--------|-------------|--------------------------|
| 교통사고 데이터 확보·적재 | active | 다발지역 폴리곤 + 사망사고 건별 raw 수집·적재 | 하이브리드 전략 확정: 폴리곤=공간단위, 사망사고 건별=시간축 |
| 기상 데이터 수집·적재 | active | KMA ASOS/AWS OpenAPI 배치 수집 | 대상 도시 ASOS 정시자료 우선, AWS 보조 |
| 시공간 결합 | active | PostGIS 최근접 관측소 + 정시 기상 매칭 | ST_Distance 기반, 관측소↔폴리곤 중심점 매핑 |
| 기상 가중 위험지수 산출 | active | 노출보정 상대위험 지표 | 설계 확정 (아래 Goal 참조) |
| 산출물/시각화 | active | 지도 + 기상 필터 토글 대시보드 | MVP = 필터 토글 시연 |

## Goal
특정 광역시 1곳의 **교통사고 다발지역**을, 그 지역에서 발생한 **사망교통사고 건별 데이터**의 발생 시각을 기준으로 **기상 관측 데이터와 시공간 결합**하여, "특정 기상조건(비/눈)에서 어느 구역이 상대적으로 더 위험한가"를 **노출보정 상대위험 지표**로 산출하고, 이를 **기상 필터를 토글하면 위험 분포가 바뀌는 지도 대시보드**로 시연한다.

**확정된 위험지수 설계:**
1. 분석 대상: 광역시 1곳 + 최근 5~10년 누적 (표본·관측소 밀도 확보)
2. 이중 공간 레이어: 다발지역 폴리곤(표시) + 시군구/도로유형 집계(통계 유효성)
3. 기상 범주화: `맑음 / 비 / 눈` 등 3~4개 이산 범주 (연속값 회귀 지양)
4. 노출보정 상대위험 = 사고건수 ÷ 해당 기상조건 노출시간 (노출편향 완화)
5. 통계적 겸손: 셀당 표본 n·신뢰구간 병기, 소표본 셀 경고

## Constraints
- 교통사고 건별(시각 포함) 데이터는 사실상 **사망사고 한정** → 표본 작음, 한계 명시 필수
- 다발지역(집계) 데이터에는 개별 사고 시각이 없음 → 단독으로는 시간매칭 불가
- ASOS 관측소는 전국 100개 미만 → 도심 내 변별력 위해 대상 도시 지점 + AWS 보조 필요
- AWS는 적설(눈) 지표 부족 가능 → 눈 분석은 ASOS 지점 의존
- "기획 PBL"이므로 구현물과 별개로 문제정의·데이터근거·기대효과 문서 병행 필요

## Non-Goals
- 전국 전체 대상 분석 (표본·관측소 밀도 문제로 이번 범위 제외)
- 부상/경상 포함 전체 사고 건별 분석 (건별 시각 데이터 미공개 → 제외)
- 연속값 기상 회귀모델 / 인과추론 수준의 통계 검정 (범주별 상대위험 비교로 한정)
- 실시간 스트리밍 (과거 데이터 배치 처리만)

## Acceptance Criteria
- [ ] 대상 광역시의 다발지역 폴리곤 + 사망사고 건별 데이터가 PostGIS에 적재됨
- [ ] 각 사망사고 발생 시각에 대해 최근접 관측소의 정시 기상이 매핑됨
- [ ] 기상 범주별(맑음/비/눈) 노출시간이 계산되고 상대위험 지표가 산출됨
- [ ] 지도에서 다발지역별 위험도가 색으로 표시됨
- [ ] **기상 필터 토글(맑음/비/눈) 시 지도의 위험 분포가 실제로 바뀜 (MVP 핵심)**
- [ ] 소표본 셀에 대한 표본수/신뢰 경고가 표시되거나 문서에 기재됨
- [ ] 기획 문서에 문제정의·데이터근거·한계·기대효과가 포함됨

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| 교통사고 데이터에 발생 시각이 있다 | 다발지역은 집계라 시각 없음 | 하이브리드: 폴리곤=공간, 사망사고 건별=시간축 |
| 최근접 관측소 매핑이 국지성을 준다 | ASOS 저밀도로 동일 관측소 매핑 위험 | 대상 도시 1곳으로 축소, AWS 보조 |
| 기상 가중 위험지수가 의미 있다 | 표본 부족·노출편향으로 무의미 위험 | 광역 집계 + 범주화 + 노출보정 상대위험 |
| 구현 중심이 맞다 | 기획 PBL은 기획 평가일 수 있음 | 산출물=동작 대시보드 확인 → 구현 정당화 + 문서 병행 |

## Technical Context (greenfield)
- DB: PostgreSQL + PostGIS (ST_Distance 최근접 매칭)
- 데이터: TAAS/공공데이터포털 사망교통사고정보(건별) + 교통사고 다발지역(폴리곤) + KMA ASOS 시간자료(+AWS 보조)
- 처리: 배치 (사고 시각 목록 추출 → 해당 기간 기상 수집 → 적재 → 결합 → 지수 산출)
- 산출물: 지도 대시보드 (기상 필터 토글)

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| FatalAccident | core domain | 발생일시, 위경도, 사고유형 | belongs to HotspotZone; matched to WeatherObservation |
| HotspotZone | core domain | 폴리곤, 중심점, 사고건수 | contains FatalAccidents; mapped to nearest Station |
| WeatherObservation | core domain | 관측일시, 기상범주, 강수/적설/기온 | measured by Station |
| Station | supporting | 위경도, 관측소ID, 종류(ASOS/AWS) | nearest to HotspotZone |
| WeatherCategory | supporting | 맑음/비/눈 | classifies WeatherObservation |
| ExposureNormalizedRisk | derived | 상대위험, 노출시간, 표본수, 신뢰구간 | computed per HotspotZone × WeatherCategory |
| Dashboard | deliverable | 지도, 기상필터 토글 | renders ExposureNormalizedRisk |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 5 | 5 | - | - | N/A |
| 2 | 5 | 0 | 1 (Accident→FatalAccident) | 4 | 100% |
| 3 | 6 | 1 (Dashboard) | 0 | 5 | 83% |
| 4 | 7 | 1 | 1 (RiskIndex→ExposureNormalizedRisk) | 5 | 86% |
| 5 | 7 | 0 | 0 | 7 | 100% |

## Interview Transcript
<details>
<summary>Full Q&A (5 rounds)</summary>

### Round 0 (Topology)
5개 최상위 구성요소 확정 (accident-data, weather-ingest, spatiotemporal-join, risk-index, visualization).

### Round 1
**Q:** 확보했거나 확보 가능한 교통사고 데이터는 실제로 어떤 형태인가?
**A:** 아직 미확보/검토 중.
**Ambiguity:** 68.5%

### Round 2
**Q:** 데이터 현실을 보고 데이터 전략을 어느 방향으로?
**A:** 하이브리드 (폴리곤=공간, 사망사고 건별=시간축).
**Ambiguity:** 48.5%

### Round 3
**Q:** 실제로 제출·평가되는 최종 산출물은?
**A:** 동작 프로토타입/대시보드.
**Ambiguity:** 36.5%

### Round 4 (Contrarian)
**Q:** 표본 부족·노출편향 하에서 위험지수를 어떻게 설계?
**A:** 추천안 채택 (광역집계+범주화+노출보정 상대위험).
**Ambiguity:** 22.5%

### Round 5
**Q:** 대시보드 MVP는 최소 무엇이 동작해야?
**A:** 지도 + 기상 필터 토글.
**Ambiguity:** 14.5% (PASSED)

</details>
