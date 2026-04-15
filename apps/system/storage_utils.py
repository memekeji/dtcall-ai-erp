"""
存储工具模块 - 提供简化的文件存储接口

使用方法:
    from apps.system.storage_utils import storage_utils

    # 保存文件（自动同步到所有启用的存储位置）
    file_path = storage_utils.save_file(file_obj, 'uploads/')

    # 删除文件（从所有存储位置删除）
    storage_utils.delete_file(file_path)

    # 获取文件URL
    file_url = storage_utils.get_url(file_path)

    # 检查文件是否存在
    exists = storage_utils.exists(file_path)
"""

import os
import uuid
import logging
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from apps.system.storage_service import storage_service

logger = logging.getLogger(__name__)


class StorageUtils:
    """存储工具类"""

    @staticmethod
    def save_file(file_obj, path='', sync=True):
        """
        保存文件到存储

        Args:
            file_obj: 文件对象（django UploadedFile 或类似对象）
            path: 存储子路径，如 'uploads/', 'documents/'
            sync: 是否同步到其他存储位置

        Returns:
            str: 保存后的文件路径
        """
        if sync:
            return storage_service.save_file_with_sync(file_obj, path)
        else:
            file_ext = os.path.splitext(file_obj.name)[1]
            unique_name = f"{uuid.uuid4().hex}{file_ext}"
            full_path = os.path.join(
                path, unique_name) if path else unique_name
            return default_storage.save(
                full_path, ContentFile(file_obj.read()))

    @staticmethod
    def save_local_file(content, filename, path=''):
        """
        保存本地文件内容

        Args:
            content: bytes 或 ContentFile 对象
            filename: 文件名
            path: 存储子路径

        Returns:
            str: 保存后的文件路径
        """
        file_ext = os.path.splitext(filename)[1]
        unique_name = f"{uuid.uuid4().hex}{file_ext}"
        full_path = os.path.join(path, unique_name) if path else unique_name

        if isinstance(content, bytes):
            content = ContentFile(content)

        return default_storage.save(full_path, content)

    @staticmethod
    def delete_file(file_path, sync=True):
        """
        删除文件

        Args:
            file_path: 文件路径
            sync: 是否从所有存储位置删除

        Returns:
            dict: 删除结果
        """
        if sync:
            return storage_service.delete_file_from_all_storages(file_path)
        else:
            try:
                if default_storage.exists(file_path):
                    default_storage.delete(file_path)
                    return {'success': True, 'message': '文件删除成功'}
                return {'success': False, 'message': '文件不存在'}
            except Exception as e:
                logger.error(f'删除文件失败: {e}')
                return {'success': False, 'message': str(e)}

    @staticmethod
    def get_url(file_path):
        """
        获取文件的访问URL

        Args:
            file_path: 文件路径

        Returns:
            str: 文件访问URL
        """
        return storage_service.get_file_url(file_path)

    @staticmethod
    def exists(file_path):
        """
        检查文件是否存在

        Args:
            file_path: 文件路径

        Returns:
            bool: 文件是否存在
        """
        return storage_service.check_file_exists(file_path)

    @staticmethod
    def get_size(file_path):
        """
        获取文件大小

        Args:
            file_path: 文件路径

        Returns:
            int: 文件大小（字节），0表示文件不存在或无法获取
        """
        return storage_service.get_file_size(file_path)

    @staticmethod
    def read_file(file_path):
        """
        读取文件内容

        Args:
            file_path: 文件路径

        Returns:
            bytes: 文件内容
        """
        try:
            with default_storage.open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f'读取文件失败: {e}')
            return None

    @staticmethod
    def open_file(file_path, mode='rb'):
        """
        打开文件

        Args:
            file_path: 文件路径
            mode: 打开模式

        Returns:
            file-like object: 文件对象
        """
        return default_storage.open(file_path, mode)

    @staticmethod
    def copy_file(source_path, dest_path, sync=True):
        """
        复制文件

        Args:
            source_path: 源文件路径
            dest_path: 目标路径
            sync: 是否同步到其他存储

        Returns:
            str: 保存后的文件路径
        """
        if sync:
            try:
                with default_storage.open(source_path, 'rb') as f:
                    content = ContentFile(f.read())
                    return storage_service.save_file_with_sync(content, '')
            except Exception as e:
                logger.error(f'复制文件失败: {e}')
                return None
        else:
            with default_storage.open(source_path, 'rb') as f:
                content = ContentFile(f.read())
                return default_storage.save(dest_path, content)

    @staticmethod
    def get_file_path(url):
        """
        根据文件URL获取文件路径

        Args:
            url: 文件URL

        Returns:
            str: 文件路径
        """
        if url.startswith(settings.MEDIA_URL):
            return url[len(settings.MEDIA_URL):]
        return url

    @staticmethod
    def list_files(path=''):
        """
        列出目录下的文件

        Args:
            path: 目录路径

        Returns:
            list: 文件名列表
        """
        try:
            return default_storage.listdir(path)[1]
        except Exception as e:
            logger.error(f'列出文件失败: {e}')
            return []

    @staticmethod
    def sync_file_to_storages(file_path, storage_pks=None):
        """
        手动同步文件到指定存储

        Args:
            file_path: 文件路径
            storage_pks: 存储配置PK列表，None表示所有活动存储

        Returns:
            dict: 同步结果
        """
        from apps.system.models import StorageConfiguration

        try:
            with default_storage.open(file_path, 'rb') as f:
                content = ContentFile(f.read())
        except Exception as e:
            return {'success': False, 'message': f'读取源文件失败: {str(e)}'}

        if storage_pks is None:
            configs = StorageConfiguration.objects.filter(status='active')
        else:
            configs = StorageConfiguration.objects.filter(
                pk__in=storage_pks, status='active')

        success_count = 0
        fail_count = 0
        errors = []

        for config in configs:
            try:
                backend = storage_service.get_backend(config)
                backend.save(file_path, content)
                success_count += 1
            except Exception as e:
                logger.error(f'同步到存储{config.pk}失败: {e}')
                fail_count += 1
                errors.append(f'{config.name}: {str(e)}')

        return {
            'success_count': success_count,
            'fail_count': fail_count,
            'errors': errors,
            'total': success_count + fail_count
        }

    @staticmethod
    def get_storage_info():
        """
        获取当前存储配置信息

        Returns:
            dict: 存储配置信息
        """
        default_config = storage_service.get_default_storage()
        return {
            'default_storage': {
                'name': default_config.name if default_config else '默认存储',
                'type': default_config.storage_type if default_config else 'local',
                'type_display': default_config.get_storage_type_display() if default_config else '本地存储',
            } if default_config else None,
            'media_root': settings.MEDIA_ROOT,
            'media_url': settings.MEDIA_URL,
        }


storage_utils = StorageUtils()
