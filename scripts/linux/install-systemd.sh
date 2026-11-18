#!/usr/bin/env bash
# Install FitManager as a systemd service (Linux).
# Usage (as root):
#   sudo bash scripts/linux/install-systemd.sh [/path/to/fitness-manager-v1]
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root: sudo bash scripts/linux/install-systemd.sh" >&2
  exit 1
fi

ROOT="$(cd "${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}" && pwd)"
SERVICE_SRC="${ROOT}/deploy/linux/fitmanager.service"
SERVICE_DST="/etc/systemd/system/fitmanager.service"
RUN_SCRIPT="${ROOT}/scripts/linux/run-prod.sh"
APP_USER="${FITMANAGER_USER:-fitmanager}"
APP_PORT="${APP_PORT:-18080}"

if [[ ! -f "${SERVICE_SRC}" ]]; then
  echo "Service unit not found: ${SERVICE_SRC}" >&2
  exit 1
fi
if [[ ! -x "${RUN_SCRIPT}" ]]; then
  chmod +x "${RUN_SCRIPT}" "${ROOT}/scripts/linux/install-systemd.sh" || true
fi
if [[ ! -f "${ROOT}/frontend/dist/index.html" ]]; then
  echo "frontend/dist missing. Build first: cd frontend && npm ci && npm run build" >&2
  exit 1
fi
if [[ ! -x "${ROOT}/backend/.venv/bin/uvicorn" ]]; then
  echo "backend/.venv missing. Create venv and: pip install -e '.[dev]'" >&2
  exit 1
fi

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --home "${ROOT}" --shell /usr/sbin/nologin "${APP_USER}"
  echo "Created system user: ${APP_USER}"
fi

mkdir -p "${ROOT}/data" "${ROOT}/backups"
if [[ ! -f "${ROOT}/.env" ]]; then
  cp "${ROOT}/.env.example" "${ROOT}/.env"
  cat >> "${ROOT}/.env" <<EOF

# Linux production defaults (SSH tunnel friendly)
APP_ENV=production
APP_HOST=127.0.0.1
APP_PORT=${APP_PORT}
APP_DATA_DIR=${ROOT}/data
BACKUP_DIR=${ROOT}/backups
ALLOWED_HOSTS=localhost,127.0.0.1
EOF
  echo "Created ${ROOT}/.env — review before first start."
fi

chown -R "${APP_USER}:${APP_USER}" "${ROOT}"

# Rewrite unit paths to the actual install root / user.
sed \
  -e "s|/opt/fitness-manager-v1|${ROOT}|g" \
  -e "s|User=fitmanager|User=${APP_USER}|g" \
  -e "s|Group=fitmanager|Group=${APP_USER}|g" \
  "${SERVICE_SRC}" > "${SERVICE_DST}"

systemctl daemon-reload
systemctl enable fitmanager.service
systemctl restart fitmanager.service
systemctl --no-pager --full status fitmanager.service || true

echo
echo "Installed. Service: fitmanager.service"
echo "Commands:"
echo "  sudo systemctl status fitmanager"
echo "  sudo systemctl restart fitmanager"
echo "  sudo journalctl -u fitmanager -f"
echo
echo "SSH tunnel from your PC:"
echo "  ssh -N -L ${APP_PORT}:127.0.0.1:${APP_PORT} USER@SERVER"
echo "Then open: http://127.0.0.1:${APP_PORT}"
