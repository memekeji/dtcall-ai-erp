import os
import sys
import inspect
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.urls import resolve, reverse
from django.template.loader import get_template

from apps.contract import views


def assert_subclass(view_class, base_class):
    assert issubclass(view_class, base_class), f'{view_class.__name__} should inherit {base_class.__name__}'


for view_class in [
    views.ContractCategoryView,
    views.ProductCategoryView,
    views.ServiceCategoryView,
    views.SupplierView,
    views.PurchaseCategoryView,
    views.PurchaseItemView,
]:
    assert_subclass(view_class, views.BasicDataListView)
    assert view_class.template_name
    assert view_class.formatter

for view_class in [
    views.ProductAddView,
    views.ServicesAddView,
    views.ContractCategoryAddView,
    views.ProductCategoryAddView,
    views.ServiceCategoryAddView,
    views.SupplierAddView,
    views.PurchaseCategoryAddView,
    views.PurchaseItemAddView,
]:
    assert_subclass(view_class, views.BasicDataCreateView)
    assert view_class.form_class
    assert view_class.template_name

for view_class in [
    views.ProductDetailView,
    views.ServicesDetailView,
    views.ContractCategoryEditView,
    views.ProductCategoryEditView,
    views.ServiceCategoryEditView,
    views.SupplierEditView,
    views.PurchaseCategoryEditView,
    views.PurchaseItemEditView,
]:
    assert_subclass(view_class, views.BasicDataUpdateView)
    assert view_class.model
    assert view_class.form_class
    assert view_class.template_name

assert views.ProductAddView._save_form is not views.BasicDataCreateView._save_form

parent = SimpleNamespace(name='父级')
created_at = SimpleNamespace(strftime=lambda fmt: '2026-06-13 18:00:00')
category = SimpleNamespace(
    id=1,
    name='合同分类',
    code='HT',
    parent=parent,
    description='说明',
    template_path='/tmp/tpl.docx',
    sort_order=3,
    is_active=True,
    created_at=created_at,
)
assert views.ContractCategoryView.formatter(category) == {
    'id': 1,
    'name': '合同分类',
    'code': 'HT',
    'parent': '父级',
    'description': '说明',
    'template_path': '/tmp/tpl.docx',
    'sort_order': 3,
    'is_active': True,
    'created_at': '2026-06-13 18:00:00',
}

supplier = SimpleNamespace(
    id=2,
    name='供应商',
    code='SUP',
    contact_person='张三',
    contact_phone='13800000000',
    contact_email='a@example.com',
    address='上海',
    is_active=True,
    created_at=created_at,
)
assert views.SupplierView.search_fields == ['name', 'code', 'contact_person']
assert views.SupplierView.formatter(supplier)['contact'] == '张三'
assert views.SupplierView.formatter(supplier)['phone'] == '13800000000'

route_expectations = {
    'contract:product_list': views.ProductView,
    'contract:product_add': views.ProductAddView,
    'contract:product_edit': views.ProductDetailView,
    'contract:service_list': views.ServiceListView,
    'contract:service_add': views.ServiceListAddView,
    'contract:service_edit': views.ServiceListEditView,
    'contract:contract_category_list': views.ContractCategoryView,
    'contract:contract_category_add': views.ContractCategoryAddView,
    'contract:product_category_list': views.ProductCategoryView,
    'contract:service_category_list': views.ServiceCategoryView,
    'contract:supplier_add': views.SupplierAddView,
    'contract:purchase_item_edit': views.PurchaseItemEditView,
}

for route_name, view_class in route_expectations.items():
    if route_name.endswith('_edit'):
        path = reverse(route_name, kwargs={'id': 1})
    else:
        path = reverse(route_name)
    assert resolve(path).func.view_class is view_class

context = views.ContractCategoryView().get_context_data()
assert context['page_title'] == '合同分类管理'
assert context['list_url'] == reverse('contract:contract_category_datalist')
assert context['add_url'] == reverse('contract:contract_category_add')
assert context['edit_url'].endswith('/edit/{id}/')
assert context['delete_url'].endswith('/contract_category/delete/{id}/')

product_context = views.ProductView().get_context_data()
assert product_context['page_title'] == '产品管理'
assert product_context['list_url'] == reverse('contract:product_datalist')
assert product_context['add_url'] == reverse('contract:product_add')
assert product_context['edit_url'].endswith('/edit/{id}/')
assert product_context['delete_url'].endswith('/product/delete/{id}/')

service_context = views.ServicesView().get_context_data()
assert service_context['page_title'] == '服务管理'
assert service_context['list_url'] == reverse('contract:service_datalist')
assert service_context['add_url'] == reverse('contract:service_add')
assert service_context['edit_url'].endswith('/edit/{id}/')
assert service_context['delete_url'].endswith('/service/delete/{id}/')

product_data_source = inspect.getsource(views.ProductView.get_data_list)
assert "params.get('search') or params.get('keywords')" in product_data_source

for template_name in [
    'contract/product_list.html',
    'contract/service_list.html',
    'contract/contract_category_list.html',
    'contract/product_category_list.html',
    'contract/service_category_list.html',
    'contract/supplier_list.html',
    'contract/purchase_category_list.html',
    'contract/purchase_item_list.html',
]:
    get_template(template_name)

print('contract basic view checks passed')
