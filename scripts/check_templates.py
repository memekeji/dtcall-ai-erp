import re

def check_template(file_path, name):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f'=== {name} ===')
    print(f'文件长度: {len(content)} 字符')
    
    checks = [
        ('<!DOCTYPE html>', 'DOCTYPE声明'),
        ('<html', 'HTML标签'),
        ('</html>', 'HTML闭合标签'),
        ('<head>', 'HEAD标签'),
        ('</head>', 'HEAD闭合标签'),
        ('<body>', 'BODY标签'),
        ('</body>', 'BODY闭合标签'),
        ('<script>', 'SCRIPT标签'),
        ('</script>', 'SCRIPT闭合标签'),
        ('<style>', 'STYLE标签'),
        ('</style>', 'STYLE闭合标签'),
        ('#category-app', 'Vue容器ID') if 'category' in name else ('#brand-app', 'Vue容器ID'),
        ('createApp', 'Vue createApp'),
        ('onMounted', 'Vue onMounted钩子'),
        ('loadCategories', 'loadCategories函数') if 'category' in name else ('loadBrands', 'loadBrands函数'),
    ]
    
    for pattern, desc in checks:
        if pattern in content:
            print(f'  OK: {desc}')
        else:
            print(f'  MISSING: {desc} - 缺失!')
    
    django_tags = re.findall(r'\{\%.*?\%\}', content)
    if django_tags:
        print(f'  WARNING: 残留Django标签: {django_tags}')
    else:
        print(f'  OK: 无残留Django标签')
    
    if "delimiters:" in content and "'[[', '" in content:
        print(f'  OK: Vue delimiters已设置')
    else:
        print(f'  WARNING: Vue delimiters可能未设置')
    
    print()

check_template('templates/asset/category_list.html', 'category_list.html')
check_template('templates/asset/brand_list.html', 'brand_list.html')
