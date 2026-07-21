#!/bin/sh
# 컨테이너 진입점: (선택) 파이프라인 재생성 후 대시보드 서빙.
set -e

if [ "${RUN_PIPELINE:-0}" = "1" ]; then
  echo "[entrypoint] RUN_PIPELINE=1 → 대시보드 재생성 시도..."
  if python -m src.analysis.pipeline; then
    echo "[entrypoint] 재생성 완료."
  else
    echo "[entrypoint] 재생성 실패(데이터/키 확인) → 기존 대시보드로 서빙."
  fi
fi

exec python -m src.serve
