import json
import logging
import time
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import MeetingRecord
from apps.ai.utils.analysis_tools import default_meeting_analysis_tool

logger = logging.getLogger(__name__)

@login_required
def ai_meeting_summary(request, meeting_id):
    """
    AI会议纪要生成API
    :param request: HTTP请求对象
    :param meeting_id: 会议记录ID
    :return: JSON响应，包含生成的会议纪要
    """
    try:
        # 获取会议记录信息
        meeting = MeetingRecord.objects.get(id=meeting_id)
        
        # 准备会议数据
        meeting_data = {
            'id': meeting.id,
            'title': meeting.title,
            'meeting_date': meeting.meeting_date.strftime('%Y-%m-%d %H:%M:%S') if meeting.meeting_date else '',
            'host_id': meeting.host_id,
            'host_name': meeting.host.username if meeting.host else '',
            'recorder_id': meeting.recorder_id,
            'recorder_name': meeting.recorder.username if meeting.recorder else '',
            'meeting_address': meeting.room.name if meeting.room else '',
            'meeting_content': meeting.content,
            'resolutions': meeting.resolution,
            'join_names': ', '.join([participant.username for participant in meeting.participants.all()]),
            'department': meeting.department.name if meeting.department else '',
            'create_time': meeting.created_at.strftime('%Y-%m-%d %H:%M:%S') if meeting.created_at else ''
        }
        
        # 调用AI分析工具生成会议纪要
        result = default_meeting_analysis_tool.generate_meeting_summary(meeting_data)
        
        # 记录分析日志
        logger.info(f"会议ID {meeting_id} 纪要生成完成")
        
        # 更新会议记录的决议内容（如果需要）
        if isinstance(result, dict) and 'resolutions' in result and result['resolutions']:
            meeting.resolution = result['resolutions']
            meeting.save()
        
        return JsonResponse({
            'code': 0,
            'msg': '会议纪要生成成功',
            'data': result
        })
        
    except MeetingRecord.DoesNotExist:
        logger.error(f"会议记录ID {meeting_id} 不存在")
        return JsonResponse({'code': 404, 'msg': '会议记录不存在'}, status=404)
    except Exception as e:
        logger.error(f"会议纪要生成失败: {str(e)}")
        return JsonResponse({'code': 500, 'msg': f'会议纪要生成失败: {str(e)}'}, status=500)

@login_required
def ai_meeting_action_items(request, meeting_id):
    """
    AI会议任务项提取API
    :param request: HTTP请求对象
    :param meeting_id: 会议记录ID
    :return: JSON响应，包含提取的任务项
    """
    try:
        # 获取会议记录信息
        meeting = MeetingRecord.objects.get(id=meeting_id)
        
        # 准备会议数据
        meeting_data = {
            'id': meeting.id,
            'title': meeting.title,
            'meeting_content': meeting.content,
            'resolutions': meeting.resolution,
            'host_name': meeting.host.username if meeting.host else '',
            'join_names': ', '.join([participant.username for participant in meeting.participants.all()])
        }
        
        # 调用AI分析工具提取任务项
        result = default_meeting_analysis_tool.extract_action_items(meeting_data)
        
        # 记录分析日志
        logger.info(f"会议ID {meeting_id} 任务项提取完成")
        
        return JsonResponse({
            'code': 0,
            'msg': '任务项提取成功',
            'data': result
        })
        
    except MeetingRecord.DoesNotExist:
        logger.error(f"会议记录ID {meeting_id} 不存在")
        return JsonResponse({'code': 404, 'msg': '会议记录不存在'}, status=404)
    except Exception as e:
        logger.error(f"任务项提取失败: {str(e)}")
        return JsonResponse({'code': 500, 'msg': f'任务项提取失败: {str(e)}'}, status=500)