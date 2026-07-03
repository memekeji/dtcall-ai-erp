from django.conf import settings
from django.db import models


class UserMenuPreference(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='menu_preferences',
        verbose_name='用户',
    )
    menu = models.ForeignKey(
        'user.Menu',
        on_delete=models.CASCADE,
        related_name='user_preferences',
        verbose_name='菜单',
    )
    use_count = models.PositiveIntegerField(default=0, verbose_name='使用次数')
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name='最近使用时间')
    is_pinned = models.BooleanField(default=False, verbose_name='是否固定')
    pin_sort = models.IntegerField(default=0, verbose_name='固定排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'user_menu_preference'
        verbose_name = '用户菜单偏好'
        verbose_name_plural = verbose_name
        unique_together = ('user', 'menu')
        ordering = ['-is_pinned', '-use_count', '-last_used_at', 'id']
        indexes = [
            models.Index(fields=['user', 'is_pinned'], name='ump_user_pin_idx'),
            models.Index(fields=['user', '-use_count'], name='ump_user_use_idx'),
        ]

    def __str__(self):
        return f'{self.user} - {self.menu} ({self.use_count})'
