"""
员工相关数据模型
"""
from django.db import models
from django.contrib.auth import get_user_model
from apps.department.models import Department

User = get_user_model()


class EmployeeFile(models.Model):
    """员工档案"""
    EDUCATION_CHOICES = (
        ('primary', '小学'),
        ('junior', '初中'),
        ('senior', '高中'),
        ('college', '大专'),
        ('bachelor', '本科'),
        ('master', '硕士'),
        ('doctor', '博士'),
    )

    MARITAL_STATUS = (
        ('single', '未婚'),
        ('married', '已婚'),
        ('divorced', '离异'),
        ('widowed', '丧偶'),
    )

    employee = models.OneToOneField(
        User, on_delete=models.CASCADE, verbose_name='员工')
    id_card = models.CharField(max_length=18, unique=True, verbose_name='身份证号')
    birth_date = models.DateField(verbose_name='出生日期')
    gender = models.CharField(
        max_length=10, choices=[
            ('male', '男'), ('female', '女')], verbose_name='性别')
    nationality = models.CharField(
        max_length=50, default='汉族', verbose_name='民族')
    native_place = models.CharField(max_length=200, verbose_name='籍贯')
    address = models.TextField(verbose_name='现住址')
    education = models.CharField(
        max_length=20,
        choices=EDUCATION_CHOICES,
        verbose_name='学历')
    graduate_school = models.CharField(
        max_length=200, blank=True, verbose_name='毕业院校')
    major = models.CharField(max_length=100, blank=True, verbose_name='专业')
    graduation_date = models.DateField(
        null=True, blank=True, verbose_name='毕业时间')
    marital_status = models.CharField(
        max_length=20,
        choices=MARITAL_STATUS,
        verbose_name='婚姻状况')
    emergency_contact = models.CharField(max_length=50, verbose_name='紧急联系人')
    emergency_phone = models.CharField(max_length=20, verbose_name='紧急联系电话')
    bank_account = models.CharField(
        max_length=50, blank=True, verbose_name='银行账号')
    bank_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='开户银行')
    social_security_number = models.CharField(
        max_length=50, blank=True, verbose_name='社保号')
    housing_fund_number = models.CharField(
        max_length=50, blank=True, verbose_name='公积金号')
    work_experience = models.TextField(blank=True, verbose_name='工作经历')
    skills = models.TextField(blank=True, verbose_name='技能特长')
    remarks = models.TextField(blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '员工档案'
        verbose_name_plural = verbose_name
        db_table = 'user_employee_file'

    def __str__(self):
        return f"{self.employee.username} - 档案"


class EmployeeTransfer(models.Model):
    """员工调动记录"""
    STATUS_CHOICES = (
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
        ('completed', '已完成'),
    )

    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='员工')
    from_department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='transfer_from',
        verbose_name='原部门')
    to_department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='transfer_to',
        verbose_name='调入部门')
    from_position = models.CharField(max_length=100, verbose_name='原职位')
    to_position = models.CharField(max_length=100, verbose_name='新职位')
    transfer_reason = models.TextField(verbose_name='调动原因')
    transfer_date = models.DateField(verbose_name='调动日期')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='状态')
    applicant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='transfer_applications',
        verbose_name='申请人')
    approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transfer_approvals',
        verbose_name='审批人')
    approve_time = models.DateTimeField(
        null=True, blank=True, verbose_name='审批时间')
    approve_comment = models.TextField(blank=True, verbose_name='审批意见')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='申请时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '员工调动'
        verbose_name_plural = verbose_name
        db_table = 'user_employee_transfer'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.username} - {self.from_department.title} -> {self.to_department.title}"


class EmployeeDimission(models.Model):
    """员工离职记录"""
    DIMISSION_TYPE = (
        ('resignation', '主动离职'),
        ('dismissal', '被动离职'),
        ('retirement', '退休'),
        ('contract_end', '合同到期'),
    )

    STATUS_CHOICES = (
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
        ('completed', '已完成'),
    )

    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='员工')
    dimission_type = models.CharField(
        max_length=20,
        choices=DIMISSION_TYPE,
        verbose_name='离职类型')
    dimission_reason = models.TextField(verbose_name='离职原因')
    apply_date = models.DateField(verbose_name='申请日期')
    dimission_date = models.DateField(verbose_name='离职日期')
    handover_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handover_tasks',
        verbose_name='交接人')
    handover_content = models.TextField(blank=True, verbose_name='交接内容')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='状态')
    approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dimission_approvals',
        verbose_name='审批人')
    approve_time = models.DateTimeField(
        null=True, blank=True, verbose_name='审批时间')
    approve_comment = models.TextField(blank=True, verbose_name='审批意见')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='申请时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '员工离职'
        verbose_name_plural = verbose_name
        db_table = 'user_employee_dimission'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.username} - {self.get_dimission_type_display()}"


class RewardPunishment(models.Model):
    """奖惩记录"""
    TYPE_CHOICES = (
        ('reward', '奖励'),
        ('punishment', '惩罚'),
    )

    LEVEL_CHOICES = (
        ('verbal', '口头'),
        ('written', '书面'),
        ('monetary', '经济'),
        ('promotion', '晋升'),
        ('demotion', '降级'),
        ('dismissal', '开除'),
    )

    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='员工')
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name='类型')
    level = models.CharField(
        max_length=20,
        choices=LEVEL_CHOICES,
        verbose_name='级别')
    title = models.CharField(max_length=200, verbose_name='标题')
    reason = models.TextField(verbose_name='原因')
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='金额')
    effective_date = models.DateField(verbose_name='生效日期')
    executor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='executed_rewards',
        verbose_name='执行人')
    remarks = models.TextField(blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '奖惩记录'
        verbose_name_plural = verbose_name
        db_table = 'user_reward_punishment'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.username} - {self.get_type_display()} - {self.title}"


class EmployeeCare(models.Model):
    """员工关怀记录"""
    CARE_TYPE = (
        ('birthday', '生日关怀'),
        ('holiday', '节日关怀'),
        ('illness', '生病慰问'),
        ('family', '家庭关怀'),
        ('achievement', '成就祝贺'),
        ('other', '其他'),
    )

    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='员工')
    care_type = models.CharField(
        max_length=20,
        choices=CARE_TYPE,
        verbose_name='关怀类型')
    title = models.CharField(max_length=200, verbose_name='关怀标题')
    content = models.TextField(verbose_name='关怀内容')
    care_date = models.DateField(verbose_name='关怀日期')
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='关怀金额')
    executor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='executed_cares',
        verbose_name='执行人')
    remarks = models.TextField(blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '员工关怀'
        verbose_name_plural = verbose_name
        db_table = 'user_employee_care'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.username} - {self.get_care_type_display()} - {self.title}"


class EmployeeContract(models.Model):
    """员工合同记录"""
    CONTRACT_TYPE = (
        ('fixed', '固定期限'),
        ('unfixed', '无固定期限'),
        ('project', '项目合同'),
        ('intern', '实习合同'),
    )

    STATUS_CHOICES = (
        ('active', '生效中'),
        ('expired', '已到期'),
        ('terminated', '已终止'),
        ('renewed', '已续签'),
    )

    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='员工')
    contract_type = models.CharField(
        max_length=20,
        choices=CONTRACT_TYPE,
        verbose_name='合同类型')
    contract_number = models.CharField(
        max_length=100, unique=True, verbose_name='合同编号')
    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')
    salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='基本工资')
    position = models.CharField(max_length=100, verbose_name='职位')
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        verbose_name='部门')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name='状态')
    remarks = models.TextField(blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '员工合同'
        verbose_name_plural = verbose_name
        db_table = 'user_employee_contract'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.username} - {self.contract_number}"
