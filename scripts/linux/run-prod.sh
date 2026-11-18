#!/usr/bin/env bash
# Production entrypoint used by systemd (and can be run manually).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND="${ROOT}/backend"
ENV_FILE="${ROOT}/.env"

if [[ ! -f "${BACKEND}/.venv/bin/uvicorn" ]]; then
  echo "Missing backend/.venv. Create venv and pip install -e '.[dev]' first." >&2
  exit 1
fi
if [[ ! -f "${ROOT}/frontend/dist/index.html" ]]; then
  echo "Missing frontend/dist. Run: cd frontend && npm ci && npm run build" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
[[ -f "${ENV_FILE}" ]] && source "${ENV_FILE}"
set +a

export APP_ENV="${APP_ENV:-production}"
export APP_HOST="${APP_HOST:-127.0.0.1}"
export APP_PORT="${APP_PORT:-18080}"
export APP_TIMEZONE="${APP_TIMEZONE:-Asia/Shanghai}"
export APP_DATA_DIR="${APP_DATA_DIR:-${ROOT}/data}"
export BACKUP_DIR="${BACKUP_DIR:-${ROOT}/backups}"
export SCHEDULE_HORIZON_DAYS="${SCHEDULE_HORIZON_DAYS:-365}"
export ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost,127.0.0.1}"

# Prefer absolute data paths under the repo when relative.
if [[ "${APP_DATA_DIR}" != /* ]]; then
  export APP_DATA_DIR="${ROOT}/${APP_DATA_DIR#./}"
fi
if [[ "${BACKUP_DIR}" != /* ]]; then
  export BACKUP_DIR="${ROOT}/${BACKUP_DIR#./}"
fi

mkdir -p "${APP_DATA_DIR}" "${BACKUP_DIR}"

cd "${BACKEND}"
"${BACKEND}/.venv/bin/alembic" upgrade head
exec "${BACKEND}/.venv/bin/uvicorn" app.main:app \
  --host "${APP_HOST}" \
  --port "${APP_PORT}" \
  --proxy-headers \
  --forwarded-allow-ips "127.0.0.1"
