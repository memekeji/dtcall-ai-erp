from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import Schedule, Approval
from .models import MeetingRoom, MeetingRecord
from .utils import get_admin, get_leader_departments, is_leader, is_auth, value_auth
from django.db.models import Q
import json
import time
from datetime import datetime
from django.utils import timezone  # 添加时区支持
from django.views import View
from django.views.generic import ListView, DetailView
from apps.user.models import Admin as User
from apps.project.models import Project, Task
from apps.work.models import WorkCate
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import logging
import os
import uuid

logger = logging.getLogger(__name__)
# 导入会议纪要模型
from apps.personal.models import MeetingMinutes

from django.contrib.auth.mixins import LoginRequiredMixin

class ScheduleAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    def get(self, request):
        return render(request, 'oa/schedule/add.html')
        
    def post(self, request):
        params = json.loads(request.body)
        admin_id = request.user.id
        
        start_time = datetime.strptime(params['start_time'], '%Y-%m-%d %H:%M')
        end_time = datetime.strptime(params['end_time'], '%Y-%m-%d %H:%M')
        
        if start_time > timezone.now():
            return JsonResponse({'code': 1, 'msg': "开始时间不能大于现在时间"})
            
        if end_time <= start_time:
            return JsonResponse({'code': 1, 'msg': "结束时间需要大于开始时间"})
            
        if end_time.date() != start_time.date():
            return JsonResponse({'code': 1, 'msg': "结束时间与开始时间必须是同一天"})
            
        # 检查时间冲突
        conflict = Schedule.objects.filter(
            Q(deleted_at=None, admin_id=admin_id) &
            (
                Q(start_time__range=(start_time, end_time)) |
                Q(end_time__range=(start_time, end_time)) |
                Q(start_time__lte=start_time, end_time__gte=end_time)
            )
        ).exists()
        
        if conflict:
            return JsonResponse({'code': 1, 'msg': "您所选的时间区间已有工作记录，请重新选时间"})
            
        labor_time = (end_time - start_time).total_seconds() / 3600
        schedule = Schedule.objects.create(
            title=params['title'],
            start_time=start_time,
            end_time=end_time,
            labor_time=labor_time,
            admin_id=admin_id,
            did=get_admin(admin_id)['did'],
            labor_type=params.get('labor_type', 1),
            cid=params.get('cid'),
            tid=params.get('tid'),
            content=params.get('content', '')
        )
        return JsonResponse({'code': 0, 'msg': '操作成功', 'data': {'aid': schedule.id}}, json_dumps_params={'ensure_ascii': False})

class MeetingView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request, *args, **kwargs):
        if 'pk' in kwargs:
            return self.retrieve(request, kwargs['pk'])
        return self.list(request)
    
    def post(self, request, *args, **kwargs):
        if request.path.endswith('update_summary/'):
            return self.update_summary(request)
        return JsonResponse({'code': 1, 'msg': '不支持的请求方式'})
    
    def list(self, request):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            params = json.loads(request.body)
            query = Q(deleted_at=None)
            
            if params.get('keywords'):
                query &= Q(title__icontains=params['keywords'])
                
            if params.get('host_id'):
                query &= Q(host_id=params['host_id']) | Q(host=params['host_id'])  # 兼容新旧数据
                
            if params.get('diff_time'):
                start, end = params['diff_time'].split('~')
                start_date = datetime.strptime(start.strip(), '%Y-%m-%d')
                end_date = datetime.strptime(end.strip() + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
                query &= Q(meeting_date__range=(start_date, end_date))
                
            uid = request.user.id
            query &= (
                    Q(recorder_id=uid) | 
                    Q(host=uid) |     # 使用正确的ForeignKey字段
                    Q(participants__id=uid) |
                    Q(attendees__id=uid) |
                    Q(shared_users__id=uid)
                )
            
            meetings = MeetingRecord.objects.filter(query)
            # 构建响应数据
            data = []
            for meeting in meetings:
                data.append({
                    'id': meeting.id,
                    'title': meeting.title,
                    'meeting_date': meeting.meeting_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'host_id': meeting.host.id if meeting.host else None,
                    'host_name': meeting.host.username if meeting.host else '',
                    'recorder_id': meeting.recorder_id,
                    'recorder_name': meeting.recorder.username if meeting.recorder else '',
                    'room': meeting.room.name if meeting.room else '',
                    'join_names': ', '.join([p.username for p in meeting.participants.all()]),
                    'content': meeting.content,
                    'summary': meeting.summary,
                    'resolution': meeting.resolution,
                    'audio_file': meeting.audio_file.url if meeting.audio_file else ''
                })
            return JsonResponse({
                'code': 0,
                'msg': '',
                'data': data
            })
        return render(request, 'oa/meeting/list.html')
    
    def retrieve(self, request, pk):
        try:
            meeting = MeetingRecord.objects.get(id=pk)
            # 检查用户权限
            uid = request.user.id
            if not (
                meeting.recorder_id == uid or 
                meeting.host.id == uid or
                meeting.participants.filter(id=uid).exists() or
                meeting.shared_users.filter(id=uid).exists()
            ):
                return JsonResponse({'code': 1, 'msg': '无权限查看此会议'})
            
            # 构造返回数据
            data = {
                'id': meeting.id,
                'title': meeting.title,
                'meeting_date': meeting.meeting_date.strftime('%Y-%m-%d %H:%M:%S'),
                'host_id': meeting.host.id if meeting.host else None,
                'host_name': meeting.host.username if meeting.host else '',
                'recorder_id': meeting.recorder_id,
                'recorder_name': meeting.recorder.username if meeting.recorder else '',
                'room': meeting.room.name if meeting.room else '',
                'join_names': ', '.join([participant.username for participant in meeting.participants.all()]),
                'content': meeting.content,
                'summary': meeting.summary,
                'resolution': meeting.resolution,
                'action_items': meeting.action_items.split(';') if meeting.action_items else [],
                'audio_file': meeting.audio_file.url if meeting.audio_file else ''
            }
            
            # 如果是AJAX请求，返回JSON数据
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'code': 0, 'msg': '', 'data': data})
            
            # 查询与当前会议记录关联的所有会议纪要
            meeting_minutes = MeetingMinutes.objects.filter(meeting_record=meeting).order_by('-created_at')
            
            # 否则返回HTML页面
            context = {'detail': meeting, 'meeting_minutes': meeting_minutes}
            return render(request, 'meeting/records_view.html', context)
        except MeetingRecord.DoesNotExist:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'code': 1, 'msg': '会议不存在'})
            return render(request, '404.html')
    
    def update_summary(self, request):
        try:
            params = json.loads(request.body)
            meeting_id = params.get('meeting_id')
            summary = params.get('summary', '')
            resolution = params.get('resolution', '')
            
            if not meeting_id:
                return JsonResponse({'code': 1, 'msg': '会议ID不能为空'})
            
            meeting = MeetingRecord.objects.get(id=meeting_id)
            
            # 检查用户权限
            uid = request.user.id
            if meeting.recorder_id != uid and (meeting.host and meeting.host.id != uid):
                return JsonResponse({'code': 1, 'msg': '无权限编辑此会议纪要'})
            
            # 更新会议纪要和决议
            meeting.summary = summary
            meeting.resolution = resolution
            meeting.save()
            
            return JsonResponse({'code': 0, 'msg': '会议纪要更新成功'})
        except MeetingRecord.DoesNotExist:
            return JsonResponse({'code': 1, 'msg': '会议不存在'})
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': str(e)})

    # 保留旧的静态方法以保持向后兼容
    @staticmethod
    def datalist(request):
        return MeetingView().list(request)
    
    @staticmethod
    def view(request, id):
        return MeetingView().retrieve(request, id)

class MeetingApplyView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        # 获取所有可用会议室
        from apps.system.models import MeetingRoom
        rooms = MeetingRoom.objects.filter(status=1)
        return render(request, 'oa/meeting/apply.html', {'rooms': rooms})

    def post(self, request):
        try:
            # 获取表单数据
            title = request.POST.get('title')
            meeting_type = request.POST.get('meeting_type', 'regular')
            meeting_date = request.POST.get('meeting_date')
            end_time_str = request.POST.get('end_time')
            room_id = request.POST.get('room_id')
            join_uids = request.POST.get('join_uids')
            content = request.POST.get('content')

            # 验证必填字段
            if not all([title, meeting_date, end_time_str, title]):
                return JsonResponse({'code': 1, 'msg': '请填写所有必填字段'})

            # 解析日期时间
            meeting_datetime = datetime.strptime(meeting_date, '%Y-%m-%d %H:%M:%S')
            end_datetime = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')

            # 检查时间是否合理
            if meeting_datetime >= end_datetime:
                return JsonResponse({'code': 1, 'msg': '会议结束时间必须晚于开始时间'})

            # 处理音频文件上传（如果有）
            audio_file_path = ''
            if 'audio_file' in request.FILES:
                audio_file = request.FILES['audio_file']
                # 验证文件类型
                import os
                file_extension = audio_file.name.split('.')[-1].lower()
                allowed_extensions = ['mp3', 'wav', 'flac', 'ogg', 'aac']
                if file_extension not in allowed_extensions:
                    return JsonResponse({'code': 1, 'msg': '不支持的音频格式，请上传MP3、WAV、FLAC、OGG或AAC格式'})

                # 确保目录存在
                from django.conf import settings
                import uuid
                audio_dir = os.path.join(settings.MEDIA_ROOT, 'meeting_recordings')
                os.makedirs(audio_dir, exist_ok=True)

                # 保存文件
                filename = f"{uuid.uuid4()}.{file_extension}"
                file_path = os.path.join(audio_dir, filename)
                with open(file_path, 'wb+') as destination:
                    for chunk in audio_file.chunks():
                        destination.write(chunk)

                # 存储相对路径
                audio_file_path = f"meeting_recordings/{filename}"

            # 创建会议室预订
            from apps.system.models import MeetingRoom, MeetingReservation
            from django.contrib.auth import get_user_model
            User = get_user_model()

            reservation = MeetingReservation()
            reservation.title = title
            reservation.start_time = meeting_datetime
            reservation.end_time = end_datetime
            reservation.description = content
            reservation.organizer = request.user
            reservation.status = 'pending'  # 初始状态为待批准

            # 设置会议室
            if room_id:
                try:
                    room = MeetingRoom.objects.get(id=room_id)
                    reservation.meeting_room = room
                except MeetingRoom.DoesNotExist:
                    return JsonResponse({'code': 1, 'msg': '会议室不存在'})

            reservation.save()

            # 添加参会人员
            if join_uids:
                user_ids = [int(uid) for uid in join_uids.split(',') if uid]
                for user_id in user_ids:
                    try:
                        participant = User.objects.get(id=user_id)
                        reservation.attendees.add(participant)
                    except User.DoesNotExist:
                        continue

            reservation.save()

            # 如果有音频文件，创建临时存储（实际记录将在预订批准后创建）
            if audio_file_path:
                # 这里可以将音频文件保存到一个临时位置，或在预订批准后再处理
                from django.conf import settings
                import json
                import os
                
                # 创建预订相关数据的临时存储
                temp_data_file = os.path.join(settings.MEDIA_ROOT, 'temp_reservation_data', f'{reservation.id}.json')
                os.makedirs(os.path.dirname(temp_data_file), exist_ok=True)
                
                with open(temp_data_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'audio_file_path': audio_file_path,
                        'meeting_type': meeting_type
                    }, f, ensure_ascii=False)

            # 返回预订成功信息，提示用户等待审批
            return JsonResponse({
                'code': 0, 
                'msg': '会议预订已提交，等待管理员审批', 
                'data': {
                    'reservation_id': reservation.id
                }
            })

        except Exception as e:
            logger.error(f"Error in MeetingApplyView.post: {str(e)}")
            return JsonResponse({'code': 1, 'msg': f'会议预订失败: {str(e)}'})

# 会议纪要视图
class MeetingListView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        try:
            # 安全查询 - 使用values()方法明确指定要获取的字段，避免触发room_id字段访问
            # 完全避免任何可能访问room或room_id的操作
            user = request.user
            
            # 定义要获取的字段列表，只包含模型中实际存在的字段
            fields = ['id', 'title', 'meeting_date', 'status']
            
            # 获取所有已完成的会议 - 使用正确的模型
            completed_meetings_query = MeetingRecord.objects.filter(
                deleted_at=None,
                status='completed',
                host=user
            ).values(*fields)
            
            # 转换为字典列表并手动添加所需信息
            completed_meetings = []
            for meeting in completed_meetings_query:
                # 安全地处理所有字段，避免任何可能的数据库错误
                safe_meeting = {
                    'id': meeting.get('id', ''),
                    'title': meeting.get('title', ''),
                    'meeting_date': meeting.get('meeting_date', ''),
                    'status': meeting.get('status', ''),
                    'host_name': '未知',  # 安全默认值
                    'room_name': ''  # 完全避免访问room字段
                }
                completed_meetings.append(safe_meeting)
            
            # 获取所有进行中的会议 - 使用正确的模型
            in_progress_meetings_query = MeetingRecord.objects.filter(
                deleted_at=None,
                status='in_progress',
                host=user
            ).values(*fields)
            
            in_progress_meetings = []
            for meeting in in_progress_meetings_query:
                safe_meeting = {
                    'id': meeting.get('id', ''),
                    'title': meeting.get('title', ''),
                    'meeting_date': meeting.get('meeting_date', ''),
                    'status': meeting.get('status', ''),
                    'host_name': '未知',
                    'room_name': ''
                }
                in_progress_meetings.append(safe_meeting)
            
            # 获取所有即将开始的会议 - 使用正确的模型
            upcoming_meetings_query = MeetingRecord.objects.filter(
                deleted_at=None,
                status='scheduled',
                host=user
            ).values(*fields)
            
            upcoming_meetings = []
            for meeting in upcoming_meetings_query:
                safe_meeting = {
                    'id': meeting.get('id', ''),
                    'title': meeting.get('title', ''),
                    'meeting_date': meeting.get('meeting_date', ''),
                    'status': meeting.get('status', ''),
                    'host_name': '未知',
                    'room_name': ''
                }
                upcoming_meetings.append(safe_meeting)
            
            context = {
                'completed_meetings': completed_meetings,
                'in_progress_meetings': in_progress_meetings,
                'upcoming_meetings': upcoming_meetings
            }
            
            # 使用存在的模板文件
            return render(request, 'personal/minutes/list.html', context)

        except Exception as e:
            # 导入必要的模块以避免潜在的导入错误
            import logging
            from django.contrib import messages
            
            # 记录详细错误信息到日志
            logging.error(f"获取会议列表数据库操作失败: {str(e)}", exc_info=True)
            
            # 显示友好的错误消息
            messages.error(request, '获取会议记录失败，请稍后再试')
            
            # 返回空列表和适当的提示
            return render(request, 'personal/minutes/list.html', {
                'completed_meetings': [],
                'in_progress_meetings': [],
                'upcoming_meetings': [],
                'show_empty_state': True
            })

class MeetingMinutesView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        meeting_id = request.GET.get('id')
        
        if meeting_id:
            try:
                # 获取会议记录信息
                from apps.oa.models import MeetingRecord
                meeting = MeetingRecord.objects.get(id=meeting_id)
                
                # 检查当前用户是否有权限创建该会议的纪要
                if meeting.host != request.user and meeting.recorder != request.user and not meeting.participants.filter(id=request.user.id).exists():
                    messages.warning(request, '您没有权限为该会议创建纪要')
                    return redirect('/oa/meeting/list/')
                
                # 检查是否已经存在该会议的纪要
                from apps.personal.models import MeetingMinutes
                existing_minutes = MeetingMinutes.objects.filter(meeting_record_id=meeting_id).first()
                
                # 准备初始数据，添加错误处理以避免room_id字段问题
                initial_data = {
                    'title': meeting.title,
                    'meeting_type': meeting.meeting_type,
                    'meeting_date': meeting.meeting_date,
                    'location': meeting.location or '',  # 避免访问room字段
                    'host': meeting.host.username if meeting.host else '',
                    'attendees': ', '.join([user.username for user in meeting.participants.all()]) if meeting.participants.exists() else ''
                }
                
                # 尝试安全地获取room名称（如果可用）
                try:
                    if meeting.room:
                        initial_data['location'] = meeting.location or meeting.room.name
                except Exception:
                    # 忽略room相关的数据库错误
                    pass
                
                context = {
                    'meeting': meeting,
                    'initial_data': initial_data,
                    'existing_minutes': existing_minutes
                }
                
                return render(request, 'personal/minutes/form.html', context)
                
            except MeetingRecord.DoesNotExist:
                messages.error(request, '未找到对应的会议记录')
                return redirect('/oa/meeting/list/')
            except Exception as e:
                messages.error(request, f'获取会议信息失败: {str(e)}')
                return redirect('/oa/meeting/list/')
        
        # 没有提供会议ID，重定向到个人办公的会议纪要列表页面
        return redirect('/personal/minutes/')
    
    def post(self, request):
        try:
            meeting_id = request.POST.get('meeting_id')
            if not meeting_id:
                return JsonResponse({'code': 1, 'msg': '会议ID不能为空'})
            
            # 获取会议记录
            from apps.oa.models import MeetingRecord
            meeting = MeetingRecord.objects.get(id=meeting_id)
            
            # 检查权限
            if meeting.host != request.user and meeting.recorder != request.user and not meeting.participants.filter(id=request.user.id).exists():
                return JsonResponse({'code': 1, 'msg': '您没有权限为该会议创建纪要'})
            
            # 处理音频文件上传和AI生成纪要
            if request.FILES.get('audio_file'):
                return self._generate_minutes_with_audio(request, meeting)
            
            # 处理手动输入纪要
            return self._save_manual_minutes(request, meeting)
            
        except MeetingRecord.DoesNotExist:
            return JsonResponse({'code': 1, 'msg': '未找到对应的会议记录'})
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'处理请求失败: {str(e)}'})
    
    def _generate_minutes_with_audio(self, request, meeting):
        """\通过上传音频文件调用AI接口生成会议纪要"""
        try:
            # 处理音频文件上传
            audio_file = request.FILES['audio_file']
            
            # 验证文件格式
            import os
            file_extension = audio_file.name.split('.')[-1].lower()
            allowed_extensions = ['mp3', 'wav', 'flac', 'ogg', 'aac']
            
            if file_extension not in allowed_extensions:
                return JsonResponse({'code': 1, 'msg': '不支持的音频格式，请上传MP3、WAV、FLAC、OGG或AAC格式'})
            
            # 确保音频文件目录存在
            from django.conf import settings
            import uuid
            audio_dir = os.path.join(settings.MEDIA_ROOT, 'meeting_recordings')
            os.makedirs(audio_dir, exist_ok=True)
            
            # 保存文件
            filename = f"{uuid.uuid4()}.{file_extension}"
            file_path = os.path.join(audio_dir, filename)
            
            with open(file_path, 'wb+') as destination:
                for chunk in audio_file.chunks():
                    destination.write(chunk)
            
            # 存储相对路径
            audio_file_path = f"meeting_recordings/{filename}"
            
            # 添加音频文件到会议记录的附件
            if meeting.attachments:
                meeting.attachments += f",{audio_file_path}"
            else:
                meeting.attachments = audio_file_path
            meeting.save()
            
            # 准备会议数据
            meeting_data = {
                'id': meeting.id,
                'title': meeting.title,
                'meeting_date': meeting.meeting_date.strftime('%Y-%m-%d %H:%M:%S') if meeting.meeting_date else '',
                'host': meeting.host.username if meeting.host else '',
                'recorder': meeting.recorder.username if meeting.recorder else '',
                # 设置默认location为meeting.location，避免访问room字段
                'location': meeting.location or '',
                'content': meeting.content,
                'attendees': ', '.join([user.username for user in meeting.participants.all()]) if meeting.participants.exists() else '',
                'audio_file': audio_file_path
            }
            
            # 尝试安全地获取room名称（如果可用）
            try:
                if meeting.room:
                    meeting_data['location'] = meeting.location or meeting.room.name
            except Exception:
                # 忽略room相关的数据库错误
                pass
            
            # 调用AI生成纪要
            from apps.ai.utils.analysis_tools import default_meeting_analysis_tool
            ai_result = default_meeting_analysis_tool.generate_meeting_minutes(meeting_data)
            
            # 保存生成的纪要
            from apps.personal.models import MeetingMinutes
            from django.utils import timezone
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # 检查是否已存在纪要
            minutes = MeetingMinutes.objects.filter(meeting_record_id=meeting.id).first()
            
            if not minutes:
                minutes = MeetingMinutes()
            
            minutes.title = meeting.title
            minutes.meeting_type = meeting.meeting_type
            minutes.meeting_date = meeting.meeting_date
            # 安全地设置location，避免访问不存在的room_id字段
            try:
                minutes.location = meeting.location
                # 只有当location为空且能够安全访问room.name时才设置
                if not minutes.location:
                    minutes.location = meeting.room.name if meeting.room else ''
            except Exception:
                # 忽略room相关的数据库错误
                pass
            minutes.host = meeting.host.username if meeting.host else ''
            minutes.recorder = request.user
            minutes.attendees = ', '.join([user.username for user in meeting.participants.all()]) if meeting.participants.exists() else ''
            minutes.user = request.user
            minutes.meeting_record = meeting
            
            # 填充AI生成的内容
            if isinstance(ai_result, dict):
                minutes.content = ai_result.get('content', '')
                minutes.decisions = ai_result.get('decisions', '')
                minutes.action_items = ai_result.get('action_items', '')
            else:
                # 如果AI返回的不是字典，将其作为内容保存
                minutes.content = str(ai_result)
            
            minutes.save()
            
            # 返回生成的内容数据供前端填充表单
            return JsonResponse({
                'code': 0, 
                'msg': 'AI生成会议纪要成功', 
                'data': {
                    'content': minutes.content,
                    'decisions': minutes.decisions,
                    'action_items': minutes.action_items
                }
            })
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'AI生成会议纪要失败: {str(e)}'})
    
    def _save_manual_minutes(self, request, meeting):
        """手动保存会议纪要"""
        try:
            from apps.personal.models import MeetingMinutes
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # 获取表单数据
            content = request.POST.get('content', '')
            decisions = request.POST.get('decisions', '')
            action_items = request.POST.get('action_items', '')
            attachments = request.POST.get('attachments', '')
            is_public = request.POST.get('is_public', 'true').lower() == 'true'
            
            # 验证必要字段
            if not content:
                return JsonResponse({'code': 1, 'msg': '会议内容不能为空'})
            
            # 检查是否已存在纪要
            minutes = MeetingMinutes.objects.filter(meeting_record_id=meeting.id).first()
            
            if not minutes:
                minutes = MeetingMinutes()
            
            # 填充数据
            minutes.title = meeting.title
            minutes.meeting_type = meeting.meeting_type
            minutes.meeting_date = meeting.meeting_date
            # 设置默认location为meeting.location，避免访问room字段
            minutes.location = meeting.location or ''
            # 尝试安全地获取room名称（如果可用）
            try:
                if meeting.room:
                    minutes.location = meeting.location or meeting.room.name
            except Exception:
                # 忽略room相关的数据库错误
                pass
            minutes.host = meeting.host.username if meeting.host else ''
            minutes.recorder = request.user
            minutes.attendees = ', '.join([user.username for user in meeting.participants.all()]) if meeting.participants.exists() else ''
            minutes.content = content
            minutes.decisions = decisions
            minutes.action_items = action_items
            minutes.attachments = attachments
            minutes.is_public = is_public
            minutes.user = request.user
            minutes.meeting_record = meeting
            
            # 保存纪要
            minutes.save()
            
            return JsonResponse({'code': 0, 'msg': '会议纪要保存成功'})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'保存会议纪要失败: {str(e)}'})

from django.views.generic import DetailView
from .models import OAMessage as Message

class MessageDetailView(LoginRequiredMixin, DetailView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Message
    template_name = 'oa/message/view.html'
    context_object_name = 'message'

class MessageView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    @staticmethod
    def datalist(request):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            params = json.loads(request.body)
            query = Q(deleted_at=None)
            if params.get('keywords'):
                query &= Q(title__icontains=params['keywords'])
            uid = request.user.id
            query &= (Q(sender_id=uid) | Q(receiver_id=uid))
            messages = Message.objects.filter(query)
            return JsonResponse({
                'code': 0,
                'msg': '',
                'data': list(messages.values())
            })
        return render(request, 'oa/message/list.html')

    @staticmethod
    def view(request, id):
        message = Message.objects.get(id=id)
        context = {'detail': message}
        return render(request, 'oa/message/view.html', context)

    @staticmethod
    def delete(request, id):
        # 使用标准的软删除方法，与ScheduleView保持一致
        Message.objects.filter(id=id).update(deleted_at=timezone.now())
        return JsonResponse({'code': 0, 'msg': '删除成功'}, json_dumps_params={'ensure_ascii': False})


def get_meeting_rooms(request):
    """获取所有可用的会议室"""
    try:
        rooms = MeetingRoom.objects.filter(status='active')
        data = [{
            'id': room.id,
            'title': room.name,
            'code': room.code,
            'location': room.location,
            'capacity': room.capacity,
            'has_projector': room.has_projector,
            'has_whiteboard': room.has_whiteboard,
            'has_tv': room.has_tv,
            'has_phone': room.has_phone,
            'has_wifi': room.has_wifi
        } for room in rooms]
        return JsonResponse({'code': 0, 'data': data})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': str(e)})

def get_all_users(request):
    """获取所有用户"""
    try:
        users = User.objects.all()
        data = [{
            'id': user.id,
            'name': user.name,
            'department': user.department.name if hasattr(user, 'department') and user.department else ''
        } for user in users]
        return JsonResponse({'code': 0, 'data': data})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': str(e)})




def upload_audio(request):
    """处理音频文件上传"""
    if request.method == 'POST':
        try:
            if 'file' not in request.FILES:
                return JsonResponse({'code': 1, 'msg': '请选择要上传的文件'})
            
            audio_file = request.FILES['file']
            # 生成唯一的文件名
            file_extension = audio_file.name.split('.')[-1].lower()
            allowed_extensions = ['mp3', 'wav', 'flac', 'ogg', 'aac']
            
            if file_extension not in allowed_extensions:
                return JsonResponse({'code': 1, 'msg': '不支持的音频格式，请上传MP3、WAV、FLAC、OGG或AAC格式'})
            
            # 确保音频文件目录存在
            audio_dir = os.path.join(settings.MEDIA_ROOT, 'meeting_recordings')
            os.makedirs(audio_dir, exist_ok=True)
            
            # 保存文件
            filename = f"{uuid.uuid4()}.{file_extension}"
            file_path = os.path.join(audio_dir, filename)
            
            with open(file_path, 'wb+') as destination:
                for chunk in audio_file.chunks():
                    destination.write(chunk)
            
            # 存储相对路径
            relative_path = f"meeting_recordings/{filename}"
            return JsonResponse({'code': 0, 'data': {'file_path': relative_path}})
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': str(e)})
    else:
        return JsonResponse({'code': 1, 'msg': '不支持的请求方法'})


@login_required
def create_temp_meeting(request):
    """创建临时会议记录（OA会议记录，而非个人会议纪要）"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    try:
        # 获取请求数据
        title = request.POST.get('title', '临时会议记录')
        meeting_date_str = request.POST.get('meeting_date')
        
        # 导入正确的MeetingRecord模型
        from apps.oa.models import MeetingRecord
        from django.utils import timezone
        import datetime
        
        # 确保会议日期是datetime对象
        if meeting_date_str:
            try:
                # 尝试解析不同格式的日期字符串
                meeting_date = datetime.datetime.fromisoformat(meeting_date_str.replace('Z', '+00:00'))
            except ValueError:
                # 如果解析失败，使用当前时间
                meeting_date = timezone.now()
        else:
            meeting_date = timezone.now()
        
        # 会议结束时间设置为开始时间后1小时
        meeting_end_time = meeting_date + datetime.timedelta(hours=1)
        
        # 创建临时会议记录（使用MeetingRecord模型）
        meeting = MeetingRecord(
            title=title,
            meeting_type='other',  # 使用有效的会议类型
            meeting_date=meeting_date,
            meeting_end_time=meeting_end_time,
            host=request.user,  # 设置主持人为主创用户
            recorder=request.user,  # 设置记录人为创建者
            status='completed'  # 使用有效的状态值
        )
        meeting.save()
        
        # 添加创建者为参与者
        meeting.participants.add(request.user)
        
        logger.info(f"创建临时会议记录成功，ID: {meeting.id}, 用户: {request.user.username}")
        return JsonResponse({
            'success': True,
            'meeting_id': meeting.id,
            'message': '临时会议记录创建成功'
        })
    
    except Exception as e:
        logger.error(f"创建临时会议记录失败: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': '创建临时会议记录失败'
        })


@login_required
def save_audio(request):
    """保存录音文件并进行语音转文字"""
    if request.method == 'POST':
        try:
            # 导入会议记录模型
            from apps.oa.models import MeetingRecord
            
            # 检查文件是否存在
            if 'audio_file' not in request.FILES:
                return JsonResponse({'success': False, 'message': '未收到音频文件'})
            
            audio_file = request.FILES['audio_file']
            meeting_id = request.POST.get('meeting_id')
            
            if not meeting_id:
                return JsonResponse({'success': False, 'message': '缺少会议ID'})
            
            # 查找会议记录
            try:
                meeting = MeetingRecord.objects.get(id=meeting_id)
                
                # 添加权限检查：确保用户是主持人、记录人或参与者
                has_permission = (
                    meeting.host == request.user or 
                    meeting.recorder == request.user or
                    meeting.participants.filter(id=request.user.id).exists()
                )
                
                if not has_permission:
                    return JsonResponse({'success': False, 'message': '会议记录不存在或无权访问'})
                    
            except MeetingRecord.DoesNotExist:
                return JsonResponse({'success': False, 'message': '会议记录不存在或无权访问'})
            
            # 验证文件格式
            file_extension = audio_file.name.split('.')[-1].lower()
            allowed_extensions = ['mp3', 'wav', 'flac', 'ogg', 'aac', 'wma', 'mpeg']
            
            if file_extension not in allowed_extensions:
                return JsonResponse({'success': False, 'message': '不支持的音频格式，请上传MP3、WAV、FLAC、OGG、AAC或WMA格式'})
            
            # 验证文件大小（限制100MB）
            max_size = 100 * 1024 * 1024  # 100MB
            if audio_file.size > max_size:
                return JsonResponse({'success': False, 'message': '音频文件过大，请上传小于100MB的文件'})
            
            # 确保音频文件目录存在
            audio_dir = os.path.join(settings.MEDIA_ROOT, 'meeting_recordings')
            os.makedirs(audio_dir, exist_ok=True)
            
            # 生成唯一的文件名
            filename = f"meeting_{meeting_id}_{uuid.uuid4()}.{file_extension}"
            file_path = os.path.join(audio_dir, filename)
            
            # 保存音频文件 - 优化文件写入性能
            try:
                # 使用更高效的文件写入方式
                with open(file_path, 'wb') as destination:
                    # 使用更大的块大小
                    for chunk in audio_file.chunks(chunk_size=8192):
                        destination.write(chunk)
            except Exception as file_save_error:
                logger.error(f"保存音频文件失败: {str(file_save_error)}")
                return JsonResponse({'success': False, 'message': f'保存音频文件失败: {str(file_save_error)}'})
            
            # 存储相对路径
            relative_path = f"meeting_recordings/{filename}"
            
            # 更新会议记录的音频文件路径
            meeting.audio_file = relative_path
            # 添加或更新last_updated字段
            if hasattr(meeting, 'last_updated'):
                meeting.last_updated = timezone.now()
            meeting.save()
            
            # 进行语音转文字处理
            transcript = ''
            try:
                logger.info(f"开始处理会议 {meeting_id} 的音频转文字和纪要生成")
                # 准备音频文件路径
                full_audio_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                
                # 准备完整的会议数据
                meeting_data = {
                    'audio_file_path': relative_path,
                    'meeting_id': meeting_id,
                    'user_id': request.user.id,
                    'meeting_theme': meeting.title,
                    'meeting_content': meeting.content or '',
                    'meeting_time': meeting.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(meeting, 'created_at') else timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # 添加参会人员信息（如果有）
                if hasattr(meeting, 'participants'):
                    try:
                        participants = list(meeting.participants.values_list('username', flat=True))
                        meeting_data['participants'] = ', '.join(participants)
                    except:
                        meeting_data['participants'] = '参会人员信息获取中'
                
                # 即使音频文件不存在，也尝试生成会议纪要
                if not os.path.exists(full_audio_path):
                    logger.error(f"音频文件不存在: {full_audio_path}")
                    # 提供结构化的默认会议纪要
                    transcript = "# 会议纪要\n\n## 会议信息\n- **会议ID**: {meeting_id}\n- **会议主题**: {meeting.title}\n- **会议时间**: {meeting_data['meeting_time']}\n\n## 提示\n音频文件未找到，但已创建会议纪要框架。请根据实际会议情况补充内容。\n\n## 会议内容结构\n\n### 1. 会议目的\n- [请描述会议的主要目的和期望成果]\n\n### 2. 讨论要点\n- [讨论点1]\n- [讨论点2]\n- [讨论点3]\n\n### 3. 决议事项\n- [决议1]\n- [决议2]\n\n### 4. 行动项\n| 任务 | 负责人 | 截止日期 | 状态 |\n|------|--------|----------|------|\n|      |        |          |      |\n|      |        |          |      |\n\n## 备注\n建议重新上传音频文件或手动完善会议记录。"
                else:
                    logger.info(f"确认音频文件存在: {full_audio_path}, 大小: {os.path.getsize(full_audio_path)} 字节")
                    
                    # 调用analysis_tools中的处理逻辑
                    try:
                        from apps.ai.utils.analysis_tools import MeetingAnalysisTool
                        logger.info("导入MeetingAnalysisTool成功")
                        
                        # 设置超时保护机制
                        import threading
                        result_container = {'value': None, 'error': None}
                        
                        def generate_minutes_thread():
                            try:
                                meeting_tool = MeetingAnalysisTool()
                                # 修复参数传递，使用正确的参数调用
                                result_container['value'] = meeting_tool.generate_meeting_minutes(
                                    user=request.user,
                                    meeting_id=meeting_id,
                                    audio_file_path=relative_path,
                                    started_at=timezone.now(),
                                    completed_at=timezone.now()
                                )
                            except Exception as e:
                                result_container['error'] = e
                        
                        # 创建并启动线程
                        minutes_thread = threading.Thread(target=generate_minutes_thread)
                        minutes_thread.daemon = True
                        minutes_thread.start()
                        
                        # 等待线程完成，设置超时时间为30秒
                        minutes_thread.join(timeout=30)
                        
                        # 检查是否超时或发生错误
                        if minutes_thread.is_alive():
                            logger.error("生成会议纪要超时（30秒）")
                            # 超时情况下提供真实错误提示
                            transcript = f"# 会议纪要 - 处理超时\n\n## 系统提示\n语音转文字处理超时，请检查音频文件或稍后重试。\n\n## 会议信息\n- **会议ID**: {meeting_id}\n- **会议主题**: {meeting.title}\n\n## 建议操作\n1. 请检查音频文件是否有效\n2. 尝试重新上传较小的音频文件\n3. 或手动输入会议内容"
                        elif result_container['error']:
                            logger.error(f"会议纪要生成过程中发生错误: {str(result_container['error'])}")
                            # 错误情况下提供真实错误提示
                            transcript = f"# 会议纪要 - 处理错误\n\n## 系统提示\n语音转文字处理失败: {str(result_container['error'])}\n\n## 会议信息\n- **会议ID**: {meeting_id}\n- **会议主题**: {meeting.title}\n\n## 建议操作\n请检查音频文件或联系系统管理员。"
                        else:
                            minutes_result = result_container['value']
                            
                            # 详细日志记录生成结果
                            logger.info(f"会议纪要生成完成，结果类型: {type(minutes_result)}, 是否为空: {minutes_result is None or minutes_result == ''}")
                            
                            # 确保transcript是字符串类型且不为空
                            if minutes_result:
                                if isinstance(minutes_result, str):
                                    transcript = minutes_result
                                    logger.info(f"成功获取字符串格式的会议纪要，长度: {len(transcript)}")
                                    # 记录前100个字符用于调试
                                    if len(transcript) > 100:
                                        logger.info(f"会议纪要预览: {transcript[:100]}...")
                                else:
                                    transcript = str(minutes_result)
                                    logger.warning(f"会议纪要不是字符串类型，已转换: {type(minutes_result)}")
                            else:
                                # 如果生成的纪要为空，提供真实错误提示
                                logger.warning("生成的会议纪要为空，语音转文字内容无效")
                                transcript = f"# 会议纪要\n\n## 系统提示\n语音转文字处理失败，未能提取有效内容。\n\n## 会议信息\n- **会议ID**: {meeting_id}\n- **会议主题**: {meeting.title}\n- **音频文件**: 已上传但内容提取失败\n\n## 建议操作\n请检查音频文件质量或重新上传。"
                    except ImportError:
                        logger.error("无法导入MeetingAnalysisTool")
                        # 导入失败时提供默认会议纪要
                        transcript = f"# 会议纪要\n\n## 系统提示\n由于系统组件缺失，未能生成完整会议纪要。\n\n## 会议基本信息\n- **会议ID**: {meeting_id}\n- **会议主题**: {meeting.title}\n- **音频文件**: 已成功上传\n\n请手动记录会议内容和决议事项。"
                    except Exception as tool_error:
                        logger.error(f"调用MeetingAnalysisTool时发生异常: {str(tool_error)}", exc_info=True)
                        # 工具出错时提供默认会议纪要
                        transcript = f"# 会议纪要\n\n## 系统提示\n处理过程中发生错误，但音频文件已成功保存。\n\n## 会议基本信息\n- **会议ID**: {meeting_id}\n- **会议主题**: {meeting.title}\n\n请手动补充会议内容和决议事项。"
            except Exception as e:
                logger.error(f"处理音频文件时发生异常: {str(e)}")
                transcript = "# 会议纪要\n\n处理过程中遇到未知错误，请手动输入会议内容。"
            
            # 确保transcript变量被正确设置
            if not transcript or not isinstance(transcript, str):
                logger.critical("会议纪要变量未正确设置，使用最终默认值")
                transcript = "# 会议纪要\n\n音频文件已上传，但未能生成会议内容。\n\n请手动输入会议纪要。"
            
            # 格式化transcript中的变量（如果有）
            try:
                # 先尝试最完整的格式化
                transcript = transcript.format(meeting_id=meeting_id, meeting=meeting, meeting_data=meeting_data)
            except Exception as fmt_error1:
                try:
                    # 尝试简化的格式化
                    transcript = transcript.format(meeting_id=meeting_id, meeting=meeting)
                except Exception as fmt_error2:
                    try:
                        # 只格式化会议ID
                        transcript = transcript.format(meeting_id=meeting_id)
                    except Exception as fmt_error3:
                        logger.warning(f"格式化会议纪要时出错，已跳过格式化: {str(fmt_error3)}")
            
            # 检查会议纪要是否包含实际语音内容，而不是默认模板
            if "语音转文字内容为空" in transcript or "无法基于语音内容生成" in transcript:
                logger.warning("会议纪要内容无效，基于实际语音内容生成失败")
                # 不添加任何默认模板，保持原始错误信息
            elif not transcript.startswith('#'):
                # 只有当内容有效且缺少标题时，才添加简单的标题
                logger.info("会议纪要缺少标题，添加简单标题")
                transcript = f"# 会议纪要\n\n{transcript}"
            else:
                logger.info("会议纪要已包含标题结构，无需修改")
            
            # 保存转写结果到会议内容，采用覆盖模式确保内容清晰
            logger.info(f"准备保存会议纪要到数据库，长度: {len(transcript)}")
            
            # 数据库操作添加事务支持
            from django.db import transaction
            try:
                with transaction.atomic():
                    meeting.content = transcript  # 直接覆盖，避免重复内容堆积
                    # 添加或更新last_updated字段
                    if hasattr(meeting, 'last_updated'):
                        meeting.last_updated = timezone.now()
                    # 确保保存音频文件路径到attachments字段
                    if meeting.attachments:
                        # 如果已有附件，追加音频文件路径
                        if relative_path not in meeting.attachments:
                            meeting.attachments += f",{relative_path}"
                    else:
                        # 如果没有附件，直接设置音频文件路径
                        meeting.attachments = relative_path
                    meeting.save()
                    
                    # 从AI生成的会议纪要中提取决议和行动项
                    try:
                        from apps.ai.utils.analysis_tools import MeetingAnalysisTool
                        meeting_analysis_tool = MeetingAnalysisTool()
                        
                        # 准备会议数据用于提取
                        meeting_data_for_extraction = {
                            'meeting_content': transcript,
                            'meeting_id': meeting_id,
                            'meeting_title': meeting.title if meeting else '会议'
                        }
                        
                        # 提取会议决议
                        try:
                            resolutions = meeting_analysis_tool.extract_resolutions(meeting_data_for_extraction)
                            if not resolutions or resolutions.strip() == '':
                                resolutions = "本次会议暂无明确的决议内容。"
                        except Exception as e:
                            logger.error(f"提取会议决议失败: {str(e)}")
                            resolutions = "提取会议决议时发生错误。"
                        
                        # 提取行动项
                        try:
                            action_items = meeting_analysis_tool.extract_action_items(meeting_data_for_extraction)
                            if not action_items or action_items.strip() == '':
                                action_items = "本次会议暂无明确的行动项。"
                        except Exception as e:
                            logger.error(f"提取行动项失败: {str(e)}")
                            action_items = "提取行动项时发生错误。"
                    except ImportError:
                        logger.warning("无法导入MeetingAnalysisTool，使用默认决议和行动项")
                        resolutions = "本次会议暂无明确的决议内容。"
                        action_items = "本次会议暂无明确的行动项。"
                    except Exception as e:
                        logger.error(f"提取决议和行动项时发生异常: {str(e)}")
                        resolutions = "提取会议决议时发生错误。"
                        action_items = "提取行动项时发生错误。"
                    
                    # 创建MeetingMinutes记录（简化逻辑，避免重复处理）
                    try:
                        from apps.personal.models import User
                        
                        # 检查是否已存在关联的会议纪要
                        existing_minutes = MeetingMinutes.objects.filter(meeting_record=meeting).first()
                        
                        if not existing_minutes:
                            # 创建新的会议纪要记录
                            meeting_minutes = MeetingMinutes(
                                title=meeting.title,
                                meeting_type='regular',
                                meeting_date=meeting.meeting_date if hasattr(meeting, 'meeting_date') else timezone.now(),
                                location=meeting.location if hasattr(meeting, 'location') else '',
                                host=meeting.host.name if meeting.host else '',
                                attendees=', '.join([user.name for user in meeting.participants.all()]) if hasattr(meeting, 'participants') and meeting.participants.exists() else '',
                                content=transcript,
                                decisions=resolutions,
                                action_items=action_items,
                                attachments=relative_path,
                                is_public=True,
                                user=request.user,
                                recorder=request.user,
                                meeting_record=meeting
                            )
                            meeting_minutes.save()
                            logger.info(f"成功创建MeetingMinutes记录，ID: {meeting_minutes.id}")
                        else:
                            # 更新已存在的会议纪要
                            existing_minutes.content = transcript
                            existing_minutes.decisions = resolutions
                            existing_minutes.action_items = action_items
                            existing_minutes.attachments = relative_path
                            existing_minutes.updated_at = timezone.now()
                            existing_minutes.save()
                            logger.info(f"更新已存在的MeetingMinutes记录，ID: {existing_minutes.id}")
                            
                    except ImportError:
                        logger.warning("无法导入MeetingMinutes模型，跳过创建会议纪要记录")
                    except Exception as minutes_error:
                        logger.error(f"创建MeetingMinutes记录时发生错误: {str(minutes_error)}")
                        # 继续流程，不中断主流程
                        
                logger.info(f"会议ID {meeting_id} 会议纪要已保存到数据库")
            except Exception as db_error:
                logger.error(f"保存会议纪要到数据库时发生错误: {str(db_error)}")
                # 数据库保存失败，但仍继续流程，返回会议纪要内容
                pass
            
            # 返回前端期望的数据结构，包含决议和行动项
            return JsonResponse({
                'code': 0,
                'msg': '音频保存和会议纪要生成完成',
                'data': {
                    'content': transcript,
                    'decisions': resolutions,
                    'action_items': action_items,
                    'file_path': relative_path,
                    'meeting_id': meeting_id
                }
            })
            
        except Exception as e:
            logger.error(f"保存录音失败: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'message': f'保存录音失败: {str(e)}'})
    else:
        return JsonResponse({'success': False, 'message': '不支持的请求方法'})


class ApprovalView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    @staticmethod
    def datalist(request):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            params = json.loads(request.body)
            query = Q(deleted_at=None)
            if params.get('keywords'):
                query &= Q(title__icontains=params['keywords'])
            uid = request.user.id
            query &= (Q(applicant_id=uid) | Q(approver_id=uid))
            approvals = Approval.objects.filter(query)
            return JsonResponse({
                'code': 0,
                'msg': '',
                'data': list(approvals.values())
            })
        return render(request, 'oa/approval/list.html')

    def approve(self, request, id):
        approval = Approval.objects.get(id=id)
        if request.method == 'POST':
            params = json.loads(request.body)
            approval.status = params['status']
            approval.approve_time = timezone.now()
            approval.save()
            return JsonResponse({'code': 0, 'msg': '审批完成'})
        context = {'detail': approval}
        return render(request, 'oa/approval/approve.html', context)
class ScheduleView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    def get(self, request):
        return self.datalist(request)
        
    def datalist(self, request):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            params = request.GET.dict()
            query = Q(deleted_at=None)
            
            if params.get('keywords'):
                query &= Q(title__icontains=params['keywords'])
                
            if params.get('labor_type'):
                query &= Q(labor_type=params['labor_type'])
                
            if params.get('cid'):
                query &= Q(cid=params['cid'])
                
            if params.get('diff_time'):
                start, end = params['diff_time'].split('~')
                start_date = datetime.strptime(start.strip(), '%Y-%m-%d')
                end_date = datetime.strptime(end.strip() + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
                query &= Q(start_time__range=(start_date, end_date))
                
            uid = request.user.id
            if params.get('uid'):
                query &= Q(admin_id=params['uid'])
            else:
                query &= (Q(admin_id=uid) | Q(did__in=get_leader_departments(uid)))
                
            schedules = Schedule.objects.filter(query)
            return JsonResponse({
                'code': 0,
                'msg': '',
                'data': list(schedules.values())
            })
        return render(request, 'oa/schedule/list.html')

    def calendar(self, request):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            params = request.GET.dict()
            uid = params.get('uid', request.user.id)
            
            start = datetime.strptime(params['start'], '%Y-%m-%d')
            end = datetime.strptime(params['end'], '%Y-%m-%d')
            
            query = Q(
                start_time__gte=start,
                end_time__lte=end,
                admin_id=uid,
                deleted_at=None
            )
            
            schedules = Schedule.objects.filter(query).values('id', 'title', 'labor_time', 'start_time', 'end_time')
            events = []
            count_events = {}
            
            for schedule in schedules:
                event = {
                    'id': schedule['id'],
                    'title': f"[{schedule['labor_time']}工时] {schedule['title']}",
                    'start': schedule['start_time'].strftime('%Y-%m-%d %H:%M'),
                    'end': schedule['end_time'].strftime('%Y-%m-%d %H:%M'),
                    'backgroundColor': '#12bb37',
                    'borderColor': '#12bb37'
                }
                events.append(event)
                
                day = schedule['start_time'].strftime('%Y-%m-%d')
                if day in count_events:
                    count_events[day]['times'] += schedule['labor_time']
                else:
                    count_events[day] = {
                        'times': schedule['labor_time'],
                        'start': day
                    }
            
            for day, data in count_events.items():
                events.append({
                    'id': 0,
                    'title': f"【当天总工时：{data['times']}】",
                    'start': data['start'],
                    'end': data['start'],
                    'backgroundColor': '#eeeeee',
                    'borderColor': '#eeeeee'
                })
                
            return JsonResponse(events, safe=False)
        return render(request, 'oa/schedule/calendar.html')

    def add(self, request):
        params = json.loads(request.body)
        admin_id = request.user.id
        
        if params['id'] == 0:
            start_time = datetime.strptime(params['start_time'], '%Y-%m-%d %H:%M')
            end_time = datetime.strptime(params['end_time'], '%Y-%m-%d %H:%M')
            
            if start_time > timezone.now():
                return JsonResponse({'code': 1, 'msg': "开始时间不能大于现在时间"})
                
            if end_time <= start_time:
                return JsonResponse({'code': 1, 'msg': "结束时间需要大于开始时间"})
                
            if end_time.date() != start_time.date():
                return JsonResponse({'code': 1, 'msg': "结束时间与开始时间必须是同一天"})
                
            # 检查时间冲突
            conflict = Schedule.objects.filter(
                Q(deleted_at=None, admin_id=admin_id) &
                (
                    Q(start_time__range=(start_time, end_time)) |
                    Q(end_time__range=(start_time, end_time)) |
                    Q(start_time__lte=start_time, end_time__gte=end_time)
                )
            ).exists()
            
            if conflict:
                return JsonResponse({'code': 1, 'msg': "您所选的时间区间已有工作记录，请重新选时间"})
                
            labor_time = (end_time - start_time).total_seconds() / 3600
            schedule = Schedule.objects.create(
                title=params['title'],
                start_time=start_time,
                end_time=end_time,
                labor_time=labor_time,
                admin_id=admin_id,
                did=get_admin(admin_id)['did'],
                labor_type=params.get('labor_type', 1),
                cid=params.get('cid'),
                tid=params.get('tid'),
                content=params.get('content', '')
            )
            return JsonResponse({'code': 0, 'msg': '操作成功', 'data': {'aid': schedule.id}}, json_dumps_params={'ensure_ascii': False})
        else:
            Schedule.objects.filter(id=params['id']).update(
                title=params['title'],
                labor_type=params.get('labor_type', 1),
                cid=params.get('cid'),
                tid=params.get('tid'),
                content=params.get('content', '')
            )
            return JsonResponse({'code': 0, 'msg': '操作成功'}, json_dumps_params={'ensure_ascii': False})

    def delete(self, request, id):
        # 使用标准的软删除方法
        Schedule.objects.filter(id=id).update(deleted_at=timezone.now())
        return JsonResponse({'code': 0, 'msg': '删除成功'}, json_dumps_params={'ensure_ascii': False})

    def view(self, request, id):
        schedule = Schedule.objects.get(id=id)
        data = {
            'id': schedule.id,
            'title': schedule.title,
            'start_time': schedule.start_time.strftime('%Y-%m-%d'),
            'end_time': schedule.end_time.strftime('%Y-m-d'),
            'start_time_1': schedule.start_time.strftime('%H:%i'),
            'end_time_1': schedule.end_time.strftime('%H:%i'),
            'create_time': schedule.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            'name': User.objects.get(id=schedule.admin_id).name,
            'labor_type_string': '案头工作' if schedule.labor_type == 1 else '外勤工作',
            'department': get_admin(schedule.admin_id)['department'],
            'work_cate': WorkCate.objects.get(id=schedule.cid).title if schedule.cid else ''
        }
        
        if schedule.tid:
            task = Task.objects.get(id=schedule.tid)
            data['task'] = task.title
            data['project'] = Project.objects.get(id=task.project_id).name
            
        return JsonResponse({'code': 0, 'msg': '', 'data': data})
