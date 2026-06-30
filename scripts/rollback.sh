#!/bin/bash
set -euo pipefail

ROOT="$(dirname "$(dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")")"
cd "$ROOT"

[ -f .rollback_state ] || { echo "No rollback state"; exit 1; }
PC="$(python3 -c "import json;print(json.load(open('.rollback_state'))['previous_commit'])")"
PV="$(python3 -c "import json;print(json.load(open('.rollback_state'))['previous_version'])")"
echo "Rolling back to $PV ($PC)"

git checkout "$PC"
echo "$PV" > VERSION
python manage.py migrate --noinput || true
python manage.py collectstatic --noinput || true
rm -f .rollback_state

if [ -f docker-compose.yml ]; then
  (docker-compose 2>/dev/null || docker compose) -f docker-compose.yml up -d --force-recreate web
fi

echo "Rollback complete. Restored to $PV."
