from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from apps.system.models import SystemBackup
import os
import logging
from datetime import datetime
import threading
import subprocess
import traceback

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = 'Create a database backup'

    def add_arguments(self, parser):
        parser.add_argument('--name', type=str, help='Backup name')
        parser.add_argument(
            '--type',
            type=str,
            default='full',
            help='Backup type: full, incremental, differential')
        parser.add_argument(
            '--description',
            type=str,
            default='',
            help='Backup description')

    def handle(self, *args, **options):
        try:
            # 获取参数
            backup_name = options['name'] or f'auto_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            backup_type = options['type']
            description = options['description']

            # 创建备份记录
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                admin_user = User.objects.first()

            backup = SystemBackup(
                name=backup_name,
                backup_type=backup_type,
                description=description,
                creator=admin_user
            )

            # 确保media目录存在
            if not os.path.exists(settings.MEDIA_ROOT):
                os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

            # 创建备份目录
            backup_dir = os.path.join(
                settings.MEDIA_ROOT,
                'backups',
                datetime.now().strftime('%Y%m%d'))
            os.makedirs(backup_dir, exist_ok=True)

            # 生成备份文件名，根据备份类型添加后缀
            timestamp = datetime.now().strftime('%H%M%S')
            backup_filename = f"{backup.name}_{timestamp}_{backup.backup_type}.sql"
            backup.file_path = os.path.join(
                'backups', datetime.now().strftime('%Y%m%d'), backup_filename)

            # 先保存备份记录，生成ID
            backup.save()

            logger.info(f'开始创建数据备份：{backup.name}')

            # 定义备份函数
            def async_backup():
                try:
                    # 确保目录存在
                    backup_dir = os.path.dirname(os.path.join(
                        settings.MEDIA_ROOT, backup.file_path))
                    os.makedirs(backup_dir, exist_ok=True)
                    full_backup_path = os.path.join(
                        settings.MEDIA_ROOT, backup.file_path)

                    # 获取数据库配置
                    db_config = settings.DATABASES['default']
                    schema = db_config['OPTIONS']['options'].split('=')[
                        1]  # 获取schema

                    # 使用PostgreSQL的pg_dump命令来备份数据，生成完整的SQL格式备份
                    # 构建pg_dump命令，确保包含完整的数据库结构和数据
                    pg_dump_cmd = [
                        'pg_dump',
                        '-h', db_config['HOST'],
                        '-p', str(db_config['PORT']),
                        '-U', db_config['USER'],
                        '--schema', schema,
                        '--format', 'plain',  # 生成纯SQL格式
                        '--create',  # 包含创建数据库语句
                        '--clean',  # 包含清理数据库对象语句
                        '--if-exists',  # 清理时使用IF EXISTS
                        '--no-owner',  # 不包含所有者信息
                        '--no-privileges',  # 不包含权限信息
                        '--encoding', 'UTF8',  # 使用UTF-8编码
                        '--verbose',  # 详细输出
                        '--file', full_backup_path
                    ]

                    # 设置环境变量，避免输入密码
                    env = os.environ.copy()
                    env['PGPASSWORD'] = db_config['PASSWORD']
                    env['PGDATABASE'] = db_config['NAME']

                    # 执行pg_dump命令
                    subprocess.run(pg_dump_cmd, env=env, check=True)

                    # 获取备份文件大小
                    file_size = os.path.getsize(full_backup_path)

                    # 更新数据库记录
                    backup_obj = SystemBackup.objects.get(id=backup.id)
                    backup_obj.file_size = file_size
                    backup_obj.save()

                    # 记录日志
                    logger.info(f'数据备份创建成功：{backup.name}，文件大小：{file_size}字节')
                    self.stdout.write(
                        self.style.SUCCESS(f'数据备份创建成功：{backup.name}，文件大小：{file_size}字节'))
                except Exception as e:
                    # 记录详细错误信息
                    error_msg = f'备份失败：{str(e)}\n{traceback.format_exc()}'
                    logger.error(error_msg)
                    self.stderr.write(self.style.ERROR(f'备份失败：{str(e)}'))

            # 使用线程异步执行备份
            backup_thread = threading.Thread(target=async_backup)
            backup_thread.start()

            self.stdout.write(self.style.SUCCESS(
                f'数据{backup.get_backup_type_display()}任务已创建，正在后台执行中！'))
        except Exception as e:
            logger.error(f'创建备份失败：{str(e)}')
            self.stderr.write(self.style.ERROR(f'创建备份失败：{str(e)}'))
