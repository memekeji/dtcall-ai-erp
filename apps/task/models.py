from django.db import models

# Create your models here.

class Task(models.Model):
    title = models.CharField(max_length=200, verbose_name='任务标题')
    description = models.TextField(verbose_name='任务描述', blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    status = models.IntegerField(choices=[(0, '未完成'), (1, '已完成')], default=0, verbose_name='任务状态')
    assignee = models.ForeignKey('user.Admin', on_delete=models.CASCADE, verbose_name='负责人', null=True, blank=True)

    class Meta:
        verbose_name = '任务'
        verbose_name_plural = '任务'
        ordering = ['-created_at']
