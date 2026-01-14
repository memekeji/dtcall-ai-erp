from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
try:
    from apps.user.models import SystemConfiguration as SystemConfig
except ImportError:
    SystemConfig = None

def validate_config_title(value, instance=None):
    """
    验证配置名称是否唯一
    """
    if not SystemConfig:
        return
    queryset = SystemConfig.objects.filter(title=value)
    if instance and instance.pk:
        queryset = queryset.exclude(pk=instance.pk)
    if queryset.exists():
        raise ValidationError(_('同样的配置名称已经存在'))
        
def validate_config_name(value, instance=None):
    """
    验证配置标识是否唯一
    """
    if not SystemConfig:
        return
    queryset = SystemConfig.objects.filter(name=value)
    if instance and instance.pk:
        queryset = queryset.exclude(pk=instance.pk)
    if queryset.exists():
        raise ValidationError(_('同样的配置标识已经存在'))

class SystemConfigValidator:
    @staticmethod
    def validate_add(data):
        errors = {}
        
        if not SystemConfig:
            return errors
        
        # 验证配置名称
        if not data.get('title'):
            errors['title'] = _('配置名称不能为空')
        else:
            try:
                validate_config_title(data['title'])
            except ValidationError as e:
                errors['title'] = str(e)
                
        # 验证配置标识
        if not data.get('name'):
            errors['name'] = _('配置标识不能为空')
        else:
            try:
                validate_config_name(data['name'])
            except ValidationError as e:
                errors['name'] = str(e)
                
        return errors

    @staticmethod
    def validate_edit(data):
        errors = {}
        
        if not SystemConfig:
            return errors
        
        # 验证ID
        if not data.get('id'):
            errors['id'] = _('缺少更新条件')
            
        # 验证配置名称
        if not data.get('title'):
            errors['title'] = _('配置名称不能为空')
        else:
            try:
                instance = SystemConfig.objects.get(pk=data['id'])
                validate_config_title(data['title'], instance)
            except SystemConfig.DoesNotExist:
                errors['id'] = _('无效的ID')
            except ValidationError as e:
                errors['title'] = str(e)
                
        # 验证配置标识
        if not data.get('name'):
            errors['name'] = _('配置标识不能为空')
        else:
            try:
                instance = SystemConfig.objects.get(pk=data['id'])
                validate_config_name(data['name'], instance)
            except SystemConfig.DoesNotExist:
                errors['id'] = _('无效的ID')
            except ValidationError as e:
                errors['name'] = str(e)
                
        return errors