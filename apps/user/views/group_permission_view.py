"""
角色管理视图模块
使用PermissionManager统一权限处理逻辑
支持根据权限管理详细设计文档精确控制权限
"""
import json
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group, Permission
from django.shortcuts import render, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from apps.user.utils.permission_utils import PermissionManager
from apps.user.models_new import GroupExtension
from apps.user.models.menu import Menu
from apps.user.config.permission_nodes import PERMISSION_NODES
from apps.system.middleware.data_permission_middleware import (
    DataScopeFilter, 
    PermissionChecker
)
from apps.user.services.permission_node_mapper import permission_node_mapper


class GroupPermissionView(LoginRequiredMixin, View):
    """角色权限配置"""
    
    def get(self, request, pk):
        """获取角色权限配置页面"""
        try:
            group = Group.objects.get(id=pk)
            permissions = Permission.objects.all()
            group_permissions = group.permissions.all()
            
            permission_data = PermissionManager.get_permission_data(list(permissions))
            group_permission_ids = [perm.id for perm in group_permissions]
            
            try:
                extension = group.extension
                group.description = extension.description
            except ObjectDoesNotExist:
                group.description = ''
            
            menu_tree = self._build_menu_tree(group_permission_ids)
            
            return render(request, 'permission/role_permission.html', {
                'group': group,
                'permissions': permission_data,
                'group_permissions': group_permissions,
                'group_permission_ids': group_permission_ids,
                'menu_tree': menu_tree,
                'isInIframe': True
            })
        
        except Group.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '角色不存在'})
    
    def post(self, request, pk):
        """更新角色权限"""
        try:
            group = Group.objects.get(id=pk)
            permission_ids = request.POST.getlist('permissions[]', [])
            
            if not permission_ids:
                permission_ids = []
            
            permission_ids = [int(pid) for pid in permission_ids if pid]
            
            old_permissions = set(group.permissions.values_list('id', flat=True))
            new_permissions = set(permission_ids)
            
            permissions_to_add = new_permissions - old_permissions
            permissions_to_remove = old_permissions - new_permissions
            
            if permissions_to_remove:
                remove_perms = Permission.objects.filter(id__in=permissions_to_remove)
                group.permissions.remove(*remove_perms)
            
            if permissions_to_add:
                add_perms = Permission.objects.filter(id__in=permissions_to_add)
                group.permissions.add(*add_perms)
            
            return JsonResponse({
                'code': 200, 
                'msg': '权限配置成功',
                'data': {
                    'permissions_count': len(permission_ids),
                    'added': len(permissions_to_add),
                    'removed': len(permissions_to_remove)
                }
            })
        
        except Group.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '角色不存在'})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': f'保存失败: {str(e)}'})
    
    def _build_menu_tree(self, group_permission_ids):
        """构建菜单树结构，包含权限信息和菜单路径
        
        Args:
            group_permission_ids: 角色已有的权限ID列表
            
        Returns:
            菜单树结构列表，包含menu_path信息用于显示面包屑
        """
        menus = Menu.objects.filter(status=1).order_by('sort', 'id')
        
        for menu in menus:
            if not menu.view_permission:
                menu.create_view_permission()
        
        menu_dict = {menu.id: menu for menu in menus}
        
        def build_tree(parent_id=None, path=None):
            if path is None:
                path = []
            
            tree = []
            for menu in menus:
                if menu.pid_id == parent_id:
                    current_path = path + [menu.title]
                    
                    menu_data = {
                        'id': menu.id,
                        'title': menu.title,
                        'src': menu.src,
                        'icon': menu.icon,
                        'sort': menu.sort,
                        'permission_required': menu.permission_required,
                        'view_permission_id': menu.get_view_permission_id(),
                        'has_view_permission': (
                            menu.get_view_permission_id() in group_permission_ids 
                            if menu.get_view_permission_id() else False
                        ),
                        'menu_path': json.dumps(current_path, ensure_ascii=False),
                        'expanded': len(current_path) <= 2,
                        'children': build_tree(menu.id, current_path)
                    }
                    tree.append(menu_data)
            return tree
        
        return build_tree(None)


class MenuPermissionsAPIView(LoginRequiredMixin, View):
    """菜单权限API视图
    
    根据权限管理详细设计文档提供菜单权限查询接口
    返回指定菜单的查看权限和相关操作权限
    """
    
    MENU_TITLE_TO_CODE = {
        '工作台': 'workbench',
        '系统管理': 'system',
        '功能模块': 'module',
        '菜单管理': 'menu',
        '操作日志': 'operation_log',
        '附件管理': 'attachment',
        '备份数据': 'backup',
        '系统配置': 'config',
        '人事管理': 'hr',
        '角色管理': 'role',
        '部门管理': 'department',
        '岗位职称': 'position',
        '员工管理': 'employee',
        '奖罚管理': 'reward_punishment',
        '员工关怀': 'employee_care',
        '行政办公': 'admin',
        '固定资产': 'assets',
        '资产管理': 'asset_management',
        '资产归还': 'asset_return',
        '资产维修': 'asset_repair',
        '资产报废': 'asset_scrap',
        '车辆管理': 'vehicle',
        '车辆信息': 'vehicle_info',
        '用车申请': 'vehicle_apply',
        '车辆维修': 'vehicle_maintenance',
        '车辆调度': 'vehicle_dispatch',
        '车辆保养': 'vehicle_upkeep',
        '车辆费用': 'vehicle_fee',
        '车辆油耗': 'vehicle_oil',
        '会议管理': 'meeting',
        '会议室管理': 'meeting_room',
        '会议记录': 'meeting_record',
        '会议纪要': 'meeting_minutes',
        '公文管理': 'document',
        '公文起草': 'document_draft',
        '公文审核': 'document_approve',
        '公文发布': 'document_publish',
        '公文查看': 'document_view',
        '公文分类': 'document_category',
        '用章管理': 'seal',
        '印章管理': 'seal_management',
        '用章申请': 'seal_application',
        '用章记录': 'seal_record',
        '公告列表': 'notice',
        '公司动态': 'company_news',
        '通知类型': 'notice_type',
        '个人办公': 'personal',
        '日程安排': 'schedule',
        '工作日历': 'work_calendar',
        '工作汇报': 'report',
        '财务管理': 'finance',
        '报销管理': 'reimbursement',
        '开票管理': 'invoice',
        '收票管理': 'receive_invoice',
        '回款管理': 'payment_receive',
        '付款管理': 'payment',
        '报销类型': 'reimbursement_type',
        '费用类型': 'expense_type',
        '财务统计': 'finance_statistics',
        '报销记录': 'reimbursement_record',
        '开票记录': 'invoice_record',
        '收票记录': 'receive_invoice_record',
        '回款记录': 'payment_receive_record',
        '付款记录': 'payment_record',
        '客户管理': 'customer',
        '客户列表': 'customer_list',
        '客户公海': 'customer_pool',
        '公海列表': 'pool_list',
        '爬虫任务': 'spider_task',
        'AI机器人': 'ai_robot',
        '废弃客户': 'abandoned_customer',
        '客户订单': 'customer_order',
        '跟进记录': 'follow_record',
        '拨号记录': 'call_record',
        '客户字段': 'customer_field',
        '客户来源': 'customer_source',
        '客户等级': 'customer_grade',
        '客户意向': 'customer_intent',
        '跟进字段': 'follow_field',
        '订单字段': 'order_field',
        '合同管理': 'contract',
        '合同列表': 'contract_list',
        '合同模板': 'contract_template',
        '合同归档': 'contract_archive',
        '合同分类': 'contract_category',
        '产品管理': 'product',
        '服务管理': 'service',
        '供应商管理': 'supplier',
        '采购分类': 'purchase_category',
        '采购项目': 'purchase_item',
        '项目管理': 'project',
        '项目列表': 'project_list',
        '项目分类': 'project_category',
        '任务列表': 'task_list',
        '工时管理': 'workhour',
        '文档列表': 'project_document',
        '风险预测': 'risk_prediction',
        '进度分析': 'progress_analysis',
        '项目阶段': 'project_stage',
        '工作类型': 'work_type',
        '生产管理': 'production',
        '基础信息': 'baseinfo',
        '基本工序': 'procedure',
        '工序集': 'procedureset',
        'BOM管理': 'bom',
        '设备管理': 'equipment',
        '数据采集': 'datacollection',
        '性能分析': 'performance_analysis',
        'SOP管理': 'sop',
        '产品管理': 'production_product',
        '工艺路线': 'process',
        '生产任务': 'production_task',
        '生产计划': 'production_plan',
        '生产任务': 'production_task',
        '资源调度': 'resource_dispatch',
        '质量管理': 'quality_check',
        '设备监控': 'equipment_monitor',
        'AI智能中心': 'ai',
        '知识库管理': 'knowledge_base',
        'AI模型配置': 'model_config',
        'AI任务管理': 'task_management',
        'AI工作流': 'workflow',
        '企业网盘': 'disk',
        '网盘首页': 'disk_index',
        '个人文件': 'personal_file',
        '共享文件': 'shared_file',
        '收藏文件': 'starred_file',
        '分享管理': 'share_management',
        '回收站': 'recycle',
    }
    
    def get(self, request, menu_id):
        """获取指定菜单的权限配置
        
        Args:
            menu_id: 菜单ID
            
        Returns:
            JSON响应，包含菜单的查看权限和相关权限节点
        """
        try:
            menu = Menu.objects.get(id=menu_id)
            
            group_permission_ids = []
            
            group_id = request.GET.get('group_id')
            if group_id:
                try:
                    group = Group.objects.filter(id=group_id).first()
                    if group:
                        group_permission_ids = list(
                            group.permissions.values_list('id', flat=True)
                        )
                except (ValueError, TypeError):
                    pass
            
            if not group_permission_ids:
                group_ids = request.user.groups.values_list('id', flat=True)
                for gid in group_ids:
                    group = Group.objects.filter(id=gid).first()
                    if group:
                        group_permission_ids.extend(
                            group.permissions.values_list('id', flat=True)
                        )
                group_permission_ids = list(set(group_permission_ids))
            
            menu_code = self._get_menu_code(menu)
            related_permissions = self._get_related_permissions(menu_code, group_permission_ids)
            
            data = {
                'menu_id': menu.id,
                'menu_title': menu.title,
                'menu_code': menu_code,
                'view_permission': None,
                'permissions': related_permissions
            }
            
            return JsonResponse({
                'code': 200,
                'msg': 'success',
                'data': data
            })
        
        except Menu.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '菜单不存在'
            })
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'msg': f'获取菜单权限失败: {str(e)}'
            })
    
    def _get_menu_code(self, menu):
        """根据菜单获取对应的权限节点代码
        
        Args:
            menu: Menu实例
            
        Returns:
            权限节点代码
        """
        menu_title = menu.title.strip()
        
        if menu_title in self.MENU_TITLE_TO_CODE:
            return self.MENU_TITLE_TO_CODE[menu_title]
        
        return None
    
    def _get_related_permissions(self, menu_code, group_permission_ids):
        """根据菜单代码获取相关权限（支持层级显示）
        
        根据设计文档要求：
        - 点击一级菜单：显示该菜单下所有子菜单的权限
        - 点击二级菜单：显示该二级菜单的权限
        - 点击三级菜单：显示该三级菜单的权限
        
        Args:
            menu_code: 菜单代码
            group_permission_ids: 角色已有的权限ID列表
            
        Returns:
            分组后的权限数据字典
        """
        related_perms = {}
        
        if not menu_code:
            return related_perms
        
        perm_cache = permission_node_mapper._build_permission_cache()
        
        def add_permission_to_result(codename, perm_name, group_name):
            """将权限添加到结果中"""
            if codename in perm_cache:
                perm = perm_cache[codename]
                checked = perm.id in group_permission_ids
                
                if group_name not in related_perms:
                    related_perms[group_name] = {}
                
                model_name = '操作权限'
                if model_name not in related_perms[group_name]:
                    related_perms[group_name][model_name] = []
                
                existing_ids = [p['id'] for p in related_perms[group_name][model_name]]
                if perm.id not in existing_ids:
                    related_perms[group_name][model_name].append({
                        'id': perm.id,
                        'name': perm_name,
                        'codename': codename,
                        'checked': checked
                    })
        
        def collect_permissions_from_config(config, group_name):
            """从配置中收集权限"""
            if 'permissions' in config:
                for perm_config in config['permissions']:
                    codename = perm_config.get('codename')
                    perm_name = perm_config.get('name')
                    if codename and perm_name:
                        add_permission_to_result(codename, perm_name, group_name)
            
            if 'children' in config:
                for child_key, child_config in config['children'].items():
                    child_name = child_config.get('name', child_key)
                    collect_permissions_from_config(child_config, child_name)
        
        for module_key, module_config in PERMISSION_NODES.items():
            module_name = module_config.get('name', module_key)
            
            if module_key == menu_code:
                collect_permissions_from_config(module_config, module_name)
                break
            
            if 'children' in module_config:
                for child_key, child_config in module_config['children'].items():
                    if child_key == menu_code:
                        child_name = child_config.get('name', child_key)
                        collect_permissions_from_config(child_config, child_name)
                        break
                    
                    if 'children' in child_config:
                        for sub_key, sub_config in child_config['children'].items():
                            if sub_key == menu_code:
                                sub_name = sub_config.get('name', sub_key)
                                collect_permissions_from_config(sub_config, sub_name)
                                break
        
        if not related_perms:
            all_perms = Permission.objects.all()
            for perm in all_perms:
                codename = perm.codename
                if menu_code and (codename.startswith(f'view_{menu_code}') or 
                                  codename.startswith(f'add_{menu_code}') or
                                  codename.startswith(f'change_{menu_code}') or
                                  codename.startswith(f'delete_{menu_code}') or
                                  codename.endswith(f'_{menu_code}') or
                                  menu_code in codename):
                    checked = perm.id in group_permission_ids
                    
                    group_name = self._get_group_name(codename)
                    if group_name not in related_perms:
                        related_perms[group_name] = {}
                    
                    model_name = '权限'
                    if model_name not in related_perms[group_name]:
                        related_perms[group_name][model_name] = []
                    
                    related_perms[group_name][model_name].append({
                        'id': perm.id,
                        'name': perm.name,
                        'codename': perm.codename,
                        'checked': checked
                    })
        
        return related_perms
    
    def _get_group_name(self, codename):
        """根据权限codename获取分组名称"""
        if 'workbench' in codename:
            return '工作台'
        elif 'config' in codename or 'module' in codename or 'menu' in codename:
            return '系统管理'
        elif any(x in codename for x in ['role', 'department', 'position', 'employee', 'reward', 'care']):
            return '人事管理'
        elif any(x in codename for x in ['asset', 'vehicle', 'meeting', 'document', 'seal', 'notice']):
            return '行政办公'
        elif any(x in codename for x in ['schedule', 'calendar', 'report']):
            return '个人办公'
        elif any(x in codename for x in ['reimbursement', 'invoice', 'payment']):
            return '财务管理'
        elif any(x in codename for x in ['customer', 'order', 'follow']):
            return '客户管理'
        elif 'contract' in codename:
            return '合同管理'
        elif 'project' in codename or 'task' in codename:
            return '项目管理'
        elif any(x in codename for x in ['production', 'procedure', 'bom', 'equipment', 'quality']):
            return '生产管理'
        elif any(x in codename for x in ['knowledge', 'ai', 'workflow']):
            return 'AI智能中心'
        elif 'disk' in codename or 'file' in codename:
            return '企业网盘'
        else:
            return '其他权限'


class DataPermissionAPIView(LoginRequiredMixin, View):
    """数据权限API视图
    
    提供数据权限范围查询和数据过滤功能
    确保用户只能访问其权限范围内的数据
    """
    
    def get(self, request):
        """获取当前用户的数据权限信息"""
        try:
            user = request.user
            
            if not user.is_authenticated:
                return JsonResponse({
                    'code': 401,
                    'msg': '用户未登录'
                })
            
            data_scope = DataScopeFilter.get_user_data_scope(user)
            
            return JsonResponse({
                'code': 200,
                'msg': 'success',
                'data': {
                    'user_id': user.id,
                    'username': user.username,
                    'is_superuser': user.is_superuser,
                    'data_scope': data_scope
                }
            })
        
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'msg': f'获取数据权限信息失败: {str(e)}'
            })
    
    def post(self, request):
        """过滤QuerySet数据
        
        请求参数:
            - model_path: 模型路径 (如 'customer.Customer')
            - queryset_json: QuerySet的JSON表示（包含filters）
        """
        try:
            user = request.user
            
            if not user.is_authenticated:
                return JsonResponse({
                    'code': 401,
                    'msg': '用户未登录'
                })
            
            from django.db import models
            
            model_path = request.POST.get('model_path')
            filters_json = request.POST.get('filters', '{}')
            
            if not model_path:
                return JsonResponse({
                    'code': 400,
                    'msg': '缺少模型路径参数'
                })
            
            import json
            filters = json.loads(filters_json) if filters_json else {}
            
            try:
                app_label, model_name = model_path.split('.')
                model = models.get_model(app_label, model_name)
                
                if model is None:
                    return JsonResponse({
                        'code': 404,
                        'msg': f'模型 {model_path} 不存在'
                    })
                
                queryset = model.objects.all()
                
                if not user.is_superuser:
                    queryset = DataScopeFilter.filter_queryset(
                        user, 
                        queryset,
                        scope_field=filters.get('scope_field', 'created_by_id'),
                        department_field=filters.get('department_field', 'department_id')
                    )
                
                data = [{
                    'id': obj.id,
                    'str': str(obj)
                } for obj in queryset[:100]]
                
                return JsonResponse({
                    'code': 200,
                    'msg': 'success',
                    'data': {
                        'count': queryset.count(),
                        'results': data
                    }
                })
            
            except ValueError as ve:
                return JsonResponse({
                    'code': 400,
                    'msg': f'模型路径格式错误: {str(ve)}'
                })
        
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'msg': f'数据过滤失败: {str(e)}'
            })


class PermissionCheckAPIView(LoginRequiredMixin, View):
    """权限检查API视图
    
    提供细粒度的权限检查功能
    """
    
    def get(self, request):
        """检查用户是否拥有指定权限
        
        请求参数:
            - permission_code: 权限代码 (如 'view_customer')
            - resource_type: 资源类型 (如 'customer')
            - operation: 操作类型 (如 'view', 'add', 'change', 'delete', 'approve')
        """
        try:
            user = request.user
            
            if not user.is_authenticated:
                return JsonResponse({
                    'code': 401,
                    'msg': '用户未登录'
                })
            
            permission_code = request.GET.get('permission_code')
            resource_type = request.GET.get('resource_type')
            operation = request.GET.get('operation')
            
            if permission_code:
                has_permission = PermissionChecker.can_operate(user, permission_code)
                return JsonResponse({
                    'code': 200,
                    'msg': 'success',
                    'data': {
                        'permission_code': permission_code,
                        'has_permission': has_permission
                    }
                })
            
            elif resource_type and operation:
                method_name = f'can_{operation}'
                if hasattr(PermissionChecker, method_name):
                    checker = getattr(PermissionChecker, method_name)
                    has_permission = checker(user, resource_type)
                    return JsonResponse({
                        'code': 200,
                        'msg': 'success',
                        'data': {
                            'resource_type': resource_type,
                            'operation': operation,
                            'has_permission': has_permission
                        }
                    })
                else:
                    return JsonResponse({
                        'code': 400,
                        'msg': f'不支持的操作类型: {operation}'
                    })
            
            else:
                return JsonResponse({
                    'code': 400,
                    'msg': '缺少权限检查参数'
                })
        
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'msg': f'权限检查失败: {str(e)}'
            })
