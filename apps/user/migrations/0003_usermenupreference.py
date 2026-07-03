from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0002_alter_menu_options_remove_menu_permission_required_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserMenuPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('use_count', models.PositiveIntegerField(default=0, verbose_name='使用次数')),
                ('last_used_at', models.DateTimeField(blank=True, null=True, verbose_name='最近使用时间')),
                ('is_pinned', models.BooleanField(default=False, verbose_name='是否固定')),
                ('pin_sort', models.IntegerField(default=0, verbose_name='固定排序')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('menu', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_preferences', to='user.menu', verbose_name='菜单')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='menu_preferences', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '用户菜单偏好',
                'verbose_name_plural': '用户菜单偏好',
                'db_table': 'user_menu_preference',
                'ordering': ['-is_pinned', '-use_count', '-last_used_at', 'id'],
                'unique_together': {('user', 'menu')},
            },
        ),
        migrations.AddIndex(
            model_name='usermenupreference',
            index=models.Index(fields=['user', 'is_pinned'], name='ump_user_pin_idx'),
        ),
        migrations.AddIndex(
            model_name='usermenupreference',
            index=models.Index(fields=['user', '-use_count'], name='ump_user_use_idx'),
        ),
    ]
