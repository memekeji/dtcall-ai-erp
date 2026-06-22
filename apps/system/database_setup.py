import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse

from django.conf import settings
from django.core.management import call_command
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.utils import load_backend


SETUP_PATH = '/setup/database/'
BASE_DIR = Path(settings.BASE_DIR)
ENV_PATH = BASE_DIR / '.env'
STATE_TTL_SECONDS = 10

DATABASE_ENGINE_ALIASES = {
    'sqlite': 'django.db.backends.sqlite3',
    'sqlite3': 'django.db.backends.sqlite3',
    'postgres': 'django.db.backends.postgresql',
    'postgresql': 'django.db.backends.postgresql',
    'pgsql': 'django.db.backends.postgresql',
    'psql': 'django.db.backends.postgresql',
    'mysql': 'django.db.backends.mysql',
    'mariadb': 'django.db.backends.mysql',
}

_state_cache = {
    'checked_at': 0.0,
    'state': None,
}


@dataclass
class DatabaseState:
    can_connect: bool
    has_tables: bool
    reason: str = ''

    @property
    def needs_setup(self):
        return not self.can_connect or not self.has_tables

    @property
    def is_locked(self):
        return self.can_connect and self.has_tables


def resolve_database_engine(value):
    engine = (value or '').strip()
    if not engine:
        return ''
    normalized = engine.lower()
    if normalized in DATABASE_ENGINE_ALIASES:
        return DATABASE_ENGINE_ALIASES[normalized]
    if engine.startswith('django.db.backends.'):
        return engine
    raise ValueError('不支持的数据库类型')


def build_database_config(data):
    raw_engine = (data.get('DATABASE_ENGINE') or 'postgresql').strip()
    engine = resolve_database_engine(raw_engine)
    database_url = (data.get('DATABASE_URL') or '').strip()
    if database_url and engine != 'django.db.backends.sqlite3':
        return _database_config_from_url(database_url)

    name = (data.get('DATABASE_NAME') or '').strip()
    if engine == 'django.db.backends.sqlite3':
        db_name = name or 'db.sqlite3'
        db_path = Path(db_name)
        if db_name != ':memory:' and not db_path.is_absolute():
            db_name = str(BASE_DIR / db_path)
        _ensure_sqlite_parent(db_name)
        return {
            'ENGINE': engine,
            'NAME': db_name,
        }

    default_port = '3306' if engine == 'django.db.backends.mysql' else '5432'
    config = {
        'ENGINE': engine,
        'NAME': name or 'dtcall',
        'USER': (data.get('DATABASE_USER') or '').strip(),
        'PASSWORD': (data.get('DATABASE_PASSWORD') or '').strip(),
        'HOST': (data.get('DATABASE_HOST') or '127.0.0.1').strip(),
        'PORT': (data.get('DATABASE_PORT') or default_port).strip(),
        'CONN_MAX_AGE': _int_value(
            data.get('DATABASE_CONN_MAX_AGE'), 1800, '连接复用'),
        'CONN_HEALTH_CHECKS': _as_bool(
            data.get('DATABASE_CONN_HEALTH_CHECKS'), True),
    }
    options = {}
    connect_timeout = _int_value(
        data.get('DATABASE_CONNECT_TIMEOUT'), 10, '连接超时')
    if connect_timeout:
        options['connect_timeout'] = connect_timeout
    if engine == 'django.db.backends.mysql':
        options['charset'] = (data.get('MYSQL_CHARSET') or 'utf8mb4').strip()
        options['init_command'] = (
            data.get('MYSQL_INIT_COMMAND')
            or "SET sql_mode='STRICT_TRANS_TABLES'"
        )
    if options:
        config['OPTIONS'] = options
    return config


def test_database_config(config):
    wrapper = None
    try:
        backend = load_backend(config['ENGINE'])
        wrapper = backend.DatabaseWrapper(
            _complete_database_config(config),
            alias='setup_validation',
        )
        wrapper.ensure_connection()
        with wrapper.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    finally:
        if wrapper is not None:
            wrapper.close()


def get_database_state(force=False):
    if not has_explicit_database_config():
        return DatabaseState(
            can_connect=False,
            has_tables=False,
            reason='未配置数据库连接',
        )

    now = time.monotonic()
    cached = _state_cache['state']
    if (
        not force
        and cached is not None
        and now - _state_cache['checked_at'] < STATE_TTL_SECONDS
    ):
        return cached

    try:
        connection = connections[DEFAULT_DB_ALIAS]
        connection.ensure_connection()
        tables = connection.introspection.table_names()
        state = DatabaseState(can_connect=True, has_tables=bool(tables))
    except Exception as exc:
        connections.close_all()
        state = DatabaseState(
            can_connect=False,
            has_tables=False,
            reason=str(exc),
        )

    _state_cache['checked_at'] = now
    _state_cache['state'] = state
    return state


def save_database_environment(form_data):
    engine = resolve_database_engine(
        (form_data.get('DATABASE_ENGINE') or 'postgresql').strip())
    is_sqlite = engine == 'django.db.backends.sqlite3'
    sqlite_name = (form_data.get('DATABASE_NAME') or '').strip() or 'db.sqlite3'
    updates = {
        'DATABASE_URL': '' if is_sqlite else (
            form_data.get('DATABASE_URL') or '').strip(),
        'DATABASE_ENGINE': (form_data.get('DATABASE_ENGINE') or '').strip(),
        'DATABASE_HOST': '' if is_sqlite else (
            form_data.get('DATABASE_HOST') or '').strip(),
        'DATABASE_PORT': '' if is_sqlite else (
            form_data.get('DATABASE_PORT') or '').strip(),
        'DATABASE_NAME': sqlite_name if is_sqlite else (
            form_data.get('DATABASE_NAME') or '').strip(),
        'DATABASE_USER': '' if is_sqlite else (
            form_data.get('DATABASE_USER') or '').strip(),
        'DATABASE_PASSWORD': '' if is_sqlite else (
            form_data.get('DATABASE_PASSWORD') or '').strip(),
        'DATABASE_CONN_MAX_AGE': '0' if is_sqlite else (
            form_data.get('DATABASE_CONN_MAX_AGE') or '1800').strip(),
        'DATABASE_CONN_HEALTH_CHECKS': 'False' if is_sqlite else (
            form_data.get('DATABASE_CONN_HEALTH_CHECKS') or 'True').strip(),
        'DATABASE_CONNECT_TIMEOUT': '' if is_sqlite else (
            form_data.get('DATABASE_CONNECT_TIMEOUT') or '10').strip(),
        'MYSQL_CHARSET': '' if is_sqlite else (
            form_data.get('MYSQL_CHARSET') or 'utf8mb4').strip(),
        'MYSQL_INIT_COMMAND': '' if is_sqlite else (
            form_data.get('MYSQL_INIT_COMMAND')
            or "SET sql_mode='STRICT_TRANS_TABLES'"
        ).strip(),
        'AUTO_MIGRATE_ON_STARTUP': 'True',
    }
    _write_env(updates)
    os.environ.update(updates)


def apply_database_config(config):
    complete_config = _complete_database_config(config)
    settings.DATABASES[DEFAULT_DB_ALIAS] = complete_config
    connections.databases[DEFAULT_DB_ALIAS] = complete_config
    connections.close_all()
    _clear_state_cache()


def run_base_migrations():
    call_command('migrate', interactive=False, verbosity=1)
    _clear_state_cache()
    return get_database_state(force=True)


def current_form_values():
    engine = os.environ.get('DATABASE_ENGINE', 'postgresql') or 'postgresql'
    is_sqlite = resolve_database_engine(engine) == 'django.db.backends.sqlite3'
    return {
        'DATABASE_URL': os.environ.get('DATABASE_URL', ''),
        'DATABASE_ENGINE': engine,
        'DATABASE_HOST': os.environ.get('DATABASE_HOST', ''),
        'DATABASE_PORT': os.environ.get('DATABASE_PORT', ''),
        'DATABASE_NAME': os.environ.get(
            'DATABASE_NAME', 'db.sqlite3' if is_sqlite else 'dtcall'
        ) or ('db.sqlite3' if is_sqlite else 'dtcall'),
        'DATABASE_USER': os.environ.get('DATABASE_USER', ''),
        'DATABASE_PASSWORD': os.environ.get('DATABASE_PASSWORD', ''),
        'DATABASE_CONN_MAX_AGE': os.environ.get('DATABASE_CONN_MAX_AGE', '1800'),
        'DATABASE_CONN_HEALTH_CHECKS': os.environ.get(
            'DATABASE_CONN_HEALTH_CHECKS', 'True'),
        'DATABASE_CONNECT_TIMEOUT': os.environ.get(
            'DATABASE_CONNECT_TIMEOUT', '10'),
        'MYSQL_CHARSET': os.environ.get('MYSQL_CHARSET', 'utf8mb4'),
        'MYSQL_INIT_COMMAND': os.environ.get(
            'MYSQL_INIT_COMMAND', "SET sql_mode='STRICT_TRANS_TABLES'"),
    }


def has_explicit_database_config():
    return any(
        os.environ.get(name, '').strip()
        for name in ('DATABASE_URL', 'DATABASE_ENGINE', 'DATABASE_HOST')
    )


def is_setup_path(path):
    return path.startswith(SETUP_PATH)


def _write_env(updates):
    lines = []
    seen = set()
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding='utf-8').splitlines()

    output = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in line:
            output.append(line)
            continue
        key = line.split('=', 1)[0].strip()
        if key in updates:
            output.append(f'{key}={_env_value(updates[key])}')
            seen.add(key)
        else:
            output.append(line)

    missing = [key for key in updates if key not in seen]
    if missing and output and output[-1].strip():
        output.append('')
    for key in missing:
        output.append(f'{key}={_env_value(updates[key])}')

    ENV_PATH.write_text('\n'.join(output) + '\n', encoding='utf-8')


def _database_config_from_url(database_url):
    parsed = urlparse(database_url)
    engine = resolve_database_engine(parsed.scheme.split('+', 1)[0])
    if engine == 'django.db.backends.sqlite3':
        db_name = unquote(parsed.path.lstrip('/')) or 'db.sqlite3'
        db_path = Path(db_name)
        if db_name != ':memory:' and not db_path.is_absolute():
            db_name = str(BASE_DIR / db_path)
        _ensure_sqlite_parent(db_name)
        return {
            'ENGINE': engine,
            'NAME': db_name,
        }

    config = {
        'ENGINE': engine,
        'NAME': unquote(parsed.path.lstrip('/')) or 'dtcall',
        'USER': unquote(parsed.username or ''),
        'PASSWORD': unquote(parsed.password or ''),
        'HOST': parsed.hostname or '127.0.0.1',
        'PORT': str(parsed.port or (
            3306 if engine == 'django.db.backends.mysql' else 5432)),
        'CONN_MAX_AGE': _int_value(
            os.environ.get('DATABASE_CONN_MAX_AGE'), 1800, '连接复用'),
        'CONN_HEALTH_CHECKS': True,
    }
    options = dict(parse_qsl(parsed.query))
    if engine == 'django.db.backends.mysql':
        options.setdefault('charset', os.environ.get('MYSQL_CHARSET', 'utf8mb4'))
        options.setdefault('init_command', "SET sql_mode='STRICT_TRANS_TABLES'")
    if options:
        config['OPTIONS'] = options
    return config


def _as_bool(value, default=False):
    if value is None or value == '':
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _int_value(value, default, label):
    if value is None or str(value).strip() == '':
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{label}必须是整数') from exc


def _env_value(value):
    return str(value).replace('\r', ' ').replace('\n', ' ').strip()


def _ensure_sqlite_parent(db_name):
    if db_name == ':memory:':
        return
    Path(db_name).expanduser().parent.mkdir(parents=True, exist_ok=True)


def _complete_database_config(config):
    complete = {
        'ATOMIC_REQUESTS': False,
        'AUTOCOMMIT': True,
        'CONN_HEALTH_CHECKS': False,
        'CONN_MAX_AGE': 0,
        'ENGINE': '',
        'HOST': '',
        'NAME': '',
        'OPTIONS': {},
        'PASSWORD': '',
        'PORT': '',
        'TEST': {
            'CHARSET': None,
            'COLLATION': None,
            'MIGRATE': True,
            'MIRROR': None,
            'NAME': None,
        },
        'TIME_ZONE': None,
        'USER': '',
    }
    complete.update(config)
    complete['OPTIONS'] = dict(config.get('OPTIONS') or {})
    test_config = dict(complete['TEST'] or {})
    for key, value in {
        'CHARSET': None,
        'COLLATION': None,
        'MIGRATE': True,
        'MIRROR': None,
        'NAME': None,
    }.items():
        test_config.setdefault(key, value)
    complete['TEST'] = test_config
    return complete


def _clear_state_cache():
    _state_cache['checked_at'] = 0.0
    _state_cache['state'] = None
