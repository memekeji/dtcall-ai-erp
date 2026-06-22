# Generated for approval flow graph structure

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('approval', '0003_approvalstep_canvas_position'),
    ]

    operations = [
        migrations.AddField(
            model_name='approvalstep',
            name='approval_mode',
            field=models.CharField(
                choices=[
                    ('single', '单人审批'),
                    ('all', '全部同意'),
                    ('any', '任一同意'),
                ],
                default='single',
                max_length=20,
                verbose_name='审批方式',
            ),
        ),
        migrations.AddField(
            model_name='approvalstep',
            name='timeout_action',
            field=models.CharField(
                choices=[
                    ('none', '无'),
                    ('auto_approve', '自动通过'),
                    ('auto_reject', '自动拒绝'),
                    ('escalate', '升级处理'),
                ],
                default='none',
                max_length=20,
                verbose_name='超时策略',
            ),
        ),
        migrations.AddField(
            model_name='approvalstep',
            name='config_json',
            field=models.TextField(default='{}', verbose_name='扩展配置'),
        ),
        migrations.AlterField(
            model_name='approvalrecord',
            name='action',
            field=models.CharField(
                choices=[
                    ('submit', '提交'),
                    ('approve', '通过'),
                    ('reject', '拒绝'),
                    ('cancel', '取消'),
                    ('delegate', '委托'),
                    ('return', '退回'),
                    ('transfer', '转办'),
                    ('add_before', '前加签'),
                    ('add_after', '后加签'),
                    ('withdraw', '撤回'),
                    ('execute', '办理'),
                    ('external_approve', '外部审批'),
                    ('urge', '催办'),
                    ('timeout', '超时'),
                    ('force_end', '强制结束'),
                    ('archive', '归档'),
                ],
                max_length=20,
                verbose_name='操作类型',
            ),
        ),
        migrations.AlterField(
            model_name='approvalstep',
            name='step_type',
            field=models.CharField(
                choices=[
                    ('department_head', '部门负责人'),
                    ('specific_user', '指定用户'),
                    ('department', '指定部门'),
                    ('role', '指定角色'),
                    ('level', '指定级别'),
                    ('cc', '抄送'),
                    ('notification', '通知'),
                    ('custom', '自定义条件'),
                    ('countersign', '多人会签'),
                    ('orsign', '多人或签'),
                    ('execute', '办理/执行'),
                    ('external', '外部审批'),
                    ('condition', '条件分支'),
                    ('status_update', '状态更新'),
                    ('writeback', '数据回写'),
                    ('archive', '归档通知'),
                    ('intervention', '异常干预'),
                ],
                default='department_head',
                max_length=20,
                verbose_name='步骤类型',
            ),
        ),
        migrations.AlterField(
            model_name='approvalstep',
            name='action_type',
            field=models.CharField(
                choices=[
                    ('approve', '审批'),
                    ('review', '审阅'),
                    ('sign', '会签'),
                    ('notify', '通知'),
                    ('execute', '办理'),
                    ('external', '外部审批'),
                    ('archive', '归档'),
                    ('system', '系统动作'),
                ],
                default='approve',
                max_length=20,
                verbose_name='操作类型',
            ),
        ),
        migrations.CreateModel(
            name='ApprovalFlowEdge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('from_node', models.CharField(max_length=50, verbose_name='源节点')),
                ('to_node', models.CharField(max_length=50, verbose_name='目标节点')),
                ('edge_type', models.CharField(
                    choices=[
                        ('success', '通过'),
                        ('condition', '条件'),
                        ('reject', '拒绝'),
                        ('return', '退回'),
                    ],
                    default='success',
                    max_length=20,
                    verbose_name='连线类型',
                )),
                ('label', models.CharField(blank=True, default='', max_length=100, verbose_name='连线标签')),
                ('condition_field', models.CharField(blank=True, default='', max_length=100, verbose_name='条件字段')),
                ('condition_operator', models.CharField(blank=True, default='', max_length=20, verbose_name='条件操作符')),
                ('condition_value', models.CharField(blank=True, default='', max_length=200, verbose_name='条件值')),
                ('sort_order', models.IntegerField(default=0, verbose_name='排序')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('flow', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='edges', to='approval.approvalflow', verbose_name='所属流程')),
                ('from_step', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='outgoing_edges', to='approval.approvalstep', verbose_name='源步骤')),
                ('to_step', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='incoming_edges', to='approval.approvalstep', verbose_name='目标步骤')),
            ],
            options={
                'verbose_name': '审批流程连线',
                'verbose_name_plural': '审批流程连线',
                'db_table': 'basedata_approval_flow_edge',
                'ordering': ['sort_order', 'id'],
            },
        ),
    ]
