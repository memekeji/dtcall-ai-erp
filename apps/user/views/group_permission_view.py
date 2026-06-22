"""
角色管理视图模块
使用PermissionManager统一权限处理逻辑
支持根据权限管理详细设计文档精确控制权限
"""
import json
from collections import defaultdict
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group, Permission
from django.shortcuts import render
from django.core.exceptions import ObjectDoesNotExist
from django.core.cache import cache

from apps.user.utils.permission_utils import PermissionManager
from apps.user.models.menu import Menu
from apps.user.config.permission_nodes import (
    PERMISSION_NODES,
    get_permission_metadata,
)
from apps.system.middleware.data_permission_middleware import (
    DataScopeFilter,
    PermissionChecker
)
from apps.user.services.permission_node_mapper import permission_node_mapper
from apps.system.context_processors import get_permission_from_src


def _resolve_menu_permission_codename(menu):
    permission_required = getattr(menu, 'permission_required', None)
    if permission_required:
        return permission_required
    return get_permission_from_src(menu.src)


def _resolve_permission_id_by_codename(codename, permission_cache=None):
    if not codename:
        return None
    if permission_cache is None:
        permission_cache = {}
    normalized_codename = (
        codename.split('.', 1)[1] if '.' in codename else codename
    )
    if normalized_codename in permission_cache:
        return permission_cache[normalized_codename]
    permission = Permission.objects.filter(
        content_type__app_label='user',
        codename=normalized_codename,
    ).only('id').first()
    permission_cache[normalized_codename] = (
        permission.id if permission else None
    )
    return permission_cache[normalized_codename]


def clear_permission_cache_for_group(group_id):
    """清除角色相关的所有权限缓存

    Args:
        group_id: 角色ID
    """
    from apps.user.models import Admin

    try:
        group = Group.objects.get(id=group_id)

        # 获取该角色的所有用户
        users = Admin.objects.filter(groups=group)

        # 清除每个用户的菜单缓存
        for user in users:
            cache.delete(f'menus_user_{user.id}')
            cache.delete(f'dashboard_menu_{user.id}')

        # 清除角色的权限数据缓存
        cache.delete(f'group_permissions_{group_id}')
        cache.delete(f'group_menu_tree_{group_id}')

        # 清除系统配置缓存（因为权限配置可能影响系统配置）
        cache.delete('system_configs')

        return True
    except Group.DoesNotExist:
        return False


class GroupPermissionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """角色权限配置"""
    permission_required = 'user.config_role_permission'

    def get(self, request, pk):
        """获取角色权限配置页面"""
        try:
            group = Group.objects.get(id=pk)
            permissions = Permission.objects.all()
            group_permissions = group.permissions.all()

            permission_data = PermissionManager.get_permission_data(
                list(permissions))
            group_permission_ids = [perm.id for perm in group_permissions]
            permission_summary = self._build_permission_summary(
                group_permission_ids)

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
                'permission_summary': permission_summary,
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

            old_permissions = set(
                group.permissions.values_list(
                    'id', flat=True))
            new_permissions = set(permission_ids)

            permissions_to_add = new_permissions - old_permissions
            permissions_to_remove = old_permissions - new_permissions

            if permissions_to_remove:
                remove_perms = Permission.objects.filter(
                    id__in=permissions_to_remove)
                group.permissions.remove(*remove_perms)

            if permissions_to_add:
                add_perms = Permission.objects.filter(
                    id__in=permissions_to_add)
                group.permissions.add(*add_perms)

            clear_permission_cache_for_group(pk)

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

    def _build_permission_summary(self, group_permission_ids):
        all_permissions = self._get_all_defined_permission_nodes()
        total = len(all_permissions)
        selected = sum(
            1 for permission in all_permissions
            if permission['id'] in group_permission_ids
        )
        category_summary = defaultdict(lambda: {
            'name': '',
            'total': 0,
            'selected': 0,
            'order': 99,
        })

        for permission in all_permissions:
            category = permission['category']
            item = category_summary[category]
            item['name'] = category
            item['order'] = permission['category_order']
            item['total'] += 1
            if permission['id'] in group_permission_ids:
                item['selected'] += 1

        return {
            'total': total,
            'selected': selected,
            'page_total': len([
                item for item in all_permissions
                if item['category'] == '页面权限'
            ]),
            'button_total': len([
                item for item in all_permissions
                if item['category'] == '按钮权限'
            ]),
            'categories': sorted(
                category_summary.values(),
                key=lambda item: item['order'],
            ),
        }

    def _get_all_defined_permission_nodes(self):
        content_permissions = {
            permission.codename: permission
            for permission in Permission.objects.filter(
                content_type__app_label='user'
            ).select_related('content_type')
        }
        result = []

        def collect(
            node_key,
            node_data,
            module_key,
            module_name,
            parent_names=None,
        ):
            parent_names = parent_names or []
            current_names = parent_names + [node_data['name']]

            for permission_config in node_data.get('permissions', []):
                codename = permission_config['codename']
                permission = content_permissions.get(codename)
                if not permission:
                    continue
                metadata = get_permission_metadata(
                    codename, permission_config['name'])
                result.append({
                    **metadata,
                    'id': permission.id,
                    'codename': codename,
                    'full_codename': (
                        f'{permission.content_type.app_label}.{codename}'
                    ),
                    'name': permission_config['name'],
                    'module_key': module_key,
                    'module_name': module_name,
                    'page_key': node_key,
                    'page_name': node_data['name'],
                    'page_path': ' / '.join(current_names),
                })

            for child_key, child_data in node_data.get('children', {}).items():
                collect(
                    child_key,
                    child_data,
                    module_key,
                    module_name,
                    current_names,
                )

        for module_key, module_data in PERMISSION_NODES.items():
            collect(module_key, module_data, module_key, module_data['name'])

        return sorted(
            result,
            key=lambda item: (
                item['module_name'],
                item['page_path'],
                item['category_order'],
                item['weight'],
                item['id'],
            ),
        )

    def _get_permission_id_by_codename(self, codename, permission_cache=None):
        return _resolve_permission_id_by_codename(codename, permission_cache)

    def _get_menu_permission_codename(self, menu):
        return _resolve_menu_permission_codename(menu)

    def _build_menu_tree(self, group_permission_ids):
        """构建菜单树结构，包含权限信息和菜单路径

        Args:
            group_permission_ids: 角色已有的权限ID列表

        Returns:
            菜单树结构列表，包含menu_path信息用于显示面包屑
        """
        menus = Menu.objects.filter(status=1).order_by('sort', 'id')

        permission_cache = {}

        def get_menu_permission_id(menu):
            perm_codename = self._get_menu_permission_codename(menu)
            return self._get_permission_id_by_codename(
                perm_codename, permission_cache)

        def build_tree(parent_id=None, path=None):
            if path is None:
                path = []

            tree = []
            for menu in menus:
                if menu.pid_id == parent_id:
                    current_path = path + [menu.title]

                    view_perm_id = get_menu_permission_id(menu)

                    menu_data = {
                        'id': menu.id,
                        'title': menu.title,
                        'src': menu.src,
                        'icon': menu.icon,
                        'sort': menu.sort,
                        'permission_required': self._get_menu_permission_codename(
                            menu),
                        'view_permission_id': view_perm_id,
                        'has_view_permission': (
                            view_perm_id in group_permission_ids
                            if view_perm_id else False
                        ),
                        'menu_path': json.dumps(current_path, ensure_ascii=False),
                        'expanded': len(current_path) <= 2,
                        'children': build_tree(menu.id, current_path)
                    }
                    tree.append(menu_data)
            return tree

        return build_tree(None)


class MenuPermissionsAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """菜单权限API视图

    根据权限管理详细设计文档提供菜单权限查询接口
    返回指定菜单的查看权限和相关操作权限
    """
    permission_required = 'user.config_role_permission'

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
        '权限列表': 'role',
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
        '工作日历': 'work_calendar',
        '工作汇报': 'report',
        '财务管理': 'finance',
        '报销管理': 'reimbursement',
        '开票管理': 'invoice',
        '收票管理': 'receive_invoice',
        '回款管理': 'payment_receive',
        '付款管理': 'payment',
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
        '审批流程': 'approval',
        '审批类型': 'approval_type',
        '审批流程': 'approval_flow',
        '我的审批': 'my_approval',
        '发起审批': 'apply_approval',
        '待我审批': 'pending_approval',
        '消息管理': 'message',
        '消息中心': 'message_center',
        '通知偏好': 'message_preference',
        '消息统计': 'message_stats',
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
            related_permissions = self._get_related_permissions(
                menu_code, group_permission_ids)
            view_permission = self._get_view_permission(menu, group_permission_ids)
            if view_permission:
                related_permissions = self._remove_duplicate_permission(
                    related_permissions, view_permission['id'])

            data = {
                'menu_id': menu.id,
                'menu_title': menu.title,
                'menu_code': menu_code,
                'view_permission': view_permission,
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

        permission_codename = _resolve_menu_permission_codename(menu)
        if permission_codename and permission_codename.startswith('view_'):
            return permission_codename[5:]

        return None

    def _format_permission(self, permission, permission_name, group_permission_ids):
        metadata = get_permission_metadata(permission.codename, permission_name)
        return {
            **metadata,
            'id': permission.id,
            'name': permission_name,
            'codename': permission.codename,
            'full_codename': (
                f'{permission.content_type.app_label}.{permission.codename}'
            ),
            'checked': permission.id in group_permission_ids,
        }

    def _get_view_permission(self, menu, group_permission_ids):
        permission_codename = _resolve_menu_permission_codename(menu)
        if not permission_codename:
            return None
        normalized_codename = (
            permission_codename.split('.', 1)[1]
            if '.' in permission_codename else permission_codename
        )
        permission = Permission.objects.filter(
            content_type__app_label='user',
            codename=normalized_codename,
        ).select_related('content_type').first()
        if not permission:
            return None
        return self._format_permission(
            permission, permission.name, group_permission_ids)

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
                permission_data = self._format_permission(
                    perm, perm_name, group_permission_ids)

                if group_name not in related_perms:
                    related_perms[group_name] = {}

                category_name = permission_data['category']
                if category_name not in related_perms[group_name]:
                    related_perms[group_name][category_name] = []

                existing_ids = [
                    item['id']
                    for item in related_perms[group_name][category_name]
                ]
                if perm.id not in existing_ids:
                    related_perms[group_name][category_name].append(
                        permission_data)

        def collect_permissions_from_config(config, group_name):
            """从配置中收集权限"""
            if 'permissions' in config:
                for perm_config in config['permissions']:
                    codename = perm_config.get('codename')
                    perm_name = perm_config.get('name')
                    if codename and perm_name:
                        add_permission_to_result(
                            codename, perm_name, group_name)

            if 'children' in config:
                for child_key, child_config in config['children'].items():
                    child_name = child_config.get('name', child_key)
                    collect_permissions_from_config(child_config, child_name)

        def find_and_collect(node_key, node_config, node_name):
            if node_key == menu_code:
                collect_permissions_from_config(node_config, node_name)
                return True

            for child_key, child_config in node_config.get(
                    'children', {}).items():
                child_name = child_config.get('name', child_key)
                if find_and_collect(child_key, child_config, child_name):
                    return True
            return False

        for module_key, module_config in PERMISSION_NODES.items():
            module_name = module_config.get('name', module_key)
            if find_and_collect(module_key, module_config, module_name):
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
                    group_name = self._get_group_name(codename)
                    permission_data = self._format_permission(
                        perm, perm.name, group_permission_ids)
                    category_name = permission_data['category']

                    if group_name not in related_perms:
                        related_perms[group_name] = {}
                    if category_name not in related_perms[group_name]:
                        related_perms[group_name][category_name] = []

                    related_perms[group_name][category_name].append(
                        permission_data)

        for group_permissions in related_perms.values():
            for permission_list in group_permissions.values():
                permission_list.sort(
                    key=lambda item: (
                        item.get('category_order', 99),
                        item.get('weight', 999),
                        item.get('id', 0),
                    )
                )

        return related_perms

    def _remove_duplicate_permission(self, related_perms, permission_id):
        cleaned_perms = {}
        for group_name, group_permissions in related_perms.items():
            cleaned_group = {}
            for category_name, permission_list in group_permissions.items():
                cleaned_list = [
                    permission for permission in permission_list
                    if permission.get('id') != permission_id
                ]
                if cleaned_list:
                    cleaned_group[category_name] = cleaned_list
            if cleaned_group:
                cleaned_perms[group_name] = cleaned_group
        return cleaned_perms

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
        elif any(x in codename for x in ['message', 'notification']):
            return '消息管理'
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
                        scope_field=filters.get(
                            'scope_field', 'created_by_id'),
                        department_field=filters.get(
                            'department_field', 'department_id')
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
                has_permission = PermissionChecker.can_operate(
                    user, permission_code)
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
