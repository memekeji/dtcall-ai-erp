from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="企业名称")
    legal_person = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="法定代表人")
    registered_capital = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="注册资本")
    establishment_date = models.DateField(
        null=True, blank=True, verbose_name="成立日期")
    registration_status = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="登记状态")
    business_scope = models.TextField(
        null=True, blank=True, verbose_name="经营范围")
    address = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="注册地址")
    tianyancha_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="天眼查链接")

    class Meta:
        verbose_name = "企业信息"
        verbose_name_plural = "企业信息"

    def __str__(self):
        return self.name
