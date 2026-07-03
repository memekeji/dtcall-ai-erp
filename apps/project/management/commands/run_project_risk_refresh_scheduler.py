import logging
import os
import time
from datetime import timedelta
from pathlib import Path

from django.core.management import BaseCommand, call_command
from django.utils import timezone


logger = logging.getLogger(__name__)
PID_FILE = Path(__file__).resolve().parents[4] / 'runtime' / 'project_risk_refresh_scheduler.pid'


def _local_now():
    current = timezone.now()
    if timezone.is_aware(current):
        return timezone.localtime(current)
    return current


def get_next_run_time(now=None, *, hour=12, minute=0):
    current = now or _local_now()
    current = timezone.localtime(current) if timezone.is_aware(current) else current
    next_run = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if next_run <= current:
        next_run += timedelta(days=1)
    return next_run


def _is_process_running(pid):
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def acquire_scheduler_lock():
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            fd = os.open(str(PID_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w', encoding='utf-8') as lock_file:
                lock_file.write(str(os.getpid()))
            return True
        except FileExistsError:
            try:
                existing_pid = int(PID_FILE.read_text(encoding='utf-8').strip() or '0')
            except (OSError, ValueError):
                existing_pid = 0

            if _is_process_running(existing_pid):
                return False

            try:
                PID_FILE.unlink()
            except FileNotFoundError:
                continue


def release_scheduler_lock():
    try:
        if not PID_FILE.exists():
            return
        existing_pid = int(PID_FILE.read_text(encoding='utf-8').strip() or '0')
        if existing_pid == os.getpid():
            PID_FILE.unlink()
    except (OSError, ValueError):
        return


class Command(BaseCommand):
    help = '每天定时刷新所有项目风险分析结果'

    def add_arguments(self, parser):
        parser.add_argument('--hour', type=int, default=12, help='每日执行小时，默认 12')
        parser.add_argument('--minute', type=int, default=0, help='每日执行分钟，默认 0')
        parser.add_argument('--sleep-step', type=int, default=60, help='等待时的轮询间隔秒数')
        parser.add_argument('--once', action='store_true', help='仅执行一次后退出')

    def handle(self, *args, **options):
        if not acquire_scheduler_lock():
            self.stdout.write(self.style.WARNING('项目风险分析定时调度已在运行，跳过重复启动'))
            return

        hour = max(0, min(int(options.get('hour') or 12), 23))
        minute = max(0, min(int(options.get('minute') or 0), 59))
        sleep_step = max(1, int(options.get('sleep_step') or 60))
        run_once = bool(options.get('once'))

        try:
            if run_once:
                self._run_refresh()
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f'项目风险分析定时调度已启动，每天 {hour:02d}:{minute:02d} 执行'
                )
            )
            while True:
                next_run = get_next_run_time(_local_now(), hour=hour, minute=minute)
                wait_seconds = max(0, int((next_run - _local_now()).total_seconds()))
                logger.info('项目风险分析下一次执行时间: %s', next_run)

                while wait_seconds > 0:
                    sleep_seconds = min(sleep_step, wait_seconds)
                    time.sleep(sleep_seconds)
                    wait_seconds -= sleep_seconds

                self._run_refresh()
        finally:
            release_scheduler_lock()

    def _run_refresh(self):
        logger.info('开始执行项目风险分析定时刷新')
        try:
            call_command('refresh_project_risk_analyses', verbosity=1)
            logger.info('项目风险分析定时刷新完成')
        except Exception:
            logger.exception('项目风险分析定时刷新失败')
