<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-07-21 | Updated: 2026-07-21 -->

# config

## Purpose
`.env` 파일의 환경변수를 읽어 타입이 정해진 단일 설정 객체(`settings`)로 노출하는 패키지. 프로젝트 전역에서 인증키·대상지역·수집 동작·경로·API 엔드포인트를 여기 한 곳에서만 가져간다.

## Key Files
| File | Description |
|------|-------------|
| `settings.py` | `Settings` frozen dataclass + 모듈 수준 `settings` 싱글턴. `.env` 로드, 기본값, 파생 프로퍼티(`years`, `koroad_url`), 인증키 검증(`require_key`) |
| `__init__.py` | 빈 파일. 패키지 마커 |

## Subdirectories
없음.

## For AI Agents

### Working In This Directory
- 새 설정값을 추가할 때는 **3곳을 함께 갱신**한다: `Settings` 필드, `.env.example` 항목(한국어 주석 포함), 필요하면 루트 `README.md` 의 설명.
- 기본값은 필드 선언부의 `os.getenv("KEY", "기본값")` 에 둔다. 기본값이 있으면 `.env` 없이도 임포트가 성공해야 한다 — 임포트 시점에 예외를 던지지 않는다.
- 인증키처럼 **없으면 실행 불가한 값**은 기본값을 빈 문자열로 두고, 실제 사용 직전에 `require_key()` 같은 검증 메서드로 막는다. 이래야 오류 메시지가 "어디서 발급받아 어디에 넣어라"까지 안내할 수 있다.
- `ROOT` 는 이 파일 기준 2단계 상위(프로젝트 루트)다. `settings.py` 를 다른 깊이로 옮기면 `ROOT` 계산과 `.env` 로드가 함께 깨진다.
- `raw_dir` / `cache_dir` 는 `ROOT` 에 상대경로를 이어붙인 절대 `Path` 다. 문자열로 다루지 말고 `Path` 그대로 전달한다.
- `Settings` 는 `frozen=True` 다. 런타임에 값을 바꾸려 하지 말고 `.env` 를 고친다.

### Testing Requirements
- 설정 로드 확인: `python -c "from config.settings import settings; print(settings.years, settings.koroad_url, settings.raw_dir)"`
- 인증키 가드 확인: `.env` 의 키를 비운 상태에서 `settings.require_key()` 가 안내 문구와 함께 `RuntimeError` 를 내는지 본다.

### Common Patterns
- 단일 싱글턴 임포트: `from config.settings import settings`. 다른 모듈에서 `Settings()` 를 새로 인스턴스화하지 않는다.
- 계산이 필요한 값은 필드가 아닌 `@property` 로 파생시킨다 (`years`, `koroad_url`). 예: `koroad_url` 은 `hotspot_op` 에서 `getRest{Op}` 접미사를 만들어 조립한다 — 핫스팟 유형을 `.env` 하나로 전환할 수 있는 이유다.
- `_get()` 헬퍼는 "기본값 없는 필수 환경변수"용으로 준비돼 있으나 현재 사용처가 없다. 필수값을 추가할 때 쓰거나, 계속 안 쓰이면 제거를 고려한다.

## Dependencies

### Internal
- 없음 — 이 패키지는 프로젝트 내 다른 모듈에 의존하지 않는다. 반대로 `src/` 전체가 여기에 의존한다.

### External
- `python-dotenv` — `load_dotenv` 로 프로젝트 루트 `.env` 로드

<!-- MANUAL: -->
