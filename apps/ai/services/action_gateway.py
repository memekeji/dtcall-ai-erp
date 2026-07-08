from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.action_contracts import AIActionRequest
from apps.ai.services.module_adapters.approval import ApprovalModuleAdapter
from apps.ai.services.module_adapters.customer import CustomerModuleAdapter
from apps.ai.services.module_adapters.disk import DiskModuleAdapter
from apps.ai.services.module_adapters.finance import FinanceModuleAdapter
from apps.ai.services.module_adapters.project import ProjectModuleAdapter
from apps.ai.services.module_adapters.order import OrderModuleAdapter
from apps.ai.services.module_adapters.contract import ContractModuleAdapter
from apps.ai.services.module_adapters.supplier import SupplierModuleAdapter
from apps.ai.services.module_adapters.product import ProductModuleAdapter
from apps.ai.services.module_adapters.task import TaskModuleAdapter
from apps.ai.services.module_adapters.workhour import WorkHourModuleAdapter
from apps.ai.services.module_adapters.notice import NoticeModuleAdapter
from apps.ai.services.module_adapters.schedule import ScheduleModuleAdapter
from apps.ai.services.module_adapters.message import MessageModuleAdapter
from apps.ai.services.module_adapters.meeting import MeetingModuleAdapter
from apps.ai.services.module_adapters.approval_flow import ApprovalFlowModuleAdapter
from apps.ai.services.module_adapters.production import ProductionModuleAdapter
from apps.ai.services.module_adapters.followup import FollowupModuleAdapter
from apps.ai.services.module_adapters.employee import EmployeeModuleAdapter
from apps.ai.services.module_adapters.department import DepartmentModuleAdapter
from apps.ai.services.module_adapters.inventory import InventoryModuleAdapter
from apps.ai.services.module_adapters.document import DocumentModuleAdapter
from apps.ai.services.module_adapters.stock import StockDocumentModuleAdapter
from apps.ai.services.module_adapters.warehouse import WarehouseModuleAdapter
from apps.ai.services.module_adapters.project_metadata import ProjectMetadataModuleAdapter
from apps.ai.services.module_adapters.position import PositionModuleAdapter
from apps.ai.services.module_adapters.enterprise import EnterpriseModuleAdapter
from apps.ai.services.module_adapters.personal_workspace import PersonalWorkspaceModuleAdapter
from apps.ai.services.module_adapters.approval_task import ApprovalTaskModuleAdapter
from apps.ai.services.module_adapters.contact import ContactModuleAdapter
from apps.ai.services.module_adapters.production_resource import ProductionResourceModuleAdapter


class AIActionGateway:
    RESOURCE_ALIASES = {
        'disk_folder': 'disk',
        'disk_share': 'disk',
        'finance_expense': 'finance',
        'finance_income': 'finance',
        'expense': 'finance',
        'income': 'finance',
        'finance_invoice': 'finance',
        'invoice': 'finance',
        'payment': 'finance',
        'production_plan': 'production',
        'project_document': 'project_document',
        'project_stage': 'project_stage',
        'project_category': 'project_category',
        'work_type': 'work_type',
    }

    def __init__(self):
        self._registry: dict[str, AIBaseModuleAdapter] = {}
        self.register(CustomerModuleAdapter())
        self.register(ApprovalModuleAdapter())
        self.register(DiskModuleAdapter())
        self.register(FinanceModuleAdapter())
        self.register(ProjectModuleAdapter())
        self.register(OrderModuleAdapter())
        self.register(ContractModuleAdapter())
        self.register(SupplierModuleAdapter())
        self.register(ProductModuleAdapter())
        self.register(TaskModuleAdapter())
        self.register(WorkHourModuleAdapter())
        self.register(NoticeModuleAdapter())
        self.register(ScheduleModuleAdapter())
        self.register(MessageModuleAdapter())
        self.register(MeetingModuleAdapter())
        self.register(ApprovalFlowModuleAdapter())
        self.register(ApprovalTaskModuleAdapter())
        self.register(ProductionModuleAdapter())
        self.register(ContactModuleAdapter())
        self.register(ProductionResourceModuleAdapter('production_task'))
        self.register(ProductionResourceModuleAdapter('production_equipment'))
        self.register(ProductionResourceModuleAdapter('production_procedure'))
        self.register(FollowupModuleAdapter())
        self.register(EmployeeModuleAdapter())
        self.register(DepartmentModuleAdapter())
        self.register(InventoryModuleAdapter())
        self.register(DocumentModuleAdapter())
        self.register(StockDocumentModuleAdapter('stockin'))
        self.register(StockDocumentModuleAdapter('stockout'))
        self.register(WarehouseModuleAdapter())
        self.register(ProjectMetadataModuleAdapter('project_document'))
        self.register(ProjectMetadataModuleAdapter('project_stage'))
        self.register(ProjectMetadataModuleAdapter('project_category'))
        self.register(ProjectMetadataModuleAdapter('work_type'))
        self.register(PositionModuleAdapter())
        self.register(EnterpriseModuleAdapter())
        self.register(PersonalWorkspaceModuleAdapter('work_record'))
        self.register(PersonalWorkspaceModuleAdapter('work_report'))
        self.register(PersonalWorkspaceModuleAdapter('personal_note'))
        self.register(PersonalWorkspaceModuleAdapter('personal_task'))
        self.register(PersonalWorkspaceModuleAdapter('personal_contact'))

    def register(self, adapter: AIBaseModuleAdapter):
        self._registry[adapter.resource] = adapter

    def get_adapter(self, resource: str) -> AIBaseModuleAdapter:
        resource = self.RESOURCE_ALIASES.get(resource, resource)
        try:
            return self._registry[resource]
        except KeyError as exc:
            raise KeyError(f'No AI module adapter registered for resource: {resource}') from exc

    def execute_confirmed_action(self, operation, user):
        adapter = self.get_adapter(operation.resource_type)
        normalized_resource = self.RESOURCE_ALIASES.get(operation.resource_type, operation.resource_type)
        action = AIActionRequest(
            resource=normalized_resource,
            operation=operation.operation_type,
            object_ids=(operation.confirmed_payload or {}).get('object_ids', []),
            changes=(operation.confirmed_payload or {}).get('changes', {}),
            filters=(operation.confirmed_payload or {}).get('filters', {}),
            context=(operation.confirmed_payload or {}).get('context', {}),
        )
        return adapter.execute(action, user, operation=operation)
