"""대시보드 정적 서버 — '/'로 접속하면 outputs/dashboard.html이 뜬다.

의존성 없이 표준 라이브러리만 사용. Docker 컨테이너의 기본 실행 대상.
환경변수: HOST(기본 0.0.0.0), PORT(기본 8000).
"""
from __future__ import annotations

import functools
import http.server
import os
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """루트 경로를 대시보드로 매핑하고 outputs/를 정적 서빙."""

    def do_GET(self) -> None:  # noqa: N802 (stdlib 시그니처)
        if self.path in ("", "/", "/index.html"):
            self.path = "/dashboard.html"
        super().do_GET()

    def log_message(self, fmt: str, *args) -> None:
        print(f"[serve] {self.address_string()} - {fmt % args}")


def main() -> None:
    dashboard = OUTPUTS / "dashboard.html"
    if not dashboard.exists():
        raise SystemExit(
            f"{dashboard} 가 없습니다. 먼저 'python -m src.analysis.pipeline' 로 대시보드를 생성하세요."
        )
    handler = functools.partial(DashboardHandler, directory=str(OUTPUTS))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((HOST, PORT), handler) as httpd:
        print(f"대시보드 서빙 중 → http://localhost:{PORT}/  (Ctrl+C 종료)")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
