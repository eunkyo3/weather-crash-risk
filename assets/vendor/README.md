# assets/vendor

대시보드를 **네트워크 없이** 열기 위해 저장소에 포함한 서드파티 자산이다.
`src/analysis/dashboard.py` 의 `_use_offline_assets()` 가 이 파일들을 읽어
생성되는 HTML의 `<head>` 에 인라인한다(CDN 링크를 만들지 않는다).

발표장 네트워크 장애로 데모가 통째로 죽는 것을 막기 위한 장치이므로,
CDN 링크로 되돌리지 말 것.

| 파일 | 출처 | 라이선스 |
|---|---|---|
| `leaflet.css`, `leaflet.js` | [Leaflet](https://leafletjs.com) 1.9.3 (folium 0.20이 참조하는 버전과 동일) | BSD-2-Clause — [`LICENSE-leaflet.txt`](LICENSE-leaflet.txt) |
| `images/layers.png`, `images/layers-2x.png` | 위와 동일 | 동일 |

`leaflet.css` 안의 `url(images/...)` 참조는 인라인 시점에 data URI로 치환되므로
런타임 이미지 요청도 발생하지 않는다. 사용하지 않는 기본 마커 아이콘
(`marker-icon.png`)은 1px 투명 GIF로 대체된다.

## 갱신 방법

folium을 판올림해 Leaflet 버전이 달라지면 함께 갱신한다
(버전 확인: `python -c "import folium; print(folium.Map().default_js)"`).

```bash
V=1.9.3
curl -o assets/vendor/leaflet.css  https://cdn.jsdelivr.net/npm/leaflet@$V/dist/leaflet.css
curl -o assets/vendor/leaflet.js   https://cdn.jsdelivr.net/npm/leaflet@$V/dist/leaflet.js
curl -o assets/vendor/images/layers.png     https://cdn.jsdelivr.net/npm/leaflet@$V/dist/images/layers.png
curl -o assets/vendor/images/layers-2x.png  https://cdn.jsdelivr.net/npm/leaflet@$V/dist/images/layers-2x.png
curl -o assets/vendor/LICENSE-leaflet.txt   https://raw.githubusercontent.com/Leaflet/Leaflet/v$V/LICENSE
```

버전이 어긋나면 folium이 생성하는 JS와 인라인된 라이브러리가 불일치할 수 있다.
`_save_atomic()` 이 외부 참조 잔존을 단언하므로 CDN 자산이 새로 추가되면 저장 단계에서 실패한다.
