import logging
from apps.customer.models import Customer, Contact
from apps.project.models import Project, Task
from apps.oa.models import MeetingRecord
from apps.finance.models import Expense
from apps.ai.utils.ai_client import AIClient, AIClientError
from apps.ai.models import AITask
from apps.common.utils import timestamp_to_date

logger = logging.getLogger(__name__)


def _display_or_attr(obj, display_method, *attr_names, default=''):
    method = getattr(obj, display_method, None)
    if callable(method):
        try:
            return method()
        except Exception:
            pass

    for attr_name in attr_names:
        value = getattr(obj, attr_name, None)
        if value not in (None, ''):
            return value
    return default


def _format_date(value, fmt='%Y-%m-%d'):
    if not value:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime(fmt)
    return str(value)


def _customer_status_text(customer):
    display = _display_or_attr(customer, 'get_status_display')
    if display:
        return display
    if getattr(customer, 'discard_time', 0):
        return '已废弃'
    if getattr(customer, 'belong_uid', 0):
        return '已分配'
    return '公海客户'


def _build_customer_follow_info(customer, limit=5):
    follow_manager = getattr(customer, 'follow_records', None)
    if not follow_manager:
        return ''

    try:
        records = follow_manager.filter(delete_time=0).order_by('-follow_time')[:limit]
    except Exception:
        try:
            records = follow_manager.all()[:limit]
        except Exception:
            return ''

    lines = []
    for record in records:
        content = getattr(record, 'content', None) or getattr(record, 'follow_content', '')
        if not content:
            continue
        follow_type = _display_or_attr(record, 'get_follow_type_display', 'follow_type', default='跟进')
        follow_time = _format_date(getattr(record, 'follow_time', None), '%Y-%m-%d %H:%M')
        follow_user = getattr(record, 'follow_user', None)
        follow_user_name = getattr(follow_user, 'username', '') or getattr(follow_user, 'name', '')
        lines.append(f"- {follow_time} {follow_type} {follow_user_name}：{content}")

    if not lines:
        return ''
    return "最近跟进记录：\n" + "\n".join(lines) + "\n"


class AIAnalysisService:
    """AI分析服务"""

    @classmethod
    def analyze_customer(cls, user, customer_id, **kwargs):
        """客户智能分析"""
        try:
            # 获取客户信息
            customer = Customer.objects.get(id=customer_id)
            contacts = Contact.objects.filter(customer=customer)

            # 构建客户信息文本
            owner = getattr(customer, 'principal', None) or getattr(customer, 'owner', None)
            owner_name = getattr(owner, 'username', '') if owner else '未分配'
            description = (
                getattr(customer, 'content', None) or
                getattr(customer, 'description', None) or
                getattr(customer, 'remark', '')
            )
            customer_info = f"客户名称：{customer.name}\n"\
                f"客户来源/类型：{_display_or_attr(customer, 'get_customer_type_display', 'customer_source_id', default='')}\n"\
                f"所在地区：{getattr(customer, 'province', '')}{getattr(customer, 'city', '')}{getattr(customer, 'district', '')}\n"\
                f"创建时间：{_format_date(getattr(customer, 'create_time', None) or getattr(customer, 'created_at', None))}\n"\
                f"客户状态：{_customer_status_text(customer)}\n"\
                f"所属销售人员：{owner_name}\n"\
                f"客户描述：{description}\n"

            # 添加联系人信息
            contact_info = "联系人信息：\n"
            for contact in contacts:
                contact_name = getattr(contact, 'contact_person', None) or getattr(contact, 'name', '')
                contact_info += f"- {contact_name}（{getattr(contact, 'position', '')}），电话：{getattr(contact, 'phone', '')}，邮箱：{getattr(contact, 'email', '')}\n"

            follow_info = _build_customer_follow_info(customer)

            # 构建分析请求
            prompt = f"请分析以下客户信息，并提供客户画像、需求预测和跟进建议：\n\n{customer_info}{contact_info}{follow_info}"

            # 调用AI客户端
            ai_client = AIClient()
            result = ai_client.generate_content(prompt, **kwargs)

            # 保存AI任务记录
            ai_task = AITask.objects.create(
                user=user,
                task_type='customer_analysis',
                task_params={'customer_id': customer_id},
                status='completed',
                result={'analysis': result},
                started_at=kwargs.get('started_at'),
                completed_at=kwargs.get('completed_at')
            )

            return {
                'success': True,
                'analysis': result,
                'task_id': ai_task.id
            }

        except Customer.DoesNotExist:
            logger.error(f"客户ID {customer_id} 不存在")
            return {'success': False, 'error': '客户不存在'}
        except AIClientError as e:
            logger.error(f"AI客户分析失败: {str(e)}")
            return {'success': False, 'error': 'AI客户分析失败，请检查模型配置后重试'}
        except Exception as e:
            logger.error(f"客户分析过程中发生错误: {str(e)}")
            return {'success': False, 'error': '分析过程中发生错误'}

    @classmethod
    def generate_meeting_minutes(
            cls,
            user,
            meeting_id,
            transcript_content=None,
            **kwargs):
        """生成会议纪要"""
        try:
            # 获取会议记录
            meeting = MeetingRecord.objects.get(id=meeting_id)

            # 构建会议信息文本
            meeting_info = f"会议主题：{meeting.title}\n" + \
                f"会议时间：{meeting.meeting_date.strftime('%Y-%m-%d %H:%M:%S') if meeting.meeting_date else '待确认'}\n" + \
                f"会议地点：{meeting.location}\n" + \
                f"主持人：{meeting.host.username if meeting.host else '未知'}\n" + \
                f"记录人：{meeting.recorder.username if meeting.recorder else '未知'}\n" + \
                f"参会人员：{', '.join([user.username for user in meeting.participants.all()]) if meeting.participants.exists() else '暂无'}\n"

            # 检查是否有语音转文字内容
            if transcript_content and transcript_content.strip():
                # 使用真实的语音转文字内容
                content_to_analyze = f"{meeting_info}会议语音转文字内容：\n{transcript_content}"
                prompt = f"请根据以下会议信息和语音转文字内容，生成结构化的会议纪要，包含：1.会议基本信息 2.会议主要内容（基于语音内容） 3.决策事项 4.行动项（含负责人和截止时间） 5.下一步计划\n\n{content_to_analyze}"
            else:
                # 如果没有语音内容，使用会议记录内容
                content_to_analyze = f"{meeting_info}会议记录内容：{meeting.content if meeting.content else '暂无详细内容'}"
                prompt = f"请根据以下会议信息生成结构化的会议纪要，包含：1.会议基本信息 2.会议主要内容 3.决策事项 4.行动项（含负责人和截止时间） 5.下一步计划\n\n{content_to_analyze}"

            # 调用AI客户端
            ai_client = AIClient()
            minutes = ai_client.generate_content(prompt, **kwargs)

            # 保存AI任务记录
            ai_task = AITask.objects.create(
                user=user,
                task_type='meeting_minutes',
                task_params={
                    'meeting_id': meeting_id,
                    'has_transcript': bool(transcript_content)},
                status='completed',
                result={
                    'minutes': minutes},
                started_at=kwargs.get('started_at'),
                completed_at=kwargs.get('completed_at'))

            return {
                'success': True,
                'minutes': minutes,
                'task_id': ai_task.id,
                'used_transcript': bool(transcript_content)
            }

        except MeetingRecord.DoesNotExist:
            logger.error(f"会议记录ID {meeting_id} 不存在")
            return {'success': False, 'error': '会议记录不存在'}
        except AIClientError as e:
            logger.error(f"AI会议纪要生成失败: {str(e)}")
            return {'success': False, 'error': 'AI会议纪要生成失败，请检查模型配置后重试'}
        except Exception as e:
            logger.error(f"会议纪要生成过程中发生错误: {str(e)}")
            return {'success': False, 'error': '生成过程中发生错误'}

    @classmethod
    def assess_project_risk(cls, user, project_id, **kwargs):
        """项目风险评估"""
        try:
            # 获取项目信息
            project = Project.objects.get(id=project_id)
            tasks = Task.objects.filter(project=project)

            # 构建项目信息文本
            project_info = f"项目名称：{project.name}\n"\
                f"项目分类：{project.category.name if project.category else '未分类'}\n"\
                f"项目负责人：{project.manager.username if project.manager else '未分配'}\n"\
                f"开始日期：{project.start_date.strftime('%Y-%m-%d') if project.start_date else '未设置'}\n"\
                f"预计结束日期：{project.end_date.strftime('%Y-%m-%d') if project.end_date else '未设置'}\n"\
                f"实际结束日期：{_format_date(getattr(project, 'completed_date', None), '%Y-%m-%d') or '未完成'}\n"\
                f"项目状态：{_display_or_attr(project, 'get_status_display', 'status_display', default=getattr(project, 'status', ''))}\n"\
                f"项目描述：{project.description}\n"\
                f"预算金额：{project.budget}\n"\
                f"实际成本：{getattr(project, 'actual_cost', getattr(project, 'spent', 0))}\n"

            # 添加任务信息
            task_info = "项目任务：\n"
            for task in tasks:
                task_status = _display_or_attr(task, 'get_status_display', 'status_display', default=getattr(task, 'status', ''))
                task_due_value = getattr(task, 'due_date', None) or getattr(task, 'end_date', None)
                task_due = task_due_value.strftime('%Y-%m-%d') if task_due_value else '未设置'
                task_info += f"- {task.title}（状态：{task_status}，截止日期：{task_due}）\n"

            # 构建AI请求
            prompt = f"请根据以下项目信息，进行风险评估，包括：1.风险等级（高、中、低） 2.主要风险点 3.风险原因分析 4.应对建议\n\n{project_info}{task_info}"

            # 调用AI客户端
            ai_client = AIClient()
            risk_assessment = ai_client.generate_content(prompt, **kwargs)

            # 保存AI任务记录
            ai_task = AITask.objects.create(
                user=user,
                task_type='project_risk',
                task_params={'project_id': project_id},
                status='completed',
                result={'risk_assessment': risk_assessment},
                started_at=kwargs.get('started_at'),
                completed_at=kwargs.get('completed_at')
            )

            return {
                'success': True,
                'risk_assessment': risk_assessment,
                'task_id': ai_task.id
            }

        except Project.DoesNotExist:
            logger.error(f"项目ID {project_id} 不存在")
            return {'success': False, 'error': '项目不存在'}
        except AIClientError as e:
            logger.error(f"AI项目风险评估失败: {str(e)}")
            return {'success': False, 'error': 'AI项目风险评估失败，请检查模型配置后重试'}
        except Exception as e:
            logger.error(f"项目风险评估过程中发生错误: {str(e)}")
            return {'success': False, 'error': '评估过程中发生错误'}

    @classmethod
    def audit_expense(cls, user, expense_id, **kwargs):
        """报销单智能审核"""
        try:
            # 获取报销单信息
            expense = Expense.objects.get(id=expense_id)

            # 构建报销单信息文本
            expense_info = f"报销人：{expense.user.username if hasattr(expense, 'user') else '未知'}\n"\
                f"报销金额：{expense.cost}\n"\
                f"报销日期：{timestamp_to_date(expense.expense_time) if expense.expense_time else '未设置'}\n"\
                f"提交日期：{timestamp_to_date(expense.create_time) if expense.create_time else '未设置'}\n"\
                f"报销事由：{expense.remark}\n"\
                f"当前状态：{expense.get_check_status_display()}\n"

            # 构建AI请求
            prompt = f"请根据以下报销单信息，进行智能审核，包括：1.审核建议（通过/驳回/需补充材料） 2.审核理由 3.异常项说明（如有）\n\n{expense_info}"

            # 调用AI客户端
            ai_client = AIClient()
            audit_result = ai_client.generate_content(prompt, **kwargs)

            # 保存AI任务记录
            ai_task = AITask.objects.create(
                user=user,
                task_type='expense_audit',
                task_params={'expense_id': expense_id},
                status='completed',
                result={'audit_result': audit_result},
                started_at=kwargs.get('started_at'),
                completed_at=kwargs.get('completed_at')
            )

            return {
                'success': True,
                'audit_result': audit_result,
                'task_id': ai_task.id
            }

        except Expense.DoesNotExist:
            logger.error(f"报销单ID {expense_id} 不存在")
            return {'success': False, 'error': '报销单不存在'}
        except AIClientError as e:
            logger.error(f"AI报销单审核失败: {str(e)}")
            return {'success': False, 'error': 'AI报销单审核失败，请检查模型配置后重试'}
        except Exception as e:
            logger.error(f"报销单审核过程中发生错误: {str(e)}")
            return {'success': False, 'error': '审核过程中发生错误'}

    @classmethod
    def summarize_document(
            cls,
            user,
            document_content,
            document_type='通用文档',
            **kwargs):
        """文档智能摘要"""
        try:
            # 构建AI请求
            prompt = f"请对以下{document_type}内容生成简洁的摘要，包含主要观点、关键信息和核心结论：\n\n{document_content}"

            # 调用AI客户端
            ai_client = AIClient()
            summary = ai_client.summarize_text(prompt, **kwargs)

            # 保存AI任务记录
            ai_task = AITask.objects.create(
                user=user,
                task_type='document_summary',
                task_params={'document_type': document_type},
                status='completed',
                result={'summary': summary},
                started_at=kwargs.get('started_at'),
                completed_at=kwargs.get('completed_at')
            )

            return {
                'success': True,
                'summary': summary,
                'task_id': ai_task.id
            }

        except AIClientError as e:
            logger.error(f"AI文档摘要生成失败: {str(e)}")
            return {'success': False, 'error': 'AI文档摘要生成失败，请检查模型配置后重试'}
        except Exception as e:
            logger.error(f"文档摘要生成过程中发生错误: {str(e)}")
            return {'success': False, 'error': '摘要生成过程中发生错误'}
