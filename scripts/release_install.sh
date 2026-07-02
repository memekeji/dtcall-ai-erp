#!/bin/bash
set -euo pipefail

DEPLOY_ROOT="${DTCALL_DEPLOY_ROOT:-/opt/dtcall}"
PACKAGE_PATH="${1:-}"

if [ -z "$PACKAGE_PATH" ]; then
  echo "Usage: ./install.sh /path/to/dtcall-release-<version>-linux-x86_64.zip"
  exit 1
fi

mkdir -p "$DEPLOY_ROOT/releases" "$DEPLOY_ROOT/shared/env" "$DEPLOY_ROOT/shared/media" "$DEPLOY_ROOT/shared/backups" "$DEPLOY_ROOT/shared/runtime" "$DEPLOY_ROOT/downloads"
cp "$PACKAGE_PATH" "$DEPLOY_ROOT/downloads/"
echo "Release package copied to $DEPLOY_ROOT/downloads"
echo "Offline import command:"
echo "  python manage.py import_release_package $DEPLOY_ROOT/downloads/$(basename "$PACKAGE_PATH")"
