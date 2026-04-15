from django.http import JsonResponse
from apps.system.config_service import config_service


class FileUploadSizeMiddleware:
    """文件上传大小限制中间件，动态读取系统配置"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 处理文件上传请求
        if request.method == 'POST' and request.FILES:
            # 获取配置的最大上传大小（MB）
            max_size_mb = config_service.get_int_config('attachment_size', 5)
            max_size_bytes = max_size_mb * 1024 * 1024

            # 检查每个文件的大小
            for file_name, file in request.FILES.items():
                if file.size > max_size_bytes:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'文件 {file_name} 大小超过限制，最大允许 {max_size_mb}MB',
                        'code': 413
                    }, status=413)

        response = self.get_response(request)
        return response
