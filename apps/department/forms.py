from django import forms
from django.forms import ValidationError
from .models import Department
from apps.user.models import Admin


class DepartmentForm(forms.ModelForm):
    # 上级部门选择框 - 使用ChoiceField才能正确渲染choices
    pid = forms.ChoiceField(
        required=False,
        label='上级部门',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    # 部门负责人 - 单选（主负责人）
    manager = forms.ModelChoiceField(
        queryset=Admin.objects.all(),
        required=False,
        label='部门负责人',
        widget=forms.Select(attrs={'class': 'form-control select2'})
    )

    # 部门负责人选择框，支持多选（保留用于向后兼容）
    leader_ids = forms.CharField(
        required=False,
        label='部门负责人（多选）',
        widget=forms.HiddenInput()
    )

    # 状态选择框，中文显示
    STATUS_CHOICES = [
        (1, '启用'),
        (0, '禁用'),
    ]
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        label='状态',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Department
        fields = [
            'name',
            'code',
            'pid',
            'manager',
            'leader_ids',
            'phone',
            'sort',
            'remark',
            'status']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入部门名称',
                    'autocomplete': 'off'}),
            'code': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'id': 'departmentCodeField',
                    'placeholder': '系统将根据层级自动生成',
                    'readonly': 'readonly',
                    'data-auto-generate': 'true'}),
            'phone': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '负责人联系电话将自动带出',
                    'autocomplete': 'off'}),
            'sort': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '数字越小越靠前',
                    'min': '0'}),
            'remark': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'rows': 4,
                    'placeholder': '补充部门职责、协作范围或管理说明'}),
        }

    def clean_pid(self):
        # 处理pid字段，将字符串ID转换为整数
        pid_value = self.cleaned_data.get('pid')
        if pid_value and pid_value != '0':
            try:
                pid_int = int(pid_value)
                # 验证部门是否存在
                if Department.objects.filter(id=pid_int).exists():
                    return pid_int
                else:
                    raise ValidationError('选择的上级部门不存在')
            except (ValueError, TypeError):
                return None
        return None  # 0或空表示无上级部门

    def clean_leader_ids(self):
        # 处理leader_ids字段，将字符串ID转换为Admin对象列表
        leader_ids_str = self.cleaned_data.get('leader_ids')
        if not leader_ids_str:
            return []

        # 确保是字符串类型
        if not isinstance(leader_ids_str, str):
            leader_ids_str = str(leader_ids_str)

        # 分割ID字符串并过滤空值
        leader_ids = [id.strip()
                      for id in leader_ids_str.split(',') if id.strip()]

        # 获取所有对应的Admin对象
        try:
            return Admin.objects.filter(id__in=leader_ids)
        except (ValueError, TypeError):
            raise ValidationError('负责人ID格式错误')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 动态设置上级部门choices
        departments = Department.objects.all().order_by('sort', 'id')
        pid_choices = [(0, '无上级部门（顶级部门）')]  # 默认选项
        for dept in departments:
            # 排除自己（编辑时不能选择自己为上级）
            if self.instance and self.instance.id and dept.id == self.instance.id:
                continue
            pid_choices.append((dept.id, dept.name))
        self.fields['pid'].choices = pid_choices
        self.fields['pid'].widget.attrs.update({
            'class': 'layui-select',
            'id': 'departmentParentField',
        })
        self.fields['manager'].widget.attrs.update({
            'class': 'layui-select',
            'id': 'departmentManagerField',
        })
        self.fields['status'].widget.attrs.update({
            'class': 'layui-select',
            'id': 'departmentStatusField',
        })

        # 编辑时设置负责人初始值
        if self.instance and self.instance.leader_ids:
            leader_ids_str = self.instance.leader_ids.strip('[] ')
            if leader_ids_str:
                leader_ids = [id.strip() for id in leader_ids_str.split(
                    ',') if id.strip().isdigit()]
                if leader_ids:
                    self.fields['leader_ids'].initial = ','.join(leader_ids)

        # 编辑时设置主负责人初始值
        if self.instance and self.instance.manager:
            self.fields['manager'].initial = self.instance.manager

        # 设置pid初始值 - pid现在是整数
        if self.instance and self.instance.pid:
            self.fields['pid'].initial = str(
                self.instance.pid) if self.instance.pid else '0'

    def save(self, commit=True):
        # 保存表单前同步status与is_active字段
        instance = super().save(commit=False)
        instance.is_active = bool(instance.status)

        # 处理pid字段：ChoiceField返回的是字符串，需要转换为整数
        pid_value = self.cleaned_data.get('pid') if hasattr(
            self, 'cleaned_data') and 'pid' in self.cleaned_data else None
        if pid_value and pid_value != '0':
            try:
                instance.pid = int(pid_value)
            except (ValueError, TypeError):
                instance.pid = 0
        else:
            instance.pid = 0

        # 如果设置了manager但没有设置leader_ids，将manager添加到leader_ids
        if instance.manager and not instance.leader_ids:
            instance.leader_ids = str(instance.manager.id)
        elif instance.manager:
            leader_ids = instance.leader_ids.split(
                ',') if instance.leader_ids else []
            manager_id = str(instance.manager.id)
            if manager_id not in leader_ids:
                leader_ids.append(manager_id)
                instance.leader_ids = ','.join(leader_ids)

        # 自动生成部门代码
        if not instance.code or instance.code.strip() == '':
            instance.code = self._generate_department_code(instance)

        if commit:
            instance.save()
        return instance

    def _generate_department_code(self, department):
        """
        自动生成部门代码
        规则：
        1. 顶级部门：D001, D002, D003...
        2. 子部门：父部门代码 + 序号（如D001001, D001002...）
        """
        import re

        if department.pid == 0:
            top_level_departments = Department.objects.filter(pid=0)
            if department.id:
                top_level_departments = top_level_departments.exclude(id=department.id)

            max_top_level = 0
            for existing_department in top_level_departments:
                match = re.fullmatch(r'D(\d{3})', (existing_department.code or '').strip())
                if match:
                    max_top_level = max(max_top_level, int(match.group(1)))
            return f"D{max_top_level + 1:03d}"
        else:
            # 子部门：父部门代码 + 序号
            try:
                parent_dept = Department.objects.get(id=department.pid)
                if parent_dept.code:
                    # 查找该父部门下的最大序号
                    siblings = Department.objects.filter(
                        pid=department.pid).exclude(
                        id=department.id)
                    max_suffix = 0
                    for sibling in siblings:
                        if sibling.code and sibling.code.startswith(
                                parent_dept.code):
                            suffix = sibling.code[len(parent_dept.code):]
                            if re.fullmatch(r'\d{3}', suffix):
                                max_suffix = max(max_suffix, int(suffix))

                    next_suffix = max_suffix + 1
                    return f"{parent_dept.code}{next_suffix:03d}"
            except Department.DoesNotExist:
                pass

            # 如果父部门不存在或没有代码，生成默认代码
            return f"D{department.pid:03d}001"
