# -*- coding: utf-8 -*-
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('production', '0003_add_process_route'),
    ]

    operations = [
        migrations.AddField(
            model_name='processroute',
            name='product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='production.product', verbose_name='适用产品'),
        ),
    ]
