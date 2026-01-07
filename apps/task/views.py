from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum
from django.db import models
from django.utils import timezone
from apps.project.models import Task, WorkHour, Project
from django.contrib.auth import get_user_model
from apps.user.models import Admin

User = get_user_model()

class TaskListView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request):
        # 检查是否是Ajax请求数据
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        
        try:
            projects = Project.objects.filter(delete_time__isnull=True)
            users = Admin.objects.filter(status=1)
            return render(request, 'project/list.html', {
                'projects': projects,
                'users': users
            })
        except Exception as e:
            return render(request, 'project/list.html', {
                'projects': [],
                'users': []
            })

    def get_data_list(self, request):
        try:
            # 获取查询参数
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 20))
            status = request.GET.get('status', '')
            priority = request.GET.get('priority', '')
            project_id = request.GET.get('project_id', '')
            assignee_id = request.GET.get('assignee_id', '')
            keywords = request.GET.get('keywords', '')
            tab = request.GET.get('tab', '0')  # 选项卡筛选
            
            # 构建查询条件
            queryset = Task.objects.filter(delete_time__isnull=True)
            
            # 根据选项卡筛选
            if tab == '1':  # 我创建的
                queryset = queryset.filter(creator=request.user)
            elif tab == '2':  # 分配给我的
                queryset = queryset.filter(assignee=request.user)
            elif tab == '3':  # 我参与的
                queryset = queryset.filter(participants=request.user)
            elif tab == '4':  # 已逾期的
                queryset = queryset.filter(
                    end_date__lt=timezone.now().date(),
                    status__in=[1, 2]  # 未开始或进行中
                )
            
            # 状态筛选
            if status:
                queryset = queryset.filter(status=status)
            
            # 优先级筛选
            if priority:
                queryset = queryset.filter(priority=priority)
            
            # 项目筛选
            if project_id:
                queryset = queryset.filter(project_id=project_id)
            
            # 负责人筛选
            if assignee_id:
                queryset = queryset.filter(assignee_id=assignee_id)
            
            # 关键词搜索
            if keywords:
                queryset = queryset.filter(
                    Q(title__icontains=keywords) |
                    Q(description__icontains=keywords)
                )
            
            # 权限过滤 - 只显示用户相关的任务
            if not request.user.is_superuser:
                queryset = queryset.filter(
                    Q(creator=request.user) |
                    Q(assignee=request.user) |
                    Q(participants=request.user) |
                    Q(project__creator=request.user) |
                    Q(project__manager=request.user) |
                    Q(project__members=request.user)
                ).distinct()
            
            # 分页
            total = queryset.count()
            start = (page - 1) * limit
            end = start + limit
            tasks = queryset.select_related('project', 'assignee', 'creator')[start:end]
            
            # 构建返回数据
            data_list = []
            for task in tasks:
                data_list.append({
                    'id': task.id,
                    'title': task.title,
                    'description': task.description[:100] + '...' if len(task.description) > 100 else task.description,
                    'status': task.status,
                    'status_display': task.status_display,
                    'priority': task.priority,
                    'priority_display': task.priority_display,
                    'progress': task.progress,
                    'project_name': task.project.name if task.project else '无项目',
                    'assignee_name': task.assignee.username if task.assignee else '未分配',
                    'creator_name': task.creator.username if task.creator else '',
                    'start_date': task.start_date.strftime('%Y-%m-%d') if task.start_date else '',
                    'end_date': task.end_date.strftime('%Y-%m-%d') if task.end_date else '',
                    'estimated_hours': task.estimated_hours,
                    'actual_hours': task.actual_hours,
                    'is_overdue': task.is_overdue,
                    'create_time': task.create_time.strftime('%Y-%m-%d %H:%M')
                })
            
            return JsonResponse({
                'code': 0,
                'msg': 'success',
                'count': total,
                'data': data_list
            })
        except Exception as e:
            return JsonResponse({
                'code': 1,
                'msg': f'获取数据失败: {str(e)}',
                'count': 0,
                'data': []
            })

class WorkHourListView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request):
        # 检查是否是Ajax请求数据
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        
        try:
            tasks = Task.objects.filter(delete_time__isnull=True)
            users = Admin.objects.filter(status=1)
            return render(request, 'project/workhour.html', {
                'tasks': tasks,
                'users': users
            })
        except Exception as e:
            return render(request, 'project/workhour.html', {
                'tasks': [],
                'users': []
            })

    def get_data_list(self, request):
        try:
            # 获取查询参数
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 20))
            user_id = request.GET.get('user_id', '')
            task_id = request.GET.get('task_id', '')
            start_date = request.GET.get('start_date', '')
            end_date = request.GET.get('end_date', '')
            
            # 构建查询条件
            queryset = WorkHour.objects.all()
            
            # 用户筛选
            if user_id:
                queryset = queryset.filter(user_id=user_id)
            
            # 任务筛选
            if task_id:
                queryset = queryset.filter(task_id=task_id)
            
            # 日期范围筛选
            if start_date:
                queryset = queryset.filter(work_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(work_date__lte=end_date)
            
            # 权限过滤 - 只显示用户相关的工时记录
            if not request.user.is_superuser:
                queryset = queryset.filter(
                    Q(user=request.user) |
                    Q(task__assignee=request.user) |
                    Q(task__creator=request.user) |
                    Q(task__project__manager=request.user)
                ).distinct()
            
            # 分页
            total = queryset.count()
            start = (page - 1) * limit
            end = start + limit
            work_hours = queryset.select_related('user', 'task')[start:end]
            
            # 构建返回数据
            data_list = []
            for wh in work_hours:
                data_list.append({
                    'id': wh.id,
                    'user_name': wh.user.username,
                    'task_title': wh.task.title,
                    'project_name': wh.task.project.name if wh.task.project else '无项目',
                    'work_date': wh.work_date.strftime('%Y-%m-%d'),
                    'hours': str(wh.hours),
                    'description': wh.description,
                    'create_time': wh.create_time.strftime('%Y-%m-%d %H:%M')
                })
            
            return JsonResponse({
                'code': 0,
                'msg': 'success',
                'count': total,
                'data': data_list
            })
        except Exception as e:
            return JsonResponse({
                'code': 1,
                'msg': f'获取数据失败: {str(e)}',
                'count': 0,
                'data': []
            })
class TaskAddView(LoginRequiredMixin, View):
    """新增任务视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        # 获取URL参数中的project_id
        project_id = request.GET.get('project_id')
        
        # 修复：获取所有未删除的项目，确保包含所有项目
        projects = Project.objects.all()
        users = User.objects.filter(is_active=True)
        
        # 调试信息：打印项目ID和项目列表
        print(f"URL参数project_id: {project_id}")
        print(f"项目列表中包含的ID: {[p.id for p in projects]}")
        
        return render(request, 'project/task_form.html', {
            'projects': projects,
            'users': users,
            'is_edit': False,
            'current_project_id': project_id
        })
    
    def dispatch(self, request, *args, **kwargs):
        """重写dispatch方法，确保next参数包含完整的URL（包括query_string）"""
        if not request.user.is_authenticated:
            from django.urls import reverse
            login_url = self.get_login_url()
            next_url = request.get_full_path()  # 获取完整的URL，包括query_string
            return self.redirect_to_login(next_url, login_url, self.redirect_field_name)
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        try:
            # 获取表单数据
            title = request.POST.get('title')
            description = request.POST.get('description', '')
            project_id = request.POST.get('project_id')
            assignee_id = request.POST.get('assignee_id')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            estimated_hours = request.POST.get('estimated_hours', 0)
            priority = request.POST.get('priority', 2)
            
            # 验证必填字段
            if not all([title, start_date, end_date]):
                return JsonResponse({'code': 1, 'msg': '请填写标题、开始日期和结束日期'})
            
            # 创建任务
            task = Task.objects.create(
                title=title,
                description=description,
                project_id=project_id if project_id else None,
                assignee_id=assignee_id if assignee_id else None,
                start_date=start_date,
                end_date=end_date,
                estimated_hours=estimated_hours,
                priority=priority,
                creator=request.user
            )
            
            # 添加参与人员
            participant_ids_str = request.POST.get('participant_ids', '')
            if participant_ids_str:
                # 处理逗号分隔的员工ID字符串
                participant_ids = [id.strip() for id in participant_ids_str.split(',') if id.strip()]
                if participant_ids:
                    task.participants.set(participant_ids)
            
            return JsonResponse({'code': 0, 'msg': '任务创建成功', 'data': {'id': task.id}})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'创建失败: {str(e)}'})


class TaskEditView(LoginRequiredMixin, View):
    """编辑任务视图"""
    login_url = '/user/login/'
    
    def get(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, delete_time__isnull=True)
        
        # 检查权限
        if not self.has_permission(request.user, task):
            return JsonResponse({'code': 1, 'msg': '没有权限编辑此任务'})
        
        projects = Project.objects.filter(delete_time__isnull=True)
        users = User.objects.filter(is_active=True)
        
        return render(request, 'project/task_form.html', {
            'task': task,
            'projects': projects,
            'users': users,
            'is_edit': True
        })
    
    def post(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, delete_time__isnull=True)
        
        # 检查权限
        if not self.has_permission(request.user, task):
            return JsonResponse({'code': 1, 'msg': '没有权限编辑此任务'})
        
        try:
            # 获取表单数据
            title = request.POST.get('title')
            description = request.POST.get('description', '')
            project_id = request.POST.get('project_id')
            assignee_id = request.POST.get('assignee_id')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            estimated_hours = request.POST.get('estimated_hours', 0)
            priority = request.POST.get('priority', 2)
            status = request.POST.get('status', task.status)
            progress = request.POST.get('progress', task.progress)
            
            # 验证必填字段
            if not all([title, start_date, end_date]):
                return JsonResponse({'code': 1, 'msg': '请填写标题、开始日期和结束日期'})
            
            # 更新任务
            task.title = title
            task.description = description
            task.project_id = project_id if project_id else None
            task.assignee_id = assignee_id if assignee_id else None
            task.start_date = start_date
            task.end_date = end_date
            task.estimated_hours = estimated_hours
            task.priority = priority
            task.status = status
            task.progress = progress
            task.save()
            
            # 更新参与人员
            participant_ids_str = request.POST.get('participant_ids', '')
            if participant_ids_str:
                # 处理逗号分隔的员工ID字符串
                participant_ids = [id.strip() for id in participant_ids_str.split(',') if id.strip()]
                if participant_ids:
                    task.participants.set(participant_ids)
            
            return JsonResponse({'code': 0, 'msg': '任务更新成功'})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'更新失败: {str(e)}'})
    
    def has_permission(self, user, task):
        """检查用户是否有权限编辑任务"""
        if user.is_superuser:
            return True
        return (
            task.creator == user or
            task.assignee == user or
            user in task.participants.all() or
            (task.project and task.project.manager == user)
        )


class TaskDeleteView(LoginRequiredMixin, View):
    """删除任务视图"""
    login_url = '/user/login/'
    
    def post(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, delete_time__isnull=True)
        
        # 检查权限
        if not self.has_permission(request.user, task):
            return JsonResponse({'code': 1, 'msg': '没有权限删除此任务'})
        
        try:
            # 软删除
            task.delete_time = timezone.now()
            task.save()
            
            return JsonResponse({'code': 0, 'msg': '任务删除成功'})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})
    
    def has_permission(self, user, task):
        """检查用户是否有权限删除任务"""
        if user.is_superuser:
            return True
        return (
            task.creator == user or
            (task.project and task.project.creator == user)
        )


class TaskDetailView(LoginRequiredMixin, View):
    """任务详情视图"""
    login_url = '/user/login/'
    
    def get(self, request, task_id):
        task = get_object_or_404(Task, id=task_id, delete_time__isnull=True)
        
        # 检查权限
        if not self.has_permission(request.user, task):
            return JsonResponse({'code': 1, 'msg': '没有权限查看此任务'})
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Ajax请求返回JSON数据
            return JsonResponse({
                'code': 0,
                'msg': 'success',
                'data': {
                    'id': task.id,
                    'title': task.title,
                    'description': task.description,
                    'status': task.status,
                    'status_display': task.status_display,
                    'priority': task.priority,
                    'priority_display': task.priority_display,
                    'progress': task.progress,
                    'project_name': task.project.name if task.project else '无项目',
                    'assignee_name': task.assignee.username if task.assignee else '未分配',
                    'creator_name': task.creator.username if task.creator else '',
                    'start_date': task.start_date.strftime('%Y-%m-%d') if task.start_date else '',
                    'end_date': task.end_date.strftime('%Y-%m-%d') if task.end_date else '',
                    'estimated_hours': task.estimated_hours,
                    'actual_hours': task.actual_hours,
                    'is_overdue': task.is_overdue,
                    'create_time': task.create_time.strftime('%Y-%m-%d %H:%M')
                }
            })
        
        # 普通请求返回HTML页面
        work_hours = task.work_hours.all()[:10]
        return render(request, 'project/task_detail.html', {
            'task': task,
            'work_hours': work_hours
        })
    
    def has_permission(self, user, task):
        """检查用户是否有权限查看任务"""
        if user.is_superuser:
            return True
        return (
            task.creator == user or
            task.assignee == user or
            user in task.participants.all() or
            (task.project and (
                task.project.creator == user or
                task.project.manager == user or
                user in task.project.members.all()
            ))
        )


class WorkHourAddView(LoginRequiredMixin, View):
    """新增工时记录视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        tasks = Task.objects.filter(delete_time__isnull=True)
        users = User.objects.filter(is_active=True)
        return render(request, 'project/workhour_form.html', {
            'tasks': tasks,
            'users': users,
            'is_edit': False
        })
    
    def post(self, request):
        try:
            # 获取表单数据
            task_id = request.POST.get('task_id')
            user_id = request.POST.get('user_id', request.user.id)
            work_date = request.POST.get('work_date')
            hours = request.POST.get('hours')
            description = request.POST.get('description', '')
            
            # 验证必填字段
            if not all([task_id, work_date, hours]):
                return JsonResponse({'code': 1, 'msg': '请填写任务、工作日期和工作时长'})
            
            # 创建工时记录
            work_hour = WorkHour.objects.create(
                task_id=task_id,
                user_id=user_id,
                work_date=work_date,
                hours=hours,
                description=description
            )
            
            # 更新任务的实际工时
            task = work_hour.task
            task.actual_hours = task.work_hours.aggregate(
                total=models.Sum('hours')
            )['total'] or 0
            task.save()
            
            return JsonResponse({'code': 0, 'msg': '工时记录创建成功', 'data': {'id': work_hour.id}})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'创建失败: {str(e)}'})


class WorkHourEditView(LoginRequiredMixin, View):
    """编辑工时记录视图"""
    login_url = '/user/login/'
    
    def get(self, request, workhour_id):
        work_hour = get_object_or_404(WorkHour, id=workhour_id)
        
        # 检查权限
        if not self.has_permission(request.user, work_hour):
            return JsonResponse({'code': 1, 'msg': '没有权限编辑此工时记录'})
        
        tasks = Task.objects.filter(delete_time__isnull=True)
        users = User.objects.filter(is_active=True)
        
        return render(request, 'project/workhour_form.html', {
            'work_hour': work_hour,
            'tasks': tasks,
            'users': users,
            'is_edit': True
        })
    
    def post(self, request, workhour_id):
        work_hour = get_object_or_404(WorkHour, id=workhour_id)
        
        # 检查权限
        if not self.has_permission(request.user, work_hour):
            return JsonResponse({'code': 1, 'msg': '没有权限编辑此工时记录'})
        
        try:
            # 获取表单数据
            task_id = request.POST.get('task_id')
            user_id = request.POST.get('user_id')
            work_date = request.POST.get('work_date')
            hours = request.POST.get('hours')
            description = request.POST.get('description', '')
            
            # 验证必填字段
            if not all([task_id, work_date, hours]):
                return JsonResponse({'code': 1, 'msg': '请填写任务、工作日期和工作时长'})
            
            old_task = work_hour.task
            
            # 更新工时记录
            work_hour.task_id = task_id
            work_hour.user_id = user_id
            work_hour.work_date = work_date
            work_hour.hours = hours
            work_hour.description = description
            work_hour.save()
            
            # 更新旧任务的实际工时
            if old_task:
                old_task.actual_hours = old_task.work_hours.aggregate(
                    total=models.Sum('hours')
                )['total'] or 0
                old_task.save()
            
            # 更新新任务的实际工时
            new_task = work_hour.task
            if new_task and new_task != old_task:
                new_task.actual_hours = new_task.work_hours.aggregate(
                    total=models.Sum('hours')
                )['total'] or 0
                new_task.save()
            
            return JsonResponse({'code': 0, 'msg': '工时记录更新成功'})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'更新失败: {str(e)}'})
    
    def has_permission(self, user, work_hour):
        """检查用户是否有权限编辑工时记录"""
        if user.is_superuser:
            return True
        return (
            work_hour.user == user or
            work_hour.task.assignee == user or
            work_hour.task.creator == user or
            (work_hour.task.project and work_hour.task.project.manager == user)
        )


class WorkHourDeleteView(LoginRequiredMixin, View):
    """删除工时记录视图"""
    login_url = '/user/login/'
    
    def post(self, request, workhour_id):
        work_hour = get_object_or_404(WorkHour, id=workhour_id)
        
        # 检查权限
        if not self.has_permission(request.user, work_hour):
            return JsonResponse({'code': 1, 'msg': '没有权限删除此工时记录'})
        
        try:
            task = work_hour.task
            
            # 删除工时记录
            work_hour.delete()
            
            # 更新任务的实际工时
            if task:
                task.actual_hours = task.work_hours.aggregate(
                    total=models.Sum('hours')
                )['total'] or 0
                task.save()
            
            return JsonResponse({'code': 0, 'msg': '工时记录删除成功'})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})
    
    def has_permission(self, user, work_hour):
        """检查用户是否有权限删除工时记录"""
        if user.is_superuser:
            return True
        return (
            work_hour.user == user or
            work_hour.task.creator == user or
            (work_hour.task.project and work_hour.task.project.creator == user)
        )