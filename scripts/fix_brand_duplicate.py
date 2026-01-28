import os

# 读取brand_list.html
with open('templates/asset/brand_list.html', 'r', encoding='utf-8') as f:
    content = f.read()

print(f'原始文件长度: {len(content)} 字符')

# 找到第二个<script>标签和Vue应用的位置
# 第二个Vue应用从 <!-- Vue.js 3 本地 开始
second_script_start = content.find('<!-- Vue.js 3 本地 -->')

if second_script_start > 0:
    # 保留第一个<script>部分，删除第二个
    # 第一个<script>结束于 </script> 后跟 <style>
    first_script_end = content.find('</script>', content.find('<script>', content.find('<script src="/static/layui/layui.js"></script>')))
    
    # 计算需要保留的部分
    # 从开始到第一个<script>结束
    part1_end = content.find('</script>', content.find('<script src="/static/layui/layui.js"></script>'))
    if part1_end > 0:
        part1_end = content.find('</script>', part1_end + 10) + 9  # +9 for </script>
        part1 = content[:part1_end]
        
        # 从第二个脚本开始找到 </script> 结束
        # 第二个脚本后的内容应该保留
        second_script_content_start = second_script_start
        second_script_tag_start = content.rfind('<script>', 0, second_script_start)
        
        # 找到第二个<script>块的结束
        second_script_end = content.find('</script>', second_script_tag_start) + 9
        remaining = content[second_script_end:]
        
        # 合并
        new_content = part1 + remaining
        
        with open('templates/asset/brand_list.html', 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f'清理后文件长度: {len(new_content)} 字符')
        print('重复代码已清理')
else:
    print('未找到重复代码')

# 验证
import re
with open('templates/asset/brand_list.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 检查是否只有一个Vue应用定义
vue_apps = re.findall(r'const BrandApp = \{', content)
print(f'BrandApp定义数量: {len(vue_apps)}')

# 检查是否只有一个createApp
create_apps = re.findall(r'createApp\(BrandApp\)', content)
print(f'createApp调用数量: {len(create_apps)}')

# 检查Django标签
django_tags = re.findall(r'\{\%.*?\%\}', content)
if django_tags:
    print(f'残留Django标签: {django_tags}')
else:
    print('无残留Django标签')
