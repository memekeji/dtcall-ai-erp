from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

home_base = (ROOT / 'templates' / 'home' / 'base.html').read_text(encoding='utf-8')
include_common = (ROOT / 'templates' / 'include' / 'common.html').read_text(encoding='utf-8')
include_popup = (ROOT / 'templates' / 'include' / 'popup.html').read_text(encoding='utf-8')
iframe_base = (ROOT / 'templates' / 'home' / 'iframe_base.html').read_text(encoding='utf-8')
common_js = (ROOT / 'static' / 'js' / 'common.js').read_text(encoding='utf-8')
contract_csrf_templates = [
    ROOT / 'templates' / 'contract' / 'purchase_list.html',
    ROOT / 'templates' / 'contract' / 'archive_list.html',
    ROOT / 'templates' / 'contract' / 'sales_list.html',
    ROOT / 'templates' / 'contract' / 'view.html',
]
home_base_utility_templates = [
    ROOT / 'templates' / 'ai' / 'chat.html',
    ROOT / 'templates' / 'Approval' / 'approval_flow_steps.html',
    ROOT / 'templates' / 'Approval' / 'my_approval_list.html',
    ROOT / 'templates' / 'permission' / 'role_permission.html',
    ROOT / 'templates' / 'personal' / 'minutes' / 'preview.html',
]
iframe_utility_templates = [
    ROOT / 'templates' / 'ai' / 'workflow_designer.html',
    ROOT / 'templates' / 'message' / 'message_center.html',
    ROOT / 'templates' / 'message' / 'message_preference.html',
]
standalone_csrf_templates = [
    ROOT / 'templates' / 'Approval' / 'approval_detail.html',
    ROOT / 'templates' / 'Approval' / 'process_approval.html',
    ROOT / 'templates' / 'project' / 'detail.html',
]

assert "static 'js/common.js'" in home_base
assert "static 'js/common.js'" in include_common
assert "static 'js/common.js'" in include_popup
assert "static 'js/common.js'" in iframe_base
assert 'function getCookie(name)' in common_js
assert 'getCookie,' in common_js
assert "return getCookie('csrftoken');" in common_js

for template_path in contract_csrf_templates:
    source = template_path.read_text(encoding='utf-8')
    assert "static 'js/common.js'" in source or template_path.name == 'view.html'
    assert 'function getCsrfToken' not in source
    assert 'window.DTCallCommon.getCsrfToken' in source

for template_path in home_base_utility_templates:
    source = template_path.read_text(encoding='utf-8')
    assert 'function getCookie' not in source
    assert 'function getCsrfToken' not in source
    assert 'function escapeHtml' not in source
    assert 'DTCallCommon' in source

for template_path in iframe_utility_templates:
    source = template_path.read_text(encoding='utf-8')
    assert 'function getCookie' not in source
    assert 'function getCsrfToken' not in source
    assert 'function escapeHtml' not in source
    assert 'DTCallCommon' in source

for template_path in standalone_csrf_templates:
    source = template_path.read_text(encoding='utf-8')
    assert "static 'js/common.js'" in source
    assert 'function getCsrfToken' not in source
    assert 'window.DTCallCommon.getCsrfToken' in source

allowed_template_function_files = {
    ROOT / 'templates' / 'disk' / 'preview.html',
}
for template_path in (ROOT / 'templates').rglob('*.html'):
    source = template_path.read_text(encoding='utf-8')
    matches = re.findall(r'function\s+(getCookie|getCsrfToken|escapeHtml|getFileExtension|getMimeType)\s*\(', source)
    if template_path in allowed_template_function_files:
        continue
    assert not matches, f'{template_path}: {matches}'

print('common asset checks passed')
