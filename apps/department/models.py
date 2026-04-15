from django.db import models


class Department(models.Model):
    # 与模板中使用的name保持一致
    name = models.CharField(
        max_length=50,
        default='未命名部门',
        verbose_name="部门名称")
    pid = models.IntegerField(
        default=0,
        verbose_name="上级部门ID",
        db_column='pid')
    # 添加code字段，模板中使用
    code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="部门代码")
    # 使用ForeignKey关联用户表，替代原来的leader_ids
    manager = models.ForeignKey(
        'user.Admin',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name="部门负责人",
        related_name='managed_departments')
    # 保留原来的leader_ids字段用于向后兼容
    leader_ids = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="部门负责人ID列表",
        db_column='leader_ids')
    phone = models.CharField(
        max_length=60,
        blank=True,
        null=True,
        verbose_name="部门联系电话",
        db_column='phone')
    remark = models.TextField(
        blank=True,
        null=True,
        verbose_name="部门描述",
        db_column='description')
    sort = models.IntegerField(default=0, verbose_name="排序值", db_column='sort')
    status = models.IntegerField(
        default=1,
        verbose_name="状态",
        db_column='status')
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间",
        db_column='create_time')
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新时间",
        db_column='update_time')
    # 添加level字段用于模板中的层级显示
    level = models.IntegerField(default=0, verbose_name="部门层级")
    # 添加is_active字段与模板中的状态显示匹配
    is_active = models.BooleanField(default=True, verbose_name="是否启用")

    class Meta:
        verbose_name = '部门'
        verbose_name_plural = verbose_name
        # 显式指定使用department_department表，确保读取正确的数据
        db_table = 'department_department'
        # 添加ordering以优化查询性能
        ordering = ['sort', 'id']

    def __str__(self):
        return self.name

    # 获取部门成员数量
    @property
    def users_count(self):
        from apps.user.models.admin import Admin
        return Admin.objects.filter(did=self.id).count()

    # 兼容模板中的title字段
    @property
    def title(self):
        return self.name

    # 重写save方法，自动计算部门层级
    def save(self, *args, **kwargs):
        # 如果是顶级部门(pid=0)，层级为0
        if self.pid == 0:
            self.level = 0
        else:
            # 查找父部门并设置当前部门的层级
            parent_dept = Department.objects.filter(id=self.pid).first()
            if parent_dept:
                self.level = parent_dept.level + 1
            else:
                self.level = 0
        # 同步status和is_active字段
        self.is_active = self.status == 1
        # 调用父类的save方法保存数据
        super(Department, self).save(*args, **kwargs)
