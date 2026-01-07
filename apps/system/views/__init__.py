from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.template.loader import render_to_string
from datetime import datetime, timedelta
import json

from apps.user.models import SystemConfiguration, SystemModule, SystemLog
from apps.system.models import SystemAttachment, SystemBackup, SystemTask, BackupPolicy
from apps.system.forms import (
    SystemConfigForm, SystemModuleForm, 
    SystemBackupForm, SystemTaskForm, BackupPolicyForm
)
from apps.system.config_service import config_service
from apps.department.models import Department


@login_required
def config_list(request):
    """系统配置列表"""
    search = request.GET.get('search', '')
    configs = SystemConfiguration.objects.all()
    
    if search:
        configs = configs.filter(
            Q(key__icontains=search) | 
            Q(description__icontains=search)
        )
    
    configs = configs.order_by('key')
    
    # 分页
    paginator = Paginator(configs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
    }
    return render(request, 'config/list.html', context)


@login_required
def config_form(request, pk=None):
    """系统配置表单"""
    config = None
    if pk:
        config = get_object_or_404(SystemConfiguration, pk=pk)
    
    if request.method == 'POST':
        form = SystemConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            # 刷新配置缓存，使新配置立即生效
            config_service.refresh_configs()
            messages.success(request, '系统配置保存成功！')
            return redirect('system:config_list')
    else:
        form = SystemConfigForm(instance=config)
    
    context = {'form': form, 'config': config}
    return render(request, 'config/form.html', context)


@login_required
def module_list(request):
    """功能模块列表"""
    search = request.GET.get('search', '')
    
    # 获取所有顶层模块，不再过滤掉有效的功能模块
    modules = SystemModule.objects.filter(parent__isnull=True)
    
    # 只过滤掉明显是配置项、正则表达式或重复的模块
    import re
    valid_modules = []
    seen_module_names = set()
    
    for module in modules:
        # 排除明显是正则表达式的模块（以^开头或包含\的模块）
        if module.code.startswith('^') or '\\' in module.code or '-' in module.code:
            continue
        
        # 处理重复模块：只保留代码是英文的模块，排除中文代码的重复模块
        if '个人办公' in module.name:
            if module.code == 'personal':
                # 保留英文代码的个人办公模块
                # 先移除可能已添加的中文代码模块
                for existing_module in valid_modules[:]:
                    if existing_module.name == module.name and existing_module.code != 'personal':
                        valid_modules.remove(existing_module)
                valid_modules.append(module)
                seen_module_names.add(module.name)
        elif module.name not in seen_module_names:
            # 添加其他非重复模块
            valid_modules.append(module)
            seen_module_names.add(module.name)
    
    # 转换为查询集
    valid_module_ids = [module.id for module in valid_modules]
    modules = SystemModule.objects.filter(id__in=valid_module_ids)
    
    if search:
        modules = modules.filter(name__icontains=search)
    
    modules = modules.order_by('sort_order', 'id')
    
    context = {
        'modules': modules,
        'search': search,
    }
    return render(request, 'module/list.html', context)


@login_required
def module_form(request, pk=None):
    """功能模块表单"""
    module = None
    if pk:
        module = get_object_or_404(SystemModule, pk=pk)
    
    if request.method == 'POST':
        form = SystemModuleForm(request.POST, instance=module)
        if form.is_valid():
            module_name = form.cleaned_data['name']
            module_code = form.cleaned_data['code']
            is_active = form.cleaned_data['is_active']
            
            # 保存当前模块
            current_module = form.save()
            
            # 处理关联的中英文版本模块
            # 1. 获取所有顶层模块（parent为None）
            all_top_modules = SystemModule.objects.filter(parent__isnull=True)
            
            # 2. 定义模块名称映射关系（包含英文代码和中文名称）
            module_mapping = {
                # 英文代码映射到相关模块
                'system': ['system', '系统管理'],
                'user': ['user', '用户管理'],
                'basedata': ['basedata', '基础数据'],
                'customer': ['customer', '客户管理'],
                'project': ['project', '项目管理'],
                'production': ['production', '生产管理'],
                'finance': ['finance', '财务管理'],
                'contract': ['contract', '合同管理'],
                'personal': ['personal', '个人办公'],
                'oa': ['oa', 'oa系统'],
                'disk': ['disk', '知识网盘'],
                'ai': ['ai', 'AI智能', 'ai智能服务'],
                
                # 中文名称映射到相关模块
                '系统管理': ['system', '系统管理'],
                '用户管理': ['user', '用户管理'],
                '基础数据': ['basedata', '基础数据'],
                '客户管理': ['customer', '客户管理'],
                '项目管理': ['project', '项目管理'],
                '生产管理': ['production', '生产管理'],
                '财务管理': ['finance', '财务管理'],
                '合同管理': ['contract', '合同管理'],
                '个人办公': ['personal', '个人办公'],
                'oa系统': ['oa', 'oa系统'],
                '知识网盘': ['disk', '知识网盘'],
                'AI智能': ['ai', 'AI智能'],
                'ai智能服务': ['ai', 'ai智能服务'],
            }
            
            # 3. 查找所有相关模块
            related_codes = set()
            
            # 从映射中获取相关代码
            if module_code in module_mapping:
                related_codes.update(module_mapping[module_code])
            if module_name in module_mapping:
                related_codes.update(module_mapping[module_name])
            
            # 4. 特殊处理一些常见的模块名称
            if '个人办公' in module_name or module_code in ['personal', '个人办公']:
                related_codes.update(['personal', '个人办公'])
            if '客户管理' in module_name or module_code in ['customer', '客户管理']:
                related_codes.update(['customer', '客户管理'])
            if '系统管理' in module_name or module_code in ['system', '系统管理']:
                related_codes.update(['system', '系统管理'])
            
            # 5. 获取所有相关模块
            related_modules = []
            for code in related_codes:
                modules = all_top_modules.filter(code=code)
                related_modules.extend(modules)
            
            # 6. 去重，避免重复处理
            unique_related_modules = []
            seen_ids = set()
            for module in related_modules:
                if module.id not in seen_ids:
                    seen_ids.add(module.id)
                    unique_related_modules.append(module)
            
            # 7. 更新所有相关模块的状态
            if unique_related_modules:
                for related_module in unique_related_modules:
                    related_module.is_active = is_active
                    related_module.save()
                        
            messages.success(request, '功能模块保存成功！')
            
            # 记录操作日志
            SystemLog.objects.create(
                user=request.user,
                log_type='update' if module else 'create',
                module='功能模块管理',
                action=f"{'编辑' if module else '新增'}功能模块：{form.cleaned_data['name']}",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # AJAX请求，返回JSON响应
                return JsonResponse({
                    'success': True,
                    'message': '功能模块保存成功！'
                })
            else:
                # 非AJAX请求，重定向
                return redirect('system:module_list')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # AJAX请求，返回HTML内容（包含错误信息）
                context = {'form': form, 'module': module}
                html = render_to_string('module/form.html', context, request=request)
                return HttpResponse(html)
            else:
                # 非AJAX请求，渲染表单
                context = {'form': form, 'module': module}
                return render(request, 'module/form.html', context)
    else:
        form = SystemModuleForm(instance=module)
    
    context = {'form': form, 'module': module}
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # AJAX请求，返回HTML内容
        html = render_to_string('module/form.html', context, request=request)
        return HttpResponse(html)
    else:
        # 非AJAX请求，返回完整页面
        return render(request, 'module/form.html', context)






@login_required
def log_list(request):
    """操作日志列表"""
    from django.core.paginator import Paginator
    from django.db.models import Q
    from datetime import datetime
    from apps.user.models import SystemLog, Admin
    
    # 获取查询参数
    search = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    user_filter = request.GET.get('user', '')
    log_type = request.GET.get('log_type', '')
    
    # 构建查询条件
    logs = SystemLog.objects.select_related('user').all()
    
    if search:
        logs = logs.filter(
            Q(action__icontains=search) |
            Q(module__icontains=search) |
            Q(content__icontains=search) |
            Q(user__username__icontains=search)
        )
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            logs = logs.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            logs = logs.filter(created_at__lte=date_to_obj)
        except ValueError:
            pass
    
    if user_filter:
        logs = logs.filter(user_id=user_filter)
    
    if log_type:
        logs = logs.filter(log_type=log_type)
    
    # 按时间倒序排列
    logs = logs.order_by('-created_at')
    
    # 分页
    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 获取用户列表用于筛选
    users = Admin.objects.filter(status=1).order_by('username')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'date_from': date_from,
        'date_to': date_to,
        'user_filter': user_filter,
        'log_type': log_type,
        'log_types': SystemLog.LOG_TYPES,
        'users': users,
        'total_count': paginator.count,
    }
    return render(request, 'log/list.html', context)


@login_required
def attachment_list(request):
    """附件管理列表"""
    search = request.GET.get('search', '')
    module = request.GET.get('module', '')
    file_type = request.GET.get('file_type', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    min_size = request.GET.get('min_size', '')
    max_size = request.GET.get('max_size', '')
    sort_by = request.GET.get('sort_by', 'created_at')
    sort_order = request.GET.get('sort_order', 'desc')
    
    # 1. 获取SystemAttachment模型中的附件记录
    attachments = SystemAttachment.objects.select_related('uploader')
    
    # 2. 应用筛选条件
    # 搜索（文件名或上传者）
    if search:
        attachments = attachments.filter(
            Q(original_name__icontains=search) |
            Q(uploader__username__icontains=search)
        )
    
    # 模块筛选
    if module:
        attachments = attachments.filter(module=module)
    
    # 文件类型筛选
    if file_type:
        attachments = attachments.filter(file_type__icontains=file_type)
    
    # 上传时间筛选
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            attachments = attachments.filter(created_at__gte=start_datetime)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            attachments = attachments.filter(created_at__lt=end_datetime)
        except ValueError:
            pass
    
    # 文件大小筛选（单位：KB）
    if min_size:
        try:
            min_size_bytes = int(min_size) * 1024
            attachments = attachments.filter(file_size__gte=min_size_bytes)
        except ValueError:
            pass
    
    if max_size:
        try:
            max_size_bytes = int(max_size) * 1024
            attachments = attachments.filter(file_size__lte=max_size_bytes)
        except ValueError:
            pass
    
    # 3. 应用排序
    sort_field = f"{'-' if sort_order == 'desc' else ''}{sort_by}"
    attachments = attachments.order_by(sort_field)
    
    # 4. 分页
    paginator = Paginator(attachments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 5. 获取筛选选项列表
    modules = SystemAttachment.objects.values_list('module', flat=True).distinct()
    file_types = SystemAttachment.objects.values_list('file_type', flat=True).distinct().exclude(file_type='')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'module': module,
        'file_type': file_type,
        'start_date': start_date,
        'end_date': end_date,
        'min_size': min_size,
        'max_size': max_size,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'modules': modules,
        'file_types': file_types,
    }
    return render(request, 'attachment/list.html', context)


@login_required
def backup_list(request):
    """数据备份列表"""
    search = request.GET.get('search', '')
    backup_type = request.GET.get('backup_type', '')
    
    backups = SystemBackup.objects.select_related('creator')
    
    if search:
        backups = backups.filter(name__icontains=search)
    
    if backup_type:
        backups = backups.filter(backup_type=backup_type)
    
    backups = backups.order_by('-created_at')
    
    # 分页
    paginator = Paginator(backups, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'backup_type': backup_type,
        'backup_types': SystemBackup.BACKUP_TYPES,
    }
    return render(request, 'backup/list.html', context)


@login_required
def backup_form(request, pk=None):
    """数据备份表单"""
    backup = None
    if pk:
        backup = get_object_or_404(SystemBackup, pk=pk)
    
    if request.method == 'POST':
        form = SystemBackupForm(request.POST, instance=backup)
        if form.is_valid():
            # 检查备份类型是否支持
            backup_type = form.cleaned_data.get('backup_type')
            if backup_type in ['incremental', 'differential']:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': '该功能将在下一个版本中更新，暂时不可用'
                    }, json_dumps_params={'ensure_ascii': False})
                else:
                    messages.error(request, '该功能将在下一个版本中更新，暂时不可用')
                    return redirect('system:backup_list')
            
            backup = form.save(commit=False)
            backup.creator = request.user
            
            # 确保media目录存在
            from datetime import datetime
            import os
            from django.conf import settings
            
            if not os.path.exists(settings.MEDIA_ROOT):
                os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
            
            # 创建备份目录
            backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups', datetime.now().strftime('%Y%m%d'))
            os.makedirs(backup_dir, exist_ok=True)
            
            # 生成备份文件名，根据备份类型添加后缀
            timestamp = datetime.now().strftime('%H%M%S')
            backup_filename = f"{backup.name}_{timestamp}_{backup.backup_type}.sql"
            backup.file_path = os.path.join('backups', datetime.now().strftime('%Y%m%d'), backup_filename)
            
            # 先保存备份记录，生成ID
            backup.save()
            
            # 记录日志
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f'开始创建数据备份：{backup.name}')
            
            # 定义异步备份函数
            def async_backup():
                import traceback
                from django.conf import settings
                from apps.system.models import SystemBackup
                from django.db import connection
                import os
                from datetime import datetime, date, time
                from decimal import Decimal
                from uuid import UUID
                
                try:
                    # 确保目录存在
                    backup_dir = os.path.dirname(os.path.join(settings.MEDIA_ROOT, backup.file_path))
                    os.makedirs(backup_dir, exist_ok=True)
                    full_backup_path = os.path.join(settings.MEDIA_ROOT, backup.file_path)
                    
                    # 获取数据库配置
                    db_config = settings.DATABASES['default']
                    schema = db_config['OPTIONS']['options'].split('=')[1]  # 获取schema
                    
                    # 使用Django的ORM和原生SQL实现完整的SQL备份
                    with connection.cursor() as cursor:
                        # 创建SQL备份文件
                        with open(full_backup_path, 'w', encoding='utf-8') as f:
                            # 写入备份头信息
                            f.write(f"-- 数据库备份\n")
                            f.write(f"-- 备份名称: {backup.name}\n")
                            f.write(f"-- 备份类型: {backup.get_backup_type_display()}\n")
                            f.write(f"-- 备份时间: {datetime.now().isoformat()}\n")
                            f.write(f"-- 数据库: {db_config['NAME']}\n")
                            f.write(f"-- Schema: {schema}\n")
                            f.write("-- \n")
                            f.write("-- 注意：此备份包含完整的数据库结构和数据\n")
                            f.write("-- \n\n")
                            
                            # 1. 备份序列
                            f.write("-- 1. 备份序列\n")
                            cursor.execute(f"SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = '{schema}'")
                            sequences = cursor.fetchall()
                            for seq in sequences:
                                seq_name = seq[0]
                                try:
                                    # 直接从序列获取当前值，不使用pg_sequence表
                                    cursor.execute(f"SELECT last_value FROM {schema}.{seq_name}")
                                    last_value = cursor.fetchone()[0]
                                    # 生成简单的序列创建语句
                                    f.write(f"CREATE SEQUENCE {schema}.{seq_name} START WITH {last_value};")
                                    f.write("\n")
                                except Exception as e:
                                    # 如果获取序列值失败，跳过该序列
                                    pass
                            f.write("\n")
                            f.write("\n")
                            
                            # 2. 备份表结构
                            f.write("-- 2. 备份表结构\n")
                            cursor.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}' AND table_type = 'BASE TABLE'")
                            tables = cursor.fetchall()
                            
                            # 先创建所有表结构
                            for table in tables:
                                table_name = table[0]
                                # 直接从information_schema获取表结构，不再依赖pg_get_tabledef
                                cursor.execute(f"SELECT column_name, data_type, is_nullable, column_default, character_maximum_length, numeric_precision, numeric_scale FROM information_schema.columns WHERE table_schema = '{schema}' AND table_name = '{table_name}' ORDER BY ordinal_position")
                                columns = cursor.fetchall()
                                
                                if columns:
                                    # 构建CREATE TABLE语句
                                    create_stmt = f"CREATE TABLE {schema}.{table_name} (\n"
                                    column_defs = []
                                    
                                    for col in columns:
                                        col_name, data_type, is_nullable, col_default, char_max_len, num_prec, num_scale = col
                                        col_def = f"    {col_name} {data_type}"
                                        
                                        # 添加数据类型长度或精度
                                        if char_max_len is not None:
                                            col_def += f"({char_max_len})"
                                        elif num_prec is not None:
                                            if num_scale is not None:
                                                col_def += f"({num_prec}, {num_scale})"
                                            else:
                                                col_def += f"({num_prec})"
                                        
                                        # 添加NOT NULL约束
                                        if is_nullable == 'NO':
                                            col_def += " NOT NULL"
                                        
                                        # 添加默认值，确保值被正确引用
                                        if col_default is not None:
                                            col_def += f" DEFAULT {col_default}"
                                        
                                        column_defs.append(col_def)
                                    
                                    # 获取主键约束
                                    cursor.execute(f"SELECT kcu.column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name WHERE tc.table_schema = '{schema}' AND tc.table_name = '{table_name}' AND tc.constraint_type = 'PRIMARY KEY' ORDER BY kcu.ordinal_position")
                                    pk_columns = cursor.fetchall()
                                    if pk_columns:
                                        pk_col_names = [col[0] for col in pk_columns]
                                        column_defs.append(f"    PRIMARY KEY ({', '.join(pk_col_names)})")
                                    
                                    # 获取唯一约束
                                    cursor.execute(f"SELECT tc.constraint_name, kcu.column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name WHERE tc.table_schema = '{schema}' AND tc.table_name = '{table_name}' AND tc.constraint_type = 'UNIQUE' ORDER BY tc.constraint_name, kcu.ordinal_position")
                                    unique_constraints = cursor.fetchall()
                                    unique_dict = {}
                                    for con_name, col_name in unique_constraints:
                                        if con_name not in unique_dict:
                                            unique_dict[con_name] = []
                                        unique_dict[con_name].append(col_name)
                                    for con_name, cols in unique_dict.items():
                                        column_defs.append(f"    CONSTRAINT {con_name} UNIQUE ({', '.join(cols)})")
                                    
                                    create_stmt += ",\n".join(column_defs)
                                    create_stmt += "\n);\n"
                                    f.write(create_stmt)
                            f.write("\n")
                            
                            # 3. 备份表数据
                            f.write("-- 3. 备份表数据\n")
                            for table in tables:
                                table_name = table[0]
                                
                                try:
                                    f.write(f"-- 备份表：{table_name}\n")
                                    # 获取表的列名
                                    cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_schema = '{schema}' AND table_name = '{table_name}' ORDER BY ordinal_position")
                                    columns = [col[0] for col in cursor.fetchall()]
                                    
                                    if not columns:
                                        f.write(f"-- 表 {table_name} 没有列\n\n")
                                        continue
                                    
                                    # 获取表的数据
                                    cursor.execute(f"SELECT * FROM {schema}.{table_name}")
                                    rows = cursor.fetchall()
                                    
                                    if not rows:
                                        f.write(f"-- 表 {table_name} 没有数据\n\n")
                                        continue
                                    
                                    # 生成INSERT语句
                                    column_names = ', '.join(columns)
                                    
                                    # 构建VALUES子句
                                    for row in rows:
                                        # 处理每个值
                                        values = []
                                        for val in row:
                                            if val is None:
                                                values.append('NULL')
                                            elif isinstance(val, (int, float)):
                                                values.append(str(val))
                                            elif isinstance(val, bool):
                                                values.append('TRUE' if val else 'FALSE')
                                            elif isinstance(val, (datetime, date, time)):
                                                # 处理日期时间类型
                                                values.append(f"'{val}'")
                                            elif isinstance(val, (Decimal, UUID)):
                                                # 处理Decimal和UUID类型
                                                values.append(f"'{str(val)}'")
                                            else:
                                                # 字符串类型，需要转义
                                                val_str = str(val).replace("'", "''")
                                                values.append(f"'{val_str}'")
                                        values_str = ', '.join(values)
                                        f.write(f"INSERT INTO {schema}.{table_name} ({column_names}) VALUES ({values_str});\n")
                                    f.write("\n")
                                except Exception as e:
                                    # 如果备份表数据失败，记录警告并跳过
                                    logger.warning(f"无法备份表 {schema}.{table_name} 的数据: {str(e)}")
                                    f.write(f"-- 无法备份表 {table_name} 的数据: {str(e)}\n\n")
                            
                            # 4. 备份索引
                            f.write("-- 4. 备份索引\n")
                            # 获取所有索引
                            cursor.execute(f"SELECT indexname, tablename FROM pg_indexes WHERE schemaname = '{schema}'")
                            indexes = cursor.fetchall()
                            for idx in indexes:
                                index_name, table_name = idx
                                try:
                                    # 跳过主键索引，因为它们已经在表结构中定义
                                    cursor.execute(f"SELECT COUNT(*) FROM pg_constraint WHERE conname = '{index_name}' AND contype = 'p' AND connamespace = (SELECT oid FROM pg_namespace WHERE nspname = '{schema}')")
                                    if cursor.fetchone()[0] > 0:
                                        continue
                                    
                                    # 使用更简单的方式获取索引定义
                                    cursor.execute(f"SELECT pg_get_indexdef(oid) FROM pg_class WHERE relname = '{index_name}' AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = '{schema}')")
                                    index_def = cursor.fetchone()
                                    if index_def and index_def[0]:
                                        f.write(f"{index_def[0]};\n")
                                except Exception as e:
                                    # 如果获取索引定义失败，跳过该索引
                                    logger.warning(f"无法备份索引 {schema}.{index_name}: {str(e)}")
                            f.write("\n")
                            
                            # 5. 备份约束（外键、唯一约束、检查约束）
                            f.write("-- 5. 备份约束\n")
                            # 获取所有约束
                            cursor.execute(f"SELECT conname, conrelid::regclass::text as table_name, contype FROM pg_constraint WHERE connamespace = (SELECT oid FROM pg_namespace WHERE nspname = '{schema}') AND contype IN ('f', 'u', 'c')")
                            constraints = cursor.fetchall()
                            for constraint in constraints:
                                con_name, con_table_name, con_type = constraint
                                # 获取约束的创建语句
                                cursor.execute(f"SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = '{con_name}'")
                                con_def = cursor.fetchone()[0]
                                f.write(f"ALTER TABLE {schema}.{con_table_name} ADD CONSTRAINT {con_name} {con_def};\n")
                            f.write("\n")
                    
                    # 获取备份文件大小
                    file_size = os.path.getsize(full_backup_path)
                    
                    # 更新数据库记录
                    backup_obj = SystemBackup.objects.get(id=backup.id)
                    backup_obj.file_size = file_size
                    backup_obj.save()
                    
                    # 记录日志
                    logger.info(f'数据备份创建成功：{backup.name}，文件大小：{file_size}字节')
                except Exception as e:
                    # 记录详细错误信息
                    error_msg = f'备份失败：{str(e)}\n{traceback.format_exc()}'
                    logger.error(error_msg)
            
            # 使用线程异步执行备份
            import threading
            backup_thread = threading.Thread(target=async_backup)
            backup_thread.start()
            
            # 检查是否为AJAX请求
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # AJAX请求，返回JSON响应
                from django.http import JsonResponse
                return JsonResponse({
                    'success': True,
                    'message': f'数据{backup.get_backup_type_display()}任务已创建，正在后台执行中！'
                }, json_dumps_params={'ensure_ascii': False})
            else:
                # 非AJAX请求，使用传统的消息和重定向
                messages.success(request, f'数据{backup.get_backup_type_display()}任务已创建，正在后台执行中！')
                return redirect('system:backup_list')
        else:
            # 表单验证失败
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # AJAX请求，返回JSON响应
                from django.http import JsonResponse
                # 获取表单错误信息
                errors = []
                for field, field_errors in form.errors.items():
                    for error in field_errors:
                        errors.append(f'{field}: {error}')
                return JsonResponse({
                    'success': False,
                    'message': '表单验证失败',
                    'errors': errors
                }, json_dumps_params={'ensure_ascii': False})
            else:
                # 非AJAX请求，直接返回表单页面，显示错误信息
                pass
    else:
        form = SystemBackupForm(instance=backup)
    
    context = {'form': form, 'backup': backup}
    return render(request, 'backup/form.html', context)


@login_required
def task_list(request):
    """定时任务列表"""
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    
    tasks = SystemTask.objects.select_related('creator')
    
    if search:
        tasks = tasks.filter(name__icontains=search)
    
    if status:
        tasks = tasks.filter(status=status)
    
    tasks = tasks.order_by('-created_at')
    
    # 分页
    paginator = Paginator(tasks, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'status_choices': SystemTask.TASK_STATUS,
    }
    return render(request, 'task/list.html', context)


@login_required
def task_form(request, pk=None):
    """定时任务表单"""
    task = None
    if pk:
        task = get_object_or_404(SystemTask, pk=pk)
    
    if request.method == 'POST':
        form = SystemTaskForm(request.POST, instance=task)
        if form.is_valid():
            task = form.save(commit=False)
            task.creator = request.user
            task.save()
            messages.success(request, '定时任务保存成功！')
            return redirect('system:task_list')
    else:
        form = SystemTaskForm(instance=task)
    
    context = {'form': form, 'task': task}
    return render(request, 'task/form.html', context)


@login_required
@require_http_methods(["POST"])
def task_toggle(request, pk):
    """切换任务状态"""
    task = get_object_or_404(SystemTask, pk=pk)
    
    if task.status == 'active':
        task.status = 'inactive'
        message = '任务已禁用'
    else:
        task.status = 'active'
        message = '任务已启用'
    
    task.save()
    
    return JsonResponse({
        'success': True,
        'message': message,
        'status': task.status
    }, json_dumps_params={'ensure_ascii': False})


@login_required
def restore_list(request):
    """数据还原列表"""
    backups = SystemBackup.objects.select_related('creator').order_by('-created_at')
    
    # 分页
    paginator = Paginator(backups, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'restore/list.html', context)


@login_required
@require_http_methods(["POST"])
def restore_backup(request, pk):
    """还原备份"""
    backup = get_object_or_404(SystemBackup, pk=pk)
    
    try:
        import os
        import logging
        from django.conf import settings
        from django.db import connection
        
        logger = logging.getLogger(__name__)
        logger.info(f'开始还原备份：{backup.name}')
        
        # 获取完整备份文件路径
        full_backup_path = os.path.join(settings.MEDIA_ROOT, backup.file_path)
        
        # 检查备份文件是否存在
        if not os.path.exists(full_backup_path):
            return JsonResponse({
                'success': False,
                'message': f'备份文件不存在：{full_backup_path}'
            }, json_dumps_params={'ensure_ascii': False})
        
        # 检查文件是否为空
        if os.path.getsize(full_backup_path) == 0:
            return JsonResponse({
                'success': False,
                'message': f'备份文件为空：{full_backup_path}'
            }, json_dumps_params={'ensure_ascii': False})
        
        # 使用Django的连接直接执行SQL脚本
        with connection.cursor() as cursor:
            # 读取SQL文件内容
            with open(full_backup_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # 分割SQL语句，避免直接执行整个文件导致的问题
            sql_statements = []
            current_statement = ""
            
            for line in sql_content.split('\n'):
                # 跳过注释行和空行
                line = line.strip()
                if not line or line.startswith('--'):
                    continue
                
                current_statement += line + ' '
                
                # 检查语句是否结束
                if current_statement.strip().endswith(';'):
                    # 执行语句
                    cursor.execute(current_statement)
                    sql_statements.append(current_statement)
                    current_statement = ""
            
            # 执行最后一个语句（如果有的话）
            if current_statement.strip():
                cursor.execute(current_statement)
                sql_statements.append(current_statement)
        
        logger.info(f'备份还原成功：{backup.name}，执行了 {len(sql_statements)} 条SQL语句')
        return JsonResponse({
            'success': True,
            'message': f'备份 {backup.name} 还原成功！'
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        # 记录详细错误信息
        import traceback
        error_msg = f'还原失败：{str(e)}\n{traceback.format_exc()}'
        import logging
        logger = logging.getLogger(__name__)
        logger.error(error_msg)
        
        return JsonResponse({
            'success': False,
            'message': f'还原失败：{str(e)}'
        }, json_dumps_params={'ensure_ascii': False})


@login_required
@require_http_methods(["POST"])
def delete_backup(request, pk):
    """删除备份"""
    backup = get_object_or_404(SystemBackup, pk=pk)
    
    try:
        import os
        import logging
        from django.conf import settings
        
        logger = logging.getLogger(__name__)
        logger.info(f'开始删除备份：{backup.name}')
        
        # 获取完整备份文件路径
        full_backup_path = os.path.join(settings.MEDIA_ROOT, backup.file_path)
        
        # 删除备份文件（如果存在）
        if os.path.exists(full_backup_path):
            os.remove(full_backup_path)
            logger.info(f'备份文件已删除：{full_backup_path}')
        
        # 删除数据库记录
        backup_name = backup.name
        backup.delete()
        logger.info(f'备份记录已删除：{backup_name}')
        
        return JsonResponse({
            'success': True,
            'message': f'备份 {backup_name} 删除成功！'
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        # 记录详细错误信息
        import traceback
        error_msg = f'删除备份失败：{str(e)}\n{traceback.format_exc()}'
        logger.error(error_msg)
        
        return JsonResponse({
            'success': False,
            'message': f'删除备份失败：{str(e)}'
        }, json_dumps_params={'ensure_ascii': False})


@login_required
@require_http_methods(["POST"])
def batch_delete_backups(request):
    """批量删除备份"""
    try:
        import os
        import logging
        from django.conf import settings
        
        logger = logging.getLogger(__name__)
        
        # 获取选中的备份ID列表
        backup_ids = request.POST.getlist('backup_ids[]') or request.POST.getlist('backup_ids')
        
        if not backup_ids:
            return JsonResponse({
                'success': False,
                'message': '请选择要删除的备份'
            }, json_dumps_params={'ensure_ascii': False})
        
        logger.info(f'开始批量删除备份，共 {len(backup_ids)} 个')
        
        # 获取备份对象
        backups = SystemBackup.objects.filter(id__in=backup_ids)
        deleted_count = 0
        
        for backup in backups:
            try:
                # 获取完整备份文件路径
                full_backup_path = os.path.join(settings.MEDIA_ROOT, backup.file_path)
                
                # 删除备份文件（如果存在）
                if os.path.exists(full_backup_path):
                    os.remove(full_backup_path)
                    logger.info(f'备份文件已删除：{full_backup_path}')
                
                # 删除数据库记录
                backup.delete()
                deleted_count += 1
            except Exception as e:
                # 记录单个备份删除失败的错误，但继续删除其他备份
                logger.error(f'删除备份 {backup.id} 失败：{str(e)}')
        
        logger.info(f'批量删除备份完成，成功删除 {deleted_count} 个，失败 {len(backup_ids) - deleted_count} 个')
        
        return JsonResponse({
            'success': True,
            'message': f'成功删除 {deleted_count} 个备份，失败 {len(backup_ids) - deleted_count} 个'
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        # 记录详细错误信息
        import traceback
        error_msg = f'批量删除备份失败：{str(e)}\n{traceback.format_exc()}'
        logger.error(error_msg)
        
        return JsonResponse({
            'success': False,
            'message': f'批量删除备份失败：{str(e)}'
        }, json_dumps_params={'ensure_ascii': False})


@login_required
def download_backup(request, pk):
    """下载备份文件"""
    try:
        import os
        import logging
        from io import BytesIO
        from django.conf import settings
        from django.http import HttpResponse
        
        logger = logging.getLogger(__name__)
        
        # 获取备份对象
        backup = get_object_or_404(SystemBackup, pk=pk)
        
        logger.info(f'开始下载备份文件：{backup.name}')
        
        # 获取完整备份文件路径
        full_backup_path = os.path.join(settings.MEDIA_ROOT, backup.file_path)
        
        # 检查备份文件是否存在
        if not os.path.exists(full_backup_path):
            logger.error(f'备份文件不存在：{full_backup_path}')
            messages.error(request, '备份文件不存在')
            return redirect('system:backup_list')
        
        # 获取文件名
        filename = os.path.basename(full_backup_path)
        
        # 读取文件内容到BytesIO对象
        with open(full_backup_path, 'rb') as f:
            file_content = f.read()
        
        # 使用BytesIO包装内容，确保内容在内存中
        bytes_io = BytesIO(file_content)
        
        # 创建响应对象，使用BytesIO作为内容
        response = HttpResponse(bytes_io.getvalue(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename={filename}'
        response['Content-Length'] = len(file_content)
        
        logger.info(f'备份文件下载成功：{backup.name}')
        return response
    except Exception as e:
        # 记录详细错误信息
        import traceback
        error_msg = f'下载备份失败：{str(e)}\n{traceback.format_exc()}'
        logger.error(error_msg)
        messages.error(request, f'下载备份失败：{str(e)}')
        return redirect('system:backup_list')


@login_required
def backup_policy_list(request):
    """自动备份策略列表"""
    search = request.GET.get('search', '')
    
    policies = BackupPolicy.objects.all()
    
    if search:
        policies = policies.filter(
            Q(name__icontains=search) | 
            Q(description__icontains=search)
        )
    
    policies = policies.order_by('-created_at')
    
    # 分页
    paginator = Paginator(policies, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
    }
    return render(request, 'backup/policy_list.html', context)


@login_required
def backup_policy_form(request, pk=None):
    """自动备份策略表单"""
    policy = None
    if pk:
        policy = get_object_or_404(BackupPolicy, pk=pk)
    
    if request.method == 'POST':
        form = BackupPolicyForm(request.POST, instance=policy)
        if form.is_valid():
            policy = form.save(commit=False)
            policy.creator = request.user
            policy.save()
            messages.success(request, '自动备份策略保存成功！')
            return redirect('system:backup_policy_list')
    else:
        form = BackupPolicyForm(instance=policy)
    
    context = {'form': form, 'policy': policy}
    return render(request, 'backup/policy_form.html', context)


@login_required
@require_http_methods(["POST"])
def delete_backup_policy(request, pk):
    """删除自动备份策略"""
    policy = get_object_or_404(BackupPolicy, pk=pk)
    
    try:
        policy_name = policy.name
        policy.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'自动备份策略 {policy_name} 删除成功！'
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        # 记录详细错误信息
        import traceback
        error_msg = f'删除自动备份策略失败：{str(e)}\n{traceback.format_exc()}'
        import logging
        logger = logging.getLogger(__name__)
        logger.error(error_msg)
        
        return JsonResponse({
            'success': False,
            'message': f'删除自动备份策略失败：{str(e)}'
        }, json_dumps_params={'ensure_ascii': False})


@login_required
@require_http_methods(["POST"])
def backup_policy_toggle(request, pk):
    """切换自动备份策略状态"""
    policy = get_object_or_404(BackupPolicy, pk=pk)
    
    if policy.is_active:
        policy.is_active = False
        message = '自动备份策略已禁用'
    else:
        policy.is_active = True
        message = '自动备份策略已启用'
    
    policy.save()
    
    return JsonResponse({
        'success': True,
        'message': message,
        'is_active': policy.is_active
    }, json_dumps_params={'ensure_ascii': False})


@login_required
def department_page(request):
    def build_hierarchy(parents):
        result = []
        for dept in parents:
            children = Department.objects.filter(pid=dept.id).order_by('sort')
            result.append({
                'id': dept.id,
                'title': dept.name,
                'children': build_hierarchy(children)
            })
        return result
    top_departments = Department.objects.filter(pid=0).order_by('sort')
    department_tree = build_hierarchy(top_departments)
    context = {
        'department_tree_json': json.dumps(department_tree)
    }
    return render(request, 'department/list.html', context)

# 导入行政办公相关视图
from apps.system.views.admin_office_views import *