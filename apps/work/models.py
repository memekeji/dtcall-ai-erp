from django.db import models


class WorkCate(models.Model):
    title = models.CharField(max_length=100, verbose_name="分类名称", default='')
    pid = models.IntegerField(default=0, verbose_name="父级ID")
    sort = models.IntegerField(default=0, verbose_name="排序")
    status = models.IntegerField(default=1, verbose_name="状态")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = 'work_cate'
        verbose_name = '工作分类'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title
