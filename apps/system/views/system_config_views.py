from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.generic import View, ListView, DeleteView
from django.urls import reverse_lazy
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.http import JsonResponse
from apps.user.models import SystemConfiguration
from apps.system.views.base import BaseAdminView
from apps.system.config_service import config_service


class SystemConfigListView(BaseAdminView, ListView):
    """系统配置列表视图"""
    model = SystemConfiguration
    template_name = 'config/list.html'
    context_object_name = 'configs'
    permission_required = 'user.view_systemconfiguration'
    
    def get_queryset(self):
        return SystemConfiguration.objects.filter(is_active=True)


class SystemConfigView(BaseAdminView, View):
    """系统配置视图（兼容旧版本）"""
    template_name = 'config/form.html'
    permission_required = ['user.view_systemconfiguration', 'user.change_systemconfiguration']

    def get(self, request):
        # 获取所有系统配置项
        config_items = SystemConfiguration.objects.all()
        configs = {}
        for item in config_items:
            configs[item.key] = item
        return render(request, self.template_name, {'configs': configs})

    def post(self, request):
        # 处理系统名称和ICP备案号
        self._save_config('system_name', request.POST.get('system_name', ''), '系统名称')
        self._save_config('icp_number', request.POST.get('icp_number', ''), 'ICP备案号')

        # 处理附件上传大小
        attachment_size = request.POST.get('attachment_size', 5)
        self._save_config('attachment_size', attachment_size, '允许上传附件大小(MB)')

        # 处理水印开关
        watermark_enabled = 'watermark_enabled' in request.POST
        self._save_config('watermark_enabled', str(watermark_enabled).lower(), '页面水印开关')

        # 处理系统Logo上传
        if 'system_logo' in request.FILES:
            file = request.FILES['system_logo']
            file_path = default_storage.save(f'uploads/logo/{file.name}', ContentFile(file.read()))
            self._save_config('system_logo', file_path, '系统Logo')

        # 处理客户自动流转公海规则
        no_follow_days = request.POST.get('customer_no_follow_days', 30)
        self._save_config('customer_no_follow_days', no_follow_days, '客户无跟进记录流转公海天数')
        no_deal_days = request.POST.get('customer_no_deal_days', 90)
        self._save_config('customer_no_deal_days', no_deal_days, '客户无成交流转公海天数')

        # 处理短信接口配置
        self._save_config('sms_provider', request.POST.get('sms_provider', ''), '短信服务商')
        self._save_config('sms_api_key', request.POST.get('sms_api_key', ''), '短信API密钥')
        self._save_config('sms_api_secret', request.POST.get('sms_api_secret', ''), '短信API密钥Secret')
        self._save_config('sms_sign', request.POST.get('sms_sign', ''), '短信签名')
        self._save_config('sms_template_id', request.POST.get('sms_template_id', ''), '短信模板ID')
        self._save_config('sms_api_url', request.POST.get('sms_api_url', ''), '短信API地址')

        # 刷新配置缓存，使新配置立即生效
        config_service.refresh_configs()
        messages.success(request, '系统配置更新成功')
        return redirect('system:system_config_edit')

    def _save_config(self, key, value, description):
        config, created = SystemConfiguration.objects.get_or_create(key=key)
        config.value = value
        config.description = description
        config.is_active = True
        config.save()


class SystemConfigEditView(BaseAdminView, View):
    """系统配置编辑视图"""
    template_name = 'config/form.html'
    permission_required = ['user.view_systemconfiguration', 'user.change_systemconfiguration']

    def get(self, request):
        # 获取所有系统配置项
        config_items = SystemConfiguration.objects.all()
        configs = {}
        for item in config_items:
            configs[item.key] = item
        return render(request, self.template_name, {'configs': configs})

    def post(self, request):
        # 处理系统名称和ICP备案号
        self._save_config('system_name', request.POST.get('system_name', ''), '系统名称')
        self._save_config('icp_number', request.POST.get('icp_number', ''), 'ICP备案号')

        # 处理附件上传大小
        attachment_size = request.POST.get('attachment_size', 5)
        self._save_config('attachment_size', attachment_size, '允许上传附件大小(MB)')

        # 处理水印开关
        watermark_enabled = 'watermark_enabled' in request.POST
        self._save_config('watermark_enabled', str(watermark_enabled).lower(), '页面水印开关')

        # 处理系统Logo上传
        if 'system_logo' in request.FILES:
            file = request.FILES['system_logo']
            file_path = default_storage.save(f'uploads/logo/{file.name}', ContentFile(file.read()))
            self._save_config('system_logo', file_path, '系统Logo')

        # 处理客户自动流转公海规则
        no_follow_days = request.POST.get('customer_no_follow_days', 30)
        self._save_config('customer_no_follow_days', no_follow_days, '客户无跟进记录流转公海天数')
        no_deal_days = request.POST.get('customer_no_deal_days', 90)
        self._save_config('customer_no_deal_days', no_deal_days, '客户无成交流转公海天数')

        # 处理短信接口配置
        self._save_config('sms_provider', request.POST.get('sms_provider', ''), '短信服务商')
        self._save_config('sms_api_key', request.POST.get('sms_api_key', ''), '短信API密钥')
        self._save_config('sms_api_secret', request.POST.get('sms_api_secret', ''), '短信API密钥Secret')
        self._save_config('sms_sign', request.POST.get('sms_sign', ''), '短信签名')
        self._save_config('sms_template_id', request.POST.get('sms_template_id', ''), '短信模板ID')
        self._save_config('sms_api_url', request.POST.get('sms_api_url', ''), '短信API地址')

        # 刷新配置缓存，使新配置立即生效
        config_service.refresh_configs()
        messages.success(request, '系统配置更新成功')
        return redirect('system:system_config_edit')

    def _save_config(self, key, value, description):
        config, created = SystemConfiguration.objects.get_or_create(key=key)
        config.value = value
        config.description = description
        config.is_active = True
        config.save()


class SystemConfigDeleteView(DeleteView, BaseAdminView):
    """系统配置删除视图"""
    model = SystemConfiguration
    success_url = reverse_lazy('system:system_config_list')
    permission_required = 'user.delete_systemconfiguration'
    
    def delete(self, request, *args, **kwargs):
        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(request, '配置项删除成功')
            return response
        except Exception as e:
            messages.error(request, f'删除失败: {str(e)}')
            return redirect('system:system_config_list')


class SystemConfigAPIView(BaseAdminView, View):
    """系统配置API视图"""
    permission_required = ['user.view_systemconfiguration', 'user.change_systemconfiguration']
    
    def get(self, request, *args, **kwargs):
        """获取所有系统配置"""
        configs = SystemConfiguration.objects.filter(is_active=True)
        config_dict = {}
        for config in configs:
            config_dict[config.key] = config.value
        
        return JsonResponse({'status': 'success', 'data': config_dict})
    
    def post(self, request, *args, **kwargs):
        """更新系统配置"""
        try:
            key = request.POST.get('key')
            value = request.POST.get('value')
            description = request.POST.get('description', '')
            
            if not key or not value:
                return JsonResponse({'status': 'error', 'message': '配置键和值不能为空'})
            
            config, created = SystemConfiguration.objects.get_or_create(key=key)
            config.value = value
            config.description = description
            config.is_active = True
            config.save()
            
            # 刷新配置缓存，使新配置立即生效
            config_service.refresh_configs()
            
            return JsonResponse({'status': 'success', 'message': '配置更新成功'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})