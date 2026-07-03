import os
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def _should_skip_auto_start():
    if not env_bool('AUTO_START_PROJECT_RISK_REFRESH_SCHEDULER', True):
        return True
    if os.environ.get('DTCALL_PROJECT_RISK_SCHEDULER_CHILD') == '1':
        return True
    if os.environ.get('DTCALL_PROJECT_RISK_SCHEDULER_STARTED') == '1':
        return True
    return False


def _build_scheduler_command():
    hour = os.environ.get('PROJECT_RISK_REFRESH_HOUR', '12').strip() or '12'
    minute = os.environ.get('PROJECT_RISK_REFRESH_MINUTE', '0').strip() or '0'
    sleep_step = os.environ.get('PROJECT_RISK_REFRESH_SLEEP_STEP', '60').strip() or '60'
    return [
        sys.executable,
        str(BASE_DIR / 'manage.py'),
        'run_project_risk_refresh_scheduler',
        '--hour',
        hour,
        '--minute',
        minute,
        '--sleep-step',
        sleep_step,
    ]


def start_project_risk_scheduler_subprocess(*, context='runserver'):
    if _should_skip_auto_start():
        return False

    if context == 'runserver':
        if len(sys.argv) < 2 or sys.argv[1] != 'runserver':
            return False

    env = os.environ.copy()
    env['DTCALL_PROJECT_RISK_SCHEDULER_CHILD'] = '1'
    env['DTCALL_SKIP_STARTUP_MIGRATE'] = '1'

    kwargs = {
        'cwd': str(BASE_DIR),
        'env': env,
        'stdin': subprocess.DEVNULL,
        'stdout': subprocess.DEVNULL,
        'stderr': subprocess.DEVNULL,
    }

    if os.name == 'nt':
        kwargs['creationflags'] = (
            subprocess.CREATE_NEW_PROCESS_GROUP |
            subprocess.DETACHED_PROCESS |
            subprocess.CREATE_NO_WINDOW
        )
    else:
        kwargs['start_new_session'] = True

    subprocess.Popen(_build_scheduler_command(), **kwargs)
    os.environ['DTCALL_PROJECT_RISK_SCHEDULER_STARTED'] = '1'
    return True
