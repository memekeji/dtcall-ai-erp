import logging
import os
import uuid
import json
from datetime import datetime
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View

from .constants import MeetingTypeChoices, MeetingStatusChoices, FileUploadConfig
from .response_utils import (
    success_response,
    error_response,
    validation_error_response,
    not_found_response,
    permission_denied_response,
    ajax_success_response,
    ajax_error_response)
from .models import (
    Schedule,
    Approval,
    MeetingRoom,
    MeetingRecord,
    StatusChoices,
    OAMessage,
    OAMessageReadRecord,
    ApprovalRequest,
    ApprovalRecord,
)
from .utils import get_admin, get_leader_departments
from apps.personal.models import MeetingMinutes
from apps.project.models import Project, Task
from apps.user.models import Admin as User
from apps.work.models import WorkCate
from apps.ai.services.business_result import build_business_ai_result

logger = logging.getLogger(__name__)


def _load_request_payload(request):
    """兼容 JSON 与表单请求体。"""
    if request.body:
        try:
            return json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            pass
    return request.POST.dict()


def _parse_datetime_value(value):
    """兼容 datetime-local 与普通日期时间输入格式。"""
    if not value:
        raise ValueError('时间不能为空')
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError('时间格式不正确')


def _is_ajax_request(request):
    return (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        request.GET.get('format') == 'json'
    )


def _format_unix_timestamp(timestamp_value):
    if not timestamp_value:
        return '-'
    try:
        return datetime.fromtimestamp(int(timestamp_value)).strftime('%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError, OSError):
        return '-'


def _user_can_access_message(user, message):
    """判断当前用户是否可访问消息。"""
    if not user or not user.is_authenticated:
        return False

    if message.sender_id == user.id or message.receiver_type == 'all':
        return True

    if message.receivers.filter(id=user.id).exists():
        return True

    user_department_id = getattr(user, 'did', 0)
    if user_department_id and message.receiver_departments.filter(id=user_department_id).exists():
        return True

    return False


class ScheduleAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        categories = WorkCate.objects.all().order_by('title')
        tasks = Task.objects.all().order_by('-id')[:200]
        now = timezone.localtime(timezone.now())
        context = {
            'categories': categories,
            'tasks': tasks,
            'default_start': now.strftime('%Y-%m-%dT%H:%M'),
            'default_end': (now + timezone.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
        }
        return render(request, 'oa/schedule/add.html', context)

    def post(self, request):
        params = _load_request_payload(request)
        admin_id = request.user.id

        try:
            start_time = _parse_datetime_value(params.get('start_time'))
            end_time = _parse_datetime_value(params.get('end_time'))
        except ValueError as exc:
            return validation_error_response(str(exc))

        if start_time > timezone.now():
            return error_response("开始时间不能大于现在时间")

        if end_time <= start_time:
            return error_response("结束时间需要大于开始时间")

        if end_time.date() != start_time.date():
            return error_response("结束时间与开始时间必须是同一天")

        conflict = Schedule.objects.filter(
            Q(delete_time=0, admin_id=admin_id) &
            (
                Q(start_time__range=(start_time, end_time)) |
                Q(end_time__range=(start_time, end_time)) |
                Q(start_time__lte=start_time, end_time__gte=end_time)
            )
        ).exists()

        if conflict:
            return error_response("您所选的时间区间已有工作记录，请重新选时间")

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
        return success_response({'aid': schedule.id}, '操作成功')


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
        if request.path.endswith('delete/'):
            return self.delete(request)
        return error_response('不支持的请求方式')

    def delete(self, request):
        try:
            meeting_id = request.POST.get('id')
            if not meeting_id:
                return error_response('会议ID不能为空')

            meeting = MeetingRecord.objects.get(id=meeting_id)

            if not meeting.can_user_access(request.user):
                return error_response('无权限删除此会议记录')

            meeting.deleted_at = timezone.now()
            meeting.save(update_fields=['deleted_at'])

            return success_response(message='删除成功')
        except MeetingRecord.DoesNotExist:
            return error_response('会议记录不存在')
        except Exception as e:
            logger.error(f"删除会议记录失败: {str(e)}")
            return error_response(f'删除失败: {str(e)}')

    def list(self, request):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            params = json.loads(request.body)
            query = Q(deleted_at=None)

            if params.get('keywords'):
                query &= Q(title__icontains=params['keywords'])

            if params.get('host_id'):
                query &= Q(
                    host_id=params['host_id']) | Q(
                    host=params['host_id'])

            if params.get('diff_time'):
                start, end = params['diff_time'].split('~')
                start_date = datetime.strptime(start.strip(), '%Y-%m-%d')
                end_date = datetime.strptime(
                    end.strip() + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
                query &= Q(meeting_date__range=(start_date, end_date))

            uid = request.user.id
            query &= (
                Q(recorder_id=uid) |
                Q(host=uid) |
                Q(participants__id=uid) |
                Q(attendees__id=uid) |
                Q(shared_users__id=uid)
            )

            meetings = MeetingRecord.objects.filter(query).select_related(
                'host', 'recorder', 'room'
            ).prefetch_related('participants', 'attendees', 'shared_users')

            data = []
            for meeting in meetings:
                audio_file_url = meeting.audio_file.url if meeting.audio_file else ''
                data.append({
                    'id': meeting.id,
                    'title': meeting.title,
                    'meeting_date': meeting.meeting_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'host_id': meeting.host_id_safe,
                    'host_name': meeting.host_name,
                    'recorder_id': meeting.recorder_id,
                    'recorder_name': meeting.recorder_name,
                    'room': meeting.room_name,
                    'join_names': ', '.join([p.username for p in meeting.participants.all()]),
                    'content': meeting.content,
                    'summary': meeting.summary or '',
                    'resolution': meeting.resolution or '',
                    'audio_file': audio_file_url
                })
            return success_response(data)
        return render(request, 'meeting/records.html')

    def retrieve(self, request, pk):
        try:
            meeting = MeetingRecord.objects.select_related(
                'host', 'recorder', 'room'
            ).prefetch_related(
                'participants', 'attendees', 'shared_users'
            ).get(id=pk)

            request.user.id
            if not meeting.can_user_access(request.user):
                return permission_denied_response('无权限查看此会议')

            action_items_list = meeting.action_items.split(
                ';') if meeting.action_items else []
            audio_file_url = meeting.audio_file.url if meeting.audio_file else ''

            data = {
                'id': meeting.id,
                'title': meeting.title,
                'meeting_date': meeting.meeting_date.strftime('%Y-%m-%d %H:%M:%S'),
                'host_id': meeting.host_id_safe,
                'host_name': meeting.host_name,
                'recorder_id': meeting.recorder_id,
                'recorder_name': meeting.recorder_name,
                'room': meeting.room_name,
                'join_names': ', '.join([participant.username for participant in meeting.participants.all()]),
                'content': meeting.content,
                'summary': meeting.summary or '',
                'resolution': meeting.resolution or '',
                'action_items': action_items_list,
                'audio_file': audio_file_url
            }

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return success_response(data)

            meeting_minutes = MeetingMinutes.objects.filter(
                meeting_record=meeting
            ).order_by('-created_at')

            context = {'detail': meeting, 'meeting_minutes': meeting_minutes}
            return render(request, 'oa/meeting/detail.html', context)
        except MeetingRecord.DoesNotExist:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return not_found_response('会议不存在')
            return render(request, '404.html')

    def update_summary(self, request):
        try:
            params = json.loads(request.body)
            meeting_id = params.get('meeting_id')
            summary = params.get('summary', '')
            resolution = params.get('resolution', '')

            if not meeting_id:
                return validation_error_response('会议ID不能为空')

            meeting = MeetingRecord.objects.get(id=meeting_id)

            uid = request.user.id
            if meeting.recorder_id != uid and (
                    meeting.host and meeting.host.id != uid):
                return permission_denied_response('无权限编辑此会议纪要')

            meeting.summary = summary
            meeting.resolution = resolution
            meeting.save()

            return success_response(message='会议纪要更新成功')
        except MeetingRecord.DoesNotExist:
            return not_found_response('会议不存在')
        except Exception as e:
            logger.error(f"更新会议纪要失败: {str(e)}")
            return error_response(str(e))


class MeetingApplyView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        rooms = MeetingRoom.objects.filter(status=StatusChoices.ACTIVE)
        users = User.objects.all().order_by('name', 'username')
        now = timezone.localtime(timezone.now())
        context = {
            'rooms': rooms,
            'users': users,
            'default_start': now.strftime('%Y-%m-%dT%H:%M:%S'),
            'default_end': (now + timezone.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S'),
        }
        return render(request, 'oa/meeting/apply.html', context)

    def post(self, request):
        try:
            title = request.POST.get('title')
            meeting_type = request.POST.get(
                'meeting_type', MeetingTypeChoices.REGULAR)
            meeting_date = request.POST.get('meeting_date')
            end_time_str = request.POST.get('end_time')
            room_id = request.POST.get('room_id')
            join_uids = request.POST.get('join_uids')
            content = request.POST.get('content')

            if not all([title, meeting_date, end_time_str]):
                return validation_error_response('请填写所有必填字段')

            meeting_datetime = datetime.strptime(
                meeting_date, '%Y-%m-%d %H:%M:%S')
            end_datetime = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')

            if meeting_datetime >= end_datetime:
                return validation_error_response('会议结束时间必须晚于开始时间')

            audio_file_path = ''
            if 'audio_file' in request.FILES:
                audio_file = request.FILES['audio_file']
                audio_file_path = self._save_audio_file(audio_file)
                if not audio_file_path:
                    return error_response('音频文件保存失败')

            from apps.system.models import MeetingReservation
            from django.contrib.auth import get_user_model
            User = get_user_model()

            reservation = MeetingReservation()
            reservation.title = title
            reservation.start_time = meeting_datetime
            reservation.end_time = end_datetime
            reservation.description = content
            reservation.organizer = request.user
            reservation.status = 'pending'

            if room_id:
                try:
                    room = MeetingRoom.objects.get(id=room_id)
                    reservation.meeting_room = room
                except MeetingRoom.DoesNotExist:
                    return not_found_response('会议室不存在')

            reservation.save()

            if join_uids:
                user_ids = [int(uid) for uid in join_uids.split(',') if uid]
                for user_id in user_ids:
                    try:
                        participant = User.objects.get(id=user_id)
                        reservation.attendees.add(participant)
                    except User.DoesNotExist:
                        continue

            reservation.save()

            if audio_file_path:
                self._save_temp_reservation_data(
                    reservation.id, audio_file_path, meeting_type)

            return success_response(
                {'reservation_id': reservation.id}, '会议预订已提交，等待管理员审批')

        except Exception as e:
            logger.error(f"会议预订失败: {str(e)}")
            return error_response(f'会议预订失败: {str(e)}')

    def _save_audio_file(self, audio_file):
        """保存音频文件"""
        file_extension = audio_file.name.split('.')[-1].lower()
        ext_with_dot = f'.{file_extension}'

        if ext_with_dot not in FileUploadConfig.AUDIO_ALLOWED_EXTENSIONS:
            return None

        if audio_file.size > FileUploadConfig.MAX_AUDIO_FILE_SIZE:
            return None

        audio_dir = os.path.join(
            settings.MEDIA_ROOT,
            FileUploadConfig.AUDIO_UPLOAD_DIR)
        os.makedirs(audio_dir, exist_ok=True)

        filename = f"{uuid.uuid4()}{ext_with_dot}"
        file_path = os.path.join(audio_dir, filename)

        try:
            with open(file_path, 'wb+') as destination:
                for chunk in audio_file.chunks(
                        chunk_size=FileUploadConfig.CHUNK_SIZE):
                    destination.write(chunk)
            return f"{FileUploadConfig.AUDIO_UPLOAD_DIR}/{filename}"
        except Exception as e:
            logger.error(f"保存音频文件失败: {str(e)}")
            return None

    def _save_temp_reservation_data(
            self,
            reservation_id,
            audio_file_path,
            meeting_type):
        """保存预订相关的临时数据"""
        temp_data_dir = os.path.join(
            settings.MEDIA_ROOT,
            'temp_reservation_data')
        os.makedirs(temp_data_dir, exist_ok=True)

        temp_data_file = os.path.join(temp_data_dir, f'{reservation_id}.json')
        try:
            with open(temp_data_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'audio_file_path': audio_file_path,
                    'meeting_type': meeting_type
                }, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存临时预订数据失败: {str(e)}")


class MeetingListView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        return render(request, 'meeting/records.html')


class MeetingMinutesView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        meeting_id = request.GET.get('id')

        if meeting_id:
            try:
                meeting = MeetingRecord.objects.get(id=meeting_id)

                if not meeting.can_user_access(request.user):
                    messages.warning(request, '您没有权限为该会议创建纪要')
                    return redirect('/oa/meeting/list/')

                from apps.personal.models import MeetingMinutes
                existing_minutes = MeetingMinutes.objects.filter(
                    meeting_record_id=meeting_id
                ).first()

                initial_data = {
                    'title': meeting.title,
                    'meeting_type': meeting.meeting_type,
                    'meeting_date': meeting.meeting_date,
                    'location': meeting.location or meeting.room_name,
                    'host': meeting.host_name,
                    'attendees': ', '.join(
                        [
                            user.username for user in meeting.participants.all()]) if meeting.participants.exists() else ''}

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

        return redirect('/personal/minutes/')

    def post(self, request):
        try:
            meeting_id = request.POST.get('meeting_id')
            if not meeting_id:
                return validation_error_response('会议ID不能为空')

            from apps.oa.models import MeetingRecord
            meeting = MeetingRecord.objects.get(id=meeting_id)

            if not meeting.can_user_access(request.user):
                return permission_denied_response('您没有权限为该会议创建纪要')

            if request.FILES.get('audio_file'):
                return self._generate_minutes_with_audio(request, meeting)

            return self._save_manual_minutes(request, meeting)

        except MeetingRecord.DoesNotExist:
            return not_found_response('未找到对应的会议记录')
        except Exception as e:
            logger.error(f"处理会议纪要请求失败: {str(e)}")
            return error_response(f'处理请求失败: {str(e)}')

    def _generate_minutes_with_audio(self, request, meeting):
        """通过上传音频文件调用AI接口生成会议纪要"""
        try:
            audio_file = request.FILES['audio_file']

            file_extension = audio_file.name.split('.')[-1].lower()
            ext_with_dot = f'.{file_extension}'

            if ext_with_dot not in FileUploadConfig.AUDIO_ALLOWED_EXTENSIONS:
                return validation_error_response(
                    f'不支持的音频格式，请上传{", ".join(FileUploadConfig.AUDIO_ALLOWED_EXTENSIONS)}格式'
                )

            audio_dir = os.path.join(
                settings.MEDIA_ROOT,
                FileUploadConfig.AUDIO_UPLOAD_DIR)
            os.makedirs(audio_dir, exist_ok=True)

            filename = f"{uuid.uuid4()}{ext_with_dot}"
            file_path = os.path.join(audio_dir, filename)

            with open(file_path, 'wb+') as destination:
                for chunk in audio_file.chunks(
                        chunk_size=FileUploadConfig.CHUNK_SIZE):
                    destination.write(chunk)

            audio_file_path = f"{FileUploadConfig.AUDIO_UPLOAD_DIR}/{filename}"

            if meeting.attachments:
                meeting.attachments += f",{audio_file_path}"
            else:
                meeting.attachments = audio_file_path
            meeting.save()

            meeting_data = {
                'id': meeting.id,
                'title': meeting.title,
                'meeting_date': meeting.meeting_date.strftime('%Y-%m-%d %H:%M:%S') if meeting.meeting_date else '',
                'host': meeting.host_name,
                'recorder': meeting.recorder_name,
                'location': meeting.location or meeting.room_name,
                'content': meeting.content,
                'attendees': ', '.join([user.username for user in meeting.participants.all()]) if meeting.participants.exists() else '',
                'audio_file': audio_file_path
            }

            from apps.ai.utils.analysis_tools import default_meeting_analysis_tool
            ai_result = default_meeting_analysis_tool.generate_meeting_minutes(
                meeting_data)

            from apps.personal.models import MeetingMinutes
            from django.contrib.auth import get_user_model
            get_user_model()

            minutes = MeetingMinutes.objects.filter(
                meeting_record_id=meeting.id).first()

            if not minutes:
                minutes = MeetingMinutes()

            minutes.title = meeting.title
            minutes.meeting_type = meeting.meeting_type
            minutes.meeting_date = meeting.meeting_date
            minutes.location = meeting.location or meeting.room_name
            minutes.host = meeting.host_name
            minutes.recorder = request.user
            minutes.attendees = ', '.join([user.username for user in meeting.participants.all(
            )]) if meeting.participants.exists() else ''
            minutes.user = request.user
            minutes.meeting_record = meeting

            if isinstance(ai_result, dict):
                minutes.content = ai_result.get('content', '')
                minutes.decisions = ai_result.get('decisions', '')
                minutes.action_items = ai_result.get('action_items', '')
            else:
                minutes.content = str(ai_result)

            minutes.save()
            minutes_result = build_business_ai_result(
                {
                    'content': minutes.content,
                    'decisions': minutes.decisions,
                    'action_items': minutes.action_items,
                    'summary': minutes.content,
                },
                scenario='oa_meeting_minutes_generation',
                source_refs=[{'type': 'meeting', 'id': meeting.id}],
                request=request,
                raw_input={'meeting_id': meeting.id, 'participant_count': meeting.participants.count()},
            )

            return success_response(minutes_result, 'AI生成会议纪要成功')

        except Exception as e:
            logger.error(f"AI生成会议纪要失败: {str(e)}")
            return error_response(f'AI生成会议纪要失败: {str(e)}')

    def _save_manual_minutes(self, request, meeting):
        """手动保存会议纪要"""
        try:
            from apps.personal.models import MeetingMinutes

            content = request.POST.get('content', '')
            decisions = request.POST.get('decisions', '')
            action_items = request.POST.get('action_items', '')
            attachments = request.POST.get('attachments', '')
            is_public = request.POST.get('is_public', 'true').lower() == 'true'

            if not content:
                return validation_error_response('会议内容不能为空')

            minutes = MeetingMinutes.objects.filter(
                meeting_record_id=meeting.id).first()

            if not minutes:
                minutes = MeetingMinutes()

            minutes.title = meeting.title
            minutes.meeting_type = meeting.meeting_type
            minutes.meeting_date = meeting.meeting_date
            minutes.location = meeting.location or meeting.room_name
            minutes.host = meeting.host_name
            minutes.recorder = request.user
            minutes.attendees = ', '.join([user.username for user in meeting.participants.all(
            )]) if meeting.participants.exists() else ''
            minutes.content = content
            minutes.decisions = decisions
            minutes.action_items = action_items
            minutes.attachments = attachments
            minutes.is_public = is_public
            minutes.user = request.user
            minutes.meeting_record = meeting

            minutes.save()

            return success_response(message='会议纪要保存成功')

        except Exception as e:
            logger.error(f"保存会议纪要失败: {str(e)}")
            return error_response(f'保存会议纪要失败: {str(e)}')


class MessageDetailView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, id):
        message = get_object_or_404(
            OAMessage.objects.select_related('sender').prefetch_related(
                'receivers',
                'receiver_departments',
                'read_records'),
            pk=id,
            deleted_at__isnull=True,
            is_deleted=False)

        if not _user_can_access_message(request.user, message):
            messages.error(request, '您无权查看该消息')
            return redirect('message_list')

        read_record, _ = OAMessageReadRecord.objects.get_or_create(
            message=message,
            user=request.user)
        if not read_record.is_read:
            read_record.is_read = True
            read_record.read_time = timezone.now()
            read_record.save(update_fields=['is_read', 'read_time', 'updated_at'])

        context = {
            'message': message,
            'read_record': read_record,
        }
        return render(request, 'oa/message/view.html', context)


class MessageView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        return self.datalist(request)

    def datalist(self, request):
        params = request.GET.dict()
        query = Q(deleted_at__isnull=True, is_deleted=False, is_draft=False)
        uid = request.user.id

        if params.get('keywords'):
            query &= (
                Q(title__icontains=params['keywords']) |
                Q(content__icontains=params['keywords'])
            )

        access_query = (
            Q(sender_id=uid) |
            Q(receiver_type='all') |
            Q(receivers__id=uid)
        )
        if getattr(request.user, 'did', 0):
            access_query |= Q(receiver_departments__id=request.user.did)

        messages_list = OAMessage.objects.filter(query & access_query).select_related(
            'sender'
        ).prefetch_related(
            'receivers',
            'receiver_departments',
            'read_records'
        ).distinct().order_by('-send_time', '-created_at')

        if _is_ajax_request(request):
            data = []
            for item in messages_list:
                read_record = item.read_records.filter(user=request.user).first()
                receivers = ', '.join(
                    receiver.name or receiver.username for receiver in item.receivers.all()[:5]
                )
                data.append({
                    'id': item.id,
                    'title': item.title,
                    'content': item.content,
                    'message_type': item.get_message_type_display(),
                    'priority': item.get_priority_display(),
                    'sender_name': item.sender.name or item.sender.username,
                    'receiver_type': item.get_receiver_type_display(),
                    'receivers': receivers,
                    'send_time': item.send_time.strftime('%Y-%m-%d %H:%M') if item.send_time else '-',
                    'is_read': read_record.is_read if read_record else False,
                })
            return success_response(data)

        unread_count = OAMessageReadRecord.objects.filter(
            user=request.user,
            is_read=False,
            message__in=messages_list
        ).count()
        context = {
            'messages_list': messages_list[:100],
            'unread_count': unread_count,
        }
        return render(request, 'oa/message/list.html', context)


def get_meeting_rooms(request):
    """获取所有可用的会议室"""
    try:
        rooms = MeetingRoom.objects.filter(status=StatusChoices.ACTIVE)
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
            'has_wifi': room.has_wifi,
            'equipment_display': room.get_equipment_display()
        } for room in rooms]
        return success_response(data)
    except Exception as e:
        logger.error(f"获取会议室列表失败: {str(e)}")
        return error_response(str(e))


def get_all_users(request):
    """获取所有用户"""
    try:
        users = User.objects.all()
        data = [{'id': user.id,
                 'name': user.name,
                 'department': user.department.name if hasattr(user,
                                                               'department') and user.department else ''} for user in users]
        return success_response(data)
    except Exception as e:
        logger.error(f"获取用户列表失败: {str(e)}")
        return error_response(str(e))


def upload_audio(request):
    """处理音频文件上传"""
    if request.method != 'POST':
        return error_response('不支持的请求方法')

    try:
        if 'file' not in request.FILES:
            return validation_error_response('请选择要上传的文件')

        audio_file = request.FILES['file']
        file_extension = audio_file.name.split('.')[-1].lower()
        ext_with_dot = f'.{file_extension}'

        if ext_with_dot not in FileUploadConfig.AUDIO_ALLOWED_EXTENSIONS:
            return validation_error_response(
                f'不支持的音频格式，请上传{", ".join(FileUploadConfig.AUDIO_ALLOWED_EXTENSIONS)}格式'
            )

        if audio_file.size > FileUploadConfig.MAX_AUDIO_FILE_SIZE:
            return validation_error_response('音频文件过大，请上传小于100MB的文件')

        audio_dir = os.path.join(
            settings.MEDIA_ROOT,
            FileUploadConfig.AUDIO_UPLOAD_DIR)
        os.makedirs(audio_dir, exist_ok=True)

        filename = f"{uuid.uuid4()}{ext_with_dot}"
        file_path = os.path.join(audio_dir, filename)

        with open(file_path, 'wb+') as destination:
            for chunk in audio_file.chunks(
                    chunk_size=FileUploadConfig.CHUNK_SIZE):
                destination.write(chunk)

        relative_path = f"{FileUploadConfig.AUDIO_UPLOAD_DIR}/{filename}"
        return success_response({'file_path': relative_path})
    except Exception as e:
        logger.error(f"上传音频文件失败: {str(e)}")
        return error_response(str(e))


@login_required
def create_temp_meeting(request):
    """创建临时会议记录"""
    if request.method != 'POST':
        return error_response('Method not allowed')

    try:
        title = request.POST.get('title', '临时会议记录')
        meeting_date_str = request.POST.get('meeting_date')

        from apps.oa.models import MeetingRecord
        from django.utils import timezone
        import datetime

        if meeting_date_str:
            try:
                meeting_date = datetime.datetime.fromisoformat(
                    meeting_date_str.replace('Z', '+00:00'))
            except ValueError:
                meeting_date = timezone.now()
        else:
            meeting_date = timezone.now()

        meeting_end_time = meeting_date + datetime.timedelta(hours=1)

        meeting = MeetingRecord(
            title=title,
            meeting_type=MeetingTypeChoices.OTHER,
            meeting_date=meeting_date,
            meeting_end_time=meeting_end_time,
            host=request.user,
            recorder=request.user,
            status=MeetingStatusChoices.COMPLETED
        )
        meeting.save()

        meeting.participants.add(request.user)

        logger.info(
            f"创建临时会议记录成功，ID: {meeting.id}, 用户: {request.user.username}")
        return ajax_success_response({'meeting_id': meeting.id}, '临时会议记录创建成功')

    except Exception as e:
        logger.error(f"创建临时会议记录失败: {str(e)}")
        return ajax_error_response(f'创建临时会议记录失败: {str(e)}')


@login_required
def save_audio(request):
    """保存录音文件并进行语音转文字"""
    if request.method != 'POST':
        return ajax_error_response('不支持的请求方法')

    try:
        if 'audio_file' not in request.FILES:
            return ajax_error_response('未收到音频文件')

        audio_file = request.FILES['audio_file']
        meeting_id = request.POST.get('meeting_id')

        if not meeting_id:
            return ajax_error_response('缺少会议ID')

        from apps.oa.models import MeetingRecord

        try:
            meeting = MeetingRecord.objects.get(id=meeting_id)

            if not meeting.can_user_access(request.user):
                return ajax_error_response('会议记录不存在或无权访问')

        except MeetingRecord.DoesNotExist:
            return ajax_error_response('会议记录不存在或无权访问')

        file_extension = audio_file.name.split('.')[-1].lower()
        ext_with_dot = f'.{file_extension}'

        if ext_with_dot not in FileUploadConfig.AUDIO_ALLOWED_EXTENSIONS:
            return ajax_error_response(
                f'不支持的音频格式，请上传{", ".join(FileUploadConfig.AUDIO_ALLOWED_EXTENSIONS)}格式'
            )

        if audio_file.size > FileUploadConfig.MAX_AUDIO_FILE_SIZE:
            return ajax_error_response('音频文件过大，请上传小于100MB的文件')

        audio_dir = os.path.join(
            settings.MEDIA_ROOT,
            FileUploadConfig.AUDIO_UPLOAD_DIR)
        os.makedirs(audio_dir, exist_ok=True)

        filename = f"meeting_{meeting_id}_{uuid.uuid4()}{ext_with_dot}"
        file_path = os.path.join(audio_dir, filename)

        with open(file_path, 'wb') as destination:
            for chunk in audio_file.chunks(
                    chunk_size=FileUploadConfig.CHUNK_SIZE):
                destination.write(chunk)

        relative_path = f"{FileUploadConfig.AUDIO_UPLOAD_DIR}/{filename}"

        meeting.audio_file.name = relative_path
        if hasattr(meeting, 'last_updated'):
            meeting.last_updated = timezone.now()
        meeting.save()

        transcript = _process_audio_and_generate_minutes(
            meeting, relative_path, request.user)

        transcript_result = build_business_ai_result(
            {
                'content': transcript.get('content', ''),
                'decisions': transcript.get('decisions', ''),
                'action_items': transcript.get('action_items', ''),
                'file_path': relative_path,
                'meeting_id': meeting_id,
                'summary': transcript.get('content', ''),
            },
            scenario='oa_meeting_audio_minutes',
            source_refs=[{'type': 'meeting', 'id': meeting_id}],
            request=request,
            raw_input={'meeting_id': meeting_id, 'audio_file_ext': ext_with_dot},
        )

        return ajax_success_response(transcript_result, '音频保存和会议纪要生成完成')

    except Exception as e:
        logger.error(f"保存录音失败: {str(e)}", exc_info=True)
        return ajax_error_response(f'保存录音失败: {str(e)}')


def _process_audio_and_generate_minutes(meeting, audio_file_path, user):
    """处理音频并生成会议纪要"""
    import threading

    result_container = {'content': '', 'decisions': '', 'action_items': ''}

    def generate_minutes_thread():
        try:
            from apps.ai.utils.analysis_tools import MeetingAnalysisTool
            meeting_tool = MeetingAnalysisTool()
            result = meeting_tool.generate_meeting_minutes(
                user=user,
                meeting_id=meeting.id,
                audio_file_path=audio_file_path,
                started_at=timezone.now(),
                completed_at=timezone.now()
            )

            if result:
                result_container['content'] = result

                try:
                    from apps.ai.utils.analysis_tools import MeetingAnalysisTool
                    tool = MeetingAnalysisTool()
                    result_container['decisions'] = tool.extract_resolutions(
                        result)
                    result_container['action_items'] = tool.extract_action_items(
                        result)
                except Exception as e:
                    logger.warning(f"提取决议和行动项失败: {str(e)}")

        except Exception as e:
            logger.error(f"生成会议纪要线程失败: {str(e)}")

    thread = threading.Thread(target=generate_minutes_thread)
    thread.daemon = True
    thread.start()
    thread.join(timeout=FileUploadConfig.THREAD_TIMEOUT)

    if thread.is_alive():
        logger.warning("生成会议纪要超时")
        result_container['content'] = "# 会议纪要\n\n## 系统提示\n语音转文字处理超时，请稍后重试。"

    return result_container


class ApprovalView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, *args, **kwargs):
        if 'id' in kwargs:
            return self.approve(request, kwargs['id'])
        return self.datalist(request)

    def post(self, request, *args, **kwargs):
        if 'id' in kwargs:
            return self.approve(request, kwargs['id'])
        return error_response('不支持的请求方式')

    def datalist(self, request):
        params = request.GET.dict()
        uid = request.user.id
        query = Q(deleted_at__isnull=True, is_deleted=False)

        if params.get('keywords'):
            query &= (
                Q(title__icontains=params['keywords']) |
                Q(content__icontains=params['keywords'])
            )

        if params.get('status'):
            query &= Q(status=params['status'])

        access_query = (
            Q(applicant_id=uid) |
            Q(current_step__approvers__id=uid) |
            Q(approval_records__approver_id=uid)
        )
        approvals = ApprovalRequest.objects.filter(
            query & access_query
        ).select_related(
            'applicant',
            'flow',
            'current_step'
        ).prefetch_related(
            'approval_records',
            'current_step__approvers'
        ).distinct().order_by('-submit_time')

        if _is_ajax_request(request):
            data = []
            for item in approvals:
                current_step_name = item.current_step.name if item.current_step else '已完成'
                approver_names = ''
                if item.current_step:
                    approver_names = ', '.join(
                        approver.name or approver.username
                        for approver in item.current_step.approvers.all()
                    )
                data.append({
                    'id': item.id,
                    'title': item.title,
                    'applicant_name': item.applicant.name or item.applicant.username,
                    'flow_name': item.flow.name,
                    'status': item.get_status_display(),
                    'current_step': current_step_name,
                    'current_approvers': approver_names or '-',
                    'submit_time': item.submit_time.strftime('%Y-%m-%d %H:%M'),
                })
            return success_response(data)

        context = {
            'approval_items': approvals[:100],
        }
        return render(request, 'oa/approval/list.html', context)

    def approve(self, request, id):
        approval = get_object_or_404(
            ApprovalRequest.objects.select_related(
                'applicant',
                'flow',
                'current_step'
            ).prefetch_related(
                'flow__steps',
                'flow__steps__approvers',
                'approval_records__approver'
            ),
            pk=id,
            deleted_at__isnull=True,
            is_deleted=False
        )

        uid = request.user.id
        can_view = (
            approval.applicant_id == uid or
            approval.approval_records.filter(approver_id=uid).exists() or
            (approval.current_step and approval.current_step.approvers.filter(id=uid).exists())
        )
        if not can_view:
            return permission_denied_response('无权限查看该审批')

        if request.method == 'POST':
            params = _load_request_payload(request)
            action = params.get('status') or params.get('action')
            comment = params.get('comment', '').strip()
            action_map = {
                'approve': 'approved',
                'approved': 'approved',
                'reject': 'rejected',
                'rejected': 'rejected',
                'cancel': 'cancelled',
                'cancelled': 'cancelled',
            }
            normalized_action = action_map.get(action)
            if not normalized_action:
                return validation_error_response('审批动作不正确')

            now = timezone.now()
            update_fields = ['status', 'updated_at']

            if normalized_action == 'cancelled':
                if approval.applicant_id != uid:
                    return permission_denied_response('仅申请人可撤销审批')
                approval.status = 'cancelled'
                approval.complete_time = now
                approval.current_step = None
                update_fields.extend(['complete_time', 'current_step'])
                approval.save(update_fields=update_fields)
                return success_response(message='审批已撤销')

            if not approval.current_step or not approval.current_step.approvers.filter(id=uid).exists():
                return permission_denied_response('当前用户不是该步骤审批人')

            ApprovalRecord.objects.create(
                request=approval,
                step=approval.current_step,
                approver=request.user,
                result='approved' if normalized_action == 'approved' else 'rejected',
                comment=comment
            )

            if normalized_action == 'approved':
                next_step = approval.flow.steps.filter(
                    step_order__gt=approval.current_step.step_order
                ).order_by('step_order').first()
                if next_step:
                    approval.current_step = next_step
                    approval.status = 'in_review'
                    update_fields.append('current_step')
                else:
                    approval.current_step = None
                    approval.status = 'approved'
                    approval.complete_time = now
                    update_fields.extend(['current_step', 'complete_time'])
            else:
                approval.current_step = None
                approval.status = 'rejected'
                approval.complete_time = now
                update_fields.extend(['current_step', 'complete_time'])

            approval.save(update_fields=update_fields)
            return success_response(message='审批处理完成')

        context = {
            'detail': approval,
            'approval_records': approval.approval_records.all().order_by('-approval_time'),
            'flow_steps': approval.flow.steps.all().order_by('step_order'),
        }
        return render(request, 'oa/approval/approve.html', context)


class ScheduleView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, *args, **kwargs):
        if request.path.endswith('/calendar/'):
            return self.calendar(request)
        if request.path.find('/view/') > -1 and 'id' in kwargs:
            return self.view(request, kwargs['id'])
        return self.datalist(request)

    def post(self, request, *args, **kwargs):
        if request.path.find('/delete/') > -1 and 'id' in kwargs:
            return self.delete(request, kwargs['id'])
        return error_response('不支持的请求方式')

    def datalist(self, request):
        if _is_ajax_request(request):
            params = request.GET.dict()
            query = Q(delete_time=0)

            if params.get('keywords'):
                query &= Q(title__icontains=params['keywords'])

            if params.get('labor_type'):
                query &= Q(labor_type=params['labor_type'])

            if params.get('cid'):
                query &= Q(cid=params['cid'])

            if params.get('diff_time'):
                start, end = params['diff_time'].split('~')
                start_date = datetime.strptime(start.strip(), '%Y-%m-%d')
                end_date = datetime.strptime(
                    end.strip() + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
                query &= Q(start_time__range=(start_date, end_date))

            uid = request.user.id
            if params.get('uid'):
                query &= Q(admin_id=params['uid'])
            else:
                query &= (Q(admin_id=uid) | Q(
                    did__in=get_leader_departments(uid)))

            schedules = Schedule.objects.filter(query).order_by('-start_time')
            data = []
            for schedule in schedules:
                work_cate_title = ''
                if schedule.cid:
                    work_cate_title = WorkCate.objects.filter(id=schedule.cid).values_list('title', flat=True).first() or ''

                task_title = ''
                project_name = ''
                if schedule.tid:
                    task = Task.objects.filter(id=schedule.tid).first()
                    if task:
                        task_title = task.title
                        project_name = Project.objects.filter(id=task.project_id).values_list('name', flat=True).first() or ''

                admin_info = get_admin(schedule.admin_id)
                data.append({
                    'id': schedule.id,
                    'title': schedule.title,
                    'start_time': schedule.start_time.strftime('%Y-%m-%d %H:%M'),
                    'end_time': schedule.end_time.strftime('%Y-%m-%d %H:%M'),
                    'labor_time': schedule.labor_time,
                    'labor_type': '案头工作' if schedule.labor_type == 1 else '外勤工作',
                    'content': schedule.content,
                    'admin_name': admin_info.get('name') or admin_info.get('nickname') or '',
                    'department': admin_info.get('department', ''),
                    'work_cate': work_cate_title or '-',
                    'task': task_title or '-',
                    'project': project_name or '-',
                })
            return success_response(data)
        return render(request, 'oa/schedule/list.html')

    def calendar(self, request):
        if _is_ajax_request(request):
            params = request.GET.dict()
            uid = params.get('uid', request.user.id)

            start = datetime.strptime(params['start'], '%Y-%m-%d')
            end = datetime.strptime(params['end'], '%Y-%m-%d')

            query = Q(
                start_time__gte=start,
                end_time__lte=end,
                admin_id=uid,
                delete_time=0
            )

            schedules = Schedule.objects.filter(query).values(
                'id', 'title', 'labor_time', 'start_time', 'end_time')
            events = []
            count_events = {}

            for schedule in schedules:
                event = {
                    'id': schedule['id'],
                    'title': f"[{schedule['labor_time']}工时] {schedule['title']}",
                    'start': schedule['start_time'].strftime('%Y-%m-%d %H:%M'),
                    'end': schedule['end_time'].strftime('%Y-%m-%d %H:%M'),
                    'backgroundColor': '#12bb37',
                    'borderColor': '#12bb37'}
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
            start_time = datetime.strptime(
                params['start_time'], '%Y-%m-%d %H:%M')
            end_time = datetime.strptime(params['end_time'], '%Y-%m-%d %H:%M')

            if start_time > timezone.now():
                return error_response("开始时间不能大于现在时间")

            if end_time <= start_time:
                return error_response("结束时间需要大于开始时间")

            if end_time.date() != start_time.date():
                return error_response("结束时间与开始时间必须是同一天")

            conflict = Schedule.objects.filter(
                Q(deleted_at=None, admin_id=admin_id) &
                (
                    Q(start_time__range=(start_time, end_time)) |
                    Q(end_time__range=(start_time, end_time)) |
                    Q(start_time__lte=start_time, end_time__gte=end_time)
                )
            ).exists()

            if conflict:
                return error_response("您所选的时间区间已有工作记录，请重新选时间")

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
            return success_response({'aid': schedule.id}, '操作成功')
        else:
            Schedule.objects.filter(id=params['id']).update(
                title=params['title'],
                labor_type=params.get('labor_type', 1),
                cid=params.get('cid'),
                tid=params.get('tid'),
                content=params.get('content', '')
            )
            return success_response(message='操作成功')

    def delete(self, request, id):
        schedule = get_object_or_404(Schedule, id=id, delete_time=0)
        if schedule.admin_id != request.user.id:
            return permission_denied_response('仅创建人可删除该日程')
        Schedule.objects.filter(id=id).update(
            delete_time=int(timezone.now().timestamp()),
            update_time=int(timezone.now().timestamp())
        )
        return success_response(message='删除成功')

    def view(self, request, id):
        schedule = get_object_or_404(Schedule, id=id, delete_time=0)
        data = {
            'id': schedule.id,
            'title': schedule.title,
            'start_time': schedule.start_time.strftime('%Y-%m-%d'),
            'end_time': schedule.end_time.strftime('%Y-%m-%d'),
            'start_time_1': schedule.start_time.strftime('%H:%M'),
            'end_time_1': schedule.end_time.strftime('%H:%M'),
            'create_time': _format_unix_timestamp(schedule.create_time),
            'name': User.objects.get(
                id=schedule.admin_id).name,
            'labor_type_string': '案头工作' if schedule.labor_type == 1 else '外勤工作',
            'department': get_admin(
                schedule.admin_id)['department'],
            'work_cate': WorkCate.objects.get(
                id=schedule.cid).title if schedule.cid else '',
            'content': schedule.content}

        if schedule.tid:
            task = Task.objects.get(id=schedule.tid)
            data['task'] = task.title
            data['project'] = Project.objects.get(id=task.project_id).name

        return success_response(data)
