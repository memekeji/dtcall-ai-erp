import re

# 读取brand_list.html
with open('templates/asset/brand_list.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f'原始行数: {len(lines)}')

# 找到重复代码的位置
# 第二个Vue应用从 <!-- Vue.js 3 本地 开始
duplicate_start = None
for i, line in enumerate(lines):
    if '<!-- Vue.js 3 本地 -->' in line:
        duplicate_start = i
        break

if duplicate_start:
    print(f'发现重复代码从第 {duplicate_start + 1} 行开始')
    
    # 找到重复代码结束的位置
    # 重复代码后应该有 </body></html>
    duplicate_end = None
    for i in range(duplicate_start, len(lines)):
        if '</body>' in lines[i] and '</html>' in lines[i]:
            duplicate_end = i + 1  # 包含结束标签
            break
    
    if duplicate_end:
        print(f'重复代码结束于第 {duplicate_end} 行')
        
        # 保留从duplicate_start到duplicate_end的行
        # 也就是删除这部分重复代码
        new_lines = lines[:duplicate_start] + lines[duplicate_end:]
        
        # 确保文件以 </body></html> 结尾
        if not new_lines[-1].strip().endswith('</html>'):
            # 添加缺失的闭合标签
            new_lines.append('</body>\n')
            new_lines.append('</html>\n')
        
        with open('templates/asset/brand_list.html', 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print(f'清理后行数: {len(new_lines)}')
        print('重复代码已清理')
else:
    print('未找到重复代码')

# 验证
with open('templates/asset/brand_list.html', 'r', encoding='utf-8') as f:
    content = f.read()

vue_apps = re.findall(r'const BrandApp = \{', content)
print(f'BrandApp定义数量: {len(vue_apps)}')

create_apps = re.findall(r'createApp\(BrandApp\)', content)
print(f'createApp调用数量: {len(create_apps)}')

# 检查Django标签
django_tags = re.findall(r'\{\%.*?\%\}', content)
print(f'残留Django标签: {django_tags}')
