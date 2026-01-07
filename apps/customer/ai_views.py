import json
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from .models import Customer, FollowRecord, Contact
from apps.ai.utils.analysis_tools import default_customer_analysis_tool

logger = logging.getLogger(__name__)

@login_required
def ai_customer_classification(request, customer_id):
    """
    智能客户分类API
    :param request: HTTP请求对象
    :param customer_id: 客户ID
    :return: JSON响应，包含分类结果
    """
    try:
        # 获取客户信息
        customer = Customer.objects.get(id=customer_id, delete_time=0)
        
        # 获取客户的联系人信息
        contacts = Contact.objects.filter(customer=customer)
        contact_list = []
        for contact in contacts:
            contact_list.append({
                'contact_person': contact.contact_person,
                'phone': contact.phone,
                'email': contact.email,
                'position': contact.position,
                'is_primary': contact.is_primary
            })
        
        # 准备客户数据
        customer_data = {
            'id': customer.id,
            'name': customer.name,
            'customer_source': customer.customer_source_id,
            'grade': customer.grade_id,
            'industry': customer.industry_id,
            'area': f"{customer.province}{customer.city}",
            'customer_status': 0 if customer.discard_time == 0 else 1,  # 0: 正常, 1: 废弃
            'intent_status': customer.intent_status,
            'address': customer.address,
            'create_time': customer.create_time.strftime('%Y-%m-%d %H:%M:%S') if customer.create_time else '',
            'contacts': contact_list
        }
        
        # 调用AI分析工具进行客户分类
        result = default_customer_analysis_tool.classify_customer(customer_data)
        
        # 记录分析日志
        logger.info(f"客户ID {customer_id} 分类分析完成")
        
        return JsonResponse({
            'code': 0,
            'msg': '分析成功',
            'data': result
        })
        
    except Customer.DoesNotExist:
        logger.error(f"客户ID {customer_id} 不存在")
        return JsonResponse({'code': 404, 'msg': '客户不存在'}, status=404)
    except Exception as e:
        logger.error(f"客户分类分析失败: {str(e)}")
        return JsonResponse({'code': 500, 'msg': f'分析失败: {str(e)}'}, status=500)

@login_required
def ai_customer_profile(request, customer_id):
    """
    智能客户画像生成API
    :param request: HTTP请求对象
    :param customer_id: 客户ID
    :return: JSON响应，包含客户画像分析结果
    """
    try:
        # 获取客户信息
        customer = Customer.objects.get(id=customer_id, delete_time=0)
        
        # 获取客户的联系人信息
        contacts = Contact.objects.filter(customer=customer)
        contact_list = []
        for contact in contacts:
            contact_list.append({
                'contact_person': contact.contact_person,
                'phone': contact.phone,
                'email': contact.email,
                'position': contact.position,
                'is_primary': contact.is_primary
            })
        
        # 准备客户基本数据
        customer_data = {
            'id': customer.id,
            'name': customer.name,
            'customer_source': customer.customer_source_id,
            'grade': customer.grade_id,
            'industry': customer.industry_id,
            'area': f"{customer.province}{customer.city}",
            'customer_status': 0 if customer.discard_time == 0 else 1,  # 0: 正常, 1: 废弃
            'intent_status': customer.intent_status,
            'address': customer.address,
            'create_time': customer.create_time.strftime('%Y-%m-%d %H:%M:%S') if customer.create_time else '',
            'contacts': contact_list
        }
        
        # 获取最近的跟进记录（最多20条）
        follow_records = FollowRecord.objects.filter(
            customer=customer,
            delete_time=0
        ).order_by('-follow_time')[:20]
        
        follow_record_list = []
        for record in follow_records:
            follow_record_list.append({
                'follow_type': record.follow_type,
                'follow_content': record.follow_content,
                'follow_time': record.follow_time.strftime('%Y-%m-%d %H:%M:%S') if record.follow_time else '',
                'next_follow_time': record.next_follow_time.strftime('%Y-%m-%d %H:%M:%S') if record.next_follow_time else '',
                'follow_user': record.follow_user.username if record.follow_user else ''
            })
        
        # 调用AI分析工具生成客户画像
        result = default_customer_analysis_tool.generate_customer_profile(
            customer_data, follow_record_list
        )
        
        # 记录分析日志
        logger.info(f"客户ID {customer_id} 画像分析完成")
        
        return JsonResponse({
            'code': 0,
            'msg': '分析成功',
            'data': result
        })
        
    except Customer.DoesNotExist:
        logger.error(f"客户ID {customer_id} 不存在")
        return JsonResponse({'code': 404, 'msg': '客户不存在'}, status=404)
    except Exception as e:
        logger.error(f"客户画像分析失败: {str(e)}")
        return JsonResponse({'code': 500, 'msg': f'分析失败: {str(e)}'}, status=500)