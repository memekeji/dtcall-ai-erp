from django.urls import path
from django.views.generic import RedirectView
from . import views
from .ai_views import ai_contract_risk_analysis, ai_contract_term_extraction

from .views import (
    ContractView,
    ArchiveListView,
    StopListView,
    VoidListView,
    ProductView,
    ProductAddView,
    ProductDetailView,
    ServicesView,
    ServicesAddView,
    ServicesDetailView,
    ContractBasicDataDeleteView,
    PurchaseDetailView,
    ContractAddView,
    ContractDetailView,
    ContractUpdateView,
    ContractDeleteView,
    ContractExportView,
    PurchaseUpdateView,
    PurchaseDeleteView,
    PurchaseExportView,
    ContractArchiveView,
    ContractTerminateView,
    ContractCancelView,
    ContractCategoryView,
    ContractCategoryAddView,
    ContractCategoryEditView,
    ProductCategoryView,
    ProductCategoryAddView,
    ProductCategoryEditView,
    ServiceCategoryView,
    ServiceCategoryAddView,
    ServiceCategoryEditView,
    SupplierView,
    SupplierAddView,
    SupplierEditView,
    PurchaseCategoryView,
    PurchaseCategoryAddView,
    PurchaseCategoryEditView,
    PurchaseItemView,
    PurchaseItemAddView,
    PurchaseItemEditView,
    ContractCategoryChildrenView,
    ServiceListView,
    ServiceListAddView,
    ServiceListEditView,
)

app_name = 'contract'

urlpatterns = [
    # AI 路由
    path('api/ai/risk-analysis/<int:contract_id>/', ai_contract_risk_analysis, name='ai_contract_risk_analysis'),
    path('api/ai/term-extraction/<int:contract_id>/', ai_contract_term_extraction, name='ai_contract_term_extraction'),

    # 原有路由保持兼容 - 移除会导致循环的重定向
    # 产品相关路由
    path('product/', ProductView.as_view(), name='product_list'),
    path(
        'product/datalist/',
        ProductView.as_view(),
        name='product_datalist'),
    path('product/add/', ProductAddView.as_view(), name='product_add'),
    path(
        'product/edit/<int:id>/',
        ProductDetailView.as_view(),
        name='product_edit'),
    path(
        'product/view/<int:id>/',
        ProductDetailView.as_view(),
        name='product_detail'),

    # 服务相关路由
    path('services/', ServicesView.as_view(), name='contract_services'),
    path(
        'services/datalist/',
        ServicesView.as_view(),
        name='contract_services_datalist'),
    path(
        'services/add/',
        ServicesAddView.as_view(),
        name='contract_services_add'),
    path(
        'services/view/<int:id>/',
        ServicesDetailView.as_view(),
        name='contract_services_detail'),
    path(
        'services/edit/<int:id>/',
        ServicesDetailView.as_view(),
        name='contract_service_edit'),

    # 服务列表路由
    path('service/', ServiceListView.as_view(), name='service_list'),
    path(
        'service/datalist/',
        ServiceListView.as_view(),
        name='service_datalist'),
    path('service/add/', ServiceListAddView.as_view(), name='service_add'),
    path(
        'service/edit/<int:id>/',
        ServiceListEditView.as_view(),
        name='service_edit'),

    # 合同分类路由
    path(
        'category/',
        ContractCategoryView.as_view(),
        name='contract_category_list'),
    path(
        'category/datalist/',
        ContractCategoryView.as_view(),
        name='contract_category_datalist'),
    path(
        'category/add/',
        ContractCategoryAddView.as_view(),
        name='contract_category_add'),
    path(
        'category/edit/<int:id>/',
        ContractCategoryEditView.as_view(),
        name='contract_category_edit'),
    path(
        'category/children/',
        ContractCategoryChildrenView.as_view(),
        name='contract_category_children'),
    path(
        'category/children/<int:parent_id>/',
        ContractCategoryChildrenView.as_view(),
        name='contract_category_children_by_parent'),

    # 产品分类路由
    path(
        'productcategory/',
        ProductCategoryView.as_view(),
        name='product_category_list'),
    path(
        'productcategory/datalist/',
        ProductCategoryView.as_view(),
        name='product_category_datalist'),
    path(
        'productcategory/add/',
        ProductCategoryAddView.as_view(),
        name='product_category_add'),
    path(
        'productcategory/edit/<int:id>/',
        ProductCategoryEditView.as_view(),
        name='product_category_edit'),

    # 服务分类路由
    path(
        'servicecategory/',
        ServiceCategoryView.as_view(),
        name='service_category_list'),
    path(
        'servicecategory/datalist/',
        ServiceCategoryView.as_view(),
        name='service_category_datalist'),
    path(
        'servicecategory/add/',
        ServiceCategoryAddView.as_view(),
        name='service_category_add'),
    path(
        'servicecategory/edit/<int:id>/',
        ServiceCategoryEditView.as_view(),
        name='service_category_edit'),

    # 供应商路由
    path('supplier/', SupplierView.as_view(), name='supplier_list'),
    path(
        'supplier/datalist/',
        SupplierView.as_view(),
        name='supplier_datalist'),
    path('supplier/add/', SupplierAddView.as_view(), name='supplier_add'),
    path(
        'supplier/edit/<int:id>/',
        SupplierEditView.as_view(),
        name='supplier_edit'),

    # 采购分类路由
    path(
        'purchasecategory/',
        PurchaseCategoryView.as_view(),
        name='purchase_category_list'),
    path(
        'purchasecategory/datalist/',
        PurchaseCategoryView.as_view(),
        name='purchase_category_datalist'),
    path(
        'purchasecategory/add/',
        PurchaseCategoryAddView.as_view(),
        name='purchase_category_add'),
    path('purchasecategory/edit/<int:id>/',
         PurchaseCategoryEditView.as_view(),
         name='purchase_category_edit'),

    # 采购项目路由
    path(
        'purchaseitem/',
        PurchaseItemView.as_view(),
        name='purchase_item_list'),
    path(
        'purchaseitem/datalist/',
        PurchaseItemView.as_view(),
        name='purchase_item_datalist'),
    path(
        'purchaseitem/add/',
        PurchaseItemAddView.as_view(),
        name='purchase_item_add'),
    path(
        'purchaseitem/edit/<int:id>/',
        PurchaseItemEditView.as_view(),
        name='purchase_item_edit'),

    # 销售合同路由
    path(
        '<str:model_name>/delete/<int:id>/',
        ContractBasicDataDeleteView.as_view(),
        name='basic_data_delete'),

    path('sales/', ContractView.as_view(), name='contract_sales'),
    path(
        'sales/datalist/',
        ContractView.as_view(),
        name='contract_sales_datalist'),

    # 采购合同路由
    path('purchase/', views.PurchaseView.as_view(), name='contract_purchase'),
    path(
        'purchase/datalist/',
        views.PurchaseView.as_view(),
        name='contract_purchase_datalist'),
    path(
        'purchase/add/',
        views.PurchaseAddView.as_view(),
        name='contract_purchase_add'),
    path('purchase/view/<int:id>/',
         views.PurchaseDetailView.as_view(),
         name='contract_purchase_detail'),

    # 合同归档路由
    path('archive/', ArchiveListView.as_view(), name='contract_archive'),
    path(
        'archive/datalist/',
        ArchiveListView.as_view(),
        name='contract_archive_datalist'),
    path(
        'archive/export/',
        ContractExportView.as_view(),
        {'export_type': 'archive'},
        name='contract_archive_export'),

    # 合同终止路由
    path('terminate/', StopListView.as_view(), name='contract_terminate'),
    path(
        'terminate/datalist/',
        StopListView.as_view(),
        name='contract_terminate_datalist'),
    path(
        'terminate/export/',
        ContractExportView.as_view(),
        {'export_type': 'terminate'},
        name='contract_terminate_export'),

    # 合同作废路由
    path('cancel/', VoidListView.as_view(), name='contract_cancel'),
    path(
        'cancel/datalist/',
        VoidListView.as_view(),
        name='contract_cancel_datalist'),
    path(
        'cancel/export/',
        ContractExportView.as_view(),
        {'export_type': 'cancel'},
        name='contract_cancel_export'),

    # 合同创建路由
    path('create/', ContractAddView.as_view(), name='contract_create'),
    path('sales/add/', ContractAddView.as_view(), name='contract_sales_add'),

    # 合同详情路由
    path(
        'sales/view/<int:id>/',
        ContractDetailView.as_view(),
        name='contract_sales_detail'),
    path('sales/update/<int:id>/',
         ContractUpdateView.as_view(),
         name='contract_sales_update'),
    path(
        'sales/del/',
        ContractDeleteView.as_view(),
        name='contract_sales_delete'),
    path(
        'sales/export/',
        ContractExportView.as_view(),
        {'export_type': 'sales'},
        name='contract_sales_export'),

    # 采购合同详情路由
    path(
        'purchase/edit/<int:id>/',
        PurchaseDetailView.as_view(),
        name='contract_purchase_edit'),
    path(
        'purchase/update/<int:id>/',
        PurchaseUpdateView.as_view(),
        name='contract_purchase_update'),
    path(
        'purchase/del/',
        PurchaseDeleteView.as_view(),
        name='contract_purchase_delete'),
    path(
        'purchase/export/',
        PurchaseExportView.as_view(),
        name='contract_purchase_export'),

    # 合同操作路由
    path(
        'archive/action/',
        ContractArchiveView.as_view(),
        {'action': 'archive'},
        name='contract_archive_action'),
    path(
        'archive/unarchive/',
        ContractArchiveView.as_view(),
        {'action': 'unarchive'},
        name='contract_unarchive'),
    path(
        'terminate/action/',
        ContractTerminateView.as_view(),
        name='contract_terminate_action'),
    path(
        'cancel/action/',
        ContractCancelView.as_view(),
        name='contract_cancel_action'),

    # 原有路由保持兼容
    path(
        'datalist/',
        RedirectView.as_view(url='/contract/sales/datalist/', permanent=True),
        name='contract_list'),
    path(
        'archivelist/',
        ArchiveListView.as_view(),
        name='contract_archive_list'),
    path('stoplist/', StopListView.as_view(), name='contract_stop_list'),
    path('voidlist/', VoidListView.as_view(), name='contract_void_list'),
    path(
        'view/<int:id>/',
        ContractDetailView.as_view(),
        name='contract_detail'),
    path(
        'update/<int:id>/',
        ContractUpdateView.as_view(),
        name='contract_update'),
    path('del/', ContractDeleteView.as_view(), name='contract_delete'),
]
