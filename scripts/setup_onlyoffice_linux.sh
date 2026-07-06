#!/bin/bash
set -euo pipefail

DOMAIN=""
JWT_SECRET=""
PACKAGE_PATH=""
DJANGO_UPSTREAM="${DJANGO_UPSTREAM:-127.0.0.1:8000}"
ONLYOFFICE_PORT="${ONLYOFFICE_PORT:-8082}"
PUBLIC_PATH="${ONLYOFFICE_PUBLIC_PATH:-/office/}"
NGINX_OUTPUT="${NGINX_OUTPUT:-/etc/nginx/sites-available/dtcall-onlyoffice.conf}"
ENV_OUTPUT="${ENV_OUTPUT:-/etc/dtcall/onlyoffice.env}"
SKIP_INSTALL=0

usage() {
  cat <<'EOF'
Usage:
  sudo ./scripts/setup_onlyoffice_linux.sh \
    --domain erp.example.com \
    --jwt-secret your-secret \
    [--package /path/to/onlyoffice-documentserver.deb] \
    [--django-upstream 127.0.0.1:8000] \
    [--onlyoffice-port 8082] \
    [--public-path /office/] \
    [--nginx-output /etc/nginx/sites-available/dtcall-onlyoffice.conf] \
    [--env-output /etc/dtcall/onlyoffice.env] \
    [--skip-install]

Options:
  --domain            Browser-facing domain name for dtcall.
  --jwt-secret        Shared JWT secret used by dtcall and ONLYOFFICE.
  --package           Local ONLYOFFICE Document Server .deb package path.
  --django-upstream   Django/Gunicorn upstream address. Default: 127.0.0.1:8000
  --onlyoffice-port   Local ONLYOFFICE listen port. Default: 8082
  --public-path       Same-domain reverse proxy prefix. Default: /office/
  --nginx-output      Generated nginx site file path.
  --env-output        Generated dtcall env snippet path.
  --skip-install      Skip package installation and only render config files.
EOF
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "[ERROR] Run this script as root." >&2
    exit 1
  fi
}

normalize_public_path() {
  if [[ -z "${PUBLIC_PATH}" ]]; then
    PUBLIC_PATH="/office/"
  fi
  [[ "${PUBLIC_PATH}" == /* ]] || PUBLIC_PATH="/${PUBLIC_PATH}"
  [[ "${PUBLIC_PATH}" == */ ]] || PUBLIC_PATH="${PUBLIC_PATH}/"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --domain)
        DOMAIN="${2:-}"
        shift 2
        ;;
      --jwt-secret)
        JWT_SECRET="${2:-}"
        shift 2
        ;;
      --package)
        PACKAGE_PATH="${2:-}"
        shift 2
        ;;
      --django-upstream)
        DJANGO_UPSTREAM="${2:-}"
        shift 2
        ;;
      --onlyoffice-port)
        ONLYOFFICE_PORT="${2:-}"
        shift 2
        ;;
      --public-path)
        PUBLIC_PATH="${2:-}"
        shift 2
        ;;
      --nginx-output)
        NGINX_OUTPUT="${2:-}"
        shift 2
        ;;
      --env-output)
        ENV_OUTPUT="${2:-}"
        shift 2
        ;;
      --skip-install)
        SKIP_INSTALL=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "[ERROR] Unknown argument: $1" >&2
        usage
        exit 1
        ;;
    esac
  done
}

validate_args() {
  if [[ -z "${DOMAIN}" ]]; then
    echo "[ERROR] --domain is required." >&2
    exit 1
  fi
  if [[ -z "${JWT_SECRET}" ]]; then
    echo "[ERROR] --jwt-secret is required." >&2
    exit 1
  fi
  if [[ "${SKIP_INSTALL}" -eq 0 && -n "${PACKAGE_PATH}" && ! -f "${PACKAGE_PATH}" ]]; then
    echo "[ERROR] ONLYOFFICE package not found: ${PACKAGE_PATH}" >&2
    exit 1
  fi
}

install_onlyoffice() {
  if [[ "${SKIP_INSTALL}" -eq 1 ]]; then
    echo "[INFO] Skipping ONLYOFFICE package installation."
    return
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    echo "[ERROR] This script currently supports Debian/Ubuntu systems with apt-get." >&2
    exit 1
  fi

  if [[ -z "${PACKAGE_PATH}" ]]; then
    echo "[ERROR] Provide a local ONLYOFFICE .deb package with --package, or use --skip-install." >&2
    exit 1
  fi

  echo "[INFO] Installing ONLYOFFICE dependencies..."
  apt-get update
  apt-get install -y nginx

  echo "[INFO] Preseeding ONLYOFFICE package options..."
  echo "onlyoffice-documentserver onlyoffice/ds-port select ${ONLYOFFICE_PORT}" | debconf-set-selections

  echo "[INFO] Installing ONLYOFFICE Document Server package..."
  apt-get install -y "${PACKAGE_PATH}"
}

configure_onlyoffice_jwt() {
  local config_path="/etc/onlyoffice/documentserver/local.json"

  if [[ ! -f "${config_path}" ]]; then
    echo "[WARN] ONLYOFFICE config not found at ${config_path}; skipping JWT patch."
    return
  fi

  echo "[INFO] Updating ONLYOFFICE JWT secret in ${config_path}..."
  JWT_SECRET="${JWT_SECRET}" ONLYOFFICE_CONFIG_PATH="${config_path}" python3 - <<'PY'
import json
import os
from pathlib import Path

config_path = Path(os.environ['ONLYOFFICE_CONFIG_PATH'])
secret = os.environ['JWT_SECRET']
data = json.loads(config_path.read_text(encoding='utf-8'))

services = data.setdefault('services', {})
coauthoring = services.setdefault('CoAuthoring', {})
token = coauthoring.setdefault('token', {})
enable = token.setdefault('enable', {})
request_enable = enable.setdefault('request', {})
request_enable['inbox'] = True
request_enable['outbox'] = True
enable['browser'] = True

secret_root = coauthoring.setdefault('secret', {})
for section in ('inbox', 'outbox', 'session'):
    section_config = secret_root.setdefault(section, {})
    section_config['string'] = secret

config_path.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + '\n',
    encoding='utf-8',
)
PY

  systemctl restart ds-converter ds-docservice ds-metrics
}

render_env_file() {
  mkdir -p "$(dirname "${ENV_OUTPUT}")"
  cat > "${ENV_OUTPUT}" <<EOF
X_FRAME_OPTIONS=SAMEORIGIN
ONLYOFFICE_ENABLED=True
ONLYOFFICE_SERVER_URL=http://127.0.0.1:${ONLYOFFICE_PORT}
ONLYOFFICE_PUBLIC_PATH=${PUBLIC_PATH}
ONLYOFFICE_JWT_SECRET=${JWT_SECRET}
ONLYOFFICE_JWT_HEADER=Authorization
ONLYOFFICE_VERIFY_SSL=False
ONLYOFFICE_CALLBACK_BASE_URL=https://${DOMAIN}
EOF
  echo "[INFO] Wrote dtcall env snippet: ${ENV_OUTPUT}"
}

render_nginx_config() {
  mkdir -p "$(dirname "${NGINX_OUTPUT}")"
  cat > "${NGINX_OUTPUT}" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 100m;

    location ${PUBLIC_PATH} {
        proxy_pass http://127.0.0.1:${ONLYOFFICE_PORT}/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
    }

    location / {
        proxy_pass http://${DJANGO_UPSTREAM};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
  echo "[INFO] Wrote nginx site config: ${NGINX_OUTPUT}"
}

print_next_steps() {
  cat <<EOF

[DONE] ONLYOFFICE companion deployment files are ready.

Next steps:
  1. Merge ${ENV_OUTPUT} into your dtcall process env file.
  2. Enable the nginx site and reload nginx:
       ln -sf ${NGINX_OUTPUT} /etc/nginx/sites-enabled/$(basename "${NGINX_OUTPUT}")
       nginx -t && systemctl reload nginx
  3. Restart dtcall, then run:
       python manage.py check_onlyoffice

If you are using HTTPS, add your TLS server block before going live.
EOF
}

require_root
parse_args "$@"
normalize_public_path
validate_args
install_onlyoffice
configure_onlyoffice_jwt
render_env_file
render_nginx_config
print_next_steps
