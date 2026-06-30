from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.action_contracts import AIActionRequest
from apps.ai.services.module_adapters.approval import ApprovalModuleAdapter
from apps.ai.services.module_adapters.customer import CustomerModuleAdapter
from apps.ai.services.module_adapters.disk import DiskModuleAdapter
from apps.ai.services.module_adapters.finance import FinanceModuleAdapter
from apps.ai.services.module_adapters.project import ProjectModuleAdapter


class AIActionGateway:
    def __init__(self):
        self._registry: dict[str, AIBaseModuleAdapter] = {}
        self.register(CustomerModuleAdapter())
        self.register(ApprovalModuleAdapter())
        self.register(DiskModuleAdapter())
        self.register(FinanceModuleAdapter())
        self.register(ProjectModuleAdapter())

    def register(self, adapter: AIBaseModuleAdapter):
        self._registry[adapter.resource] = adapter

    def get_adapter(self, resource: str) -> AIBaseModuleAdapter:
        try:
            return self._registry[resource]
        except KeyError as exc:
            raise KeyError(f'No AI module adapter registered for resource: {resource}') from exc

    def execute_confirmed_action(self, operation, user):
        adapter = self.get_adapter(operation.resource_type)
        action = AIActionRequest(
            resource=operation.resource_type,
            operation=operation.operation_type,
            object_ids=(operation.confirmed_payload or {}).get('object_ids', []),
            changes=(operation.confirmed_payload or {}).get('changes', {}),
            filters=(operation.confirmed_payload or {}).get('filters', {}),
            context=(operation.confirmed_payload or {}).get('context', {}),
        )
        return adapter.execute(action, user, operation=operation)
