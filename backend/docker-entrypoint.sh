#!/bin/sh
set -eu

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

if [ "${RUN_DATABASE_SETUP_ON_STARTUP:-true}" = "true" ]; then
  python -m scripts.inicializar_banco
  python -m scripts.validar_banco
fi
export RUN_MIGRATIONS_ON_STARTUP=false

exec gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers "${WEB_CONCURRENCY:-1}" \
  --bind "0.0.0.0:${PORT:-8000}" \
  --access-logfile - \
  --error-logfile - \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --graceful-timeout 30 \
  --keep-alive 5
