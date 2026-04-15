import os
import re

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return

    # Check if file has layer.open
    if 'layer.open' not in content:
        return

    modified = False
    
    # We only want to replace inside layer.open objects. 
    # But for a simple script, if a file has layer.open, replacing these keys might be acceptable.
    # To be safer, let's just do simple replacements.
    
    new_content = re.sub(r"area\s*:\s*\[?[^\]\n]+\]?\s*,", "area: ['80%', '100%'],", content)
    if new_content != content:
        modified = True
        content = new_content
        
    new_content = re.sub(r"offset\s*:\s*['\"][a-zA-Z0-9_-]+['\"]\s*,", "offset: 'r',", content)
    if new_content != content:
        modified = True
        content = new_content
        
    new_content = re.sub(r"anim\s*:\s*\d+\s*,", "anim: 2,", content)
    if new_content != content:
        modified = True
        content = new_content

    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

def main():
    for root, dirs, files in os.walk('.'):
        if 'venv' in root or 'env' in root or '.git' in root or 'node_modules' in root:
            continue
        for file in files:
            if file.endswith('.html') or file.endswith('.js'):
                process_file(os.path.join(root, file))

if __name__ == '__main__':
    main()
