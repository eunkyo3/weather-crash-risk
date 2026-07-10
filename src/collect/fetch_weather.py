"""기상청 ASOS 시간자료 수집.

기상청_지상(종관, ASOS) 시간자료 조회서비스를 월 단위로 호출해 서울(108)
관측값을 data/raw/weather/asos_{stn}_{YYYYMM}.json 로 저장한다.

실행:
    python -m src.collect.fetch_weather

시간축은 KST(관측 로컬시각) 기준이다. 주요 항목:
- tm(관측시각), ta(기온), rn(강수량), hr3Fhsc(3시간 신적설), dsnw(적설), ws(풍속) 등.
"""
from __future__ import annotations

import calendar

from config.settings import settings
from src.collect.common import extract_items, get_json, save_json, total_count


def fetch_month(year: int, month: int) -> list[dict]:
    """한 달치 시간자료를 페이지네이션하며 수집(시간당 1행, 최대 ~744행)."""
    start_dt = f"{year}{month:02d}01"
    last_day = calendar.monthrange(year, month)[1]
    end_dt = f"{year}{month:02d}{last_day:02d}"

    items: list[dict] = []
    page = 1
    while True:
        params = {
            "dataCd": "ASOS",
            "dateCd": "HR",
            "stnIds": settings.asos_station_id,
            "startDt": start_dt,
            "startHh": "00",
            "endDt": end_dt,
            "endHh": "23",
            "numOfRows": 999,
            "pageNo": page,
        }
        data = get_json(settings.asos_url, params)
        batch = extract_items(data)
        items.extend(batch)

        total = total_count(data)
        got = (page - 1) * 999 + len(batch)
        print(f"  {year}-{month:02d} p{page}: +{len(batch)} (누적 {got}/{total})")
        if not batch or got >= total:
            break
        page += 1
    return items


def main() -> None:
    out_dir = settings.raw_dir / "weather"
    print(f"[ASOS 수집] stn={settings.asos_station_id} "
          f"years={settings.start_year}~{settings.end_year}")

    for year in settings.years:
        for month in range(1, 13):
            try:
                items = fetch_month(year, month)
            except Exception as e:  # noqa: BLE001
                print(f"  ! {year}-{month:02d} 수집 실패: {e}")
                continue
            if items:
                save_json(items, out_dir / f"asos_{settings.asos_station_id}_{year}{month:02d}.json")

    print("[ASOS 수집] 완료")


if __name__ == "__main__":
    main()
