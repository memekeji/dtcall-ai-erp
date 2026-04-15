from django.db import models
from django.contrib.auth.models import Group


class GroupExtension(models.Model):
    """Group模型扩展，添加描述和状态字段"""
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='extension'
    )
    description = models.TextField(blank=True, verbose_name='角色描述')
    status = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '角色扩展信息'
        verbose_name_plural = verbose_name
        db_table = 'user_groupextension'


class DepartmentGroup(models.Model):
    """部门与角色的关联模型"""
    department = models.ForeignKey(
        'department.Department',
        on_delete=models.CASCADE,
        verbose_name='部门',
        related_name='department_groups'
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        verbose_name='角色',
        related_name='department_groups'
    )
    is_default = models.BooleanField(default=False, verbose_name='是否默认角色')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '部门角色关联'
        verbose_name_plural = verbose_name
        db_table = 'department_group'
        unique_together = ('department', 'group')
