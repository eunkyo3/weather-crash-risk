# data/ 디렉토리

실제 데이터 파일은 저장소에 포함되지 않습니다(`.gitignore`). 아래 구조로 수집됩니다.

```
data/
├── raw/                         # 수집 원본 (gitignore)
│   ├── hotspots/                # 다발지역 폴리곤 JSON (API 자동 수집)
│   │   └── frequentzoneLg_11_2023.json ...
│   ├── weather/                 # ASOS 시간자료 JSON (API 자동 수집)
│   │   └── asos_108_202301.json ...
│   └── accidents/               # ← 사망사고 CSV (수동 다운로드 필요)
│       └── 사망교통사고정보_2023.csv ...
└── cache/                       # 중간 캐시 (gitignore)
```

## 자동 수집 (API)

`.env` 에 `DATA_GO_KR_SERVICE_KEY` 를 넣은 뒤:

```bash
python -m src.collect.fetch_hotspots   # 다발지역 → data/raw/hotspots/
python -m src.collect.fetch_weather    # ASOS 시간자료 → data/raw/weather/
```

## 수동 다운로드 (사망사고 건별 CSV)

**사망 교통사고 정보**는 파일데이터(OpenAPI 아님)라 포털에서 연도별로 내려받습니다.

1. https://www.data.go.kr/data/15070340/fileData.do 접속 (로그인 불필요)
2. 연도별 파일을 내려받아 `data/raw/accidents/` 에 저장
3. 10년치가 필요하면 각 연도 데이터셋을 반복 (연도별 PK가 다를 수 있음 — "사망 교통사고 정보" 검색해 연도별 항목 확인)

**필수 컬럼(확인됨)**: 발생년월일시, **발생시간(시 0~23)**, 사고유형(차대사람 등), 위도, 경도, 발생지시도, 발생지시군구

> 수집 재현정보(데이터셋 ID·다운로드 일자·연도 범위)는 `docs/decisions-log.md` 및 향후 `docs/data-provenance.md` 에 기록합니다.
