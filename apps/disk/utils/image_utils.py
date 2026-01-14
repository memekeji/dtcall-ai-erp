import os
import logging
from PIL import Image
from io import BytesIO
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class ImageUtils:
    """图片处理工具类"""
    
    THUMBNAIL_SIZES = {
        'small': (150, 150),
        'medium': (300, 300),
        'large': (600, 600),
        'xlarge': (1200, 1200),
    }
    
    DEFAULT_SIZE = 'medium'
    CACHE_TIMEOUT = 86400
    
    @classmethod
    def get_thumbnail_cache_key(cls, file_id: int, size: str = 'medium') -> str:
        """生成缩略图缓存键"""
        return f'disk_thumb_{file_id}_{size}'
    
    @classmethod
    def generate_thumbnail(cls, image_path: str, size: str = 'medium', quality: int = 85) -> bytes:
        """生成图片缩略图
        
        Args:
            image_path: 图片文件路径
            size: 缩略图尺寸 (small/medium/large/xlarge)
            quality: JPEG质量 (1-100)
            
        Returns:
            缩略图二进制数据
        """
        try:
            target_size = cls.THUMBNAIL_SIZES.get(size, cls.THUMBNAIL_SIZES[cls.DEFAULT_SIZE])
            
            with Image.open(image_path) as img:
                img.thumbnail(target_size, Image.Resampling.LANCZOS)
                
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=quality, optimize=True)
                buffer.seek(0)
                
                return buffer.getvalue()
                
        except Exception as e:
            logger.error(f'生成缩略图失败: {str(e)}')
            raise
    
    @classmethod
    def get_thumbnail(cls, file_id: int, image_path: str, size: str = 'medium') -> bytes:
        """获取缩略图（带缓存）
        
        Args:
            file_id: 文件ID
            image_path: 图片文件路径
            size: 缩略图尺寸
            
        Returns:
            缩略图二进制数据
        """
        cache_key = cls.get_thumbnail_cache_key(file_id, size)
        
        thumbnail_data = cache.get(cache_key)
        if thumbnail_data is None:
            logger.info(f'生成新缩略图: file_id={file_id}, size={size}')
            thumbnail_data = cls.generate_thumbnail(image_path, size)
            cache.set(cache_key, thumbnail_data, cls.CACHE_TIMEOUT)
        else:
            logger.debug(f'使用缓存缩略图: file_id={file_id}, size={size}')
        
        return thumbnail_data
    
    @classmethod
    def invalidate_thumbnail_cache(cls, file_id: int):
        """清除缩略图缓存"""
        for size in cls.THUMBNAIL_SIZES.keys():
            cache_key = cls.get_thumbnail_cache_key(file_id, size)
            cache.delete(cache_key)
        logger.info(f'已清除缩略图缓存: file_id={file_id}')
    
    @classmethod
    def get_image_info(cls, image_path: str) -> dict:
        """获取图片信息
        
        Returns:
            {
                'width': 宽度,
                'height': 高度,
                'format': 格式,
                'size': 文件大小(字节),
                'mode': 颜色模式
            }
        """
        try:
            with Image.open(image_path) as img:
                return {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'size': os.path.getsize(image_path)
                }
        except Exception as e:
            logger.error(f'获取图片信息失败: {str(e)}')
            return {}
    
    @classmethod
    def should_use_thumbnail(cls, file_id: int, image_path: str, size_threshold: int = 1024 * 1024) -> bool:
        """判断是否应该使用缩略图
        
        Args:
            file_id: 文件ID
            image_path: 图片路径
            size_threshold: 文件大小阈值(字节)，超过此值使用缩略图
            
        Returns:
            是否使用缩略图
        """
        if not os.path.exists(image_path):
            return False
        
        file_size = os.path.getsize(image_path)
        return file_size > size_threshold
