from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('approval', '0004_approval_flow_graph'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ApprovalTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[
                        ('pending', '待处理'),
                        ('completed', '已完成'),
                        ('cancelled', '已取消'),
                        ('delegated', '已委托'),
                        ('returned', '已退回'),
                    ],
                    default='pending',
                    max_length=20,
                    verbose_name='任务状态',
                )),
                ('result', models.CharField(blank=True, default='', max_length=50, verbose_name='处理结果')),
                ('comment', models.TextField(blank=True, default='', verbose_name='处理意见')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='完成时间')),
                ('approval', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='approval.approval', verbose_name='审批')),
                ('handler', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approval_tasks', to=settings.AUTH_USER_MODEL, verbose_name='处理人')),
                ('step', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='approval.approvalstep', verbose_name='审批步骤')),
            ],
            options={
                'verbose_name': '审批任务',
                'verbose_name_plural': '审批任务',
                'db_table': 'basedata_approval_task',
                'ordering': ['created_at', 'id'],
            },
        ),
    ]
