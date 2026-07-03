#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def load_env_file():
    env_path = BASE_DIR / '.env'
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        _set_env_from_file(key, value)


def _set_env_from_file(key, value):
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    current = os.environ.get(key)
    if current is None or current.strip() == '':
        os.environ[key] = value


def configure_runserver_addrport():
    if len(sys.argv) < 2 or sys.argv[1] != 'runserver':
        return

    has_addrport = any(arg and not arg.startswith('-') for arg in sys.argv[2:])
    if has_addrport:
        return

    app_port = os.environ.get('APP_PORT') or os.environ.get('PORT')
    if not app_port:
        return

    app_host = os.environ.get('APP_HOST', '0.0.0.0')
    sys.argv.insert(2, f'{app_host}:{app_port}')


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def run_startup_migrations():
    if len(sys.argv) < 2 or sys.argv[1] != 'runserver':
        return
    if not env_bool('AUTO_MIGRATE_ON_STARTUP', True):
        return
    if env_bool('DTCALL_SKIP_STARTUP_MIGRATE', False):
        return
    if os.environ.get('DTCALL_STARTUP_MIGRATED') == '1':
        return
    if not has_explicit_database_config():
        print(
            'No database configuration detected; '
            'startup migrations skipped for the web database setup page.'
        )
        return

    os.environ['DTCALL_STARTUP_MIGRATED'] = '1'
    env = os.environ.copy()
    env['DTCALL_SKIP_STARTUP_MIGRATE'] = '1'
    print('Running startup database migrations...')
    try:
        subprocess.check_call(
            [sys.executable, str(BASE_DIR / 'manage.py'), 'migrate', '--noinput'],
            cwd=str(BASE_DIR),
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        print(
            'Startup database migrations failed; '
            'the web database setup page will handle configuration. '
            f'Exit code: {exc.returncode}'
        )


def has_explicit_database_config():
    return any(
        os.environ.get(name, '').strip()
        for name in (
            'DATABASE_URL',
            'DATABASE_ENGINE',
            'DATABASE_TYPE',
            'DB_ENGINE',
            'DATABASE_HOST',
        )
    )


def main():
    """Run administrative tasks."""
    load_env_file()
    configure_runserver_addrport()
    run_startup_migrations()
    try:
        from dtcall.startup_tasks import start_project_risk_scheduler_subprocess

        start_project_risk_scheduler_subprocess(context='runserver')
    except Exception as exc:
        print(f'Auto-start project risk refresh scheduler skipped: {exc}')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
