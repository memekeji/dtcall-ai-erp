import re

# 替换category_list.html中的Django标签
with open('templates/asset/category_list.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 替换Django URL标签为实际URL
content = content.replace('{% url "system:admin_office:asset_category_create" %}', '/system/admin_office/asset/category/create/')

with open('templates/asset/category_list.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('category_list.html Django标签已替换')

# 替换brand_list.html中的Django标签
with open('templates/asset/brand_list.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('{% url "system:admin_office:asset_brand_create" %}', '/system/admin_office/asset/brand/create/')

with open('templates/asset/brand_list.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('brand_list.html Django标签已替换')

# 验证
import re
for file in ['templates/asset/category_list.html', 'templates/asset/brand_list.html']:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    django_tags = re.findall(r'\{\%.*?\%\}', content)
    if django_tags:
        print(f'{file} 仍有Django标签: {django_tags}')
    else:
        print(f'{file} 已无Django标签')
