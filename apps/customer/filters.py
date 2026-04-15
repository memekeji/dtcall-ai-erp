from django_filters import rest_framework as filters
from apps.customer.models import Customer


class CustomerFilter(filters.FilterSet):
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    province = filters.CharFilter(
        field_name='province',
        lookup_expr='icontains')
    city = filters.CharFilter(field_name='city', lookup_expr='icontains')
    customer_source = filters.NumberFilter(field_name='customer_source')
    grade_id = filters.NumberFilter(field_name='grade_id')
    industry_id = filters.NumberFilter(field_name='industry_id')
    create_time_start = filters.DateTimeFilter(
        field_name='create_time', lookup_expr='gte')
    create_time_end = filters.DateTimeFilter(
        field_name='create_time', lookup_expr='lte')

    class Meta:
        model = Customer
        fields = [
            'name', 'province', 'city',
            'customer_source', 'grade_id', 'industry_id',
            'create_time_start', 'create_time_end'
        ]
