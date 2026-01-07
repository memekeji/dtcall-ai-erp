from rest_framework.routers import DefaultRouter
from .views import (
    ContractCategoryViewSet, ProductCategoryViewSet, ServiceCategoryViewSet,
    ProductViewSet, ServiceViewSet, SupplierViewSet,
    PurchaseCategoryViewSet, PurchaseItemViewSet
)

router = DefaultRouter()

router.register(r'contract/categories', ContractCategoryViewSet, basename='contract-category')
router.register(r'product/categories', ProductCategoryViewSet, basename='product-category')
router.register(r'service/categories', ServiceCategoryViewSet, basename='service-category')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'purchase/categories', PurchaseCategoryViewSet, basename='purchase-category')
router.register(r'purchase/items', PurchaseItemViewSet, basename='purchase-item')

urlpatterns = router.urls
