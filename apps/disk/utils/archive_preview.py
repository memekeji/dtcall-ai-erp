import os
import logging
import zipfile
import tarfile
import gzip
import bz2
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class ArchivePreviewHandler:
    """压缩包预览处理器"""
    
    SUPPORTED_EXTENSIONS = frozenset({'.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar'})
    
    MAX_PREVIEW_FILES = 100
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    @classmethod
    def can_preview(cls, file_ext: str) -> bool:
        """判断是否支持预览该压缩包"""
        return file_ext.lower() in cls.SUPPORTED_EXTENSIONS
    
    @classmethod
    def preview_archive(cls, file_path: str, file_name: str) -> Dict[str, Any]:
        """预览压缩包内容
        
        Args:
            file_path: 压缩包文件路径
            file_name: 文件名
            
        Returns:
            预览数据字典
        """
        try:
            file_ext = Path(file_name).suffix.lower()
            
            if file_ext == '.zip':
                return cls._preview_zip(file_path, file_name)
            elif file_ext in ('.tar', '.gz', '.bz2', '.xz'):
                return cls._preview_tar(file_path, file_name)
            else:
                return cls._create_error_response(file_name, f'不支持的压缩包格式: {file_ext}')
                
        except Exception as e:
            logger.error(f'压缩包预览失败: {str(e)}', exc_info=True)
            return cls._create_error_response(file_name, f'压缩包预览失败: {str(e)}')
    
    @classmethod
    def _preview_zip(cls, file_path: str, file_name: str) -> Dict[str, Any]:
        """预览ZIP文件内容"""
        files = []
        total_size = 0
        total_count = 0
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                for info in zf.infolist():
                    if total_count >= cls.MAX_PREVIEW_FILES:
                        break
                    
                    if info.file_size > cls.MAX_FILE_SIZE:
                        continue
                    
                    is_dir = info.filename.endswith('/')
                    files.append({
                        'name': info.filename,
                        'size': cls._format_size(info.file_size),
                        'size_bytes': info.file_size,
                        'is_dir': is_dir,
                        'date': datetime(*info.date_time).strftime('%Y-%m-%d %H:%M') if not is_dir else None,
                        'compression': info.compress_type if not is_dir else None
                    })
                    
                    total_size += info.file_size
                    total_count += 1
            
            return {
                'type': 'archive',
                'name': file_name,
                'format': 'zip',
                'files': files,
                'total_count': len(files),
                'truncated': len(files) >= cls.MAX_PREVIEW_FILES,
                'content_type': 'file_list'
            }
            
        except Exception as e:
            raise Exception(f'ZIP文件解析失败: {str(e)}')
    
    @classmethod
    def _preview_tar(cls, file_path: str, file_name: str) -> Dict[str, Any]:
        """预览TAR文件内容"""
        files = []
        total_size = 0
        total_count = 0
        
        try:
            if file_path.endswith('.gz'):
                opener = gzip.open
            elif file_path.endswith('.bz2'):
                opener = bz2.open
            else:
                opener = open
            
            with opener(file_path, 'rb') as f:
                with tarfile.open(fileobj=f, mode='r') as tf:
                    for member in tf:
                        if total_count >= cls.MAX_PREVIEW_FILES:
                            break
                        
                        if member.isfile() and member.size > cls.MAX_FILE_SIZE:
                            continue
                        
                        files.append({
                            'name': member.name,
                            'size': cls._format_size(member.size) if member.isfile() else '-',
                            'size_bytes': member.size if member.isfile() else 0,
                            'is_dir': member.isdir(),
                            'date': datetime.fromtimestamp(member.mtime).strftime('%Y-%m-%d %H:%M') if member.isfile() else None,
                            'type': 'dir' if member.isdir() else 'file'
                        })
                        
                        total_size += member.size if member.isfile() else 0
                        total_count += 1
            
            return {
                'type': 'archive',
                'name': file_name,
                'format': 'tar',
                'files': files,
                'total_count': len(files),
                'truncated': len(files) >= cls.MAX_PREVIEW_FILES,
                'content_type': 'file_list'
            }
            
        except Exception as e:
            raise Exception(f'TAR文件解析失败: {str(e)}')
    
    @classmethod
    def _format_size(cls, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    @classmethod
    def _create_error_response(cls, file_name: str, message: str) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            'type': 'archive',
            'name': file_name,
            'error': message,
            'files': [],
            'content_type': 'error'
        }
