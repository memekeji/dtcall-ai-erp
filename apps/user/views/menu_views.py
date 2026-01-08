from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from apps.user.models import Menu
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
import json


class SuperUserPermissionMixin:
    """
    自定义权限检查Mixin
    允许超级用户绕过PermissionRequiredMixin的权限检查
    """
    
    def has_permission(self):
        # 超级用户拥有所有权限
        if self.request.user.is_authenticated and self.request.user.is_superuser:
            return True
        return False


class MenuListAPIView(LoginRequiredMixin, View):
    """菜单列表API视图"""
    
    def get(self, request):
        """获取菜单列表"""
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        keyword = request.GET.get('keyword', '')
        status = request.GET.get('status', '')
        
        queryset = Menu.objects.all()
        
        if keyword:
            queryset = queryset.filter(
                Q(title__icontains=keyword) |
                Q(name__icontains=keyword)
            )
        
        if status:
            queryset = queryset.filter(status=(status == 'enabled'))
        
        total = queryset.count()
        menus = queryset[(page-1)*limit:page*limit]
        
        data = []
        for menu in menus:
            data.append({
                'id': menu.id,
                'pid': menu.pid,
                'title': menu.title,
                'name': menu.name,
                'src': menu.src,
                'module': menu.module,
                'icon': menu.icon,
                'is_menu': menu.is_menu,
                'sort': menu.sort,
                'status': menu.status,
                'create_time': menu.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                'update_time': menu.update_time.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return JsonResponse({
            'code': 200,
            'msg': 'success',
            'data': {
                'total': total,
                'items': data
            }
        })


class MenuDetailAPIView(LoginRequiredMixin, View):
    """菜单详情API视图"""
    
    def get(self, request, pk):
        """获取菜单详情"""
        try:
            menu = Menu.objects.get(id=pk)
            data = {
                'id': menu.id,
                'pid': menu.pid,
                'title': menu.title,
                'name': menu.name,
                'src': menu.src,
                'module': menu.module,
                'icon': menu.icon,
                'is_menu': menu.is_menu,
                'sort': menu.sort,
                'status': menu.status,
                'create_time': menu.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                'update_time': menu.update_time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return JsonResponse({
                'code': 200,
                'msg': 'success',
                'data': data
            })
        
        except Menu.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': 'Menu not found'
            })


class MenuView(LoginRequiredMixin, View):
    """菜单管理视图"""
    
    def get(self, request):
        """获取菜单列表或菜单树
        
        GET参数：
            tree: 是否返回树形结构，默认False
            status: 状态过滤，可选值：all/enabled/disabled，默认enabled
        """
        tree = request.GET.get('tree', 'false').lower() == 'true'
        status = request.GET.get('status', 'enabled')
        
        if tree:
            # 返回树形结构
            menu_tree = Menu.get_menu_tree()
            return JsonResponse({
                'code': 200,
                'msg': 'success',
                'data': menu_tree
            })
        
        # 构建查询条件
        query = {}
        if status != 'all':
            query['status'] = (status == 'enabled')
            
        # 获取菜单列表
        menus = Menu.objects.filter(**query).order_by('sort', 'id')
        # 过滤出可用的菜单（考虑模块启用状态）
        available_menus = [menu for menu in menus if menu.is_available()]
        
        top_menus = [{
            'id': menu.id,
            'pid': menu.pid,
            'title': menu.title,
            'name': menu.name,
            'src': menu.src,
            'module': menu.module,
            'icon': menu.icon,
            'is_menu': menu.is_menu,
            'sort': menu.sort,
            'status': menu.status,
            'create_time': menu.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            'update_time': menu.update_time.strftime('%Y-%m-%d %H:%M:%S')
        } for menu in available_menus]
        
        return JsonResponse({
            'code': 200,
            'msg': 'success',
            'data': top_menus
        })
    
    def post(self, request):
        """创建菜单"""
        try:
            data = json.loads(request.body)
            menu = Menu.objects.create(
                pid=data.get('pid', 0),
                title=data['title'],
                name=data.get('name', ''),
                src=data.get('src', ''),
                module=data.get('module', ''),
                icon=data.get('icon', ''),
                is_menu=data.get('is_menu', True),
                sort=data.get('sort', 1),
                status=data.get('status', True)
            )
            
            return JsonResponse({
                'code': 200,
                'msg': 'success',
                'data': {
                    'id': menu.id,
                    'title': menu.title
                }
            })
            
        except KeyError as e:
            return JsonResponse({
                'code': 400,
                'msg': f'Missing required field: {str(e)}'
            })
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'msg': str(e)
            })
    
    def put(self, request):
        """更新菜单"""
        try:
            data = json.loads(request.body)
            menu_id = data.get('id')
            if not menu_id:
                return JsonResponse({
                    'code': 400,
                    'msg': 'Missing menu id'
                })
                
            menu = Menu.objects.get(id=menu_id)
            
            # 更新字段
            fields = ['pid', 'title', 'name', 'src', 'module', 
                     'icon', 'is_menu', 'sort', 'status']
            for field in fields:
                if field in data:
                    setattr(menu, field, data[field])
            
            menu.save()
            
            return JsonResponse({
                'code': 200,
                'msg': 'success',
                'data': {
                    'id': menu.id,
                    'title': menu.title
                }
            })
            
        except ObjectDoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': 'Menu not found'
            })
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'msg': str(e)
            })
    
    def delete(self, request):
        """删除菜单"""
        try:
            data = json.loads(request.body)
            menu_id = data.get('id')
            if not menu_id:
                return JsonResponse({
                    'code': 400,
                    'msg': 'Missing menu id'
                })
            
            # 检查是否有子菜单
            if Menu.objects.filter(pid=menu_id).exists():
                return JsonResponse({
                    'code': 400,
                    'msg': 'Cannot delete menu with children'
                })
            
            Menu.objects.filter(id=menu_id).delete()
            
            return JsonResponse({
                'code': 200,
                'msg': 'success'
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'msg': str(e)
            })