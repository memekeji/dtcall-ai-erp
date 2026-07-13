import json

from pathlib import Path

from django import forms

from .models import (
    DemandForecastPlan,
    OutsourceIssueOrder,
    PRReviewTask,
    PriceReviewOrder,
    SampleRequest,
)


class _BaseStyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'layui-input')
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault('class', 'layui-textarea')
                widget.attrs.setdefault('rows', 3)
            else:
                widget.attrs.setdefault('class', 'layui-input')


class DemandForecastPlanForm(_BaseStyledModelForm):
    class Meta:
        model = DemandForecastPlan
        fields = [
            'name',
            'product',
            'period_start',
            'period_end',
            'version',
            'summary',
        ]
        widgets = {
            'period_start': forms.DateInput(attrs={'type': 'date'}),
            'period_end': forms.DateInput(attrs={'type': 'date'}),
        }


class ForecastRunForm(forms.Form):
    manual_adjustment = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    actual_quantity = forms.DecimalField(max_digits=14, decimal_places=2, required=False)


class ForecastReviewForm(forms.Form):
    DECISION_CHOICES = (
        ('approve', '通过'),
        ('reject', '驳回'),
    )

    decision = forms.ChoiceField(choices=DECISION_CHOICES)
    comment = forms.CharField(required=False, widget=forms.Textarea)


class OutsourceIssueOrderForm(_BaseStyledModelForm):
    class Meta:
        model = OutsourceIssueOrder
        fields = [
            'product',
            'supplier',
            'production_plan',
            'quantity',
        ]


class OutsourceStatusForm(forms.Form):
    action = forms.ChoiceField(choices=(
        ('start_picking', '开始备料'),
        ('mark_issued', '确认发料'),
        ('notify_pickup', '通知领料'),
        ('close_order', '关闭订单'),
    ))


class PRReviewTaskForm(_BaseStyledModelForm):
    class Meta:
        model = PRReviewTask
        fields = [
            'title',
            'source_type',
            'source_code',
        ]


class PRReviewEvaluateForm(forms.Form):
    SCENARIO_CHOICES = (
        ('normal', '常规需求'),
        ('urgent_shortage', '紧急缺料'),
        ('tail_order', '尾数订单'),
        ('intercompany_tail_order', '公司间尾数订单'),
        ('outsource_tail_order', '委外尾数订单'),
        ('rework_order', '异常工单 / 返工单'),
        ('npi_trial', 'NPI 试产需求'),
        ('custom', '自定义组合'),
    )
    ORDER_TYPE_CHOICES = (
        ('', '未区分'),
        ('customer', '客户订单'),
        ('intercompany', '公司间'),
        ('outsource', '委外'),
        ('npi', '试产'),
        ('internal', '内部需求'),
    )

    payload_json = forms.CharField(widget=forms.Textarea, required=False)
    scenario = forms.ChoiceField(choices=SCENARIO_CHOICES, required=False, initial='normal')
    order_type = forms.ChoiceField(choices=ORDER_TYPE_CHOICES, required=False)
    is_urgent = forms.BooleanField(required=False)
    lt_shortage = forms.BooleanField(required=False)
    tail_order = forms.BooleanField(required=False)
    intercompany_tail_order = forms.BooleanField(required=False)
    outsource_tail_order = forms.BooleanField(required=False)
    rework_order = forms.BooleanField(required=False)
    npi_trial = forms.BooleanField(required=False)

    def clean_payload_json(self):
        value = (self.cleaned_data.get('payload_json') or '').strip()
        if not value:
            return ''
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError('JSON 格式不正确') from exc
        if not isinstance(parsed, dict):
            raise forms.ValidationError('规则载荷必须是 JSON 对象')
        return value

    def build_payload(self):
        cleaned = getattr(self, 'cleaned_data', {})
        raw_json = cleaned.get('payload_json')
        if raw_json:
            return json.loads(raw_json)

        payload = {
            'is_urgent': bool(cleaned.get('is_urgent')),
            'lt_shortage': bool(cleaned.get('lt_shortage')),
            'tail_order': bool(cleaned.get('tail_order')),
            'intercompany_tail_order': bool(cleaned.get('intercompany_tail_order')),
            'outsource_tail_order': bool(cleaned.get('outsource_tail_order')),
            'rework_order': bool(cleaned.get('rework_order')),
            'npi_trial': bool(cleaned.get('npi_trial')),
        }
        order_type = cleaned.get('order_type')
        if order_type:
            payload['order_type'] = order_type

        scenario = cleaned.get('scenario') or 'normal'
        scenario_map = {
            'normal': {
                'is_urgent': False,
                'lt_shortage': False,
                'tail_order': False,
                'intercompany_tail_order': False,
                'outsource_tail_order': False,
                'rework_order': False,
                'npi_trial': False,
            },
            'urgent_shortage': {
                'is_urgent': True,
                'lt_shortage': True,
            },
            'tail_order': {
                'tail_order': True,
            },
            'intercompany_tail_order': {
                'intercompany_tail_order': True,
                'tail_order': True,
                'order_type': 'intercompany',
            },
            'outsource_tail_order': {
                'outsource_tail_order': True,
                'tail_order': True,
                'order_type': 'outsource',
            },
            'rework_order': {
                'rework_order': True,
            },
            'npi_trial': {
                'npi_trial': True,
                'is_urgent': True,
                'order_type': 'npi',
            },
        }
        for key, value in scenario_map.get(scenario, {}).items():
            payload[key] = value
        return payload


class PRQuickApproveForm(forms.Form):
    note = forms.CharField(required=False, widget=forms.Textarea)


class PRBatchApproveForm(forms.Form):
    note = forms.CharField(required=False, widget=forms.Textarea)


class PriceReviewOrderForm(_BaseStyledModelForm):
    class Meta:
        model = PriceReviewOrder
        fields = [
            'inventory_item',
            'supplier',
            'quoted_price',
        ]


class PriceReviewAnalyzeForm(forms.Form):
    material_cost = forms.DecimalField(max_digits=14, decimal_places=4, required=False)
    process_cost = forms.DecimalField(max_digits=14, decimal_places=4, required=False)
    labor_cost = forms.DecimalField(max_digits=14, decimal_places=4, required=False)
    loss_cost = forms.DecimalField(max_digits=14, decimal_places=4, required=False)
    package_cost = forms.DecimalField(max_digits=14, decimal_places=4, required=False)
    logistics_cost = forms.DecimalField(max_digits=14, decimal_places=4, required=False)
    profit_cost = forms.DecimalField(max_digits=14, decimal_places=4, required=False)
    historical_prices = forms.CharField(required=False, help_text='使用逗号分隔')
    market_price = forms.DecimalField(max_digits=14, decimal_places=4, required=False)
    target_price = forms.DecimalField(max_digits=14, decimal_places=4, required=False)


class PriceReviewDocumentForm(forms.Form):
    document_file = forms.FileField(required=False)
    raw_text = forms.CharField(required=False, widget=forms.Textarea)

    def clean_document_file(self):
        document_file = self.cleaned_data.get('document_file')
        if document_file is None:
            return None
        allowed_suffixes = {'.pdf', '.doc', '.docx', '.txt', '.png', '.jpg', '.jpeg'}
        if Path(document_file.name).suffix.lower() not in allowed_suffixes:
            raise forms.ValidationError('仅支持 PDF、Word、TXT、PNG、JPG 规格书文件')
        if document_file.size > 15 * 1024 * 1024:
            raise forms.ValidationError('规格书文件不能超过15MB')
        return document_file

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('document_file') and not cleaned_data.get('raw_text'):
            raise forms.ValidationError('请上传规格书文件或粘贴解析文本')
        return cleaned_data


class SampleRequestForm(_BaseStyledModelForm):
    class Meta:
        model = SampleRequest
        fields = [
            'material_name',
            'specification',
            'supplier',
            'engineer',
            'required_date',
            'quantity',
            'remark',
        ]
        widgets = {
            'required_date': forms.DateInput(attrs={'type': 'date'}),
        }


class SampleReceiptForm(forms.Form):
    received_quantity = forms.DecimalField(max_digits=14, decimal_places=2)
    location = forms.CharField(max_length=100)
    photo_file = forms.FileField(required=False)

    def clean_photo_file(self):
        photo_file = self.cleaned_data.get('photo_file')
        if photo_file is None:
            return None
        if Path(photo_file.name).suffix.lower() not in {'.png', '.jpg', '.jpeg'}:
            raise forms.ValidationError('到货照片仅支持 PNG、JPG 格式')
        if photo_file.size > 5 * 1024 * 1024:
            raise forms.ValidationError('到货照片不能超过5MB')
        return photo_file


class SamplePickupForm(forms.Form):
    note = forms.CharField(required=False, widget=forms.Textarea)
