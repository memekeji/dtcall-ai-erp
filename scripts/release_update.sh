#!/bin/bash
set -euo pipefail

DEPLOY_ROOT="${DTCALL_DEPLOY_ROOT:-/opt/dtcall}"
PACKAGE_PATH="${1:-}"
MANAGE_PY_PATH="${DTCALL_MANAGE_PY:-$DEPLOY_ROOT/current/manage.py}"

if [ -z "$PACKAGE_PATH" ]; then
  echo "Usage: ./update.sh /path/to/dtcall-release-<version>-linux-x86_64.zip"
  exit 1
fi

python3 "$MANAGE_PY_PATH" import_release_package "$PACKAGE_PATH"
