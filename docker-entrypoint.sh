#!/bin/bash
set -e

has_database_config() {
  [ -n "${DATABASE_URL:-}" ] || \
  [ -n "${DATABASE_ENGINE:-}" ] || \
  [ -n "${DATABASE_TYPE:-}" ] || \
  [ -n "${DB_ENGINE:-}" ] || \
  [ -n "${DATABASE_HOST:-}" ]
}

if [ "${AUTO_MIGRATE_ON_STARTUP:-true}" = "true" ] && has_database_config; then
  echo "Running database migrations..."
  python manage.py migrate --noinput || echo "Startup database migrations failed; continuing so the web database setup page can handle configuration."
elif [ "${AUTO_MIGRATE_ON_STARTUP:-true}" = "true" ]; then
  echo "No database configuration detected; skipping startup migrations for the web setup page."
fi

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn server..."
exec gunicorn dtcall.wsgi:application --bind ${APP_HOST:-0.0.0.0}:${APP_PORT:-8000} --workers ${GUNICORN_WORKERS:-4}
