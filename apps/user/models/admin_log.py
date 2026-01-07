from django.db import models

class AdminLog(models.Model):
    """管理员日志模型"""
    admin_id = models.IntegerField(verbose_name="管理员ID", null=True)
    username = models.CharField(max_length=30, verbose_name="管理员用户名", null=True)
    url = models.CharField(max_length=1500, verbose_name="操作页面", null=True)
    title = models.CharField(max_length=100, verbose_name="日志标题", null=True)
    content = models.TextField(verbose_name="内容", null=True)
    ip = models.CharField(max_length=50, verbose_name="IP", null=True)
    user_agent = models.CharField(max_length=255, verbose_name="User-Agent", null=True)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = 'mimu_admin_log'
        verbose_name = '管理员日志'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title