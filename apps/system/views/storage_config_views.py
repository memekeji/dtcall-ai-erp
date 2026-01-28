from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views import View
from django.http import JsonResponse
from django.utils import timezone
from apps.system.views.base import BaseAdminView
from apps.system.models import StorageConfiguration, StorageProvider
from apps.system.storage_service import storage_service


class StorageConfigListView(BaseAdminView, View):
    """存储配置列表视图"""
    permission_required = ()
    
    def get(self, request):
        configs = StorageConfiguration.objects.all().order_by('-is_default', 'name')
        context = {
            'configs': configs,
            'storage_types': StorageProvider.CHOICES
        }
        return render(request, 'config/storage_list.html', context)


class StorageConfigFormView(BaseAdminView, View):
    """存储配置表单视图"""
    permission_required = ()
    
    def get(self, request, pk=None):
        config = None
        if pk:
            config = get_object_or_404(StorageConfiguration, pk=pk)
            if config.max_file_size:
                config.max_file_size = config.max_file_size // (1024 * 1024)
        
        context = {
            'config': config,
            'storage_types': StorageProvider.CHOICES
        }
        return render(request, 'config/storage_form.html', context)
    
    def post(self, request, pk=None):
        try:
            if pk:
                config = get_object_or_404(StorageConfiguration, pk=pk)
            else:
                config = StorageConfiguration()
            
            config.name = request.POST.get('name', '')
            config.storage_type = request.POST.get('storage_type', '')
            config.is_default = 'is_default' in request.POST
            config.sync_to_local = 'sync_to_local' in request.POST
            
            config.access_key = request.POST.get('access_key', '')
            config.secret_key = request.POST.get('secret_key', '')
            config.bucket_name = request.POST.get('bucket_name', '')
            config.endpoint = request.POST.get('endpoint', '')
            config.region = request.POST.get('region', '')
            config.domain = request.POST.get('domain', '')
            config.base_path = request.POST.get('base_path', '')
            
            config.nas_host = request.POST.get('nas_host', '')
            config.nas_port = int(request.POST.get('nas_port', 0) or 0)
            config.nas_share_path = request.POST.get('nas_share_path', '')
            config.webdav_url = request.POST.get('webdav_url', '')
            config.webdav_username = request.POST.get('webdav_username', '')
            config.webdav_password = request.POST.get('webdav_password', '')
            
            config.local_path = request.POST.get('local_path', '')
            max_file_size = request.POST.get('max_file_size', 0)
            config.max_file_size = int(max_file_size) * 1024 * 1024 if max_file_size else 0
            config.allowed_extensions = request.POST.get('allowed_extensions', '')
            
            config.description = request.POST.get('description', '')
            config.creator = request.user
            
            # 设置默认状态
            if not pk:
                config.status = 'inactive'
            
            if not config.name:
                messages.error(request, '配置名称不能为空')
                return redirect('system:storage_config_list')
            
            if not config.storage_type:
                messages.error(request, '请选择存储类型')
                return redirect('system:storage_config_list')
            
            # 仅当非本地存储时进行测试
            if config.storage_type != 'local':
                test_result = self._test_config_from_form(request)
                if not test_result['success']:
                    config.status = 'error'
                    config.last_error = test_result['message']
                else:
                    config.status = 'active'
                    config.last_error = ''
                    config.last_test_time = timezone.now()
            else:
                # 本地存储直接设置为活跃状态
                config.status = 'active'
                config.last_error = ''
                config.last_test_time = timezone.now()
            
            config.save()
            
            messages.success(request, '存储配置保存成功')
            return redirect('system:storage_config_list')
            
        except Exception as e:
            import traceback
            messages.error(request, f'保存失败: {str(e)}\n{traceback.format_exc()}')
            return redirect('system:storage_config_list')
    
    def _test_config_from_form(self, request):
        """从表单数据测试存储配置"""
        try:
            storage_type = request.POST.get('storage_type', '')
            
            if storage_type in ['aliyun', 'tencent', 'huawei', 'baidu', 'qiniu', 'aws']:
                access_key = request.POST.get('access_key', '')
                secret_key = request.POST.get('secret_key', '')
                bucket_name = request.POST.get('bucket_name', '')
                region = request.POST.get('region', '')
                endpoint = request.POST.get('endpoint', '')
                
                if not access_key or not secret_key or not bucket_name:
                    return {'success': False, 'message': '请填写完整的云存储配置信息'}
                
                return storage_service.test_cloud_storage(
                    storage_type, access_key, secret_key, bucket_name, region, endpoint
                )
            
            elif storage_type in ['feiniu_nas', 'qunhui_nas']:
                nas_host = request.POST.get('nas_host', '')
                nas_share_path = request.POST.get('nas_share_path', '')
                
                if not nas_host or not nas_share_path:
                    return {'success': False, 'message': '请填写完整的NAS配置信息'}
                
                return storage_service.test_nas_storage(nas_host, int(request.POST.get('nas_port', 0) or 0), nas_share_path)
            
            elif storage_type == 'webdav':
                webdav_url = request.POST.get('webdav_url', '')
                
                if not webdav_url:
                    return {'success': False, 'message': '请填写WebDAV地址'}
                
                return storage_service.test_webdav_storage(
                    webdav_url,
                    request.POST.get('webdav_username', ''),
                    request.POST.get('webdav_password', '')
                )
            
            return {'success': True, 'message': '本地存储无需测试'}
            
        except Exception as e:
            return {'success': False, 'message': str(e)}


class StorageConfigDeleteView(BaseAdminView, View):
    """存储配置删除视图"""
    permission_required = ()
    
    def post(self, request, pk):
        try:
            config = get_object_or_404(StorageConfiguration, pk=pk)
            config.delete()
            messages.success(request, '存储配置删除成功')
        except Exception as e:
            messages.error(request, f'删除失败: {str(e)}')
        return redirect('system:storage_config_list')


class StorageConfigTestView(BaseAdminView, View):
    """存储配置测试视图"""
    permission_required = ()
    
    def post(self, request, pk):
        try:
            config = get_object_or_404(StorageConfiguration, pk=pk)
            config.status = 'testing'
            config.save()
            
            backend = storage_service.get_backend(config)
            success, message = backend.test_connection()
            
            config.last_test_time = timezone.now()
            if success:
                config.status = 'active'
                config.last_error = ''
            else:
                config.status = 'error'
                config.last_error = message
            config.save()
            
            if success:
                return JsonResponse({'status': 'success', 'message': message})
            else:
                return JsonResponse({'status': 'error', 'message': message})
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})


class StorageConfigTestFormView(BaseAdminView, View):
    """从表单数据测试存储配置视图"""
    permission_required = ()
    
    def post(self, request):
        try:
            storage_type = request.POST.get('storage_type', '')
            
            if not storage_type:
                return JsonResponse({'status': 'error', 'message': '请选择存储类型'})
            
            if storage_type == 'local':
                return JsonResponse({'status': 'success', 'message': '本地存储无需测试连接'})
            
            if storage_type in ['aliyun', 'tencent', 'huawei', 'baidu', 'qiniu', 'aws']:
                access_key = request.POST.get('access_key', '')
                secret_key = request.POST.get('secret_key', '')
                bucket_name = request.POST.get('bucket_name', '')
                region = request.POST.get('region', '')
                endpoint = request.POST.get('endpoint', '')
                
                if not access_key or not secret_key or not bucket_name:
                    return JsonResponse({'status': 'error', 'message': '请填写完整的云存储配置信息'})
                
                result = storage_service.test_cloud_storage(
                    storage_type, access_key, secret_key, bucket_name, region, endpoint
                )
                return JsonResponse({'status': 'success' if result['success'] else 'error', 'message': result['message']})
            
            elif storage_type in ['feiniu_nas', 'qunhui_nas']:
                nas_host = request.POST.get('nas_host', '')
                nas_share_path = request.POST.get('nas_share_path', '')
                nas_port = int(request.POST.get('nas_port', 0) or 0)
                
                if not nas_host or not nas_share_path:
                    return JsonResponse({'status': 'error', 'message': '请填写完整的NAS配置信息'})
                
                result = storage_service.test_nas_storage(nas_host, nas_port, nas_share_path)
                return JsonResponse({'status': 'success' if result['success'] else 'error', 'message': result['message']})
            
            elif storage_type == 'webdav':
                webdav_url = request.POST.get('webdav_url', '')
                webdav_username = request.POST.get('webdav_username', '')
                webdav_password = request.POST.get('webdav_password', '')
                
                if not webdav_url:
                    return JsonResponse({'status': 'error', 'message': '请填写WebDAV地址'})
                
                result = storage_service.test_webdav_storage(webdav_url, webdav_username, webdav_password)
                return JsonResponse({'status': 'success' if result['success'] else 'error', 'message': result['message']})
            
            return JsonResponse({'status': 'error', 'message': f'不支持的存储类型: {storage_type}'})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})


class StorageConfigSetDefaultView(BaseAdminView, View):
    """设置默认存储配置"""
    permission_required = ()
    
    def post(self, request, pk):
        try:
            config = get_object_or_404(StorageConfiguration, pk=pk)
            
            StorageConfiguration.objects.filter(is_default=True).update(is_default=False)
            config.is_default = True
            config.save()
            
            messages.success(request, f'已设置"{config.name}"为默认存储')
        except Exception as e:
            messages.error(request, f'设置失败: {str(e)}')
        return redirect('system:storage_config_list')


class StorageConfigToggleStatusView(BaseAdminView, View):
    """切换存储配置状态"""
    permission_required = ()
    
    def post(self, request, pk):
        try:
            config = get_object_or_404(StorageConfiguration, pk=pk)
            new_status = request.POST.get('status', 'active')
            
            if new_status in ['active', 'inactive']:
                config.status = new_status
                config.save()
                messages.success(request, f'状态已更新为"{config.get_status_display()}"')
            else:
                messages.error(request, '无效的状态')
                
        except Exception as e:
            messages.error(request, f'操作失败: {str(e)}')
        return redirect('system:storage_config_list')
