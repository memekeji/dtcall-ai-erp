from django.db import models
from django.utils import timezone
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.cache import cache

import logging
logger = logging.getLogger('django')

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
    view_permission = models.ForeignKey(Permission, on_delete=models.SET_NULL, null=True, blank=True, related_name='menu_view_permissions', verbose_name='查看权限', help_text='决定是否向用户显示该菜单的权限')
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
        
        # 检查关联模块是否启用
        if self.module and not self.module.is_active:
            return False
        
        # 检查父菜单是否可用
        if self.pid and not self.pid.is_available():
            return False
        
        return True
    
    def create_view_permission(self):
        """为菜单创建查看权限"""
        if self.view_permission:
            return self.view_permission
        
        try:
            content_type = ContentType.objects.get_for_model(self)
            codename = f'view_menu_{self.id}'
            name = f'查看菜单 - {self.title}'
            
            permission, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={'name': name}
            )
            
            if created:
                self.view_permission = permission
                self.save(update_fields=['view_permission'])
            
            return permission
        except Exception as e:
            print(f"创建菜单查看权限失败: {e}")
            return None
    
    def get_view_permission_id(self):
        """获取查看权限ID"""
        if not self.view_permission:
            self.create_view_permission()
        return self.view_permission.id if self.view_permission else None


@receiver(post_save, sender=Menu)
def create_menu_view_permission(sender, instance, created, **kwargs):
    """菜单保存时自动创建查看权限"""
    if created and not instance.view_permission:
        instance.create_view_permission()

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