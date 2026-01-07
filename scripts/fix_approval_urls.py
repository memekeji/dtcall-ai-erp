import os
from pathlib import Path

templates_dir = Path('templates/Approval')
for html_file in templates_dir.glob('*.html'):
    content = html_file.read_text(encoding='utf-8')
    original = content
    content = content.replace("basedata:batch_create_steps", "approval:batch_create_steps")
    content = content.replace("basedata:approval_flow_steps", "approval:approval_flow_steps")
    content = content.replace("basedata:approval_step_add", "approval:approval_step_add")
    if content != original:
        html_file.write_text(content, encoding='utf-8')
        print(f'Fixed: {html_file.name}')
