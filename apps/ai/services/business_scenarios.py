from typing import Any


TASK_TYPE_BY_SCENARIO = {
    'approval_assessment': 'expense_audit',
    'expense_review': 'expense_audit',
    'expense_anomaly_detection': 'expense_audit',
    'customer_classification': 'customer_analysis',
    'customer_profile': 'customer_analysis',
    'meeting_summary': 'meeting_minutes',
    'meeting_action_items': 'meeting_minutes',
    'oa_meeting_minutes_generation': 'meeting_minutes',
    'oa_meeting_audio_minutes': 'meeting_minutes',
    'personal_meeting_minutes_generation': 'meeting_minutes',
    'project_risk_prediction': 'project_risk',
    'project_progress_analysis': 'project_risk',
    'disk_file_analysis': 'document_summary',
    'contract_risk_analysis': 'text_generation',
    'contract_term_extraction': 'text_generation',
    'message_assistant': 'text_generation',
    'inventory_forecast': 'other',
    'production_optimization': 'other',
    'task_estimation': 'other',
}


def get_business_ai_task_type(scenario: Any) -> str:
    return TASK_TYPE_BY_SCENARIO.get(str(scenario or 'general'), 'other')


def build_business_ai_task_id(scenario: Any, source_refs: Any) -> str:
    scenario_text = str(scenario or 'general')
    if isinstance(source_refs, list) and source_refs:
        first_ref = source_refs[0]
        if isinstance(first_ref, dict):
            ref_type = first_ref.get('type') or 'source'
            ref_id = first_ref.get('id') or 'unknown'
            return f'{scenario_text}:{ref_type}:{ref_id}'
    return scenario_text
