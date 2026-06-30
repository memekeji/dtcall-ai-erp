# -*- coding: utf-8 -*-
"""
卡片操作视图 - 处理聊天中的快捷操作
"""
import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from rest_framework import views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.message.models import Conversation
from .services import ConversationMessageService

logger = logging.getLogger(__name__)


class CardActionView(views.APIView):
    """卡片快捷操作视图"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """执行卡片操作"""
        action = request.data.get('action')
        module = request.data.get('module')
        item_id = request.data.get('item_id')
        message_id = request.data.get('message_id')
        conversation_id = request.data.get('conversation_id')
        
        if not all([action, module, item_id]):
            return Response({'error': '参数不完整'}, status=400)
        
        user = request.user
        
        try:
            # 根据操作类型执行对应的逻辑
            if action == 'approve':
                result = self._handle_approve(user, module, item_id, request.data)
            elif action == 'claim':
                result = self._handle_claim(user, module, item_id)
            elif action == 'download':
                result = self._handle_download(user, module, item_id)
            elif action == 'preview':
                result = self._handle_preview(user, module, item_id)
            elif action == 'view':
                result = self._handle_view(user, module, item_id)
            elif action == 'comment':
                result = self._handle_comment(user, module, item_id, request.data.get('comment'))
            elif action == 'sign':
                result = self._handle_sign(user, module, item_id)
            elif action == 'update':
                result = self._handle_update(user, module, item_id, request.data)
            elif action == 'approve_finance':
                result = self._handle_approve_finance(user, module, item_id, request.data)
            elif action == 'follow':
                result = self._handle_follow(user, module, item_id, request.data)
            elif action == 'contact':
                result = self._handle_contact(user, module, item_id, request.data)
            elif action == 'complete':
                result = self._handle_complete(user, module, item_id, request.data)
            else:
                return Response({'error': f'不支持的操作: {action}'}, status=400)
            
            # 发送通知消息到对话
            if result.get('success') and conversation_id and message_id:
                self._send_notification(conversation_id, user, action, module, result)
            
            return Response(result)
        except Exception as e:
            logger.error(f'卡片操作失败: {e}', exc_info=True)
            return Response({'error': str(e), 'success': False}, status=500)
    
    def _handle_approve(self, user, module, item_id, data):
        """处理审批操作"""
        if module != 'approval':
            return {'success': False, 'message': '该模块不支持审批操作'}

        from apps.approval.models import Approval, ApprovalRecord
        from apps.approval.views import (
            _activate_next_steps,
            _cancel_pending_tasks,
            _ensure_initial_tasks,
            _get_user_pending_task,
        )

        decision = data.get('decision', 'approved')
        action = 'approve' if decision == 'approved' else 'reject'
        decision_text = '同意' if action == 'approve' else '拒绝'
        comment = (data.get('comment') or '').strip()

        try:
            approval = Approval.objects.select_related('flow').get(id=item_id)
        except Approval.DoesNotExist:
            return {'success': False, 'message': '审批单不存在'}

        if approval.status not in [0, 1]:
            return {'success': False, 'message': '该审批已处理完成，不能重复操作'}

        with transaction.atomic():
            if approval.status == 1:
                _ensure_initial_tasks(approval)
            task = _get_user_pending_task(approval, user)
            if not task:
                return {'success': False, 'message': '当前没有可处理的审批任务'}

            now = timezone.now()
            current_step = task.step
            task.status = 'completed'
            task.result = action
            task.comment = comment
            task.completed_at = now
            task.handler = user
            task.save(update_fields=['status', 'result', 'comment', 'completed_at', 'handler', 'updated_at'])

            if action == 'approve':
                step_pending_tasks = approval.tasks.filter(step=current_step, status='pending')
                if current_step.approval_mode in ('single', 'any') or current_step.step_type == 'orsign':
                    step_pending_tasks.update(
                        status='cancelled',
                        result='cancelled',
                        completed_at=now,
                        updated_at=now,
                    )
                    _activate_next_steps(approval, current_step)
                elif not step_pending_tasks.exists():
                    _activate_next_steps(approval, current_step)
            else:
                _cancel_pending_tasks(approval, 'reject', now)
                approval.status = 3
                approval.current_step_order = 0
                approval.save(update_fields=['status', 'current_step_order', 'update_time'])

            ApprovalRecord.objects.create(
                approval=approval,
                step_order=current_step.step_order,
                step_name=current_step.step_name,
                action=action,
                comment=comment,
                handler=user,
            )

        return {
            'success': True,
            'message': f'{user.name}已{decision_text}审批',
            'approval_id': int(item_id),
            'decision': decision,
            'url': f'/approval/{item_id}/',
        }
    
    def _handle_claim(self, user, module, item_id):
        """处理任务认领"""
        try:
            from apps.project.models import Task
            
            task = Task.objects.get(id=item_id)
            
            # 检查任务状态
            if task.assignee_id and task.assignee_id != user.id:
                return {'success': False, 'message': '任务已被他人认领'}
            
            if task.assignee_id == user.id:
                return {'success': False, 'message': '您已经认领过该任务'}
            
            # 认领任务
            task.assignee = user
            task.save()
            
            return {
                'success': True,
                'message': f'{user.name}已认领任务',
                'task_id': item_id,
                'task_title': task.title
            }
        except Exception as e:
            logger.error(f'任务认领失败: {e}')
            return {'success': False, 'message': f'认领失败: {str(e)}'}
    
    def _handle_download(self, user, module, item_id):
        """处理文件下载"""
        try:
            if module == 'file':
                from apps.disk.models import DiskFile
                file_obj = DiskFile.objects.get(id=item_id)
                # 检查权限
                if not self._check_file_permission(user, file_obj):
                    return {'success': False, 'message': '您没有下载该文件的权限'}
                
                file_url = file_obj.file.url if hasattr(file_obj, 'file') and file_obj.file else ''
                if not file_url and hasattr(file_obj, 'path'):
                    file_url = file_obj.path
                
                return {
                    'success': True,
                    'action': 'download',
                    'url': file_url,
                    'filename': file_obj.original_name or file_obj.name
                }
            elif module == 'contract':
                from apps.customer.models import CustomerContract
                contract = CustomerContract.objects.get(id=item_id)
                # 检查权限
                if not self._check_contract_permission(user, contract):
                    return {'success': False, 'message': '您没有下载该合同的权限'}
                
                # 获取合同文件URL
                contract_url = ''
                if hasattr(contract, 'file') and contract.file:
                    contract_url = contract.file.url
                elif hasattr(contract, 'attachment') and contract.attachment:
                    contract_url = contract.attachment.url
                
                if not contract_url:
                    return {'success': False, 'message': '该合同暂无文件'}
                
                return {
                    'success': True,
                    'action': 'download',
                    'url': contract_url,
                    'filename': f'合同_{contract.name}.pdf'
                }
            return {'success': False, 'message': '不支持下载'}
        except Exception as e:
            logger.error(f'下载失败: {e}')
            return {'success': False, 'message': f'下载失败: {str(e)}'}
    
    def _handle_preview(self, user, module, item_id):
        """处理文件预览"""
        try:
            from apps.disk.models import DiskFile
            file_obj = DiskFile.objects.get(id=item_id)
            
            # 检查权限
            if not self._check_file_permission(user, file_obj):
                return {'success': False, 'message': '您没有预览该文件的权限'}
            
            file_url = file_obj.file.url if hasattr(file_obj, 'file') and file_obj.file else ''
            if not file_url and hasattr(file_obj, 'path'):
                file_url = file_obj.path
            
            if not file_url:
                return {'success': False, 'message': '文件不存在'}
            
            # 检查文件类型是否支持预览
            filename = file_obj.original_name or file_obj.name or ''
            ext = filename.lower().split('.')[-1] if '.' in filename else ''
            previewable = ext in ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'txt', 'md', 'doc', 'docx', 'xls', 'xlsx']
            
            return {
                'success': True,
                'action': 'preview',
                'url': file_url,
                'filename': filename,
                'previewable': previewable,
                'file_type': ext
            }
        except Exception as e:
            logger.error(f'预览失败: {e}')
            return {'success': False, 'message': f'预览失败: {str(e)}'}
    
    def _handle_view(self, user, module, item_id):
        """处理查看详情"""
        metadata = self.request.data.get('metadata') or {}
        explicit_url = metadata.get('url')
        if explicit_url:
            return {
                'success': True,
                'url': explicit_url,
            }

        item_type = metadata.get('item_type')
        if module == 'project' and item_type == 'document':
            return {
                'success': True,
                'url': f'/project/document/detail/{item_id}/',
            }
        if module == 'finance' and item_type == 'invoice':
            return {
                'success': True,
                'url': f'/finance/invoice/view/{item_id}/',
            }
        if module == 'production' and item_type == 'bom':
            return {
                'success': True,
                'url': f'/production/bom/detail/{item_id}/',
            }
        if module == 'production' and item_type == 'route':
            return {
                'success': True,
                'url': f'/production/process/detail/{item_id}/',
            }

        url_map = {
            'project': f'/project/detail/{item_id}/',
            'customer': f'/customer/detail/{item_id}/',
            'contract': f'/customer/orders/{item_id}/detail/',
            'approval': f'/approval/{item_id}/',
            'task': f'/task/detail/{item_id}/',
            'file': f'/disk/file/preview/{item_id}/',
            'disk': f'/disk/file/preview/{item_id}/',
            'production': f'/production/task/plan/detail/{item_id}/',
            'finance': f'/finance/expense/view/{item_id}/'
        }
        return {
            'success': True,
            'url': url_map.get(module, '#')
        }
    
    def _handle_comment(self, user, module, item_id, comment):
        """处理评论"""
        if not comment:
            return {'success': False, 'message': '评论内容不能为空'}
        if module == 'task':
            from apps.project.models import Comment, Task

            task = Task.objects.get(id=item_id)
            task_type = ContentType.objects.get_for_model(Task)
            Comment.objects.create(
                content_type=task_type,
                object_id=task.id,
                user=user,
                content=comment,
            )
            return {
                'success': True,
                'message': f'{user.name}评论了任务: {comment[:20]}...',
                'comment': comment,
                'url': f'/task/detail/{item_id}/',
            }
        return {'success': False, 'message': '该模块不支持评论'}
    
    def _handle_sign(self, user, module, item_id):
        """处理合同签署"""
        try:
            from apps.customer.models import CustomerContract
            contract = CustomerContract.objects.get(id=item_id)

            if contract.status != 'signed':
                contract.status = 'signed'
                contract.save(update_fields=['status', 'update_time'])

            return {
                'success': True,
                'message': f'{user.name}已签署合同',
                'contract_id': item_id,
                'url': f'/customer/orders/{item_id}/detail/',
            }
        except Exception as e:
            logger.error(f'签署失败: {e}', exc_info=True)
            return {'success': False, 'message': f'签署失败: {str(e)}'}
    
    def _handle_update(self, user, module, item_id, data):
        """处理进度更新"""
        try:
            if module == 'production':
                from decimal import Decimal

                from apps.production.models import ProductionPlan

                plan = ProductionPlan.objects.get(id=item_id)
                progress = max(0, min(int(data.get('progress', 0)), 100))
                target_completed = Decimal(str(progress)) * plan.quantity / Decimal('100')

                with transaction.atomic():
                    tasks = list(plan.tasks.order_by('id'))
                    if tasks:
                        total_quantity = sum((task.quantity for task in tasks), Decimal('0'))
                        allocated = Decimal('0')
                        for index, task in enumerate(tasks):
                            if total_quantity > 0:
                                if index == len(tasks) - 1:
                                    completed_quantity = max(Decimal('0'), target_completed - allocated)
                                else:
                                    completed_quantity = (target_completed * task.quantity / total_quantity).quantize(Decimal('0.01'))
                                    allocated += completed_quantity
                            else:
                                completed_quantity = Decimal('0')

                            completed_quantity = min(task.quantity, max(Decimal('0'), completed_quantity))
                            task.completed_quantity = completed_quantity

                            if completed_quantity <= 0:
                                task.status = 1
                                task.actual_end_time = None
                            elif completed_quantity >= task.quantity:
                                task.status = 3
                                if not task.actual_start_time:
                                    task.actual_start_time = timezone.now()
                                task.actual_end_time = timezone.now()
                            else:
                                task.status = 2
                                if not task.actual_start_time:
                                    task.actual_start_time = timezone.now()
                                task.actual_end_time = None

                            task.save(update_fields=['completed_quantity', 'status', 'actual_start_time', 'actual_end_time', 'update_time'])

                    if progress <= 0:
                        plan.status = 2
                        plan.actual_start_date = None
                        plan.actual_end_date = None
                    elif progress >= 100:
                        plan.status = 4
                        if not plan.actual_start_date:
                            plan.actual_start_date = timezone.now().date()
                        plan.actual_end_date = timezone.now().date()
                    else:
                        plan.status = 3
                        if not plan.actual_start_date:
                            plan.actual_start_date = timezone.now().date()
                        plan.actual_end_date = None

                    plan.save(update_fields=['status', 'actual_start_date', 'actual_end_date', 'update_time'])

                return {
                    'success': True,
                    'message': f'{user.name}更新生产进度至{progress}%',
                    'progress': progress,
                    'url': f'/production/task/plan/detail/{item_id}/',
                }
            return {'success': False, 'message': '该模块不支持进度更新'}
        except Exception as e:
            logger.error(f'更新失败: {e}', exc_info=True)
            return {'success': False, 'message': f'更新失败: {str(e)}'}
    
    def _handle_approve_finance(self, user, module, item_id, data):
        """处理财务审核"""
        try:
            from apps.finance.models import Expense
            expense = Expense.objects.get(id=item_id)
            decision = data.get('decision', 'approved')
            comment = data.get('comment', '')

            # 更新审核状态
            if decision == 'approved':
                expense.check_status = 2
                expense.check_last_uid = str(user.id)
                expense.check_time = int(timezone.now().timestamp())
                message_text = f'{user.name}同意了报销申请'
            else:
                expense.check_status = 3
                expense.check_last_uid = str(user.id)
                expense.check_time = 0
                message_text = f'{user.name}拒绝了报销申请: {comment}'

            expense.check_history_uids = (
                f"{expense.check_history_uids},{user.id}"
                if expense.check_history_uids
                else str(user.id)
            )

            expense.save(
                update_fields=[
                    'check_status',
                    'check_last_uid',
                    'check_history_uids',
                    'check_time',
                ]
            )
            
            return {
                'success': True,
                'message': message_text,
                'decision': decision,
                'url': f'/finance/expense/view/{item_id}/',
            }
        except Exception as e:
            logger.error(f'财务审核失败: {e}', exc_info=True)
            return {'success': False, 'message': f'审核失败: {str(e)}'}
    
    def _handle_follow(self, user, module, item_id, data):
        """处理客户跟进"""
        try:
            from apps.customer.models import Customer, FollowRecord
            
            customer = Customer.objects.get(id=item_id)
            follow_content = data.get('content', '')
            
            if not follow_content:
                return {'success': False, 'message': '请输入跟进内容'}
            
            follow = FollowRecord.objects.create(
                customer=customer,
                follow_user=user,
                content=follow_content,
                follow_type=data.get('follow_type', 'other'),
            )
            
            return {
                'success': True,
                'message': f'{user.name}添加了客户跟进记录',
                'follow_id': follow.id
            }
        except Exception as e:
            logger.error(f'添加跟进记录失败: {e}', exc_info=True)
            return {'success': False, 'message': f'添加失败: {str(e)}'}
    
    def _handle_contact(self, user, module, item_id, data):
        """处理联系客户 - 创建真实沟通/跟进记录"""
        try:
            from apps.customer.models import Customer, FollowRecord

            customer = Customer.objects.get(id=item_id)
            content = (data.get('content') or '').strip()
            if not content:
                return {'success': False, 'message': '请输入沟通内容'}

            contact_type = (data.get('contact_type') or 'other').strip()
            valid_types = {choice[0] for choice in FollowRecord.FOLLOW_TYPE_CHOICES}
            if contact_type not in valid_types:
                contact_type = 'other'

            follow = FollowRecord.objects.create(
                customer=customer,
                follow_user=user,
                follow_type=contact_type,
                content=content,
            )
            follow_type_display = follow.get_follow_type_display()

            return {
                'success': True,
                'message': f'{user.name}记录了{follow_type_display}',
                'url': f'/customer/detail/{customer.id}/',
                'follow_id': follow.id,
                'follow_type': follow.follow_type,
                'follow_type_display': follow_type_display,
            }
        except Exception as e:
            logger.error(f'记录客户沟通失败: {e}', exc_info=True)
            return {'success': False, 'message': f'记录失败: {str(e)}'}
    
    def _handle_complete(self, user, module, item_id, data):
        """处理任务完成"""
        try:
            from apps.project.models import Task
            
            task = Task.objects.get(id=item_id)
            
            # 检查权限
            if task.assignee_id != user.id and not user.is_superuser:
                return {'success': False, 'message': '只有任务负责人可以完成任务'}
            
            if task.status == 3:
                return {'success': False, 'message': '任务已经完成'}
            
            task.status = 3
            task.progress = 100
            task.save(update_fields=['status', 'progress', 'update_time'])
            
            return {
                'success': True,
                'message': f'{user.name}完成了任务',
                'task_id': item_id
            }
        except Exception as e:
            logger.error(f'完成任务失败: {e}', exc_info=True)
            return {'success': False, 'message': f'操作失败: {str(e)}'}
    
    def _handle_files(self, user, module, item_id):
        """处理项目文件"""
        return {
            'success': True,
            'action': 'open_url',
            'url': f'/project/detail/{item_id}/#files'
        }
    
    def _send_notification(self, conversation_id, user, action, module, result):
        """发送操作通知到对话"""
        try:
            action_names = {
                'approve': '审批了',
                'claim': '认领了',
                'download': '下载了',
                'preview': '预览了',
                'view': '查看了',
                'comment': '评论了',
                'sign': '签署了',
                'update': '更新了',
                'approve_finance': '审核了',
                'follow': '添加了跟进记录',
                'contact': '发起了沟通',
                'complete': '完成了',
            }
            
            module_names = {
                'approval': '审批',
                'task': '任务',
                'file': '文件',
                'contract': '合同',
                'project': '项目',
                'customer': '客户',
                'production': '生产计划',
                'finance': '财务报销'
            }
            
            message_content = result.get('message', f"{user.name} {action_names.get(action, '操作了')} {module_names.get(module, '')}")
            conversation = Conversation.objects.get(id=conversation_id)
            ConversationMessageService._create_message(
                conversation,
                user,
                message_type='system',
                content=message_content,
                metadata={'type': 'card_action_notice', 'module': module, 'action': action},
            )
        except Exception as e:
            logger.error(f'发送通知失败: {e}', exc_info=True)
    
    def _check_file_permission(self, user, file_obj):
        """检查文件访问权限"""
        try:
            # 管理员可以访问所有文件
            if user.is_superuser:
                return True
            
            # 检查文件所有者
            if getattr(file_obj, 'owner_id', None) == user.id:
                return True

            if hasattr(file_obj, 'shared_users') and file_obj.shared_users.filter(id=user.id).exists():
                return True
            if getattr(file_obj, 'is_public', False):
                return True
            return False
        except Exception:
            return True  # 出错时默认允许访问
    
    def _check_contract_permission(self, user, contract):
        """检查合同访问权限"""
        try:
            # 管理员可以访问所有合同
            if user.is_superuser:
                return True
            
            # 检查合同创建者
            if hasattr(contract, 'create_user') and contract.create_user == user:
                return True
            
            customer = getattr(contract, 'customer', None)
            if customer and getattr(customer, 'principal_id', None) == user.id:
                return True

            return False
        except Exception:
            return True  # 出错时默认允许访问
