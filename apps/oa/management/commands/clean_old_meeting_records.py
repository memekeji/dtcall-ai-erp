from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    """
    清理旧的会议记录表命令
    安全删除oa_meeting_records表，避免事务管理问题
    """
    help = '清理旧的会议记录表和相关引用'

    def handle(self, *args, **options):
        self.stdout.write('开始清理旧的会议记录数据...')
        
        # 直接使用connection执行DROP TABLE，不使用事务
        with connection.cursor() as cursor:
            # 检查表是否存在
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s AND table_name = %s",
                (connection.settings_dict['NAME'], 'oa_meeting_records')
            )
            
            if cursor.fetchone():
                self.stdout.write('找到旧的会议记录表，准备删除...')
                # 简化方法，直接删除表
                cursor.execute("DROP TABLE IF EXISTS oa_meeting_records CASCADE")
                self.stdout.write(self.style.SUCCESS('成功删除旧的会议记录表'))
            else:
                self.stdout.write('旧的会议记录表不存在，无需删除')
        
        self.stdout.write(self.style.SUCCESS('清理操作完成！'))