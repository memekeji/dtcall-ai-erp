from django.core.management.base import BaseCommand, CommandError
from apps.ai.services.rag_service import rag_service


class Command(BaseCommand):
    help = '管理向量：批量生成、更新或优化向量'

    def add_arguments(self, parser):
        # 命令模式
        parser.add_argument(
            'mode',
            type=str,
            choices=[
                'generate',
                'update',
                'optimize'],
            help='操作模式：generate（批量生成）、update（更新所有向量）、optimize（优化低质量向量）')

        # 可选参数：知识条目ID列表
        parser.add_argument('--ids', type=str, help='指定知识条目ID列表，用逗号分隔')

        # 可选参数：质量阈值（仅用于优化模式）
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.7,
            help='向量质量阈值，低于此值的向量将被优化')

    def handle(self, *args, **options):
        mode = options['mode']
        ids = options['ids']
        threshold = options['threshold']

        try:
            if mode == 'generate':
                # 批量生成向量
                if ids:
                    # 解析ID列表
                    knowledge_item_ids = [int(id.strip())
                                          for id in ids.split(',') if id.strip()]
                    result = rag_service.batch_generate_vectors(
                        knowledge_item_ids)
                    self.stdout.write(self.style.SUCCESS(f'成功为指定知识条目生成向量'))
                else:
                    result = rag_service.batch_generate_vectors()
                    self.stdout.write(self.style.SUCCESS(f'成功为所有知识条目生成向量'))

            elif mode == 'update':
                # 更新所有向量
                result = rag_service.batch_generate_vectors()
                self.stdout.write(self.style.SUCCESS(f'成功更新所有向量'))

            elif mode == 'optimize':
                # 优化低质量向量
                result = rag_service.optimize_vectors(
                    quality_threshold=threshold)
                if 'error' in result:
                    raise CommandError(f'向量优化失败：{result["error"]}')

                self.stdout.write(self.style.SUCCESS(f'向量优化完成：'))
                self.stdout.write(f'  评估向量总数：{result["total_evaluated"]}')
                self.stdout.write(f'  低质量向量数：{result["low_quality_count"]}')
                self.stdout.write(f'  优化向量数：{result["optimized_count"]}')
                self.stdout.write(f'  使用的质量阈值：{result["quality_threshold"]}')

        except Exception as e:
            raise CommandError(f'操作失败：{str(e)}')
