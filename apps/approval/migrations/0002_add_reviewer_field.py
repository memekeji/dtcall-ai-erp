# -*- coding: utf-8 -*-
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('approval', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='approval',
            name='status',
            field=models.PositiveSmallIntegerField(choices=[(0, '待审批'), (1, '审批中'), (2, '已通过'), (3, '已拒绝'), (4, '已取消')], default=0, verbose_name='审批状态'),
        ),
        migrations.AddField(
            model_name='approval',
            name='reviewer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='user.admin', verbose_name='审核人'),
        ),
    ]
