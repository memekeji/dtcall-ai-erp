from .models import Region, Enterprise


class BasedataMixin:
    @classmethod
    def get_basedata_model_map(cls):
        return {
            'region': 'Region',
            'enterprise': 'Enterprise',
            'reward_punishment': 'RewardPunishmentType',
            'care_type': 'CareType',
            'duty': 'Duty',
            'job_level': 'JobLevel',
            'asset_category': 'AssetCategory',
            'asset_brand': 'AssetBrand',
            'asset_unit': 'AssetUnit',
            'car_fee_type': 'CarFeeType',
            'notice_type': 'NoticeType',
            'customer_field': 'CustomerField',
            'follow_field': 'FollowField',
            'order_field': 'OrderField',
            'contract_category': 'ContractCategory',
            'product_category': 'ProductCategory',
            'service_category': 'ServiceCategory',
            'product': 'Product',
            'service': 'Service',
            'supplier': 'Supplier',
            'purchase_category': 'PurchaseCategory',
            'purchase_item': 'PurchaseItem',
            'project_stage': 'ProjectStage',
            'project_category': 'ProjectCategory',
            'work_type': 'WorkType',
        }

    @classmethod
    def get_model_by_name(cls, name):
        from apps.hr.models import RewardPunishmentType, CareType, Duty, JobLevel
        from apps.admin.models import AssetCategory, AssetBrand, AssetUnit, CarFeeType, NoticeType
        from apps.customer.models import CustomerField, FollowField, OrderField
        from apps.contract.models import ContractCategory, ProductCategory, ServiceCategory, Product, Service, Supplier, PurchaseCategory, PurchaseItem
        from apps.project.models import ProjectStage, ProjectCategory, WorkType

        model_map = {
            'region': Region,
            'enterprise': Enterprise,
            'reward_punishment': RewardPunishmentType,
            'care_type': CareType,
            'duty': Duty,
            'job_level': JobLevel,
            'asset_category': AssetCategory,
            'asset_brand': AssetBrand,
            'asset_unit': AssetUnit,
            'car_fee_type': CarFeeType,
            'notice_type': NoticeType,
            'customer_field': CustomerField,
            'follow_field': FollowField,
            'order_field': OrderField,
            'contract_category': ContractCategory,
            'product_category': ProductCategory,
            'service_category': ServiceCategory,
            'product': Product,
            'service': Service,
            'supplier': Supplier,
            'purchase_category': PurchaseCategory,
            'purchase_item': PurchaseItem,
            'project_stage': ProjectStage,
            'project_category': ProjectCategory,
            'work_type': WorkType,
        }
        return model_map.get(name)
