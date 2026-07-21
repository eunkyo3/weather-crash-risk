<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-07-21 | Updated: 2026-07-21 -->

# docs

## Purpose
프로젝트의 **정식 기획 문서**가 있는 곳. 요구사항 도출(deep-interview) → 구현 계획(planner/architect/critic 합의) → 확정 결정 로그의 세 단계 산출물을 담는다. PBL 제출물의 일부이자, 코드보다 앞서는 **설계 근거의 단일 출처**다. 코드에서 "왜 이렇게 했는가"가 궁금하면 여기부터 본다.

## Key Files
| File | Description |
|------|-------------|
| `methodology.md` | **현행 사양의 기준 문서.** 문제정의·데이터·분류규칙·RR 산출식·CI 방법·산출물·한계 6가지 |
| `data-provenance.md` | 데이터셋 ID·저작자·이용조건·스키마·단계별 재현 절차(Step 1~6) |
| `decisions-log.md` | 확정 결정 표(2026-07-09) + **하단 "데이터 소스 변경"(2026-07-14)** — 후자가 현행 설계의 근거 |
| `implementation-plan.md` | 합의된 구현 계획. ⚠️ **데이터 소스 전환 이전 문서**라 폴리곤·개별사망사고 전제가 남아 있다. 현행과 어긋나면 `methodology.md` 가 우선 |
| `requirements-spec.md` | deep-interview 결과 스펙. ⚠️ 전환 이전 문서 (동일 주의) |

## Subdirectories
없음.

## For AI Agents

### Working In This Directory
- 이 문서들은 **합의를 거쳐 확정된 상태**다. 지나가는 개선으로 결정을 뒤집지 않는다. 코드와 문서가 어긋나면 대개 코드가 뒤처진 것이니, 먼저 어느 쪽이 맞는지 확인한다.
- 결정이 실제로 바뀌면 `decisions-log.md` 를 **추가 기록** 방식으로 갱신하고 날짜를 남긴다. 기존 행을 조용히 덮어쓰면 결정 이력이 사라진다.
- 상대 날짜("지난주", "다음 달")를 쓰지 않는다. 기존 문서가 절대 날짜를 쓴다 (예: 2026-07-09).
- **`.omc/` 의 툴 아티팩트를 정식 문서로 취급하지 않는다.** `.omc/` 는 gitignore 대상이며, `implementation-plan.md` 상단이 참조하는 `.omc/specs/...` 경로는 저장소에 없을 수 있다. 정식 문서는 `docs/` 에만 있다.
- 문서는 한국어로 쓰고, 기존 형식(표 중심 + `> ⚠️` 인용 블록으로 핵심 제약 강조)을 따른다.
- 통계적 정직성이 이 프로젝트의 명시된 제1원칙이다. 한계(소표본, 노출편차, 관측소 밀도)를 축소하거나 지워서 결과를 좋아 보이게 만들지 않는다.

### Testing Requirements
- 코드가 아니므로 실행 검증은 없다. 대신 **문서 간 일관성**을 확인한다: `decisions-log.md` 의 결정 ↔ `implementation-plan.md` 의 계획 ↔ 루트 `README.md` 의 요약 ↔ 실제 코드/`.env.example` 기본값.
- 특히 자주 어긋나는 지점: 분석 기간(**2007~2025**, 2026-07-22 확장), 대상 시도(서울 11), ASOS 지점(108), 핫스팟 유형 기본값(`frequentzoneLg` — 결정 로그는 보행자 우선이나 코드 기본값은 지자체별 폴백 상태).
- 상대 링크가 유효한지 확인한다 (`README.md` → `docs/*.md`).

### Common Patterns
- 결정 사항은 `| 항목 | 결정 |` 2열 표로 적는다. 산문보다 표가 대조·검증에 유리하다.
- 계획 문서는 대안(Option)을 Pros/Cons로 병기하고 선택 근거를 남긴다. 탈락한 대안도 지우지 않는다.
- 핵심 재정의·주의는 `> **⚠️ ...**` 인용 블록으로 본문 흐름 안에 배치한다.

## Dependencies

### Internal
- 루트 `README.md` 가 세 문서를 모두 링크한다. 파일명을 바꾸면 README도 함께 고친다.
- `data/README.md` 가 수집 재현정보의 기록처로 `decisions-log.md` 를 지목한다.

### External
- 없음. 순수 마크다운이며 빌드 단계가 없다.

<!-- MANUAL: -->
