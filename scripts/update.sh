#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"
log()  { echo -e "${GREEN}[UPDATE]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

CURRENT_VERSION="$(cat VERSION 2>/dev/null || echo 0.0.0)"
CURRENT_COMMIT="$(git rev-parse --short HEAD)"
log "Current: $CURRENT_VERSION ($CURRENT_COMMIT)"

git fetch --tags --quiet
TARGET="${1:-$(git tag --sort=-version:refname | grep -E '^[0-9]+' | head -1)}"
if [ -z "$TARGET" ]; then err "No tags found"; exit 1; fi
if [ "$TARGET" = "$CURRENT_VERSION" ]; then log "Already latest"; exit 0; fi
log "Target: $TARGET"

mkdir -p backups/pre_update
BF="backups/pre_update/pre_update_${CURRENT_VERSION}_$(date +%Y%m%d_%H%M%S).dump"
if command -v pg_dump &>/dev/null; then
  PGPASSWORD="${DATABASE_PASSWORD:-${POSTGRES_PASSWORD:-}}" pg_dump -h "${DATABASE_HOST:-localhost}" -p "${DATABASE_PORT:-5432}" -U "${DATABASE_USER:-dtcall_user}" -d "${DATABASE_NAME:-dtcall}" -F c -f "$BF" && log "Backup: $BF"
elif [ -f db.sqlite3 ]; then
  cp db.sqlite3 "${BF}.sqlite3" && log "Backup: ${BF}.sqlite3"
fi

cat > .rollback_state <<RBEOF
{"previous_commit":"$CURRENT_COMMIT","previous_version":"$CURRENT_VERSION","target_version":"$TARGET","timestamp":"$(date -Iseconds)"}
RBEOF

log "Checking out $TARGET..."
git checkout "$TARGET"
echo "$TARGET" > VERSION

python manage.py migrate --noinput || { err "Migration failed"; git checkout "$CURRENT_COMMIT"; echo "$CURRENT_VERSION" > VERSION; rm -f .rollback_state; exit 1; }
python manage.py collectstatic --noinput || true

if [ -f docker-compose.yml ]; then
  (docker-compose 2>/dev/null || docker compose) -f docker-compose.yml up -d --force-recreate web
fi

log "Done: $CURRENT_VERSION -> $TARGET. Rollback: ./scripts/rollback.sh"
