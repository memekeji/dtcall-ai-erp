from django import forms
from django.forms import inlineformset_factory
from .models import (
    Customer, Contact, CustomerOrder, CustomerContract, 
    FollowRecord, CustomerSource, CustomerGrade, CustomerIntent,
    FollowField, OrderField, CustomerField
)

class ContactForm(forms.ModelForm):
    contact_person = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入联系人姓名'}))
    phone = forms.CharField(required=True, widget=forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入联系电话'}))

    class Meta:
        model = Contact
        fields = ['contact_person', 'phone', 'is_primary', 'position', 'email']
        widgets = {
            'position': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入职位'}),
            'email': forms.EmailInput(attrs={'class': 'layui-input', 'placeholder': '请输入电子邮箱'}),
            'is_primary': forms.HiddenInput(attrs={'class': 'primary-contact-value'}),
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
            'name', 'customer_source', 'grade_id', 'industry_id', 'services_id',
            'province', 'city', 'district', 'town', 'address', 
            'content', 'market', 'remark',
            'tax_bank', 'tax_banksn', 'tax_num', 'tax_mobile', 'tax_address'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入客户名称', 'required': True}),
            'customer_source': forms.Select(attrs={'class': 'layui-input'}),
            'grade_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '客户等级ID'}),
            'industry_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '所属行业ID'}),
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
            exists = Customer.objects.filter(name=name, delete_time=0).exclude(pk=instance.pk).exists()
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
            status=1, delete_time=0
        ).order_by('sort', 'id')
        self.fields['customer_source'].empty_label = "请选择客户来源"
        
        # 动态加载客户等级选项（将grade_id改为下拉选择）
        grade_choices = [('', '请选择客户等级')]
        for grade in CustomerGrade.objects.filter(status=1, delete_time=0).order_by('sort', 'id'):
            grade_choices.append((grade.id, grade.title))
        self.fields['grade_id'] = forms.ChoiceField(
            choices=grade_choices,
            widget=forms.Select(attrs={'class': 'layui-input'}),
            required=False
        )
        
        # 动态加载客户意向选项（将services_id改为下拉选择）
        from .models import CustomerIntent
        intent_choices = [('', '请选择客户意向')]
        for intent in CustomerIntent.objects.filter(status=1, delete_time=0).order_by('sort', 'id'):
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
            'customer': forms.Select(attrs={'class': 'layui-input'}),
            'order_number': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入订单编号'}),
            'product_name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入产品名称'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入订单金额', 'step': '0.01'}),
            'order_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'layui-input'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入订单描述', 'rows': 3}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入备注信息', 'rows': 3}),
        }

    def clean_order_number(self):
        order_number = self.cleaned_data.get('order_number')
        # 检查订单编号唯一性
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            exists = CustomerOrder.objects.filter(order_number=order_number, delete_time=0).exclude(pk=instance.pk).exists()
        else:
            exists = CustomerOrder.objects.filter(order_number=order_number, delete_time=0).exists()
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
            'customer': forms.Select(attrs={'class': 'layui-input'}),
            'contract_number': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入合同编号'}),
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入合同名称'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入合同金额', 'step': '0.01'}),
            'sign_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'layui-input'}),
            'contract_type': forms.Select(attrs={'class': 'layui-input'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入合同描述', 'rows': 3}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入备注信息', 'rows': 3}),
        }

    def clean_contract_number(self):
        contract_number = self.cleaned_data.get('contract_number')
        # 检查合同编号唯一性
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            exists = CustomerContract.objects.filter(contract_number=contract_number, delete_time=0).exclude(pk=instance.pk).exists()
        else:
            exists = CustomerContract.objects.filter(contract_number=contract_number, delete_time=0).exists()
        if exists:
            raise forms.ValidationError('合同编号已存在')
        return contract_number


class FollowRecordForm(forms.ModelForm):
    """客户跟进记录表单"""
    class Meta:
        model = FollowRecord
        fields = ['customer', 'follow_type', 'content', 'next_follow_time']
        widgets = {
            'customer': forms.Select(attrs={'class': 'layui-input'}),
            'follow_type': forms.Select(attrs={'class': 'layui-input'}),
            'content': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入跟进内容', 'rows': 4}),
            'next_follow_time': forms.DateTimeInput(attrs={'class': 'layui-input', 'type': 'datetime-local'}),
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
        fields = ['name', 'field_name', 'field_type', 'options', 'is_required', 'sort_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入字段名称'}),
            'field_name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入字段标识'}),
            'field_type': forms.Select(attrs={'class': 'layui-input'}),
            'options': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '选项值，每行一个', 'rows': 3}),
            'sort_order': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '排序号'}),
        }


class OrderFieldForm(forms.ModelForm):
    class Meta:
        model = OrderField
        fields = ['name', 'field_name', 'field_type', 'options', 'is_required', 'is_summary', 'sort_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入字段名称'}),
            'field_name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入字段标识'}),
            'field_type': forms.Select(attrs={'class': 'layui-input'}),
            'options': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '选项值，每行一个', 'rows': 3}),
            'sort_order': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '排序号'}),
        }


class CustomerSourceForm(forms.ModelForm):
    status = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'lay-skin': 'switch', 'lay-text': '启用|禁用'}))
    
    class Meta:
        model = CustomerSource
        fields = ['title', 'sort']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入来源名称'}),
            'sort': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '排序号'}),
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
    status = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'lay-skin': 'switch', 'lay-text': '启用|禁用'}))
    
    class Meta:
        model = CustomerGrade
        fields = ['title', 'sort']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入等级名称'}),
            'sort': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '排序号'}),
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
    status = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'lay-skin': 'switch', 'lay-text': '启用|禁用'}))
    
    class Meta:
        model = CustomerIntent
        fields = ['name', 'sort']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入意向名称'}),
            'sort': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '排序号'}),
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
    status = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'lay-skin': 'switch', 'lay-text': '启用|禁用'}))
    
    class Meta:
        model = CustomerField
        fields = ['name', 'field_name', 'field_type', 'options', 'is_required', 'is_unique', 'is_list_display', 'sort']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入字段名称'}),
            'field_name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入字段标识'}),
            'field_type': forms.Select(attrs={'class': 'layui-input'}),
            'options': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '选项值，每行一个', 'rows': 3}),
            'sort': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '排序号'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['status'].initial = self.instance.status

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.status = 1 if self.cleaned_data.get('status') else 0
        if commit:
            instance.save()
        return instance