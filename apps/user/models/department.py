from django.db import models
from django.utils import timezone


class Department(models.Model):
    """部门模型"""
    title = models.CharField('部门名称', max_length=50)
    pid = models.IntegerField('上级部门ID', default=0)
    sort = models.IntegerField('排序', default=0)
    status = models.SmallIntegerField('状态', default=1)  # 1正常 0禁用
    create_time = models.DateTimeField('创建时间', default=timezone.now)
    update_time = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'department'
        verbose_name = '部门'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title
