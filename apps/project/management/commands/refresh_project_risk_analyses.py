from django.core.management.base import BaseCommand

from apps.project.risk_analysis import project_risk_analysis_service


class Command(BaseCommand):
    help = '为所有有效项目生成最新风险分析结果'

    def handle(self, *args, **options):
        analyses = project_risk_analysis_service.analyze_all_projects(trigger_source='scheduled')
        self.stdout.write(
            self.style.SUCCESS(f'已完成 {len(analyses)} 个项目的风险分析刷新')
        )
