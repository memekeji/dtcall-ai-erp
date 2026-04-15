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
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView

from .constants import MeetingTypeChoices, MeetingStatusChoices, FileUploadConfig
from .response_utils import (
    success_response,
    error_response,
    validation_error_response,
    not_found_response,
    permission_denied_response,
    ajax_success_response,
    ajax_error_response)
from .models import Schedule, Approval, MeetingRoom, MeetingRecord, StatusChoices
from .utils import get_admin, get_leader_departments
from apps.personal.models import MeetingMinutes
from apps.project.models import Project, Task
from apps.user.models import Admin as User
from apps.work.models import WorkCate

logger = logging.getLogger(__name__)


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
        return render(request, 'oa/meeting/list.html')

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
            return render(request, 'meeting/records_view.html', context)
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
        return render(request, 'oa/meeting/apply.html', {'rooms': rooms})

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

            return success_response({
                'content': minutes.content,
                'decisions': minutes.decisions,
                'action_items': minutes.action_items
            }, 'AI生成会议纪要成功')

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


class MessageDetailView(LoginRequiredMixin, DetailView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Approval
    template_name = 'oa/message/view.html'
    context_object_name = 'message'


class MessageView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        return self.datalist(request)

    def datalist(self, request):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            params = json.loads(request.body)
            query = Q(deleted_at=None)
            if params.get('keywords'):
                query &= Q(title__icontains=params['keywords'])
            uid = request.user.id
            query &= (Q(sender_id=uid) | Q(receiver_id=uid))
            messages_list = Approval.objects.filter(query)
            return success_response(list(messages_list.values()))
        return render(request, 'oa/message/list.html')

    def view(self, request, id):
        message = Approval.objects.get(id=id)
        context = {'detail': message}
        return render(request, 'oa/message/view.html', context)

    def delete(self, request, id):
        Approval.objects.filter(id=id).update(deleted_at=timezone.now())
        return success_response(message='删除成功')


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

        return ajax_success_response({
            'content': transcript.get('content', ''),
            'decisions': transcript.get('decisions', ''),
            'action_items': transcript.get('action_items', ''),
            'file_path': relative_path,
            'meeting_id': meeting_id
        }, '音频保存和会议纪要生成完成')

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

    def get(self, request):
        return self.datalist(request)

    def datalist(self, request):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            params = json.loads(request.body)
            query = Q(deleted_at=None)
            if params.get('keywords'):
                query &= Q(title__icontains=params['keywords'])
            uid = request.user.id
            query &= (Q(applicant_id=uid) | Q(approver_id=uid))
            approvals = Approval.objects.filter(query)
            return success_response(list(approvals.values()))
        return render(request, 'oa/approval/list.html')

    def approve(self, request, id):
        approval = Approval.objects.get(id=id)
        if request.method == 'POST':
            params = json.loads(request.body)
            approval.status = params['status']
            approval.approve_time = timezone.now()
            approval.save()
            return success_response(message='审批完成')
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
                end_date = datetime.strptime(
                    end.strip() + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
                query &= Q(start_time__range=(start_date, end_date))

            uid = request.user.id
            if params.get('uid'):
                query &= Q(admin_id=params['uid'])
            else:
                query &= (Q(admin_id=uid) | Q(
                    did__in=get_leader_departments(uid)))

            schedules = Schedule.objects.filter(query)
            return success_response(list(schedules.values()))
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
        Schedule.objects.filter(id=id).update(deleted_at=timezone.now())
        return success_response(message='删除成功')

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
            'name': User.objects.get(
                id=schedule.admin_id).name,
            'labor_type_string': '案头工作' if schedule.labor_type == 1 else '外勤工作',
            'department': get_admin(
                schedule.admin_id)['department'],
            'work_cate': WorkCate.objects.get(
                id=schedule.cid).title if schedule.cid else ''}

        if schedule.tid:
            task = Task.objects.get(id=schedule.tid)
            data['task'] = task.title
            data['project'] = Project.objects.get(id=task.project_id).name

        return success_response(data)
