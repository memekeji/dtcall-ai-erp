from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


SOURCE_MODELS = (
    'demandforecastplan',
    'outsourceissueorder',
    'prreviewtask',
    'pricerevieworder',
    'samplerequest',
)


def source_fields():
    operations = []
    for model_name in SOURCE_MODELS:
        if model_name != 'prreviewtask':
            operations.extend([
                migrations.AddField(
                    model_name=model_name,
                    name='source_code',
                    field=models.CharField(blank=True, max_length=100, verbose_name='来源单号'),
                ),
                migrations.AddField(
                    model_name=model_name,
                    name='source_type',
                    field=models.CharField(blank=True, max_length=50, verbose_name='来源类型'),
                ),
            ])
        operations.extend([
            migrations.AddField(
                model_name=model_name,
                name='source_id',
                field=models.PositiveBigIntegerField(blank=True, null=True, verbose_name='来源记录ID'),
            ),
            migrations.AddField(
                model_name=model_name,
                name='source_snapshot',
                field=models.JSONField(blank=True, default=dict, verbose_name='来源快照'),
            ),
        ])
    return operations


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('supply_chain', '0002_add_sample_reminder_fields'),
    ]

    operations = source_fields() + [
        migrations.CreateModel(
            name='SupplyChainSequence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prefix', models.CharField(max_length=20, verbose_name='业务前缀')),
                ('business_date', models.DateField(verbose_name='业务日期')),
                ('current_value', models.PositiveIntegerField(default=0, verbose_name='当前序号')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '供应链业务序列',
                'verbose_name_plural': '供应链业务序列',
                'db_table': 'supply_chain_sequence',
            },
        ),
        migrations.CreateModel(
            name='SupplyChainAIInsight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope', models.CharField(max_length=50, verbose_name='分析范围')),
                ('object_type', models.CharField(max_length=50, verbose_name='对象类型')),
                ('object_id', models.PositiveBigIntegerField(default=0, verbose_name='对象ID')),
                ('status', models.CharField(choices=[('success', '成功'), ('error', '失败')], max_length=20, verbose_name='状态')),
                ('input_hash', models.CharField(blank=True, max_length=64, verbose_name='输入摘要')),
                ('content', models.TextField(blank=True, verbose_name='分析结论')),
                ('result_payload', models.JSONField(blank=True, default=dict, verbose_name='结构化结果')),
                ('error_message', models.TextField(blank=True, verbose_name='错误信息')),
                ('generated_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='生成时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('generated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='生成人')),
            ],
            options={
                'verbose_name': '供应链AI分析记录',
                'verbose_name_plural': '供应链AI分析记录',
                'db_table': 'supply_chain_ai_insight',
            },
        ),
        migrations.AddConstraint(
            model_name='supplychainsequence',
            constraint=models.UniqueConstraint(fields=('prefix', 'business_date'), name='supply_chain_unique_sequence_day'),
        ),
        migrations.AddConstraint(
            model_name='supplychainaiinsight',
            constraint=models.UniqueConstraint(fields=('scope', 'object_type', 'object_id'), name='supply_chain_unique_ai_insight'),
        ),
        migrations.AddIndex(
            model_name='supplychainaiinsight',
            index=models.Index(fields=['scope', 'status', '-generated_at'], name='supply_chai_scope_37e569_idx'),
        ),
    ]
