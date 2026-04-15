from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Enterprise(models.Model):
    title = models.CharField(max_length=100, verbose_name='企业名称', default='')
    city = models.CharField(max_length=60, verbose_name='所在城市', default='')
    bank = models.CharField(max_length=60, verbose_name='开户银行', default='')
    bank_sn = models.CharField(max_length=60, verbose_name='银行帐号', default='')
    tax_num = models.CharField(
        max_length=100,
        verbose_name='纳税人识别号',
        default='')
    phone = models.CharField(max_length=20, verbose_name='开票电话', default='')
    address = models.CharField(max_length=200, verbose_name='开票地址', default='')
    remark = models.CharField(max_length=500, verbose_name='备注说明', default='')
    status = models.SmallIntegerField(
        default=1,
        verbose_name='状态',
        help_text='状态：-1删除 0禁用 1启用',
        db_column='status')
    create_time = models.BigIntegerField(default=0, verbose_name='创建时间')
    update_time = models.BigIntegerField(default=0, verbose_name='更新时间')

    class Meta:
        db_table = 'mimu_enterprise'
        verbose_name = '企业信息'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title
