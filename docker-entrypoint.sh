#!/bin/bash
set -e

if [ "${AUTO_MIGRATE_ON_STARTUP:-true}" = "true" ]; then
  echo "Running database migrations..."
  python manage.py migrate --noinput || echo "Startup database migrations failed; continuing so the web database setup page can handle configuration."
fi

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn server..."
exec gunicorn dtcall.wsgi:application --bind ${APP_HOST:-0.0.0.0}:${APP_PORT:-8000} --workers ${GUNICORN_WORKERS:-4}
