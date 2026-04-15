"""文件类型常量定义

统一管理所有文件类型和扩展名定义
"""

from typing import Dict, Set, Optional, Callable
from functools import lru_cache


class FileTypeConstants:
    """文件类型常量类"""

    TEXT_TYPES: Set[str] = frozenset({
        'txt', 'csv', 'json', 'xml', 'html', 'css', 'js', 'py', 'java',
        'cpp', 'c', 'h', 'md', 'markdown', 'ini', 'conf', 'log', 'yaml', 'yml',
        'bat', 'sh', 'ps1', 'rb', 'php', 'swift', 'kt', 'go', 'rs', 'ts'
    })

    IMAGE_TYPES: Set[str] = frozenset({
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico', 'jfif',
        'tiff', 'tif', 'psd', 'eps', 'ai', 'webp'
    })

    OFFICE_TYPES: Set[str] = frozenset({
        'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'odp'
    })

    AUDIO_TYPES: Set[str] = frozenset({
        'mp3', 'wav', 'ogg', 'flac', 'aac', 'wma', 'm4a', 'aiff', 'mid', 'midi'
    })

    VIDEO_TYPES: Set[str] = frozenset({
        'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv', 'mpeg', 'mpg', '3gp'
    })

    ARCHIVE_TYPES: Set[str] = frozenset({
        'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'tgz', 'tbz2', 'tar.gz', 'tar.bz2'
    })

    ARCHIVE_PREVIEW_TYPES: Set[str] = frozenset({
        'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz'
    })

    DOCUMENT_TYPES: Set[str] = frozenset({
        'pdf', 'doc', 'docx', 'odt', 'txt', 'rtf', 'wps', 'wpd'
    })

    MARKDOWN_TYPES: Set[str] = frozenset({'md', 'markdown', 'mkd'})

    PREVIEWABLE_TYPES: Dict[str, str] = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        '.svg': 'image/svg+xml',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    }

    TEXT_ENCODINGS: tuple = (
        'utf-8', 'gbk', 'gb2312', 'gb18030',
        'latin-1', 'cp1252',
        'utf-16', 'utf-16le', 'utf-16be',
        'big5', 'shift_jis', 'euc-jp',
        'iso-8859-1', 'windows-1252', 'koi8-r', 'mac_cyrillic',
        'euc-kr', 'iso-2022-jp'
    )

    @classmethod
    def get_file_type(cls, file_ext: str) -> str:
        """根据扩展名获取文件类型

        Args:
            file_ext: 文件扩展名（带或不带点）

        Returns:
            文件类型字符串
        """
        ext = file_ext.lower().lstrip('.')

        if ext in cls.TEXT_TYPES:
            return 'text'
        elif ext in cls.IMAGE_TYPES:
            return 'image'
        elif ext in cls.OFFICE_TYPES:
            return 'office'
        elif ext == 'pdf':
            return 'pdf'
        elif ext in cls.AUDIO_TYPES:
            return 'audio'
        elif ext in cls.VIDEO_TYPES:
            return 'video'
        elif ext in cls.ARCHIVE_TYPES:
            return 'archive'
        else:
            return 'other'

    @classmethod
    @lru_cache(maxsize=128)
    def get_preview_handler(cls, file_ext: str) -> Optional[Callable]:
        """根据扩展名获取预览处理器

        Returns:
            预览处理方法
        """
        file_type = cls.get_file_type(file_ext)
        handlers = {
            'text': '_preview_text_file',
            'image': '_preview_image_file',
            'office': '_preview_office_file',
            'pdf': '_preview_pdf_file',
            'audio': '_preview_audio_file',
            'video': '_preview_video_file',
        }
        return handlers.get(file_type)

    @classmethod
    def can_preview(cls, file_ext: str) -> bool:
        """判断文件是否可预览"""
        return cls.get_file_type(file_ext) != 'other'

    @classmethod
    def get_preview_mime_type(cls, file_ext: str) -> str:
        """获取预览用的MIME类型"""
        return cls.PREVIEWABLE_TYPES.get(
            file_ext.lower(), 'application/octet-stream')

    @classmethod
    def get_all_preview_extensions(cls) -> Set[str]:
        """获取所有可预览的扩展名"""
        extensions = set()
        extensions.update(cls.TEXT_TYPES)
        extensions.update(cls.IMAGE_TYPES)
        extensions.update(cls.OFFICE_TYPES)
        extensions.add('pdf')
        extensions.update(cls.AUDIO_TYPES)
        extensions.update(cls.VIDEO_TYPES)
        return extensions
