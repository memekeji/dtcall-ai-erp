# Generated for approval flow canvas node positions

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('approval', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='approvalstep',
            name='node_x',
            field=models.IntegerField(default=0, verbose_name='画布X坐标'),
        ),
        migrations.AddField(
            model_name='approvalstep',
            name='node_y',
            field=models.IntegerField(default=0, verbose_name='画布Y坐标'),
        ),
    ]
