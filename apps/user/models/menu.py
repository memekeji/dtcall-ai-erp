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
            cache_pattern = f"{MENU_CACHE_KEY_PREFIX}*"
            try:
                keys = cache.keys(cache_pattern)
                if keys:
                    cache.delete_many(keys)
                    logger.debug(f'已清除 {len(keys)} 个菜单缓存键')
            except Exception:
                cache.clear()
                logger.warning('无法精确清除菜单缓存，已使用全局清除')
        else:
            specific_key = get_menu_cache_key(menu_id)
            cache.delete(specific_key)
            cache.delete(get_menu_cache_key(tree=True))
            cache.delete(get_menu_cache_key())
            logger.debug(f'菜单[{menu_id}]缓存已清除')
    except Exception as e:
        logger.error(f'清除菜单缓存失败: {e}')


class Menu(models.Model):
    """菜单表"""
    id = models.AutoField(primary_key=True, verbose_name='ID')
    title = models.CharField(max_length=255, default='', verbose_name='菜单名称')
    src = models.CharField(max_length=255, default='', verbose_name='链接地址')
    icon = models.CharField(max_length=255, default='', verbose_name='图标')
    pid = models.ForeignKey('self', blank=True, null=True, on_delete=models.CASCADE, verbose_name='父级菜单id', related_name='submenus')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.IntegerField(default=1, verbose_name='状态:1正常,0禁用')
    module = models.ForeignKey('user.SystemModule', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='关联功能模块', help_text='关联到对应的功能模块，模块禁用时菜单自动隐藏')
    permission_required = models.CharField(max_length=255, blank=True, verbose_name='所需权限', help_text='访问该菜单所需的权限，格式为 app_label.codename')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'mimu_menu'
        verbose_name = '菜单表'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title
        
    def is_available(self):
        """判断菜单是否可用：状态正常且关联的模块（如果有）处于启用状态"""
        if self.status != 1:
            return False
        
        if self.module and not self.module.is_active:
            return False
        
        if self.pid:
            if self.pid.id == self.id:
                return False
            if not self.pid.is_available():
                return False
        
        return True


@receiver(post_save, sender=Menu)
def menu_post_save_handler(sender, instance, **kwargs):
    """菜单保存时清除菜单缓存（不清除会话）"""
    clear_menu_cache_data(instance.id if instance.id else None)
    logger.debug(f'菜单[{instance.id}]已保存，菜单缓存已更新')


@receiver(post_delete, sender=Menu)
def menu_post_delete_handler(sender, instance, **kwargs):
    """菜单删除时清除菜单缓存（不清除会话）"""
    clear_menu_cache_data(instance.id if instance.id else None)
    logger.debug(f'菜单[{instance.id}]已删除，菜单缓存已更新')
