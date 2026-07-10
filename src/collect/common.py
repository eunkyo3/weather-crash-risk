"""공공데이터포털 API 호출 공통 유틸: 재시도, rate-limit, 저장.

data.go.kr 계열 API 공통 사항:
- 인증키는 serviceKey 파라미터로 전달(디코딩 키 사용, requests가 인코딩).
- 오류 시 XML 에러바디(<OpenAPI_ServiceResponse>...)를 JSON 대신 반환할 수 있어
  응답 content-type/파싱 실패를 방어적으로 처리한다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from config.settings import settings


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "weather-crash-risk/0.1 (PBL data collection)"})
    return s


SESSION = _session()


def get_json(url: str, params: dict[str, Any]) -> dict:
    """serviceKey를 붙여 GET 호출하고 JSON을 반환. 재시도/rate-limit 포함.

    반환 실패(HTTP 오류, JSON 아님, API 에러코드)는 예외로 올린다.
    """
    params = {**params, "serviceKey": settings.require_key(), "type": "json", "dataType": "JSON"}
    last_err: Exception | None = None

    for attempt in range(1, settings.max_retries + 1):
        try:
            resp = SESSION.get(url, params=params, timeout=settings.request_timeout)
            time.sleep(settings.rate_limit_sleep)
            resp.raise_for_status()

            text = resp.text.strip()
            if text.startswith("<"):
                # data.go.kr 는 오류를 XML로 반환 (예: SERVICE_KEY_IS_NOT_REGISTERED)
                raise RuntimeError(f"API가 XML 오류를 반환했습니다:\n{text[:400]}")

            data = resp.json()
            _check_api_error(data)
            return data
        except Exception as e:  # noqa: BLE001 - 재시도 대상
            last_err = e
            wait = settings.rate_limit_sleep * (2 ** attempt)
            print(f"  [retry {attempt}/{settings.max_retries}] {e} → {wait:.1f}s 대기")
            time.sleep(wait)

    raise RuntimeError(f"최대 재시도 초과: {url}\n마지막 오류: {last_err}")


def _check_api_error(data: dict) -> None:
    """공공데이터포털 표준 응답의 resultCode를 검사한다."""
    header = (
        data.get("response", {}).get("header")
        or data.get("OpenAPI_ServiceResponse", {}).get("cmmMsgHeader")
        or {}
    )
    code = header.get("resultCode") or header.get("returnReasonCode")
    if code not in (None, "00", "0000"):
        msg = header.get("resultMsg") or header.get("returnAuthMsg") or "unknown"
        raise RuntimeError(f"API 오류 resultCode={code} msg={msg}")


def extract_items(data: dict) -> list[dict]:
    """표준 응답 구조에서 items 배열을 안전하게 추출한다."""
    body = data.get("response", {}).get("body", {})
    items = body.get("items")
    if items in (None, "", {}):
        return []
    if isinstance(items, dict):
        item = items.get("item", [])
        return item if isinstance(item, list) else [item]
    if isinstance(items, list):
        return items
    return []


def total_count(data: dict) -> int:
    body = data.get("response", {}).get("body", {})
    try:
        return int(body.get("totalCount", 0))
    except (TypeError, ValueError):
        return 0


def save_json(obj: Any, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  저장: {path}  ({len(obj) if hasattr(obj, '__len__') else '?'} 항목)")
    return path
