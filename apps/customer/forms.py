from django import forms
from django.forms import inlineformset_factory
import re
from apps.common.constants import CUSTOMER_INDUSTRY_CHOICES
from .models import (
    Customer, Contact, CustomerOrder, CustomerContract,
    FollowRecord, CustomerSource, CustomerGrade, CustomerIntent,
    FollowField, OrderField, CustomerField
)


class ContactForm(forms.ModelForm):
    contact_person = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={
                'class': 'layui-input',
                'placeholder': '请输入联系人姓名'}))
    phone = forms.CharField(required=True, widget=forms.TextInput(
        attrs={'class': 'layui-input', 'placeholder': '请输入联系电话'}))

    class Meta:
        model = Contact
        fields = ['contact_person', 'phone', 'is_primary', 'position', 'email']
        widgets = {
            'position': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入职位'}),
            'email': forms.EmailInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入电子邮箱'}),
            'is_primary': forms.HiddenInput(
                attrs={
                    'class': 'primary-contact-value'}),
        }

    def clean_is_primary(self):
        value = self.cleaned_data.get('is_primary')
        # 检查值类型，如果是字符串则转换为布尔值，如果是布尔值则直接返回
        if isinstance(value, str):
            return value.lower() == 'true'
        return bool(value)

    def clean(self):
        cleaned_data = super().clean()
        delete = cleaned_data.get('DELETE', False)
        contact_person = cleaned_data.get('contact_person', '').strip()
        phone = cleaned_data.get('phone', '').strip()

        # 如果表单被标记为删除，或者联系人和电话都为空，则跳过验证
        if delete or (not contact_person and not phone):
            return cleaned_data

        # 否则，执行正常的验证
        if not contact_person:
            self.add_error('contact_person', '这个字段是必须的')
        if not phone:
            self.add_error('phone', '这个字段是必须的')

        return cleaned_data


ContactFormSet = inlineformset_factory(
    Customer,
    Contact,
    form=ContactForm,
    extra=0,
    can_delete=True,
    can_order=False
)


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'name',
            'customer_source',
            'grade_id',
            'industry_id',
            'services_id',
            'province',
            'city',
            'district',
            'town',
            'address',
            'content',
            'market',
            'remark',
            'tax_bank',
            'tax_banksn',
            'tax_num',
            'tax_mobile',
            'tax_address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入客户名称', 'required': True}),
            'customer_source': forms.Select(attrs={'class': 'layui-input'}),
            'grade_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '客户等级ID'}),
            'industry_id': forms.Select(attrs={'class': 'layui-input'}),
            'services_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '客户意向ID'}),
            'province': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入省份'}),
            'city': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入城市'}),
            'district': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入区县'}),
            'town': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入城镇'}),
            'address': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入详细地址'}),
            'content': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入客户描述', 'rows': 3}),
            'market': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入主要经营业务', 'rows': 3}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入备注信息', 'rows': 3}),
            'tax_bank': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入开户银行'}),
            'tax_banksn': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入银行账号'}),
            'tax_num': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入纳税人识别号'}),
            'tax_mobile': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入税务联系电话'}),
            'tax_address': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入税务地址'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        # 排除当前编辑的客户（如果是更新操作）
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            exists = Customer.objects.filter(
                name=name, delete_time=0).exclude(
                pk=instance.pk).exists()
        else:
            exists = Customer.objects.filter(name=name, delete_time=0).exists()
        if exists:
            raise forms.ValidationError('客户名称已存在')
        return name

    def clean(self):
        cleaned_data = super().clean()

        # 处理grade_id字段，如果为空则设置为0（模型默认值）
        grade_id = cleaned_data.get('grade_id')
        if grade_id == '':
            cleaned_data['grade_id'] = 0
        elif grade_id:
            try:
                cleaned_data['grade_id'] = int(grade_id)
            except ValueError:
                self.add_error('grade_id', '客户等级必须是有效的数字')

        # 处理industry_id字段，如果为空则设置为0
        industry_id = cleaned_data.get('industry_id')
        if industry_id == '':
            cleaned_data['industry_id'] = 0
        elif industry_id:
            try:
                cleaned_data['industry_id'] = int(industry_id)
            except ValueError:
                self.add_error('industry_id', '所属行业必须是有效的数字')

        # 处理services_id字段，如果为空则设置为0
        services_id = cleaned_data.get('services_id')
        if services_id == '':
            cleaned_data['services_id'] = 0
        elif services_id:
            try:
                cleaned_data['services_id'] = int(services_id)
            except ValueError:
                self.add_error('services_id', '客户意向必须是有效的数字')

        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 动态加载客户来源选项
        from .models import CustomerSource, CustomerGrade
        self.fields['customer_source'].queryset = CustomerSource.objects.filter(
            status=1, delete_time=0).order_by('sort', 'id')
        self.fields['customer_source'].empty_label = "请选择客户来源"

        # 动态加载客户等级选项（将grade_id改为下拉选择）
        grade_choices = [('', '请选择客户等级')]
        for grade in CustomerGrade.objects.filter(
                status=1,
                delete_time=0).order_by(
                'sort',
                'id'):
            grade_choices.append((grade.id, grade.title))
        self.fields['grade_id'] = forms.ChoiceField(
            choices=grade_choices,
            widget=forms.Select(attrs={'class': 'layui-input'}),
            required=False
        )

        industry_choices = [('', '请选择所属行业')]
        for industry_id, industry_name in CUSTOMER_INDUSTRY_CHOICES.items():
            industry_choices.append((industry_id, industry_name))
        self.fields['industry_id'] = forms.ChoiceField(
            choices=industry_choices,
            widget=forms.Select(attrs={'class': 'layui-input'}),
            required=False
        )

        # 动态加载客户意向选项（将services_id改为下拉选择）
        from .models import CustomerIntent
        intent_choices = [('', '请选择客户意向')]
        for intent in CustomerIntent.objects.filter(
                status=1,
                delete_time=0).order_by(
                'sort',
                'id'):
            intent_choices.append((intent.id, intent.name))
        self.fields['services_id'] = forms.ChoiceField(
            choices=intent_choices,
            widget=forms.Select(attrs={'class': 'layui-input'}),
            required=False
        )


class CustomerOrderForm(forms.ModelForm):
    """客户订单表单"""
    class Meta:
        model = CustomerOrder
        fields = [
            'customer', 'order_number', 'product_name', 'amount',
            'order_date', 'status', 'description', 'remark'
        ]
        widgets = {
            'customer': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'order_number': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入订单编号'}),
            'product_name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入产品名称'}),
            'amount': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入订单金额',
                    'step': '0.01'}),
            'order_date': forms.DateInput(
                attrs={
                    'class': 'layui-input',
                    'type': 'date'}),
            'status': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'description': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入订单描述',
                    'rows': 3}),
            'remark': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入备注信息',
                    'rows': 3}),
        }

    def clean_order_number(self):
        order_number = self.cleaned_data.get('order_number')
        # 检查订单编号唯一性
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            exists = CustomerOrder.objects.filter(
                order_number=order_number,
                delete_time=0).exclude(
                pk=instance.pk).exists()
        else:
            exists = CustomerOrder.objects.filter(
                order_number=order_number, delete_time=0).exists()
        if exists:
            raise forms.ValidationError('订单编号已存在')
        return order_number


class CustomerContractForm(forms.ModelForm):
    """客户合同表单"""
    class Meta:
        model = CustomerContract
        fields = [
            'customer', 'contract_number', 'name', 'amount',
            'sign_date', 'end_date', 'status', 'contract_type',
            'description', 'remark'
        ]
        widgets = {
            'customer': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'contract_number': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入合同编号'}),
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入合同名称'}),
            'amount': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入合同金额',
                    'step': '0.01'}),
            'sign_date': forms.DateInput(
                attrs={
                    'class': 'layui-input',
                    'type': 'date'}),
            'end_date': forms.DateInput(
                attrs={
                    'class': 'layui-input',
                    'type': 'date'}),
            'status': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'contract_type': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'description': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入合同描述',
                    'rows': 3}),
            'remark': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入备注信息',
                    'rows': 3}),
        }

    def clean_contract_number(self):
        contract_number = self.cleaned_data.get('contract_number')
        # 检查合同编号唯一性
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            exists = CustomerContract.objects.filter(
                contract_number=contract_number,
                delete_time=0).exclude(
                pk=instance.pk).exists()
        else:
            exists = CustomerContract.objects.filter(
                contract_number=contract_number, delete_time=0).exists()
        if exists:
            raise forms.ValidationError('合同编号已存在')
        return contract_number


class FollowRecordForm(forms.ModelForm):
    """客户跟进记录表单"""
    class Meta:
        model = FollowRecord
        fields = ['customer', 'follow_type', 'content', 'next_follow_time']
        widgets = {
            'customer': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'follow_type': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'content': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入跟进内容',
                    'rows': 4}),
            'next_follow_time': forms.DateTimeInput(
                attrs={
                    'class': 'layui-input',
                    'type': 'datetime-local'}),
        }

    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if not content:
            raise forms.ValidationError('跟进内容不能为空')
        if len(content) < 10:
            raise forms.ValidationError('跟进内容至少需要10个字符')
        return content


class FollowFieldForm(forms.ModelForm):
    class Meta:
        model = FollowField
        fields = [
            'name',
            'field_name',
            'field_type',
            'options',
            'is_required',
            'sort_order',
            'is_active']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入字段名称'}),
            'field_name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入字段标识'}),
            'field_type': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'options': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '选项值，每行一个',
                    'rows': 3}),
            'sort_order': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '排序号'}),
        }


class OrderFieldForm(forms.ModelForm):
    class Meta:
        model = OrderField
        fields = [
            'name',
            'field_name',
            'field_type',
            'options',
            'is_required',
            'is_summary',
            'sort_order',
            'is_active']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入字段名称'}),
            'field_name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入字段标识'}),
            'field_type': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'options': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '选项值，每行一个',
                    'rows': 3}),
            'sort_order': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '排序号'}),
        }


class CustomerSourceForm(forms.ModelForm):
    status = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={
                'lay-skin': 'switch',
                'lay-text': '启用|禁用'}))

    class Meta:
        model = CustomerSource
        fields = ['title', 'sort']
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入来源名称'}),
            'sort': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '排序号'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['status'].initial = self.instance.status == 1

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.delete_time = 0
        instance.status = 1 if self.cleaned_data['status'] else 0
        if commit:
            instance.save()
        return instance


class CustomerGradeForm(forms.ModelForm):
    status = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={
                'lay-skin': 'switch',
                'lay-text': '启用|禁用'}))

    class Meta:
        model = CustomerGrade
        fields = ['title', 'sort']
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入等级名称'}),
            'sort': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '排序号'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['status'].initial = self.instance.status == 1

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.delete_time = 0
        instance.status = 1 if self.cleaned_data['status'] else 0
        if commit:
            instance.save()
        return instance


class CustomerIntentForm(forms.ModelForm):
    status = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={
                'lay-skin': 'switch',
                'lay-text': '启用|禁用'}))

    class Meta:
        model = CustomerIntent
        fields = ['name', 'sort']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入意向名称'}),
            'sort': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '排序号'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['status'].initial = self.instance.status == 1

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.delete_time = 0
        instance.status = 1 if self.cleaned_data['status'] else 0
        if commit:
            instance.save()
        return instance


class CustomerFieldForm(forms.ModelForm):
    FORMULA_TOKEN_PATTERN = re.compile(r'\{([a-zA-Z0-9_]+)\}')
    FORMULA_VALUE_PATTERN = re.compile(r'-?\d+(?:\.\d+)?')
    FORMULA_SIMPLE_EXPRESSION_PATTERN = re.compile(
        r'^\s*(\{[a-zA-Z0-9_]+\}|-?\d+(?:\.\d+)?)\s*([+\-*/])\s*(\{[a-zA-Z0-9_]+\}|-?\d+(?:\.\d+)?)\s*$'
    )
    FORMULA_OPERATOR_CHOICES = [
        ('+', '加法'),
        ('-', '减法'),
        ('*', '乘法'),
        ('/', '除法'),
    ]

    status = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={
                'lay-skin': 'switch',
                'lay-text': '启用|禁用'}))
    relation_enabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={
                'lay-skin': 'switch',
                'lay-text': '开启|关闭',
                'lay-filter': 'relationEnabledSwitch'}))

    class Meta:
        model = CustomerField
        fields = [
            'name',
            'field_name',
            'field_type',
            'options',
            'is_required',
            'is_unique',
            'relation_enabled',
            'related_field',
            'relation_type',
            'calculation_type',
            'formula_expression',
            'is_list_display',
            'sort']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入字段名称'}),
            'field_name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入字段标识'}),
            'field_type': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'options': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '选项值，每行一个',
                    'rows': 3}),
            'sort': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '排序号'}),
            'related_field': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'relation_type': forms.Select(
                attrs={
                    'class': 'layui-input',
                    'lay-filter': 'relationTypeSelect'}),
            'calculation_type': forms.Select(
                attrs={
                    'class': 'layui-input',
                    'lay-filter': 'calculationTypeSelect'}),
            'formula_expression': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入公式，例如：{unit_price} * {quantity}',
                    'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['status'].initial = self.instance.status
        self.fields['relation_enabled'].initial = getattr(self.instance, 'relation_enabled', False)
        self.fields['related_field'].required = False
        self.fields['relation_type'].required = False
        self.fields['calculation_type'].required = False
        self.fields['formula_expression'].required = False
        self.fields['relation_type'].initial = getattr(self.instance, 'relation_type', '') or 'bind'
        self.fields['calculation_type'].initial = getattr(self.instance, 'calculation_type', '') or 'count'
        self.fields['formula_expression'].initial = getattr(self.instance, 'formula_expression', '') or ''
        self.fields['related_field'].queryset = CustomerField.objects.filter(
            delete_time=0
        ).exclude(pk=self.instance.pk).order_by('sort', 'id')
        self.fields['related_field'].empty_label = '请选择关联字段'
        self.available_formula_fields = list(self.fields['related_field'].queryset)
        self.available_formula_field_options = [
            {
                'field_name': field.field_name,
                'name': field.name,
            }
            for field in self.available_formula_fields
        ]
        self.formula_operator_choices = list(self.FORMULA_OPERATOR_CHOICES)
        (
            self.formula_builder_rows,
            self.formula_builder_parse_failed,
        ) = self._build_formula_builder_rows(self.fields['formula_expression'].initial)

    def _default_formula_builder_row(self, join_operator=''):
        return {
            'join_operator': join_operator,
            'left_type': 'field',
            'left_field_name': '',
            'left_value': '',
            'operator': '*',
            'right_type': 'field',
            'right_field_name': '',
            'right_value': '',
        }

    def _parse_formula_operand(self, operand):
        operand = (operand or '').strip()
        token_match = self.FORMULA_TOKEN_PATTERN.fullmatch(operand)
        if token_match:
            return {
                'type': 'field',
                'field_name': token_match.group(1),
                'value': '',
            }
        if self.FORMULA_VALUE_PATTERN.fullmatch(operand):
            return {
                'type': 'value',
                'field_name': '',
                'value': operand,
            }
        return None

    def _split_formula_segments(self, expression):
        segments = []
        join_operators = []
        depth = 0
        current = []

        for char in expression:
            if char == '(':
                depth += 1
            elif char == ')' and depth > 0:
                depth -= 1

            if depth == 0 and char in '+-*/':
                segment = ''.join(current).strip()
                if segment:
                    segments.append(segment)
                    join_operators.append(char)
                    current = []
                    continue
            current.append(char)

        final_segment = ''.join(current).strip()
        if final_segment:
            segments.append(final_segment)
        return segments, join_operators

    def _parse_formula_segment(self, segment):
        normalized_segment = (segment or '').strip()
        if normalized_segment.startswith('(') and normalized_segment.endswith(')'):
            normalized_segment = normalized_segment[1:-1].strip()

        match = self.FORMULA_SIMPLE_EXPRESSION_PATTERN.match(normalized_segment)
        if not match:
            return None

        left_operand = self._parse_formula_operand(match.group(1))
        right_operand = self._parse_formula_operand(match.group(3))
        if not left_operand or not right_operand:
            return None

        return {
            'left_type': left_operand['type'],
            'left_field_name': left_operand['field_name'],
            'left_value': left_operand['value'],
            'operator': match.group(2),
            'right_type': right_operand['type'],
            'right_field_name': right_operand['field_name'],
            'right_value': right_operand['value'],
        }

    def _build_formula_builder_rows(self, expression):
        expression = (expression or '').strip()
        if not expression:
            return [self._default_formula_builder_row()], False

        simple_match = self.FORMULA_SIMPLE_EXPRESSION_PATTERN.match(expression)
        if simple_match:
            parsed = self._parse_formula_segment(expression)
            if parsed:
                row = self._default_formula_builder_row()
                row.update(parsed)
                return [row], False

        segments, join_operators = self._split_formula_segments(expression)
        rows = []
        if len(segments) > 1:
            for index, segment in enumerate(segments):
                parsed = self._parse_formula_segment(segment)
                if not parsed:
                    return [self._default_formula_builder_row()], True
                row = self._default_formula_builder_row(
                    '' if index == 0 else join_operators[index - 1]
                )
                row.update(parsed)
                rows.append(row)
            return rows, False

        return [self._default_formula_builder_row()], True

    def clean(self):
        cleaned_data = super().clean()
        relation_enabled = cleaned_data.get('relation_enabled')
        related_field = cleaned_data.get('related_field')
        relation_type = cleaned_data.get('relation_type')
        calculation_type = cleaned_data.get('calculation_type')
        formula_expression = (cleaned_data.get('formula_expression') or '').strip()

        if not relation_enabled:
            cleaned_data['related_field'] = None
            cleaned_data['relation_type'] = 'bind'
            cleaned_data['calculation_type'] = ''
            cleaned_data['formula_expression'] = ''
            return cleaned_data

        requires_related_field = not (
            relation_type == 'calculate' and calculation_type == 'formula'
        )

        if requires_related_field and not related_field:
            self.add_error('related_field', '开启字段关联后必须选择关联字段')
            return cleaned_data

        if relation_type == 'bind' and related_field and related_field.field_type != 'list':
            self.add_error('related_field', '关联绑定仅支持关联列表类型字段')

        if relation_type == 'calculate':
            if not calculation_type:
                self.add_error('calculation_type', '选择计算结果后必须指定计算规则')
                return cleaned_data

            if calculation_type == 'formula':
                if not formula_expression:
                    self.add_error('formula_expression', '选择公式计算后必须填写计算公式')
                    return cleaned_data

                tokens = self.FORMULA_TOKEN_PATTERN.findall(formula_expression)
                if not tokens:
                    self.add_error('formula_expression', '计算公式中至少需要引用一个字段变量，例如 {unit_price}')
                    return cleaned_data

                cleaned_data['related_field'] = None
            else:
                if calculation_type == 'count' and related_field.field_type != 'list':
                    self.add_error('calculation_type', '统计数量当前仅支持关联列表类型字段')

                if calculation_type in {'sum', 'avg', 'max', 'min'} and related_field.field_type not in {'number', 'list'}:
                    self.add_error('calculation_type', '数值计算仅支持关联数字或列表类型字段')

                if calculation_type == 'concat' and related_field.field_type == 'checkbox':
                    self.add_error('calculation_type', '文本拼接不支持复选框类型字段')
                cleaned_data['formula_expression'] = ''

        if relation_type != 'calculate':
            cleaned_data['calculation_type'] = ''
            cleaned_data['formula_expression'] = ''

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.status = 1 if self.cleaned_data.get('status') else 0
        instance.relation_enabled = bool(self.cleaned_data.get('relation_enabled'))
        if not instance.relation_enabled:
            instance.related_field = None
            instance.relation_type = 'bind'
            instance.calculation_type = ''
            instance.formula_expression = ''
        elif instance.relation_type != 'calculate':
            instance.calculation_type = ''
            instance.formula_expression = ''
        elif instance.calculation_type != 'formula':
            instance.formula_expression = ''
        else:
            instance.related_field = None
        if commit:
            instance.save()
        return instance
