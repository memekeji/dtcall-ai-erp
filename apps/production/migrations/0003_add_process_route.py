# -*- coding: utf-8 -*-
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ('production', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProcessRoute',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='工艺路线名称')),
                ('code', models.CharField(max_length=50, unique=True, verbose_name='工艺路线编码')),
                ('description', models.TextField(blank=True, verbose_name='工艺路线描述')),
                ('total_time', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='总工时(小时)')),
                ('total_cost', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='总成本')),
                ('status', models.IntegerField(choices=[(1, '待审核'), (2, '已审核'), (3, '执行中'), (4, '已完成'), (5, '已取消')], default=1, verbose_name='状态')),
                ('version', models.CharField(default='1.0', max_length=20, verbose_name='版本号')),
                ('effective_date', models.DateField(blank=True, null=True, verbose_name='生效日期')),
                ('expiry_date', models.DateField(blank=True, null=True, verbose_name='失效日期')),
                ('create_time', models.DateTimeField(default=timezone.now, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '工艺路线',
                'verbose_name_plural': '工艺路线',
                'db_table': 'production_process_route',
                'ordering': ['-create_time'],
            },
        ),
        
        migrations.CreateModel(
            name='ProcessRouteItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sequence', models.IntegerField(verbose_name='执行顺序')),
                ('estimated_time', models.DecimalField(decimal_places=2, default=0, max_digits=8, verbose_name='预估工时(小时)')),
                ('workstation', models.CharField(max_length=100, blank=True, verbose_name='工位')),
                ('work_instruction', models.TextField(blank=True, verbose_name='作业指导')),
                ('quality_check_points', models.TextField(blank=True, verbose_name='质量检查点')),
                ('cycle_time', models.DecimalField(decimal_places=2, default=0, max_digits=8, verbose_name='节拍时间(秒)')),
            ],
            options={
                'verbose_name': '工艺路线明细',
                'verbose_name_plural': '工艺路线明细',
                'db_table': 'production_process_route_item',
                'ordering': ['sequence'],
            },
        ),
        
        migrations.AddField(
            model_name='processrouteitem',
            name='procedure',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='production.productionprocedure', verbose_name='工序'),
        ),
        
        migrations.AddField(
            model_name='processrouteitem',
            name='process_route',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='production.processroute', verbose_name='工艺路线'),
        ),
        
        migrations.AddField(
            model_name='processroute',
            name='procedures',
            field=models.ManyToManyField(through='production.ProcessRouteItem', to='production.productionprocedure', verbose_name='包含工序'),
        ),
        
        migrations.AddField(
            model_name='productionplan',
            name='process_route',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='production.processroute', verbose_name='工艺路线'),
        ),
        
        migrations.AlterUniqueTogether(
            name='processrouteitem',
            unique_together={('process_route', 'procedure')},
        ),
    ]
