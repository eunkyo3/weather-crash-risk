"""환경변수(.env)를 읽어 타입이 정해진 설정값으로 노출한다.

사용:  from config.settings import settings
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# 프로젝트 루트의 .env 를 로드
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _get(key: str, default: str | None = None) -> str:
    val = os.getenv(key, default)
    if val is None:
        raise RuntimeError(f"환경변수 {key} 가 설정되지 않았습니다. .env 를 확인하세요.")
    return val


@dataclass(frozen=True)
class Settings:
    service_key: str = os.getenv("DATA_GO_KR_SERVICE_KEY", "")
    sido_code: str = os.getenv("TARGET_SIDO_CODE", "11")
    sido_name: str = os.getenv("TARGET_SIDO_NAME", "서울특별시")
    asos_station_id: str = os.getenv("ASOS_STATION_ID", "108")

    start_year: int = int(os.getenv("START_YEAR", "2014"))
    end_year: int = int(os.getenv("END_YEAR", "2023"))

    hotspot_op: str = os.getenv("KOROAD_HOTSPOT_OP", "frequentzoneLg")

    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "20"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "5"))
    rate_limit_sleep: float = float(os.getenv("RATE_LIMIT_SLEEP", "0.34"))

    raw_dir: Path = ROOT / os.getenv("RAW_DIR", "data/raw")
    cache_dir: Path = ROOT / os.getenv("CACHE_DIR", "data/cache")

    # API 엔드포인트 (확인된 값)
    asos_url: str = "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
    koroad_base: str = "http://apis.data.go.kr/B552061"

    @property
    def years(self) -> list[int]:
        return list(range(self.start_year, self.end_year + 1))

    @property
    def koroad_url(self) -> str:
        # 예: .../B552061/frequentzoneLg/getRestFrequentzoneLg
        op = self.hotspot_op
        suffix = "getRest" + op[0].upper() + op[1:]
        return f"{self.koroad_base}/{op}/{suffix}"

    def require_key(self) -> str:
        if not self.service_key or "여기에" in self.service_key:
            raise RuntimeError(
                "DATA_GO_KR_SERVICE_KEY 가 비어있습니다. "
                "https://www.data.go.kr 에서 인증키를 발급받아 .env 에 넣으세요."
            )
        return self.service_key


settings = Settings()
