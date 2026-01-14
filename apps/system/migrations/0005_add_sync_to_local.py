from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0004_add_storage_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='storageconfiguration',
            name='sync_to_local',
            field=models.BooleanField(default=False, verbose_name='同步到本地'),
        ),
    ]
