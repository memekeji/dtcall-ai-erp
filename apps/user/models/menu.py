from django.db import models
from django.utils import timezone
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

import logging
logger = logging.getLogger(__name__)


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
        
        if self.pid and not self.pid.is_available():
            return False
        
        return True


@receiver(post_save, sender=Menu)
def clear_menu_cache(sender, instance, **kwargs):
    """菜单保存时清除菜单缓存"""
    try:
        cache.clear()
        logger.debug(f'菜单[{instance.id}]已保存，已清除菜单缓存')
    except Exception as e:
        logger.error(f'清除菜单缓存失败: {e}')


@receiver(post_delete, sender=Menu)
def clear_menu_cache_on_delete(sender, instance, **kwargs):
    """菜单删除时清除菜单缓存"""
    try:
        cache.clear()
        logger.debug(f'菜单[{instance.id}]已删除，已清除菜单缓存')
    except Exception as e:
        logger.error(f'清除菜单缓存失败: {e}')
