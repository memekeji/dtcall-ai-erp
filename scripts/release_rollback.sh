#!/bin/bash
set -euo pipefail

DEPLOY_ROOT="${DTCALL_DEPLOY_ROOT:-/opt/dtcall}"
CURRENT_LINK="$DEPLOY_ROOT/current"
MANAGE_PY_PATH="${DTCALL_MANAGE_PY:-$DEPLOY_ROOT/current/manage.py}"

if [ ! -L "$CURRENT_LINK" ]; then
  echo "No current symlink found at $CURRENT_LINK"
  exit 1
fi

python3 "$MANAGE_PY_PATH" rollback_update
