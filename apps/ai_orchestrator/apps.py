from django.apps import AppConfig
from django.db.models.signals import post_save
import threading


class AiOrchestratorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_orchestrator"

    def ready(self):
        from apps.user.models.admin_log import AdminLog
        from .workflow_engine import MarketingAutomation

        def admin_log_saved(sender, instance, created, **kwargs):
            if created:
                # 在后台线程中触发AI营销分析，避免阻塞主流程
                def trigger_ai():
                    class DummyEvent:
                        user_id = instance.admin_id
                        action_type = instance.title or "unknown_action"
                        details = {
                            "url": instance.url,
                            "content": instance.content,
                            "ip": instance.ip
                        }
                    MarketingAutomation.monitor_event_log(DummyEvent())
                
                threading.Thread(target=trigger_ai, daemon=True).start()

        post_save.connect(admin_log_saved, sender=AdminLog)
