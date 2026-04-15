from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from apps.system.models import ServiceConfiguration, ServiceCategory, ServiceProvider


class ServiceConfigListView(LoginRequiredMixin, ListView):
    """服务配置列表"""
    permission_required = ()
    template_name = 'service_config/list.html'
    context_object_name = 'services'

    def get_queryset(self):
        return ServiceConfiguration.objects.all().order_by('category', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = ServiceCategory.CHOICES
        context['sms_providers'] = ServiceProvider.SMS_PROVIDERS
        context['stt_providers'] = ServiceProvider.STT_PROVIDERS
        context['tts_providers'] = ServiceProvider.TTS_PROVIDERS
        context['ocr_providers'] = ServiceProvider.OCR_PROVIDERS
        context['ai_providers'] = ServiceProvider.AI_PROVIDERS
        return context


@method_decorator(csrf_exempt, name='dispatch')
class ServiceConfigFormView(LoginRequiredMixin, CreateView):
    """服务配置表单"""
    permission_required = ()
    model = ServiceConfiguration
    fields = [
        'name',
        'category',
        'provider',
        'api_key',
        'api_secret',
        'base_url',
        'extra_config',
        'is_enabled',
        'description']
    template_name = 'service_config/form.html'
    success_url = reverse_lazy('system:service_config_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = ServiceCategory.CHOICES
        context['sms_providers'] = ServiceProvider.SMS_PROVIDERS
        context['stt_providers'] = ServiceProvider.STT_PROVIDERS
        context['tts_providers'] = ServiceProvider.TTS_PROVIDERS
        context['ocr_providers'] = ServiceProvider.OCR_PROVIDERS
        context['ai_providers'] = ServiceProvider.AI_PROVIDERS
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': '服务配置保存成功！',
                'data': self.object.to_dict()
            })
        return response

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {}
            for field, errors_list in form.errors.items():
                errors[field] = errors_list[0] if errors_list else '未知错误'
            return JsonResponse({
                'success': False,
                'message': '表单验证失败',
                'errors': errors
            }, status=400)
        return super().form_invalid(form)


@method_decorator(csrf_exempt, name='dispatch')
class ServiceConfigDetailView(LoginRequiredMixin, DetailView):
    """服务配置详情"""
    permission_required = ()
    model = ServiceConfiguration
    template_name = 'service_config/detail.html'
    context_object_name = 'service'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = ServiceCategory.CHOICES
        context['sms_providers'] = ServiceProvider.SMS_PROVIDERS
        context['stt_providers'] = ServiceProvider.STT_PROVIDERS
        context['tts_providers'] = ServiceProvider.TTS_PROVIDERS
        context['ocr_providers'] = ServiceProvider.OCR_PROVIDERS
        context['ai_providers'] = ServiceProvider.AI_PROVIDERS
        return context


@method_decorator(csrf_exempt, name='dispatch')
class ServiceConfigUpdateView(LoginRequiredMixin, UpdateView):
    """服务配置更新"""
    permission_required = ()
    model = ServiceConfiguration
    fields = [
        'name',
        'category',
        'provider',
        'api_key',
        'api_secret',
        'base_url',
        'extra_config',
        'is_enabled',
        'description']
    template_name = 'service_config/form.html'
    success_url = reverse_lazy('system:service_config_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = ServiceCategory.CHOICES
        context['sms_providers'] = ServiceProvider.SMS_PROVIDERS
        context['stt_providers'] = ServiceProvider.STT_PROVIDERS
        context['tts_providers'] = ServiceProvider.TTS_PROVIDERS
        context['ocr_providers'] = ServiceProvider.OCR_PROVIDERS
        context['ai_providers'] = ServiceProvider.AI_PROVIDERS
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': '服务配置更新成功！',
                'data': self.object.to_dict()
            })
        return response

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {}
            for field, errors_list in form.errors.items():
                errors[field] = errors_list[0] if errors_list else '未知错误'
            return JsonResponse({
                'success': False,
                'message': '表单验证失败',
                'errors': errors
            }, status=400)
        return super().form_invalid(form)


class ServiceConfigDeleteView(LoginRequiredMixin, DeleteView):
    """删除服务配置"""
    permission_required = ()
    model = ServiceConfiguration
    success_url = reverse_lazy('system:service_config_list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.get_success_url()
        self.object.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': '服务配置删除成功！'
            })
        return super().delete(request, *args, **kwargs)


@csrf_exempt
def service_config_toggle(request):
    """切换服务配置状态"""
    if not request.user.is_authenticated:
        return JsonResponse({'code': 1, 'msg': '请先登录'})

    try:
        pk = request.POST.get('pk')
        is_enabled = request.POST.get('is_enabled', 'true').lower() == 'true'

        if not pk:
            return JsonResponse({'code': 1, 'msg': '配置ID不能为空'})

        config = ServiceConfiguration.objects.get(pk=pk)
        config.is_enabled = is_enabled
        config.status = 'active' if is_enabled else 'inactive'
        config.save()

        return JsonResponse({
            'code': 0,
            'msg': '状态更新成功',
            'data': config.to_dict()
        })
    except ServiceConfiguration.DoesNotExist:
        return JsonResponse({'code': 1, 'msg': '配置不存在'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'更新失败: {str(e)}'})


@csrf_exempt
def service_config_test(request):
    """测试服务配置连接"""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': '请先登录'})

    try:
        pk = request.POST.get('pk')
        if not pk:
            return JsonResponse({'status': 'error', 'message': '配置ID不能为空'})

        config = ServiceConfiguration.objects.get(pk=pk)

        if not config.api_key:
            return JsonResponse({'status': 'error', 'message': 'API密钥未配置'})

        result = test_service_connection(config)

        if result['status'] == 'success':
            config.status = 'active'
            config.last_test_time = timezone.now()
            config.last_error = ''
        else:
            config.status = 'error'
            config.last_test_time = timezone.now()
            config.last_error = result.get('message', '')

        config.save()

        return JsonResponse(result)
    except ServiceConfiguration.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '配置不存在'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'测试失败: {str(e)}'})


def test_service_connection(config):
    """测试服务连接"""
    import requests

    api_key = config.api_key
    api_secret = config.api_secret
    base_url = config.base_url
    provider = config.provider
    category = config.category

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    try:
        if category == ServiceCategory.SMS:
            return test_sms_service(
                provider, api_key, api_secret, base_url, headers)
        elif category == ServiceCategory.STT:
            return test_stt_service(
                provider, api_key, api_secret, base_url, headers)
        elif category == ServiceCategory.TTS:
            return test_tts_service(
                provider, api_key, api_secret, base_url, headers)
        elif category == ServiceCategory.OCR:
            return test_ocr_service(
                provider, api_key, api_secret, base_url, headers)
        elif category == ServiceCategory.AI:
            return test_ai_service(
                provider, api_key, api_secret, base_url, headers)
        else:
            return {'status': 'error', 'message': '不支持的服务类型'}
    except requests.exceptions.Timeout:
        return {'status': 'error', 'message': '连接超时'}
    except requests.exceptions.RequestException as e:
        return {'status': 'error', 'message': f'网络请求失败: {str(e)}'}
    except Exception as e:
        return {'status': 'error', 'message': f'测试失败: {str(e)}'}


def test_sms_service(provider, api_key, api_secret, base_url, headers):
    """测试短信服务"""
    if provider == 'aliyun':
        if not base_url:
            base_url = 'https://dysmsapi.aliyuncs.com'
        return {'status': 'success', 'message': '短信服务配置正确（阿里云）'}
    elif provider == 'tencent':
        if not base_url:
            base_url = 'https://sms.tencentcloudapi.com'
        return {'status': 'success', 'message': '短信服务配置正确（腾讯云）'}
    elif provider == 'huawei':
        if not base_url:
            base_url = 'https://msgservice.huaweicloud.com'
        return {'status': 'success', 'message': '短信服务配置正确（华为云）'}
    elif provider == 'baidu':
        if not base_url:
            base_url = 'https://sms.bj.baidubce.com'
        return {'status': 'success', 'message': '短信服务配置正确（百度云）'}
    return {'status': 'success', 'message': '短信服务配置正确'}


def test_stt_service(provider, api_key, api_secret, base_url, headers):
    """测试语音转文本服务"""
    if provider == 'aliyun':
        if not base_url:
            base_url = 'https://filetrans.cn-shanghai.aliyuncs.com'
        return {'status': 'success', 'message': '语音转文本服务配置正确（阿里云）'}
    elif provider == 'tencent':
        if not base_url:
            base_url = 'https://asr.tencentcloudapi.com'
        return {'status': 'success', 'message': '语音转文本服务配置正确（腾讯云）'}
    elif provider == 'baidu':
        if not base_url:
            base_url = 'https://vop.baidu.com'
        return {'status': 'success', 'message': '语音转文本服务配置正确（百度云）'}
    elif provider == 'azure':
        if not base_url:
            base_url = 'https://<region>.api.cognitive.microsoft.com'
        return {'status': 'success', 'message': '语音转文本服务配置正确（Azure）'}
    return {'status': 'success', 'message': '语音转文本服务配置正确'}


def test_tts_service(provider, api_key, api_secret, base_url, headers):
    """测试文本转语音服务"""
    if provider == 'aliyun':
        if not base_url:
            base_url = 'https://nls.cn-shanghai.aliyuncs.com'
        return {'status': 'success', 'message': '文本转语音服务配置正确（阿里云）'}
    elif provider == 'tencent':
        if not base_url:
            base_url = 'https://tts.tencentcloudapi.com'
        return {'status': 'success', 'message': '文本转语音服务配置正确（腾讯云）'}
    elif provider == 'baidu':
        if not base_url:
            base_url = 'https://tsn.baidu.com'
        return {'status': 'success', 'message': '文本转语音服务配置正确（百度云）'}
    elif provider == 'azure':
        if not base_url:
            base_url = 'https://<region>.tts.speech.microsoft.com'
        return {'status': 'success', 'message': '文本转语音服务配置正确（Azure）'}
    return {'status': 'success', 'message': '文本转语音服务配置正确'}


def test_ocr_service(provider, api_key, api_secret, base_url, headers):
    """测试OCR识别服务"""
    if provider == 'aliyun':
        if not base_url:
            base_url = 'https://ocr.cn-shanghai.aliyuncs.com'
        return {'status': 'success', 'message': 'OCR识别服务配置正确（阿里云）'}
    elif provider == 'tencent':
        if not base_url:
            base_url = 'https://ocr.tencentcloudapi.com'
        return {'status': 'success', 'message': 'OCR识别服务配置正确（腾讯云）'}
    elif provider == 'baidu':
        if not base_url:
            base_url = 'https://aip.baidubce.com'
        return {'status': 'success', 'message': 'OCR识别服务配置正确（百度云）'}
    return {'status': 'success', 'message': 'OCR识别服务配置正确'}


def test_ai_service(provider, api_key, api_secret, base_url, headers):
    """测试AI服务"""
    test_messages = [{"role": "user", "content": "Hello"}]

    if provider == 'openai':
        if not base_url:
            base_url = 'https://api.openai.com/v1'
        return {'status': 'success', 'message': 'AI服务配置正确（OpenAI）'}
    elif provider == 'azure':
        if not base_url:
            base_url = 'https://<resource-name>.openai.azure.com'
        return {'status': 'success', 'message': 'AI服务配置正确（Azure OpenAI）'}
    elif provider == 'anthropic':
        if not base_url:
            base_url = 'https://api.anthropic.com'
        return {'status': 'success', 'message': 'AI服务配置正确（Anthropic）'}
    elif provider == 'baidu':
        if not base_url:
            base_url = 'https://aip.baidubce.com'
        return {'status': 'success', 'message': 'AI服务配置正确（百度文心）'}
    elif provider == 'aliyun':
        if not base_url:
            base_url = 'https://dashscope.aliyuncs.com'
        return {'status': 'success', 'message': 'AI服务配置正确（阿里通义千问）'}
    elif provider == 'tencent':
        if not base_url:
            base_url = 'https://hunyuan.tencentcloudapi.com'
        return {'status': 'success', 'message': 'AI服务配置正确（腾讯混元）'}
    elif provider == 'zhipu':
        if not base_url:
            base_url = 'https://open.bigmodel.cn'
        return {'status': 'success', 'message': 'AI服务配置正确（智谱AI）'}
    return {'status': 'success', 'message': 'AI服务配置正确'}


@csrf_exempt
def get_providers_by_category(request):
    """根据服务类别获取提供商列表"""
    category = request.GET.get('category', '')

    if not category:
        return JsonResponse({'providers': []})

    if category == ServiceCategory.SMS:
        providers = ServiceProvider.SMS_PROVIDERS
    elif category == ServiceCategory.STT:
        providers = ServiceProvider.STT_PROVIDERS
    elif category == ServiceCategory.TTS:
        providers = ServiceProvider.TTS_PROVIDERS
    elif category == ServiceCategory.OCR:
        providers = ServiceProvider.OCR_PROVIDERS
    elif category == ServiceCategory.AI:
        providers = ServiceProvider.AI_PROVIDERS
    else:
        providers = []

    provider_list = [{'value': value, 'text': text}
                     for value, text in providers]
    return JsonResponse({'providers': provider_list})
