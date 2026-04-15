from django.shortcuts import render
from django.http import JsonResponse
from .models import Enterprise
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@login_required
def enterprise_list(request):
    enterprises = Enterprise.objects.filter(status=1).order_by('-create_time')
    return render(request,
                  'enterprise/enterprise_list.html',
                  {'enterprises': enterprises})


@login_required
def enterprise_add(request, id=0):
    if request.method == 'POST':
        data = request.POST.dict()
        if id:
            # 编辑企业
            try:
                enterprise = Enterprise.objects.get(id=id)
                for key, value in data.items():
                    if hasattr(enterprise, key):
                        setattr(enterprise, key, value)
                enterprise.update_time = timezone.now().timestamp()
                enterprise.save()
                logger.info(f'编辑企业成功，ID：{id}')
                return JsonResponse({'code': 0, 'msg': '保存成功'})
            except Enterprise.DoesNotExist:
                return JsonResponse({'code': 1, 'msg': '企业不存在'})
        else:
            # 新增企业
            data['create_time'] = timezone.now().timestamp()
            data['update_time'] = data['create_time']
            try:
                enterprise = Enterprise.objects.create(**data)
                logger.info(f'新增企业成功，ID：{enterprise.id}')
                return JsonResponse({'code': 0, 'msg': '保存成功'})
            except Exception as e:
                return JsonResponse({'code': 1, 'msg': str(e)})
    else:
        # GET请求返回表单页面
        detail = Enterprise.objects.get(id=id) if id else None
        return render(request, 'enterprise/enterprise_add.html',
                      {'detail': detail, 'id': id})
