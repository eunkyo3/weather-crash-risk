"""교통사고 다발지역(핫스팟) 폴리곤 수집.

KOROAD 사고다발지역 OpenAPI(B552061)를 연도별로 호출해 서울 다발지역을
data/raw/hotspots/{op}_{siDo}_{year}.json 로 저장한다.

실행:
    python -m src.collect.fetch_hotspots

주의:
- 기본은 지자체별(frequentzoneLg). 보행자 유형으로 바꾸려면 .env 의
  KOROAD_HOTSPOT_OP 를 15105289 상세페이지의 요청주소에 맞게 교체.
- 일부 KOROAD API는 siDo 와 guGun 을 모두 요구한다. guGun 없이 오류가 나면
  GUGUN_CODES 에 서울 시군구 코드를 채워 넣으면 각 구를 순회 호출한다.
"""
from __future__ import annotations

from config.settings import settings
from src.collect.common import extract_items, get_json, save_json, total_count

# 필요 시 서울 시군구 코드를 채운다(비어 있으면 siDo 단위 단일 호출).
GUGUN_CODES: list[str] = []


def fetch_year(year: int, gugun: str | None = None) -> list[dict]:
    """한 해(+선택 시군구)의 다발지역 항목을 페이지네이션하며 모두 수집."""
    items: list[dict] = []
    page = 1
    while True:
        params = {
            "searchYearCd": str(year),
            "siDo": settings.sido_code,
            "numOfRows": 100,
            "pageNo": page,
        }
        if gugun:
            params["guGun"] = gugun

        data = get_json(settings.koroad_url, params)
        batch = extract_items(data)
        items.extend(batch)

        total = total_count(data)
        got = (page - 1) * 100 + len(batch)
        print(f"  {year} p{page}: +{len(batch)} (누적 {got}/{total})")
        if not batch or got >= total:
            break
        page += 1
    return items


def main() -> None:
    out_dir = settings.raw_dir / "hotspots"
    print(f"[다발지역 수집] op={settings.hotspot_op} siDo={settings.sido_code} "
          f"years={settings.start_year}~{settings.end_year}")

    for year in settings.years:
        try:
            if GUGUN_CODES:
                items: list[dict] = []
                for gu in GUGUN_CODES:
                    items.extend(fetch_year(year, gu))
            else:
                items = fetch_year(year)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {year} 수집 실패: {e}")
            continue

        save_json(items, out_dir / f"{settings.hotspot_op}_{settings.sido_code}_{year}.json")

    print("[다발지역 수집] 완료")


if __name__ == "__main__":
    main()
