from django.db import models

class Position(models.Model):
    """职位模型"""
    title = models.CharField(max_length=50, verbose_name="职位名称", default='')
    did = models.IntegerField(default=0, verbose_name="部门ID")
    desc = models.CharField(max_length=255, blank=True, verbose_name="职位描述")
    sort = models.IntegerField(default=0, verbose_name="排序")
    status = models.IntegerField(default=1, verbose_name="状态")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = 'mimu_position'
        verbose_name = '职位'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title