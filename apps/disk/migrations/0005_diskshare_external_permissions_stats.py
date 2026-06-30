from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('disk', '0004_diskshare_allow_preview'),
    ]

    operations = [
        migrations.AddField(
            model_name='diskshare',
            name='allow_copy',
            field=models.BooleanField(default=True, verbose_name='允许复制'),
        ),
        migrations.AddField(
            model_name='diskshare',
            name='allow_screenshot',
            field=models.BooleanField(default=True, verbose_name='允许截图'),
        ),
        migrations.AddField(
            model_name='diskshare',
            name='copy_blocked_count',
            field=models.IntegerField(default=0, verbose_name='复制拦截次数'),
        ),
        migrations.AddField(
            model_name='diskshare',
            name='copy_count',
            field=models.IntegerField(default=0, verbose_name='复制成功次数'),
        ),
        migrations.AddField(
            model_name='diskshare',
            name='screenshot_blocked_count',
            field=models.IntegerField(default=0, verbose_name='截图拦截次数'),
        ),
        migrations.AddField(
            model_name='diskshare',
            name='screenshot_count',
            field=models.IntegerField(default=0, verbose_name='截图成功次数'),
        ),
    ]
