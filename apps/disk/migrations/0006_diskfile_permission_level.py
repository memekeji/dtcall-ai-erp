from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('disk', '0005_diskshare_external_permissions_stats'),
    ]

    operations = [
        migrations.AddField(
            model_name='diskfile',
            name='permission_level',
            field=models.IntegerField(
                choices=[(1, '只读'), (2, '读写'), (3, '管理')],
                default=1,
                verbose_name='权限级别',
            ),
        ),
    ]
