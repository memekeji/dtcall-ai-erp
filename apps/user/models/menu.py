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
        keys_to_delete = []
        
        if menu_id is None:
            # 清除所有菜单缓存，包括menu_cache_开头的和menus_user_开头的
            cache_patterns = [
                f"{MENU_CACHE_KEY_PREFIX}*",
                "menus_user_*"
            ]
            
            for pattern in cache_patterns:
                try:
                    keys = cache.keys(pattern)
                    keys_to_delete.extend(keys)
                except Exception:
                    logger.warning(f'无法获取缓存键模式 {pattern} 的匹配项，将使用全局清除')
                    cache.clear()
                    logger.debug('已使用全局清除菜单缓存')
                    return
            
            if keys_to_delete:
                cache.delete_many(keys_to_delete)
                logger.debug(f'已清除 {len(keys_to_delete)} 个菜单缓存键')
        else:
            # 清除特定菜单的缓存
            specific_key = get_menu_cache_key(menu_id)
            keys_to_delete = [
                specific_key,
                get_menu_cache_key(tree=True),
                get_menu_cache_key()
            ]
            # 同时清除用户菜单缓存
            keys_to_delete.extend(cache.keys("menus_user_*"))
            
            if keys_to_delete:
                cache.delete_many(keys_to_delete)
                logger.debug(f'菜单[{menu_id}]相关缓存已清除')
    except Exception as e:
        logger.error(f'清除菜单缓存失败: {e}')
        # 尝试全局清除作为备选方案
        try:
            cache.clear()
            logger.warning('无法精确清除菜单缓存，已使用全局清除')
        except Exception as clear_error:
            logger.error(f'全局清除菜单缓存也失败: {clear_error}')


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


# 为SystemModule添加信号处理器，当模块状态变化时清除菜单缓存
# 使用字符串引用避免循环导入


@receiver(post_save, sender='user.SystemModule')
def system_module_post_save_handler(sender, instance, **kwargs):
    """系统模块保存时清除菜单缓存"""
    # 检查is_active字段是否发生变化
    if kwargs.get('created', False):
        # 新创建的模块，清除菜单缓存
        clear_menu_cache_data()
        logger.debug(f'系统模块[{instance.name}]已创建，菜单缓存已清除')
    else:
        # 检查is_active字段是否变化
        if hasattr(instance, '_original_is_active'):
            if instance._original_is_active != instance.is_active:
                # is_active字段发生变化，清除菜单缓存
                clear_menu_cache_data()
                logger.debug(f'系统模块[{instance.name}]状态已变更为{"启用" if instance.is_active else "禁用"}，菜单缓存已清除')


@receiver(post_delete, sender='user.SystemModule')
def system_module_post_delete_handler(sender, instance, **kwargs):
    """系统模块删除时清除菜单缓存"""
    clear_menu_cache_data()
    logger.debug(f'系统模块[{instance.name}]已删除，菜单缓存已清除')


# 为SystemModule模型添加保存前钩子，记录原始is_active值
@receiver(models.signals.pre_save, sender='user.SystemModule')
def system_module_pre_save_handler(sender, instance, **kwargs):
    """系统模块保存前记录原始is_active值"""
    if instance.pk:
        try:
            # 内部导入避免循环导入
            from apps.user.models import SystemModule
            original_instance = SystemModule.objects.get(pk=instance.pk)
            instance._original_is_active = original_instance.is_active
        except SystemModule.DoesNotExist:
            instance._original_is_active = instance.is_active
    else:
        instance._original_is_active = instance.is_active
