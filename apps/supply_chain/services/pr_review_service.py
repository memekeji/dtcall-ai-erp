def _matches_condition(payload, condition_json):
    condition_json = condition_json or {}
    for key, expected_value in condition_json.items():
        if payload.get(key) != expected_value:
            return False
    return True


def _build_status(recommended_action):
    if not recommended_action:
        return 'pending'
    if recommended_action == 'manual_review':
        return 'manual_review'
    if recommended_action in {'approve', 'urgent_approve', 'filter'}:
        return 'rule_matched'
    return 'pending'


def evaluate_pr_payload(payload, rules):
    payload = payload or {}
    matched_rules = [
        rule for rule in (rules or [])
        if _matches_condition(payload, rule.get('condition_json'))
    ]
    matched_rules.sort(key=lambda rule: (rule.get('priority', 100), rule.get('code', '')))

    top_rule = matched_rules[0] if matched_rules else None
    recommended_action = (top_rule or {}).get('recommended_action', '')
    is_abnormal = recommended_action in {'manual_review', 'filter'}

    return {
        'matched_rules': matched_rules,
        'recommended_action': recommended_action,
        'is_abnormal': is_abnormal,
        'status': _build_status(recommended_action),
        'evidence': {
            'payload': payload,
            'matched_rule_codes': [rule.get('code') for rule in matched_rules],
        },
    }
