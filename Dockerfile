# 교통사고×기상 위험 대시보드 서빙 이미지
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# 비루트 실행 사용자 — 컨테이너 탈출/권한 상승 표면 축소
RUN groupadd --system app && useradd --system --gid app --home-dir /app appuser

# 의존성 먼저(레이어 캐시)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 + 서빙에 필요한 산출물/정적데이터 (비루트 사용자 소유로 복사)
COPY --chown=appuser:app config ./config
COPY --chown=appuser:app src ./src
# 벤더링된 Leaflet — RUN_PIPELINE=1 로 대시보드를 재생성할 때 오프라인 인라인에 필요하다.
# 빠지면 재생성이 실패한다(그리고 기존 산출물은 원자적 저장 덕에 보존된다).
COPY --chown=appuser:app assets ./assets
COPY --chown=appuser:app data/raw/boundaries ./data/raw/boundaries
COPY --chown=appuser:app data/processed ./data/processed
COPY --chown=appuser:app outputs ./outputs
COPY --chown=appuser:app docker/entrypoint.sh ./docker/entrypoint.sh
# CRLF(윈도우 개행) 제거 후 실행권한 부여 — 컨테이너 셸 오류 방지
RUN sed -i 's/\r$//' ./docker/entrypoint.sh && chmod +x ./docker/entrypoint.sh

USER appuser

# 참고: src.serve 는 표준 http.server(SimpleHTTPRequestHandler) 기반 — 개발/데모용 단일스레드 서버.
# 운영 트래픽/동시접속이 많다면 gunicorn 등 WSGI 서버로 교체를 검토할 것.
EXPOSE 8000
# curl 미설치 이미지이므로 표준 라이브러리 기반 헬스체크 사용
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/').read()" || exit 1
ENTRYPOINT ["sh", "./docker/entrypoint.sh"]
