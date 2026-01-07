from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from .models import Expense
import json
from django.shortcuts import get_object_or_404

# 导入AI分析工具
from apps.ai.utils.analysis_tools import default_expense_analysis_tool

class AIExpenseReviewView(LoginRequiredMixin, View):
    """AI辅助报销审核视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    @method_decorator(csrf_exempt)
    def post(self, request):
        try:
            # 获取报销单ID
            data = json.loads(request.body)
            expense_id = data.get('expense_id')
            user_comment = data.get('comment', '')
            
            # 获取报销单详情
            expense = get_object_or_404(Expense, id=expense_id)
            
            # 准备报销数据用于AI分析
            expense_data = {
                'id': expense.id,
                'code': expense.code,
                'cost': float(expense.cost),
                'income_month': expense.income_month,
                'expense_time': expense.expense_time,
                'subject_id': expense.subject_id,
                'remark': expense.remark,
                'file_ids': expense.file_ids,
                'admin_id': expense.admin_id,
                'check_status': expense.check_status,
                'pay_status': expense.pay_status,
                'check_uids': expense.check_uids,
                'check_history_uids': expense.check_history_uids,
                'check_copy_uids': expense.check_copy_uids,
                'create_time': expense.create_time
            }
            
            # 调用AI分析工具进行智能审核
            analysis_result = default_expense_analysis_tool.analyze_expense(
                expense_data=expense_data,
                user_comment=user_comment,
                user_id=request.user.id
            )
            
            # 返回AI审核建议
            return JsonResponse({
                'code': 0,
                'data': analysis_result
            })
        except Exception as e:
            return JsonResponse({
                'code': 1,
                'msg': f'AI分析失败: {str(e)}'
            })

class AIExpenseAnomalyDetectionView(LoginRequiredMixin, View):
    """异常报销检测视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    @method_decorator(csrf_exempt)
    def post(self, request):
        try:
            # 获取报销单ID
            data = json.loads(request.body)
            expense_id = data.get('expense_id')
            
            # 获取报销单详情
            expense = get_object_or_404(Expense, id=expense_id)
            
            # 准备报销数据用于异常检测
            expense_data = {
                'id': expense.id,
                'code': expense.code,
                'cost': float(expense.cost),
                'income_month': expense.income_month,
                'expense_time': expense.expense_time,
                'subject_id': expense.subject_id,
                'remark': expense.remark,
                'file_ids': expense.file_ids,
                'admin_id': expense.admin_id,
                'create_time': expense.create_time
            }
            
            # 调用AI分析工具进行异常检测
            detection_result = default_expense_analysis_tool.detect_anomalies(
                expense_data=expense_data,
                user_id=request.user.id
            )
            
            # 返回异常检测结果
            return JsonResponse({
                'code': 0,
                'data': detection_result
            })
        except Exception as e:
            return JsonResponse({
                'code': 1,
                'msg': f'异常检测失败: {str(e)}'
            })

# 提供单个报销单的AI审核建议（GET请求）
def ai_expense_review(request, expense_id):
    """获取单个报销单的AI审核建议"""
    try:
        # 获取报销单详情
        expense = get_object_or_404(Expense, id=expense_id)
        
        # 准备报销数据用于AI分析
        expense_data = {
            'id': expense.id,
            'code': expense.code,
            'cost': float(expense.cost),
            'income_month': expense.income_month,
            'expense_time': expense.expense_time,
            'subject_id': expense.subject_id,
            'remark': expense.remark,
            'file_ids': expense.file_ids,
            'admin_id': expense.admin_id,
            'check_status': expense.check_status,
            'pay_status': expense.pay_status,
            'check_uids': expense.check_uids,
            'check_history_uids': expense.check_history_uids,
            'check_copy_uids': expense.check_copy_uids,
            'create_time': expense.create_time
        }
        
        # 调用AI分析工具进行智能审核
        analysis_result = default_expense_analysis_tool.analyze_expense(
            expense_data=expense_data,
            user_comment='',
            user_id=request.user.id
        )
        
        # 返回AI审核建议
        return JsonResponse({
            'code': 0,
            'data': analysis_result
        })
    except Exception as e:
        return JsonResponse({
            'code': 1,
            'msg': f'AI分析失败: {str(e)}'
        })

# 提供单个报销单的异常检测结果（GET请求）
def ai_expense_anomaly_detection(request, expense_id):
    """获取单个报销单的异常检测结果"""
    try:
        # 获取报销单详情
        expense = get_object_or_404(Expense, id=expense_id)
        
        # 准备报销数据用于异常检测
        expense_data = {
            'id': expense.id,
            'code': expense.code,
            'cost': float(expense.cost),
            'income_month': expense.income_month,
            'expense_time': expense.expense_time,
            'subject_id': expense.subject_id,
            'remark': expense.remark,
            'file_ids': expense.file_ids,
            'admin_id': expense.admin_id,
            'create_time': expense.create_time
        }
        
        # 调用AI分析工具进行异常检测
        detection_result = default_expense_analysis_tool.detect_anomalies(
            expense_data=expense_data,
            user_id=request.user.id
        )
        
        # 返回异常检测结果
        return JsonResponse({
            'code': 0,
            'data': detection_result
        })
    except Exception as e:
        return JsonResponse({
            'code': 1,
            'msg': f'异常检测失败: {str(e)}'
        })