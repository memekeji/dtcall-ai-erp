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
    shipped_quantity = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    inventory_quantity = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    wip_quantity = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    inbound_quantity = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    prepared_quantity = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    manual_adjustment = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    predicted_quantity = forms.DecimalField(max_digits=14, decimal_places=2)
    avg_daily_demand = forms.DecimalField(max_digits=14, decimal_places=2)
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
    payload_json = forms.CharField(widget=forms.Textarea)


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


class SamplePickupForm(forms.Form):
    note = forms.CharField(required=False, widget=forms.Textarea)
