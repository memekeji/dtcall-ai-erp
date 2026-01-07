from django.db import models
from apps.user.models import Admin as User
from apps.department.models import Department

# Message模型已移至models_new.py文件中
# 这里保留注释以避免导入错误

# 为了避免与models_new.py中的Message模型冲突，
# 原始的Message模型已被重命名为MessageOld，并且不再在此文件中定义
# 请使用 from apps.oa.models_new import Message 来导入消息模型
# MeetingRecords模型已移除，使用models_new.py中的MeetingRecord模型替代


class Approval(models.Model):
    class Meta:
        app_label = 'oa'
        db_table = 'mimu_flow_record'
        verbose_name = '审批记录'
        verbose_name_plural = verbose_name
    action_id = models.IntegerField(default=0, verbose_name="审批内容ID")  # 原表default=0
    check_type = models.SmallIntegerField(default=1, verbose_name='审批类型', choices=[(1,'自由审批'),(2,'固定审批')])  # 补充原表mimu_flow的check_type字段
    check_table = models.CharField(max_length=255, default='审批数据表', verbose_name="审批数据表")  # 原表default='审批数据表'
    flow_id = models.IntegerField(verbose_name="审批流程ID", default=0)
    step_id = models.IntegerField(default=0, verbose_name="审批步骤ID")  # 原表default=0
    check_uid = models.IntegerField(default=0, verbose_name="审批人ID")  # 原表default=0
    check_time = models.BigIntegerField(verbose_name="审批时间", default=0)  # 原表为时间戳类型
    check_status = models.SmallIntegerField(
        default=0,
        verbose_name="审批状态",
        choices=[(0, '发起'), (1, '通过'), (2, '拒绝'), (3, '撤销')]
    )  # 原表default=0
    content = models.CharField(max_length=500, default='', verbose_name="审批意见")  # 原表default=''
    delete_time = models.BigIntegerField(default=0, verbose_name="删除时间")

    def __str__(self):
        return self.content


class Schedule(models.Model):
    work_id = models.PositiveIntegerField(default=0, verbose_name='汇报工作ID')  # 对应原表mimu_work_record的work_id字段
    title = models.CharField(max_length=255, verbose_name="标题", default='')
    start_time = models.DateTimeField(verbose_name="开始时间")
    end_time = models.DateTimeField(verbose_name="结束时间")
    labor_time = models.FloatField(default=0.0, verbose_name="工时")
    admin_id = models.IntegerField(default=1, verbose_name="用户ID")
    did = models.IntegerField(default=1, verbose_name="部门ID")
    labor_type = models.IntegerField(default=1, verbose_name="工作类型")
    cid = models.IntegerField(null=True, blank=True, verbose_name="工作分类ID")
    tid = models.IntegerField(null=True, blank=True, verbose_name="任务ID")
    content = models.TextField(blank=True, verbose_name="内容")
    delete_time = models.BigIntegerField(default=0, verbose_name="删除时间")
    create_time = models.BigIntegerField(default=0, verbose_name="创建时间")
    update_time = models.BigIntegerField(default=0, verbose_name="更新时间")

    class Meta:
        db_table = 'oa_schedule'
        verbose_name = '工作日程'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title
