import logging
import time
from django.core.management.base import BaseCommand


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "运行 AI Orchestrator 侧车进程"

    def add_arguments(self, parser):
        parser.add_argument(
            "--heartbeat-seconds",
            type=int,
            default=30,
        )

    def handle(self, *args, **options):
        from apps.ai_orchestrator import orchestrator
        _ = orchestrator.AIOperatorBus

        heartbeat_seconds = int(options.get("heartbeat_seconds") or 30)
        logger.info("AI Orchestrator 已启动")

        while True:
            time.sleep(max(1, heartbeat_seconds))
