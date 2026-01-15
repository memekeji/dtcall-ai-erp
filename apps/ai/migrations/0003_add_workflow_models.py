# Generated migration for AI workflow models

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='WorkflowVariable',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='变量名称')),
                ('data_type', models.CharField(max_length=20, choices=[('string', '字符串'), ('number', '数字'), ('boolean', '布尔值'), ('object', '对象'), ('array', '数组')], default='string', verbose_name='数据类型')),
                ('default_value', models.JSONField(blank=True, null=True, verbose_name='默认值')),
                ('description', models.TextField(blank=True, verbose_name='变量描述')),
                ('is_required', models.BooleanField(default=False, verbose_name='是否必填')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('workflow', models.ForeignKey(on_delete=models.CASCADE, related_name='variables', to='ai.aiworkflow', verbose_name='所属工作流')),
            ],
            options={
                'verbose_name': '工作流变量',
                'verbose_name_plural': '工作流变量',
                'db_table': 'ai_workflow_variable',
            },
        ),
        migrations.CreateModel(
            name='WorkflowNodeType',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True, verbose_name='类型代码')),
                ('name', models.CharField(max_length=100, verbose_name='类型名称')),
                ('description', models.TextField(blank=True, verbose_name='类型描述')),
                ('category', models.CharField(max_length=20, choices=[('basic', '基础节点'), ('ai', 'AI节点'), ('data', '数据节点'), ('logic', '逻辑节点'), ('integration', '集成节点')], default='basic', verbose_name='分类')),
                ('icon', models.CharField(max_length=50, blank=True, verbose_name='图标类名')),
                ('config_schema', models.JSONField(verbose_name='配置模式')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否激活')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '工作流节点类型',
                'verbose_name_plural': '工作流节点类型',
                'db_table': 'ai_workflow_node_type',
            },
        ),
        migrations.CreateModel(
            name='NodeExecution',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(max_length=20, choices=[('pending', '待执行'), ('running', '执行中'), ('completed', '已完成'), ('failed', '执行失败'), ('skipped', '已跳过')], default='pending', verbose_name='执行状态')),
                ('input_data', models.JSONField(blank=True, null=True, verbose_name='输入数据')),
                ('output_data', models.JSONField(blank=True, null=True, verbose_name='输出数据')),
                ('error_message', models.TextField(blank=True, verbose_name='错误信息')),
                ('started_at', models.DateTimeField(auto_now_add=True, verbose_name='开始时间')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='完成时间')),
                ('execution_time', models.FloatField(default=0, verbose_name='执行时间(秒)')),
                ('workflow_execution', models.ForeignKey(on_delete=models.CASCADE, related_name='node_executions', to='ai.aiworkflowexecution', verbose_name='所属执行')),
                ('node', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, to='ai.workflownode', verbose_name='节点')),
            ],
            options={
                'verbose_name': '节点执行记录',
                'verbose_name_plural': '节点执行记录',
                'db_table': 'ai_node_execution',
            },
        ),
        migrations.CreateModel(
            name='WorkflowDataAccessConfig',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('access_type', models.CharField(max_length=20, choices=[('database', '数据库'), ('api', 'API接口'), ('file', '文件'), ('memory', '内存数据')], verbose_name='访问类型')),
                ('resource_name', models.CharField(max_length=100, verbose_name='资源名称')),
                ('resource_identifier', models.CharField(max_length=200, verbose_name='资源标识符')),
                ('operations', models.JSONField(verbose_name='允许的操作')),
                ('filters', models.JSONField(blank=True, null=True, verbose_name='过滤条件')),
                ('description', models.TextField(blank=True, verbose_name='配置描述')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否激活')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('workflow', models.ForeignKey(on_delete=models.CASCADE, related_name='data_access_configs', to='ai.aiworkflow', verbose_name='所属工作流')),
            ],
            options={
                'verbose_name': '工作流数据访问配置',
                'verbose_name_plural': '工作流数据访问配置',
                'db_table': 'ai_workflow_data_access',
            },
        ),
        migrations.AddField(
            model_name='aiworkflowexecution',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='创建时间'),
        ),
        migrations.AlterField(
            model_name='aiworkflowexecution',
            name='started_at',
            field=models.DateTimeField(auto_now=True, verbose_name='开始时间'),
        ),
        migrations.AddField(
            model_name='aiworkflowexecution',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='更新时间'),
        ),
        migrations.AddField(
            model_name='aiworkflowexecution',
            name='created_by',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, to='user.admin', verbose_name='执行人'),
        ),
    ]
