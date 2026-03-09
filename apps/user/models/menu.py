from django.db import models
from django.utils import timezone
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

MENU_CACHE_KEY_PREFIX = 'menu_cache_'


def get_menu_cache_key(menu_id=None, tree=False):
    """生成菜单缓存键"""
    if menu_id is None:
        return f"{MENU_CACHE_KEY_PREFIX}all_menus"
    elif tree:
        return f"{MENU_CACHE_KEY_PREFIX}tree_{menu_id}"
    else:
        return f"{MENU_CACHE_KEY_PREFIX}item_{menu_id}"


def clear_menu_cache_data(menu_id=None):
    """清除菜单相关缓存（不清除会话缓存）"""
    try:
        if menu_id is None:
            # LocMemCache 不支持 keys() 方法，直接清除所有缓存
            cache.clear()
            logger.debug('菜单缓存已全局清除')
        else:
            # 清除特定菜单的缓存
            specific_key = get_menu_cache_key(menu_id)
            cache.delete(specific_key)
            cache.delete(get_menu_cache_key(tree=True))
            cache.delete(get_menu_cache_key())
            logger.debug(f'菜单 [{menu_id}] 相关缓存已清除')
    except Exception as e:
        logger.error(f'清除菜单缓存失败：{e}')
        # 尝试全局清除作为备选方案
        try:
            cache.clear()
            logger.warning('无法精确清除菜单缓存，已使用全局清除')
        except Exception as clear_error:
            logger.error(f'全局清除菜单缓存也失败：{clear_error}')


class Menu(models.Model):
    """菜单表"""
    id = models.AutoField(primary_key=True, verbose_name='ID')
    title = models.CharField(max_length=255, default='', verbose_name='菜单名称')
    src = models.CharField(max_length=255, default='', verbose_name='链接地址')
    icon = models.CharField(max_length=255, default='', verbose_name='图标')
    pid = models.ForeignKey('self', blank=True, null=True, on_delete=models.CASCADE, verbose_name='父级菜单 id', related_name='submenus')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.IntegerField(default=1, verbose_name='状态:1 正常，0 禁用')
    module = models.ForeignKey('user.SystemModule', on_delete=models.CASCADE, default=1, verbose_name='所属模块', related_name='menus')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'system_menu'
        verbose_name = '菜单'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']
    
    def __str__(self):
        return self.title
    
    def is_available(self):
        """检查菜单是否可用"""
        return self.status == 1 and self.module and self.module.is_active


@receiver(post_save, sender=Menu)
@receiver(post_delete, sender=Menu)
def clear_menu_cache_on_change(sender, **kwargs):
    """菜单保存或删除时清除菜单缓存（不清除会话缓存）"""
    clear_menu_cache_data()


# 为 SystemModule 添加信号处理器，当模块状态变化时清除菜单缓存
@receiver(post_save, sender='user.SystemModule')
def clear_menu_cache_on_module_save(sender, instance, created, **kwargs):
    """系统模块保存时清除菜单缓存"""
    if not created:
        # 检查 is_active 字段是否发生变化
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            if old_instance.is_active != instance.is_active:
                # is_active 字段发生变化，清除菜单缓存
                clear_menu_cache_data()
        except Exception:
            # 新创建的模块，清除菜单缓存
            clear_menu_cache_data()


@receiver(post_delete, sender='user.SystemModule')
def clear_menu_cache_on_module_delete(sender, **kwargs):
    """系统模块删除时清除菜单缓存"""
    clear_menu_cache_data()
