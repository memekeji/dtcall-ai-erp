import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.template.loader import get_template


template_root = ROOT / 'templates'
common_partial = template_root / 'common' / '_right_popup_function.html'
production_partial = template_root / 'production' / '_right_popup_function.html'

common_source = common_partial.read_text(encoding='utf-8')
assert 'function openRightPopup(title, url, onClose)' in common_source

production_source = production_partial.read_text(encoding='utf-8')
assert 'common/_right_popup_function.html' in production_source

definition_locations = [
    path
    for path in template_root.rglob('*.html')
    if 'function openRightPopup' in path.read_text(encoding='utf-8')
]
assert definition_locations == [common_partial], definition_locations

for template_name in [
    'common/_right_popup_function.html',
    'production/_right_popup_function.html',
    'customer/abandoned_customer_list.html',
    'customer/follow_record_list.html',
    'customer/public_customer_list.html',
    'customer/customer_list.html',
    'oa/message/list.html',
    'oa/meeting/list.html',
]:
    get_template(template_name)

print('right popup template checks passed')
