from django.db import models

class Message(models.Model):
    """消息模型，与原项目数据库表'message'结构一致"""
    id = models.BigAutoField(primary_key=True, verbose_name='ID')
    user = models.ForeignKey('user.Admin', on_delete=models.CASCADE, verbose_name='关联用户')
    content = models.TextField(verbose_name='消息内容')
    is_read = models.BooleanField(default=False, verbose_name='是否已读')
    create_time = models.BigIntegerField(verbose_name='创建时间戳')

    class Meta:
        db_table = 'message'  # 与原项目表名一致
        verbose_name = '系统消息'
        verbose_name_plural = '系统消息'
