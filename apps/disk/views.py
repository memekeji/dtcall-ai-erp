from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, Http404, FileResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.core.cache import cache
from .models import DiskFile, DiskFolder, DiskShare, DiskOperation
from .utils.image_utils import ImageUtils
from .constants import FileTypeConstants
from .utils.archive_preview import ArchivePreviewHandler
from apps.user.models import Admin as User
from apps.department.models import Department

import os
import json
import uuid
import mimetypes
import logging
import hashlib
import time
import re
from functools import wraps
from datetime import timedelta


logger = logging.getLogger(__name__)


def handle_preview_errors(default_msg='操作失败'):
    """预览操作错误处理装饰器
    
    统一处理预览相关的异常，返回标准化的JSON错误响应
    
    Args:
        default_msg: 默认错误消息
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            try:
                return view_func(self, request, *args, **kwargs)
            except FileNotFoundError:
                logger.error(f'文件不存在: {kwargs.get("file_id", "unknown")}')
                return JsonResponse({'code': 1, 'msg': '文件不存在'}, json_dumps_params={'ensure_ascii': False})
            except PermissionError:
                logger.error(f'没有权限访问文件')
                return JsonResponse({'code': 1, 'msg': '没有权限访问文件'}, json_dumps_params={'ensure_ascii': False})
            except MemoryError:
                logger.error(f'文件过大导致内存不足')
                return JsonResponse({'code': 1, 'msg': '文件过大，无法在线预览，请下载后查看'}, json_dumps_params={'ensure_ascii': False})
            except Http404:
                return JsonResponse({'code': 1, 'msg': '资源不存在'}, json_dumps_params={'ensure_ascii': False})
            except TimeoutError as e:
                logger.error(f'操作超时: {str(e)}')
                return JsonResponse({'code': 1, 'msg': f'操作超时，请稍后重试'}, json_dumps_params={'ensure_ascii': False})
            except Exception as e:
                logger.error(f'{default_msg}: {str(e)}', exc_info=True)
                return JsonResponse({'code': 1, 'msg': f'{default_msg}: {str(e)}'}, json_dumps_params={'ensure_ascii': False})
        return wrapper
    return decorator


def validate_file_path_security(file_path, media_root):
    """验证文件路径安全性，防止路径遍历攻击
    
    Args:
        file_path: 文件路径
        media_root: 媒体根目录
        
    Returns:
        (is_valid, error_message)
    """
    try:
        real_path = os.path.realpath(file_path)
        real_media_root = os.path.realpath(media_root)
        
        if not real_path.startswith(real_media_root):
            return False, '文件路径超出允许范围'
        
        if os.path.islink(file_path):
            return False, '不支持符号链接文件'
        
        return True, None
    except Exception as e:
        return False, f'路径验证失败: {str(e)}'


def get_preview_cache_key(file_id, update_timestamp):
    """生成预览缓存键"""
    return f'disk_preview_{file_id}_{int(update_timestamp)}'


def get_preview_from_cache(file_id, update_timestamp):
    """从缓存获取预览数据"""
    cache_key = get_preview_cache_key(file_id, update_timestamp)
    return cache.get(cache_key)


def set_preview_to_cache(file_id, update_timestamp, data, timeout=3600):
    """设置预览数据到缓存"""
    cache_key = get_preview_cache_key(file_id, update_timestamp)
    cache.set(cache_key, data, timeout)


def invalidate_preview_cache(file_id):
    """使指定文件的预览缓存失效"""
    pattern = f'disk_preview_{file_id}_*'
    try:
        cache_keys = cache.keys(pattern) if hasattr(cache, 'keys') else []
        for key in cache_keys:
            cache.delete(key)
    except Exception:
        pass


class BaseDiskView(LoginRequiredMixin, View):
    """网盘视图基类，提供公共方法"""
    login_url = '/user/login/'
    
    def log_operation(self, request, operation_type, file=None, folder=None, description=''):
        """记录操作日志"""
        try:
            DiskOperation.objects.create(
                user=request.user,
                operation_type=operation_type,
                file=file,
                folder=folder,
                description=description,
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500] if request.META.get('HTTP_USER_AGENT') else ''
            )
        except Exception as e:
            logger.error(f'记录操作日志失败: {str(e)}')
    
    def get_client_ip(self, request):
        """获取客户端IP地址"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def validate_path_security(self, file_path):
        """验证文件路径安全性，防止路径遍历攻击"""
        media_root = os.path.abspath(settings.MEDIA_ROOT)
        full_path = os.path.abspath(os.path.join(media_root, file_path))
        
        if not full_path.startswith(media_root):
            return False
        
        if not os.path.exists(full_path):
            return False
            
        return True


class DiskIndexView(BaseDiskView):
    """网盘首页"""
    
    def get(self, request):
        user_files = DiskFile.objects.filter(owner=request.user, delete_time__isnull=True)
        user_folders = DiskFolder.objects.filter(owner=request.user, delete_time__isnull=True)
        
        total_size = user_files.aggregate(total=Sum('file_size'))['total'] or 0
        file_count = user_files.count()
        folder_count = user_folders.count()
        
        recent_files = user_files.order_by('-update_time')[:10]
        starred_files = user_files.filter(is_starred=True)[:10]
        
        context = {
            'total_size': total_size,
            'file_count': file_count,
            'folder_count': folder_count,
            'recent_files': recent_files,
            'starred_files': starred_files
        }
        
        return render(request, 'disk/index.html', context)


class StarredFilesView(BaseDiskView):
    """收藏文件页面"""
    
    def get(self, request):
        starred_files = DiskFile.objects.filter(
            owner=request.user, 
            delete_time__isnull=True,
            is_starred=True
        ).order_by('-update_time')
        
        context = {
            'starred_files': starred_files
        }
        
        return render(request, 'disk/starred_files.html', context)


class PersonalDiskView(BaseDiskView):
    """个人文件视图"""
    
    def get(self, request):
        folder_id = request.GET.get('folder_id', '')
        search_term = request.GET.get('search', '')
        
        current_folder = None
        if folder_id:
            current_folder = get_object_or_404(
                DiskFolder, 
                id=folder_id, 
                owner=request.user, 
                delete_time__isnull=True
            )
        
        breadcrumbs = []
        if current_folder:
            folder = current_folder
            while folder:
                breadcrumbs.insert(0, folder)
                folder = folder.parent
        
        folder_conditions = Q(owner=request.user, parent=current_folder, delete_time__isnull=True)
        file_conditions = Q(owner=request.user, folder=current_folder, delete_time__isnull=True)
        
        if search_term:
            folder_conditions &= Q(name__icontains=search_term)
            file_conditions &= Q(name__icontains=search_term)
        
        folders = DiskFolder.objects.filter(folder_conditions).order_by('name')
        
        sort_by = request.GET.get('sort', 'update_time')
        order = request.GET.get('order', 'desc')
        
        sort_field_mapping = {
            'upload_time': 'update_time',
            'size': 'file_size',
            'views': 'view_count',
            'downloads': 'download_count'
        }
        
        sort_field = sort_field_mapping.get(sort_by, 'update_time')
        order_by = f'-{sort_field}' if order == 'desc' else sort_field
        
        files = DiskFile.objects.filter(file_conditions).order_by(order_by)
        
        context = {
            'current_folder': current_folder,
            'breadcrumbs': breadcrumbs,
            'folders': folders,
            'files': files,
        }
        return render(request, 'disk/personal.html', context)


class SharedDiskView(BaseDiskView):
    """共享文件视图"""
    
    def get(self, request):
        user_dept_id = getattr(request.user, 'did', None)
        
        if user_dept_id:
            shared_files = DiskFile.objects.filter(
                Q(shared_users=request.user) | 
                Q(shared_departments__id=user_dept_id),
                delete_time__isnull=True
            ).distinct().order_by('-update_time')
            
            shared_folders = DiskFolder.objects.filter(
                Q(shared_users=request.user) | 
                Q(shared_departments__id=user_dept_id),
                delete_time__isnull=True
            ).distinct().order_by('name')
        else:
            shared_files = DiskFile.objects.filter(
                Q(shared_users=request.user) |
                Q(is_public=True),
                delete_time__isnull=True
            ).distinct().order_by('-update_time')
            
            shared_folders = DiskFolder.objects.filter(
                Q(shared_users=request.user) |
                Q(is_public=True),
                delete_time__isnull=True
            ).distinct().order_by('name')
        
        context = {
            'shared_files': shared_files,
            'shared_folders': shared_folders,
        }
        return render(request, 'disk/shared.html', context)


class RecycleBinView(BaseDiskView):
    """回收站视图"""
    
    def get(self, request):
        deleted_files = DiskFile.objects.filter(
            owner=request.user,
            delete_time__isnull=False
        ).order_by('-delete_time')
        
        deleted_folders = DiskFolder.objects.filter(
            owner=request.user,
            delete_time__isnull=False
        ).order_by('-delete_time')
        
        context = {
            'deleted_files': deleted_files,
            'deleted_folders': deleted_folders,
        }
        return render(request, 'disk/recycle.html', context)


class FileSearchView(BaseDiskView):
    """文件搜索视图"""
    
    def get(self, request):
        query = request.GET.get('q', '').strip()
        file_type = request.GET.get('type', '')
        
        if not query:
            return JsonResponse({'code': 1, 'msg': '搜索关键词不能为空'})
        
        search_conditions = Q(owner=request.user, delete_time__isnull=True)
        search_conditions &= (
            Q(name__icontains=query) |
            Q(original_name__icontains=query)
        )
        
        if file_type:
            search_conditions &= Q(file_type=file_type)
        
        files = DiskFile.objects.filter(search_conditions).order_by('-update_time')[:50]
        
        folder_conditions = Q(owner=request.user, delete_time__isnull=True)
        folder_conditions &= Q(name__icontains=query)
        folders = DiskFolder.objects.filter(folder_conditions).order_by('-update_time')[:20]
        
        results = []
        
        for folder in folders:
            results.append({
                'type': 'folder',
                'id': folder.id,
                'name': folder.name,
                'path': folder.get_full_path(),
                'create_time': folder.create_time.strftime('%Y-%m-%d %H:%M'),
                'update_time': folder.update_time.strftime('%Y-%m-%d %H:%M')
            })
        
        for file in files:
            results.append({
                'type': 'file',
                'id': file.id,
                'name': file.name,
                'original_name': file.original_name,
                'file_type': file.file_type,
                'file_size': file.get_size_display(),
                'folder_path': file.folder.get_full_path() if file.folder else '根目录',
                'create_time': file.create_time.strftime('%Y-%m-%d %H:%M'),
                'update_time': file.update_time.strftime('%Y-%m-%d %H:%M')
            })
        
        return JsonResponse({
            'code': 0,
            'msg': 'success',
            'data': {
                'query': query,
                'total': len(results),
                'results': results
            }
        })


class FileShareCreateView(BaseDiskView):
    """创建文件分享视图"""
    
    def get(self, request):
        share_type = request.GET.get('type', 'file')
        item_id = request.GET.get('id', '')
        
        if not item_id:
            return JsonResponse({'code': 1, 'msg': '参数错误'})
        
        context = {
            'share_type': share_type,
            'item_id': item_id
        }
        return render(request, 'disk/share_create.html', context)
    
    def post(self, request):
        try:
            share_type = request.POST.get('type')
            item_id = request.POST.get('id')
            password = request.POST.get('password', '')
            expire_days = int(request.POST.get('expire_days', 7))
            
            permission_type = request.POST.get('permission_type', 'download')
            allow_download = request.POST.get('allow_download') == 'on'
            access_limit = int(request.POST.get('access_limit', 0))
            download_limit = int(request.POST.get('download_limit', 0))
            
            if not item_id or share_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            if share_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
            
            share_code = self.generate_share_code()
            
            expire_time = None
            if expire_days > 0:
                expire_time = timezone.now() + timedelta(days=expire_days)
            
            hashed_password = ''
            if password:
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
            
            share_data = {
                'share_type': share_type,
                'share_code': share_code,
                'password': hashed_password,
                'creator': request.user,
                'expire_time': expire_time,
                'permission_type': permission_type,
                'allow_download': allow_download,
                'access_limit': access_limit,
                'download_limit': download_limit
            }
            
            if share_type == 'file':
                share_data['file'] = item
            else:
                share_data['folder'] = item
            
            share = DiskShare.objects.create(**share_data)
            
            self.log_operation(request, 'share', 
                             file=item if share_type == 'file' else None,
                             folder=item if share_type == 'folder' else None,
                             description=f'创建分享: {item.name}')
            
            share_url = request.build_absolute_uri(f'/disk/share/view/{share_code}/')
            
            return JsonResponse({
                'code': 0,
                'msg': '分享创建成功',
                'data': {
                    'share_code': share_code,
                    'share_url': share_url,
                    'password': password if password else '',
                    'expire_time': expire_time.strftime('%Y-%m-%d %H:%M') if expire_time else '永久有效',
                    'permission_type': permission_type,
                    'allow_download': allow_download,
                    'access_limit': access_limit,
                    'download_limit': download_limit
                }
            })
            
        except Exception as e:
            logger.error(f'创建分享失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'创建失败: {str(e)}'})
    
    def generate_share_code(self):
        """生成安全的分享码"""
        while True:
            code = ''.join(uuid.uuid4().hex[:8].upper())
            if not DiskShare.objects.filter(share_code=code).exists():
                return code


class FileShareView(View):
    """查看分享文件视图"""
    
    def get(self, request, share_code):
        try:
            share = get_object_or_404(DiskShare, share_code=share_code, is_active=True)
            
            if share.is_expired():
                return render(request, 'disk/share_expired.html', {'share': share})
            
            if not share.can_access():
                return render(request, 'disk/share_error.html', {'error': '访问次数已达上限'})
            
            if share.password and not request.session.get(f'share_auth_{share_code}'):
                return render(request, 'disk/share_password.html', {'share': share})
            
            client_ip = self.get_client_ip(request)
            share.record_access(client_ip)
            
            if share.share_type == 'file':
                item = share.file
                item_type = 'file'
            else:
                item = share.folder
                item_type = 'folder'
            
            context = {
                'share': share,
                'item': item,
                'item_type': item_type
            }
            return render(request, 'disk/share_view.html', context)
            
        except Exception as e:
            logger.error(f'查看分享失败: {str(e)}')
            return render(request, 'disk/share_error.html', {'error': str(e)})
    
    def post(self, request, share_code):
        try:
            share = get_object_or_404(DiskShare, share_code=share_code, is_active=True)
            password = request.POST.get('password', '')
            
            input_password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            if share.password == input_password_hash:
                request.session[f'share_auth_{share_code}'] = True
                return JsonResponse({'code': 0, 'msg': '验证成功'})
            else:
                return JsonResponse({'code': 1, 'msg': '密码错误'})
                
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'验证失败: {str(e)}'})
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SharePreviewView(View):
    """分享文件预览视图"""
    
    def get(self, request, file_id):
        try:
            share_code = request.GET.get('share_code')
            if not share_code:
                return JsonResponse({'code': 1, 'msg': '缺少分享码'})
            
            share = get_object_or_404(DiskShare, share_code=share_code, is_active=True)
            
            if share.is_expired():
                return JsonResponse({'code': 1, 'msg': '分享已过期'})
            
            if not share.can_access():
                return JsonResponse({'code': 1, 'msg': '访问次数已达上限'})
            
            if share.password and not request.session.get(f'share_auth_{share_code}'):
                return JsonResponse({'code': 2, 'msg': '请先验证密码', 'need_password': True})
            
            disk_file = get_object_or_404(DiskFile, id=file_id, delete_time__isnull=True)
            
            if not share.contains_file(disk_file.id):
                return JsonResponse({'code': 1, 'msg': '文件不属于此分享'})
            
            share.record_preview()
            
            file_obj = disk_file
            full_file_path = os.path.join(settings.MEDIA_ROOT, file_obj.file_path)
            
            is_valid, error_msg = validate_file_path_security(full_file_path, settings.MEDIA_ROOT)
            if not is_valid:
                logger.warning(f'分享预览路径安全验证失败: {file_id}, {error_msg}')
                return JsonResponse({'code': 1, 'msg': error_msg}, json_dumps_params={'ensure_ascii': False})
            
            if not os.path.exists(full_file_path):
                return JsonResponse({'code': 1, 'msg': '文件不存在'}, json_dumps_params={'ensure_ascii': False})
            
            preview_view = FilePreviewView()
            preview_data = preview_view._get_preview_content(file_obj, request)
            
            if preview_data:
                return JsonResponse({
                    'code': 0,
                    'msg': 'success',
                    'data': preview_data
                }, json_dumps_params={'ensure_ascii': False})
            else:
                return JsonResponse({
                    'code': 1,
                    'msg': '文件预览暂不支持此格式'
                }, json_dumps_params={'ensure_ascii': False})
            
        except Http404:
            return JsonResponse({'code': 1, 'msg': '分享或文件不存在'})
        except Exception as e:
            logger.error(f'分享预览失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': f'预览失败: {str(e)}'})


class PreviewView(View):
    """统一预览页面视图"""
    
    def get(self, request):
        file_id = request.GET.get('file_id')
        file_name = request.GET.get('file_name')
        file_type = request.GET.get('file_type')
        share_code = request.GET.get('share_code')
        
        context = {
            'file_id': file_id,
            'file_name': file_name,
            'file_type': file_type,
            'share_code': share_code
        }
        
        return render(request, 'disk/preview.html', context)


class FilePreviewView(LoginRequiredMixin, View):
    """文件预览视图"""
    login_url = '/user/login/'
    
    PREVIEW_HANDLERS = None
    
    def __init__(self):
        super().__init__()
        if self.PREVIEW_HANDLERS is None:
            self.PREVIEW_HANDLERS = {
                'text': self._preview_text_file,
                'image': self._preview_image_file,
                'office': self._preview_office_file,
                'pdf': self._preview_pdf_file,
                'audio': self._preview_audio_file,
                'video': self._preview_video_file,
                'archive': self._preview_archive_file,
            }
    
    def get(self, request, file_id):
        try:
            file_obj = get_object_or_404(DiskFile, id=file_id, owner=request.user, delete_time__isnull=True)
            
            file_obj.view_count += 1
            file_obj.preview_count += 1
            file_obj.last_preview_time = timezone.now()
            file_obj.save(update_fields=['view_count', 'preview_count', 'last_preview_time'])
            
            full_file_path = os.path.join(settings.MEDIA_ROOT, file_obj.file_path)
            
            is_valid, error_msg = validate_file_path_security(full_file_path, settings.MEDIA_ROOT)
            if not is_valid:
                logger.warning(f'路径安全验证失败: {file_id}, {error_msg}')
                return JsonResponse({'code': 1, 'msg': error_msg}, json_dumps_params={'ensure_ascii': False})
            
            if not os.path.exists(full_file_path):
                return JsonResponse({
                    'code': 1,
                    'msg': '文件不存在'
                }, json_dumps_params={'ensure_ascii': False})
            
            update_timestamp = file_obj.update_time.timestamp()
            cached_data = get_preview_from_cache(file_id, update_timestamp)
            
            if cached_data is not None:
                return JsonResponse({
                    'code': 0,
                    'msg': 'success (from cache)',
                    'data': cached_data
                }, json_dumps_params={'ensure_ascii': False})
            
            preview_data = self._get_preview_content(file_obj, request)
            
            if preview_data:
                set_preview_to_cache(file_id, update_timestamp, preview_data)
                
                return JsonResponse({
                    'code': 0,
                    'msg': 'success',
                    'data': preview_data
                }, json_dumps_params={'ensure_ascii': False})
            else:
                return JsonResponse({
                    'code': 1,
                    'msg': '文件预览暂不支持此格式'
                }, json_dumps_params={'ensure_ascii': False})
                
        except FileNotFoundError:
            logger.error(f'文件不存在: {file_id}')
            return JsonResponse({'code': 1, 'msg': '文件不存在'}, json_dumps_params={'ensure_ascii': False})
        except PermissionError:
            logger.error(f'没有权限访问文件: {file_id}')
            return JsonResponse({'code': 1, 'msg': '没有权限访问文件'}, json_dumps_params={'ensure_ascii': False})
        except MemoryError:
            logger.error(f'文件过大导致内存不足: {file_id}')
            return JsonResponse({'code': 1, 'msg': '文件过大，无法在线预览，请下载后查看'}, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            logger.error(f'文件预览失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': f'文件预览失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})
                
    def _get_preview_content(self, file_obj, request):
        file_ext = file_obj.file_ext.lstrip('.').lower()
        file_type = FileTypeConstants.get_file_type(file_ext)
        
        handler = self.PREVIEW_HANDLERS.get(file_type)
        if handler:
            if file_type in ['text']:
                return handler(file_obj)
            else:
                return handler(file_obj, request)
        
        return None
    
    def _preview_text_file(self, file_obj):
        try:
            max_size = 5 * 1024 * 1024
            max_lines = 5000
            max_chars = 2000000
            
            full_file_path = os.path.join(settings.MEDIA_ROOT, file_obj.file_path)
            
            if not os.path.exists(full_file_path):
                return {
                    'type': 'text',
                    'content': '文件不存在或无法访问',
                    'error': 'file_not_found',
                    'name': file_obj.name
                }
            
            if not os.path.isfile(full_file_path):
                return {
                    'type': 'text',
                    'content': '路径不是有效的文件',
                    'error': 'not_a_file',
                    'name': file_obj.name
                }
            
            file_size = os.path.getsize(full_file_path)
            if file_size > max_size:
                return {
                    'type': 'text',
                    'content': f'文件过大（{file_size}字节），请下载后查看',
                    'truncated': True,
                    'name': file_obj.name
                }
            
            content = None
            encoding_used = 'utf-8'
            line_count = 0
            char_count = 0
            
            for encoding in FileTypeConstants.TEXT_ENCODINGS:
                try:
                    content_lines = []
                    current_line_count = 0
                    current_char_count = 0
                    
                    with open(full_file_path, 'r', encoding=encoding, errors='replace') as f:
                        for line in f:
                            line_length = len(line)
                            if current_char_count + line_length > max_chars:
                                remaining_chars = max_chars - current_char_count
                                line = line[:remaining_chars]
                                content_lines.append(line)
                                current_char_count = max_chars
                                current_line_count += 1
                                break
                            
                            content_lines.append(line)
                            current_line_count += 1
                            current_char_count += line_length
                            
                            if current_line_count >= max_lines:
                                break
                    
                    if content_lines:
                        content = ''.join(content_lines)
                        line_count = current_line_count
                        char_count = current_char_count
                        encoding_used = encoding
                        
                        if content.strip():
                            break
                except Exception:
                    continue
            
            if content is None or not content.strip():
                try:
                    with open(full_file_path, 'rb') as f:
                        raw_content = f.read(max_size)
                    
                    if not raw_content:
                        return {
                            'type': 'text',
                            'content': '[文件内容为空]',
                            'encoding': 'empty',
                            'name': file_obj.name
                        }
                    
                    if raw_content.startswith(b'\xef\xbb\xbf'):
                        content = raw_content[3:].decode('utf-8')
                        encoding_used = 'utf-8-bom'
                    elif raw_content.startswith(b'\xff\xfe'):
                        content = raw_content[2:].decode('utf-16le')
                        encoding_used = 'utf-16le-bom'
                    elif raw_content.startswith(b'\xfe\xff'):
                        content = raw_content[2:].decode('utf-16be')
                        encoding_used = 'utf-16be-bom'
                    else:
                        content = raw_content.decode('utf-8', errors='replace')
                        encoding_used = 'binary-fallback'
                except Exception:
                    content = '[无法读取文件内容]'
                    encoding_used = 'error'
            
            import re
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', content)
            
            if not content.strip():
                content = '[文件内容为空或仅包含空白字符]'
            
            return {
                'type': 'text',
                'content': content,
                'truncated': char_count >= max_chars or line_count >= max_lines,
                'encoding': encoding_used,
                'name': file_obj.name,
                'file_ext': file_obj.file_ext,
                'file_id': file_obj.id
            }
            
        except PermissionError:
            return {
                'type': 'text',
                'content': '没有权限读取文件',
                'error': 'permission_denied',
                'name': file_obj.name
            }
        except Exception as e:
            return {
                'type': 'text',
                'content': f'读取文本文件失败: {str(e)}',
                'error': 'read_error',
                'name': file_obj.name
            }
    
    def _preview_image_file(self, file_obj, request):
        try:
            full_file_path = os.path.join(settings.MEDIA_ROOT, file_obj.file_path)
            
            if not os.path.exists(full_file_path):
                return {
                    'type': 'image',
                    'content': '文件不存在',
                    'error': 'file_not_found',
                    'name': file_obj.name
                }
            
            thumbnail_url = None
            use_thumbnail = ImageUtils.should_use_thumbnail(file_obj.id, full_file_path)
            
            if use_thumbnail:
                thumbnail_url = request.build_absolute_uri(
                    reverse('disk:image_thumbnail', kwargs={'file_id': file_obj.id})
                ) + '?size=medium'
            
            image_url = request.build_absolute_uri(
                reverse('disk:file_download', kwargs={'file_id': file_obj.id})
            )
            
            image_info = ImageUtils.get_image_info(full_file_path)
            
            return {
                'type': 'image',
                'url': image_url,
                'thumbnail_url': thumbnail_url,
                'use_thumbnail': use_thumbnail,
                'name': file_obj.name,
                'file_id': file_obj.id,
                'image_info': image_info
            }
            
        except Exception as e:
            logger.error(f'图片文件预览失败: {str(e)}')
            return None
    
    def _preview_office_file(self, file_obj, request):
        try:
            from .utils.office_preview import OfficePreviewHandler
            
            full_file_path = os.path.join(settings.MEDIA_ROOT, file_obj.file_path)
            conversion_format = request.GET.get('format')
            
            result = OfficePreviewHandler.preview_office_file(full_file_path, conversion_format)
            
            result['file_id'] = file_obj.id
            result['download_url'] = request.build_absolute_uri(
                reverse('disk:file_download', kwargs={'file_id': file_obj.id})
            )
            
            return result
                
        except Exception as e:
            logger.error(f'Office文件预览失败: {str(e)}')
            return {
                'type': 'error',
                'message': f'Office文档预览失败: {str(e)}'
            }
    
    def _preview_pdf_file(self, file_obj, request):
        try:
            full_file_path = os.path.join(settings.MEDIA_ROOT, file_obj.file_path)
            
            if not os.path.exists(full_file_path):
                return {
                    'type': 'error',
                    'message': 'PDF文件不存在'
                }
            
            file_url = request.build_absolute_uri(
                reverse('disk:file_download', kwargs={'file_id': file_obj.id})
            )
            
            return {
                'type': 'pdf',
                'url': file_url,
                'name': file_obj.name,
                'file_id': file_obj.id
            }
                
        except Exception as e:
            logger.error(f'PDF文件预览失败: {str(e)}')
            return {
                'type': 'error',
                'message': f'PDF文件预览失败: {str(e)}'
            }
    
    def _preview_audio_file(self, file_obj, request):
        try:
            audio_url = request.build_absolute_uri(
                reverse('disk:file_download', kwargs={'file_id': file_obj.id})
            )
            
            return {
                'type': 'audio',
                'url': audio_url,
                'name': file_obj.name
            }
            
        except Exception as e:
            logger.error(f'音频文件预览失败: {str(e)}')
            return None
    
    def _preview_video_file(self, file_obj, request):
        try:
            video_url = request.build_absolute_uri(
                reverse('disk:file_download', kwargs={'file_id': file_obj.id})
            )
            
            return {
                'type': 'video',
                'url': video_url,
                'name': file_obj.name
            }
            
        except Exception as e:
            logger.error(f'视频文件预览失败: {str(e)}')
            return None
    
    def _preview_archive_file(self, file_obj, request):
        try:
            full_file_path = os.path.join(settings.MEDIA_ROOT, file_obj.file_path)
            
            if not os.path.exists(full_file_path):
                return {
                    'type': 'archive',
                    'content': '文件不存在',
                    'error': 'file_not_found',
                    'name': file_obj.name
                }
            
            file_ext = file_obj.file_ext.lower()
            
            if not ArchivePreviewHandler.can_preview(file_ext):
                return {
                    'type': 'archive',
                    'content': '不支持该压缩包格式的预览',
                    'error': 'unsupported_format',
                    'name': file_obj.name
                }
            
            result = ArchivePreviewHandler.preview_archive(full_file_path, file_obj.name)
            result['file_id'] = file_obj.id
            
            return result
            
        except Exception as e:
            logger.error(f'压缩包预览失败: {str(e)}')
            return {
                'type': 'archive',
                'content': f'压缩包预览失败: {str(e)}',
                'error': 'preview_error',
                'name': file_obj.name
            }


class ImageThumbnailView(LoginRequiredMixin, View):
    """图片缩略图视图"""
    login_url = '/user/login/'
    
    def get(self, request, file_id):
        """获取图片缩略图
        
        Query Parameters:
            size: 缩略图尺寸 (small/medium/large/xlarge)，默认 medium
            quality: JPEG质量 (1-100)，默认 85
        """
        try:
            size = request.GET.get('size', 'medium')
            if size not in ImageUtils.THUMBNAIL_SIZES:
                size = 'medium'
            
            disk_file = get_object_or_404(DiskFile, id=file_id, delete_time__isnull=True)
            
            if not self.has_permission(request.user, disk_file):
                return JsonResponse({'code': 1, 'msg': '没有权限查看此图片'}, json_dumps_params={'ensure_ascii': False})
            
            full_file_path = os.path.join(settings.MEDIA_ROOT, disk_file.file_path)
            
            if not os.path.exists(full_file_path):
                return JsonResponse({'code': 1, 'msg': '文件不存在'}, json_dumps_params={'ensure_ascii': False})
            
            try:
                thumbnail_data = ImageUtils.get_thumbnail(file_id, full_file_path, size)
                
                response = HttpResponse(thumbnail_data, content_type='image/jpeg')
                response['Content-Disposition'] = f'inline; filename="thumb_{size}_{disk_file.name}.jpg"'
                response['Cache-Control'] = 'public, max-age=86400'
                return response
                
            except Exception as e:
                logger.error(f'生成缩略图失败: {str(e)}')
                return JsonResponse({'code': 1, 'msg': f'生成缩略图失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})
                
        except Http404:
            return JsonResponse({'code': 1, 'msg': '文件不存在'}, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            logger.error(f'缩略图获取失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': f'获取缩略图失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})
    
    def has_permission(self, user, disk_file):
        if user == disk_file.owner:
            return True
        if disk_file.is_public:
            return True
        if user in disk_file.shared_users.all():
            return True
        if hasattr(user, 'did') and user.did and disk_file.shared_departments.filter(id=user.did).exists():
            return True
        return False


class ShareDownloadView(View):
    """分享下载视图"""
    
    def post(self, request):
        try:
            share_code = request.POST.get('share_code')
            file_id = request.POST.get('file_id')
            
            if not share_code or not file_id:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            share = get_object_or_404(DiskShare, share_code=share_code, is_active=True)
            
            if not share.can_download():
                return JsonResponse({'code': 1, 'msg': '没有下载权限或已达下载限制'})
            
            if share.password and not request.session.get(f'share_auth_{share_code}'):
                return JsonResponse({'code': 1, 'msg': '请先验证密码'})
            
            disk_file = get_object_or_404(DiskFile, id=file_id, delete_time__isnull=True)
            
            if not share.contains_file(disk_file.id):
                return JsonResponse({'code': 1, 'msg': '文件不属于此分享'})
            
            share.record_download()
            
            return JsonResponse({'code': 0, 'msg': '下载授权成功'})
            
        except Exception as e:
            logger.error(f'分享下载失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'下载失败: {str(e)}'})

    def is_file_in_folder(self, file, folder):
        current_folder = file.folder
        while current_folder:
            if current_folder.id == folder.id:
                return True
            current_folder = current_folder.parent
        return False


class ShareFolderView(View):
    """分享文件夹内容视图"""
    
    def get(self, request):
        try:
            share_code = request.GET.get('share_code')
            folder_id = request.GET.get('folder_id', '')
            
            if not share_code:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            share = get_object_or_404(DiskShare, share_code=share_code, is_active=True)
            
            if not share.can_access():
                return JsonResponse({'code': 1, 'msg': '没有访问权限'})
            
            if share.password and not request.session.get(f'share_auth_{share_code}'):
                return JsonResponse({'code': 1, 'msg': '请先验证密码'})
            
            if share.share_type != 'folder':
                return JsonResponse({'code': 1, 'msg': '此分享不是文件夹'})
            
            if folder_id:
                target_folder = get_object_or_404(DiskFolder, id=folder_id, delete_time__isnull=True)
                if not self.is_folder_in_share(target_folder, share.folder):
                    return JsonResponse({'code': 1, 'msg': '文件夹不在分享范围内'})
            else:
                target_folder = share.folder
            
            folders = DiskFolder.objects.filter(
                parent=target_folder,
                delete_time__isnull=True
            ).order_by('name')
            
            files = DiskFile.objects.filter(
                folder=target_folder,
                delete_time__isnull=True
            ).order_by('-update_time')
            
            folder_data = []
            for folder in folders:
                folder_data.append({
                    'id': folder.id,
                    'name': folder.name,
                    'update_time': folder.update_time.strftime('%Y-%m-%d %H:%M')
                })
            
            file_data = []
            for file in files:
                file_data.append({
                    'id': file.id,
                    'name': file.name,
                    'size': file.get_size_display(),
                    'file_type': file.file_type,
                    'update_time': file.update_time.strftime('%Y-%m-%d %H:%M')
                })
            
            return JsonResponse({
                'code': 0,
                'msg': 'success',
                'data': {
                    'folders': folder_data,
                    'files': file_data
                }
            })
            
        except Exception as e:
            logger.error(f'获取分享文件夹内容失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'获取失败: {str(e)}'})
    
    def is_folder_in_share(self, folder, share_folder):
        if folder.id == share_folder.id:
            return True
        
        current_folder = folder.parent
        while current_folder:
            if current_folder.id == share_folder.id:
                return True
            current_folder = current_folder.parent
        return False


class FileStarToggleView(BaseDiskView):
    """切换文件收藏状态视图"""
    
    def post(self, request, file_id):
        try:
            disk_file = get_object_or_404(DiskFile, id=file_id, owner=request.user, delete_time__isnull=True)
            
            disk_file.is_starred = not disk_file.is_starred
            disk_file.save()
            
            action = '收藏' if disk_file.is_starred else '取消收藏'
            op_type = 'star' if disk_file.is_starred else 'unstar'
            
            self.log_operation(request, op_type, file=disk_file, description=f'{action}文件: {disk_file.name}')
            
            return JsonResponse({
                'code': 0,
                'msg': f'{action}成功',
                'data': {'is_starred': disk_file.is_starred}
            })
            
        except Exception as e:
            logger.error(f'切换收藏状态失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'操作失败: {str(e)}'})


class FileUploadView(BaseDiskView):
    """文件上传视图"""
    
    def get(self, request):
        if '/upload/check/' in request.path:
            folder_id = request.GET.get('folder_id', '')
            file_name = request.GET.get('file_name', '')
            
            if not file_name:
                return JsonResponse({'code': 1, 'msg': '文件名不能为空'})
            
            target_folder = None
            if folder_id:
                target_folder = get_object_or_404(DiskFolder, id=folder_id, owner=request.user)
            
            existing_file = DiskFile.objects.filter(
                name=file_name,
                folder=target_folder,
                owner=request.user,
                delete_time__isnull=True
            ).first()
            
            if existing_file:
                return JsonResponse({
                    'code': 0,
                    'msg': '文件已存在',
                    'data': {
                        'exists': True,
                        'file_id': existing_file.id,
                        'file_name': existing_file.name,
                        'file_size': existing_file.file_size,
                        'file_size_display': existing_file.get_size_display(),
                        'file_type': existing_file.file_type
                    }
                })
            else:
                return JsonResponse({
                    'code': 0,
                    'msg': '文件不存在',
                    'data': {
                        'exists': False
                    }
                })
        else:
            return render(request, 'disk/upload.html')
    
    def post(self, request):
        try:
            folder_id = request.POST.get('folder_id', '')
            uploaded_file = request.FILES.get('file')
            action = request.POST.get('action', 'upload')
            file_id = request.POST.get('file_id', '')
            
            if not uploaded_file:
                return JsonResponse({'code': 1, 'msg': '没有选择文件'})
            
            max_file_size = 500 * 1024 * 1024
            if uploaded_file.size > max_file_size:
                return JsonResponse({'code': 1, 'msg': f'文件大小不能超过{max_file_size // (1024*1024)}MB'})
            
            target_folder = None
            if folder_id:
                target_folder = get_object_or_404(DiskFolder, id=folder_id, owner=request.user)
            
            if action == 'overwrite' and file_id:
                existing_file = get_object_or_404(DiskFile, id=file_id, owner=request.user, delete_time__isnull=True)
                
                old_path = os.path.join(settings.MEDIA_ROOT, existing_file.file_path)
                if os.path.exists(old_path):
                    os.remove(old_path)
                
                file_ext = os.path.splitext(uploaded_file.name)[1]
                unique_filename = f"{uuid.uuid4().hex}{file_ext}"
                
                upload_dir = f'disk/{request.user.id}'
                full_upload_dir = os.path.join(settings.MEDIA_ROOT, upload_dir)
                if not os.path.exists(full_upload_dir):
                    os.makedirs(full_upload_dir)
                
                file_path = os.path.join(upload_dir, unique_filename)
                saved_path = default_storage.save(file_path, ContentFile(uploaded_file.read()))
                
                existing_file.file_path = saved_path
                existing_file.file_size = uploaded_file.size
                existing_file.update_time = timezone.now()
                existing_file.save()
                
                self.log_operation(request, 'overwrite', file=existing_file, description=f'覆盖文件: {uploaded_file.name}')
                
                return JsonResponse({
                    'code': 0,
                    'msg': '文件覆盖成功',
                    'data': {
                        'id': existing_file.id,
                        'name': existing_file.name,
                        'size': existing_file.get_size_display(),
                        'type': existing_file.file_type
                    }
                })
            
            if action == 'rename':
                base_name, file_ext = os.path.splitext(uploaded_file.name)
                counter = 1
                new_file_name = uploaded_file.name
                
                while DiskFile.objects.filter(
                    name=new_file_name,
                    folder=target_folder,
                    owner=request.user,
                    delete_time__isnull=True
                ).exists():
                    new_file_name = f"{base_name}({counter}){file_ext}"
                    counter += 1
            else:
                existing_file = DiskFile.objects.filter(
                    name=uploaded_file.name,
                    folder=target_folder,
                    owner=request.user,
                    delete_time__isnull=True
                ).first()
                
                if existing_file:
                    return JsonResponse({
                        'code': 2,
                        'msg': '文件已存在',
                        'data': {
                            'file_id': existing_file.id,
                            'file_name': existing_file.name
                        }
                    })
                
                new_file_name = uploaded_file.name
            
            file_ext = os.path.splitext(new_file_name)[1]
            unique_filename = f"{uuid.uuid4().hex}{file_ext}"
            
            upload_dir = f'disk/{request.user.id}'
            full_upload_dir = os.path.join(settings.MEDIA_ROOT, upload_dir)
            if not os.path.exists(full_upload_dir):
                os.makedirs(full_upload_dir)
            
            file_path = os.path.join(upload_dir, unique_filename)
            saved_path = default_storage.save(file_path, ContentFile(uploaded_file.read()))
            
            user_department = None
            if hasattr(request.user, 'did') and request.user.did > 0:
                try:
                    user_department = Department.objects.get(id=request.user.did)
                except Department.DoesNotExist:
                    pass
            
            disk_file = DiskFile.objects.create(
                name=new_file_name,
                original_name=uploaded_file.name,
                file_path=saved_path,
                file_size=uploaded_file.size,
                folder=target_folder,
                owner=request.user,
                department=user_department
            )
            
            self.log_operation(request, 'upload', file=disk_file, description=f'上传文件: {new_file_name}')
            
            return JsonResponse({
                'code': 0,
                'msg': '文件上传成功',
                'data': {
                    'id': disk_file.id,
                    'name': disk_file.name,
                    'size': disk_file.get_size_display(),
                    'type': disk_file.file_type
                }
            })
            
        except Exception as e:
            logger.error(f'文件上传失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'上传失败: {str(e)}'})


class FileDownloadView(BaseDiskView):
    """文件下载视图"""
    
    PREVIEWABLE_TYPES = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
    
    def get(self, request, file_id):
        try:
            disk_file = get_object_or_404(DiskFile, id=file_id, delete_time__isnull=True)
            
            if not self.has_permission(request.user, disk_file):
                return JsonResponse({'code': 1, 'msg': '没有权限下载此文件'})
            
            file_path = os.path.join(settings.MEDIA_ROOT, disk_file.file_path)
            if not os.path.exists(file_path):
                return JsonResponse({'code': 1, 'msg': '文件不存在'})
            
            if not self.validate_path_security(disk_file.file_path):
                return JsonResponse({'code': 1, 'msg': '文件路径无效'})
            
            disk_file.download_count += 1
            disk_file.save(update_fields=['download_count'])
            
            self.log_operation(request, 'download', file=disk_file, description=f'下载文件: {disk_file.name}')
            
            file_ext = disk_file.file_ext.lower()
            is_previewable = file_ext in self.PREVIEWABLE_TYPES
            
            response = FileResponse(
                open(file_path, 'rb'),
                as_attachment=not is_previewable,
                filename=disk_file.original_name
            )
            
            if is_previewable:
                content_types = {
                    '.pdf': 'application/pdf',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.webp': 'image/webp',
                    '.bmp': 'image/bmp',
                    '.svg': 'image/svg+xml',
                    '.doc': 'application/msword',
                    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    '.xls': 'application/vnd.ms-excel',
                    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    '.ppt': 'application/vnd.ms-powerpoint',
                    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                }
                response['Content-Type'] = content_types.get(file_ext, 'application/octet-stream')
            
            if file_ext != '.pdf':
                response['X-Frame-Options'] = 'SAMEORIGIN'
            else:
                response['Content-Disposition'] = 'inline; filename="' + disk_file.original_name + '"'
            
            return response
            
        except Exception as e:
            logger.error(f'文件下载失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'下载失败: {str(e)}'})
    
    def has_permission(self, user, disk_file):
        if user == disk_file.owner:
            return True
        if disk_file.is_public:
            return True
        if user in disk_file.shared_users.all():
            return True
        if hasattr(user, 'did') and user.did and disk_file.shared_departments.filter(id=user.did).exists():
            return True
        return False


class FolderCreateView(BaseDiskView):
    """创建文件夹视图"""
    
    def post(self, request):
        try:
            folder_name = request.POST.get('name', '').strip()
            parent_id = request.POST.get('parent_id', '')
            
            if not folder_name:
                return JsonResponse({'code': 1, 'msg': '文件夹名称不能为空'})
            
            if len(folder_name) > 200:
                return JsonResponse({'code': 1, 'msg': '文件夹名称不能超过200个字符'})
            
            parent_folder = None
            if parent_id:
                parent_folder = get_object_or_404(DiskFolder, id=parent_id, owner=request.user)
            
            if DiskFolder.objects.filter(
                owner=request.user,
                parent=parent_folder,
                name=folder_name,
                delete_time__isnull=True
            ).exists():
                return JsonResponse({'code': 1, 'msg': '文件夹名称已存在'})
            
            folder = DiskFolder.objects.create(
                name=folder_name,
                parent=parent_folder,
                owner=request.user,
                department_id=getattr(request.user, 'did', None) if hasattr(request.user, 'did') else None
            )
            
            self.log_operation(request, 'create', folder=folder, description=f'创建文件夹: {folder_name}')
            
            return JsonResponse({
                'code': 0,
                'msg': '文件夹创建成功',
                'data': {
                    'id': folder.id,
                    'name': folder.name
                }
            })
            
        except Exception as e:
            logger.error(f'创建文件夹失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'创建失败: {str(e)}'})


class FolderRenameView(BaseDiskView):
    """重命名文件夹视图"""
    
    def post(self, request, folder_id):
        try:
            new_name = request.POST.get('name', '').strip()
            
            if not new_name:
                return JsonResponse({'code': 1, 'msg': '文件夹名称不能为空'})
            
            if len(new_name) > 200:
                return JsonResponse({'code': 1, 'msg': '文件夹名称不能超过200个字符'})
            
            folder = get_object_or_404(DiskFolder, id=folder_id, owner=request.user, delete_time__isnull=True)
            
            if folder.name == new_name:
                return JsonResponse({'code': 0, 'msg': '重命名成功', 'data': {'name': new_name}})
            
            if DiskFolder.objects.filter(
                owner=request.user,
                parent=folder.parent,
                name=new_name,
                delete_time__isnull=True
            ).exclude(id=folder_id).exists():
                return JsonResponse({'code': 1, 'msg': '同级目录下已存在同名文件夹'})
            
            old_name = folder.name
            folder.name = new_name
            folder.save()
            
            self.log_operation(request, 'rename', folder=folder, description=f'重命名文件夹: {old_name} -> {new_name}')
            
            return JsonResponse({
                'code': 0,
                'msg': '重命名成功',
                'data': {
                    'id': folder.id,
                    'name': folder.name
                }
            })
            
        except Exception as e:
            logger.error(f'重命名文件夹失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'重命名失败: {str(e)}'})


class FileRenameView(BaseDiskView):
    """重命名文件视图"""
    
    def post(self, request, file_id):
        try:
            new_name = request.POST.get('name', '').strip()
            
            if not new_name:
                return JsonResponse({'code': 1, 'msg': '文件名称不能为空'})
            
            if len(new_name) > 200:
                return JsonResponse({'code': 1, 'msg': '文件名称不能超过200个字符'})
            
            disk_file = get_object_or_404(DiskFile, id=file_id, owner=request.user, delete_time__isnull=True)
            
            original_ext = os.path.splitext(disk_file.name)[1]
            new_ext = os.path.splitext(new_name)[1]
            
            if not new_ext and original_ext:
                new_name = f"{new_name}{original_ext}"
            
            if disk_file.name == new_name:
                return JsonResponse({'code': 0, 'msg': '重命名成功', 'data': {'name': new_name}})
            
            old_name = disk_file.name
            disk_file.name = new_name
            disk_file.save()
            
            self.log_operation(request, 'rename', file=disk_file, description=f'重命名文件: {old_name} -> {new_name}')
            
            return JsonResponse({
                'code': 0,
                'msg': '重命名成功',
                'data': {
                    'id': disk_file.id,
                    'name': disk_file.name
                }
            })
            
        except Exception as e:
            logger.error(f'重命名文件失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'重命名失败: {str(e)}'})


class FileMoveView(BaseDiskView):
    """移动文件视图"""
    
    def post(self, request):
        try:
            file_id = request.POST.get('file_id')
            target_folder_id = request.POST.get('target_folder_id', '') or None
            
            if not file_id:
                return JsonResponse({'code': 1, 'msg': '文件ID不能为空'})
            
            disk_file = get_object_or_404(DiskFile, id=file_id, owner=request.user, delete_time__isnull=True)
            
            if target_folder_id:
                target_folder = get_object_or_404(DiskFolder, id=target_folder_id, owner=request.user, delete_time__isnull=True)
                
                if target_folder == disk_file.folder:
                    return JsonResponse({'code': 0, 'msg': '文件已在目标文件夹中'})
                
                if self.is_descendant_folder(target_folder, disk_file.folder):
                    return JsonResponse({'code': 1, 'msg': '不能将文件夹移动到其子文件夹中'})
            else:
                target_folder = None
            
            disk_file.folder = target_folder
            disk_file.save()
            
            self.log_operation(request, 'move', file=disk_file, description=f'移动文件: {disk_file.name}')
            
            return JsonResponse({
                'code': 0,
                'msg': '文件移动成功',
                'data': {
                    'id': disk_file.id,
                    'name': disk_file.name
                }
            })
            
        except Exception as e:
            logger.error(f'移动文件失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'移动失败: {str(e)}'})
    
    def is_descendant_folder(self, potential_parent, potential_child):
        current = potential_child
        while current:
            if current.id == potential_parent.id:
                return True
            current = current.parent
        return False


class FolderMoveView(BaseDiskView):
    """移动文件夹视图"""
    
    def post(self, request, folder_id):
        try:
            target_folder_id = request.POST.get('target_folder_id', '') or None
            
            folder = get_object_or_404(DiskFolder, id=folder_id, owner=request.user, delete_time__isnull=True)
            
            if target_folder_id:
                target_folder = get_object_or_404(DiskFolder, id=target_folder_id, owner=request.user, delete_time__isnull=True)
                
                if target_folder == folder.parent:
                    return JsonResponse({'code': 0, 'msg': '文件夹已在目标位置'})
                
                if self.is_descendant_folder(target_folder, folder):
                    return JsonResponse({'code': 1, 'msg': '不能将文件夹移动到其子文件夹中'})
            else:
                target_folder = None
            
            folder.parent = target_folder
            folder.save()
            
            self.log_operation(request, 'move', folder=folder, description=f'移动文件夹: {folder.name}')
            
            return JsonResponse({
                'code': 0,
                'msg': '文件夹移动成功',
                'data': {
                    'id': folder.id,
                    'name': folder.name
                }
            })
            
        except Exception as e:
            logger.error(f'移动文件夹失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'移动失败: {str(e)}'})
    
    def is_descendant_folder(self, potential_parent, potential_child):
        current = potential_child
        while current:
            if current.id == potential_parent.id:
                return True
            current = current.parent
        return False


class FileDeleteView(BaseDiskView):
    """删除文件视图"""
    
    def post(self, request, file_id):
        try:
            is_permanent = request.POST.get('permanent') == 'true'
            
            if is_permanent:
                disk_file = get_object_or_404(DiskFile, id=file_id, owner=request.user)
                
                file_path = os.path.join(settings.MEDIA_ROOT, disk_file.file_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                disk_file.delete()
                msg = '文件已永久删除'
            else:
                disk_file = get_object_or_404(DiskFile, id=file_id, owner=request.user, delete_time__isnull=True)
                disk_file.delete_time = timezone.now()
                disk_file.save(update_fields=['delete_time', 'update_time'])
                msg = '文件已移至回收站'
            
            self.log_operation(request, 'delete', file=disk_file, description=f'{msg}: {disk_file.name}')
            
            return JsonResponse({'code': 0, 'msg': msg})
            
        except Exception as e:
            logger.error(f'删除文件失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})


class FileRestoreView(BaseDiskView):
    """恢复文件视图"""
    
    def post(self, request, file_id):
        try:
            disk_file = get_object_or_404(DiskFile, id=file_id, owner=request.user, delete_time__isnull=False)
            
            disk_file.delete_time = None
            disk_file.save(update_fields=['delete_time', 'update_time'])
            
            self.log_operation(request, 'restore', file=disk_file, description=f'恢复文件: {disk_file.name}')
            
            return JsonResponse({'code': 0, 'msg': '文件已恢复'})
            
        except Exception as e:
            logger.error(f'恢复文件失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'恢复失败: {str(e)}'})


class FolderDeleteView(BaseDiskView):
    """删除文件夹视图"""
    
    def post(self, request, folder_id):
        try:
            is_permanent = request.POST.get('permanent') == 'true'
            
            if is_permanent:
                folder = get_object_or_404(DiskFolder, id=folder_id, owner=request.user)
                self.permanent_delete_folder_recursive(folder)
                msg = '文件夹已永久删除'
            else:
                folder = get_object_or_404(DiskFolder, id=folder_id, owner=request.user, delete_time__isnull=True)
                self.soft_delete_folder_recursive(folder)
                msg = '文件夹已移至回收站'
            
            self.log_operation(request, 'delete', folder=folder, description=f'{msg}: {folder.name}')
            
            return JsonResponse({'code': 0, 'msg': msg})
            
        except Exception as e:
            logger.error(f'删除文件夹失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})
    
    def soft_delete_folder_recursive(self, folder):
        for file in folder.files.filter(delete_time__isnull=True):
            file.delete_time = timezone.now()
            file.save(update_fields=['delete_time', 'update_time'])
        
        for child_folder in folder.children.filter(delete_time__isnull=True):
            self.soft_delete_folder_recursive(child_folder)
        
        folder.delete_time = timezone.now()
        folder.save(update_fields=['delete_time', 'update_time'])
    
    def permanent_delete_folder_recursive(self, folder):
        for file in folder.files.all():
            file_path = os.path.join(settings.MEDIA_ROOT, file.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
            file.delete()
        
        for child_folder in folder.children.all():
            self.permanent_delete_folder_recursive(child_folder)
        
        folder.delete()


class FolderRestoreView(BaseDiskView):
    """恢复文件夹视图"""
    
    def post(self, request, folder_id):
        try:
            folder = get_object_or_404(DiskFolder, id=folder_id, owner=request.user, delete_time__isnull=False)
            
            self.restore_folder_recursive(folder)
            
            self.log_operation(request, 'restore', folder=folder, description=f'恢复文件夹: {folder.name}')
            
            return JsonResponse({'code': 0, 'msg': '文件夹已恢复'})
            
        except Exception as e:
            logger.error(f'恢复文件夹失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'恢复失败: {str(e)}'})
    
    def restore_folder_recursive(self, folder):
        folder.delete_time = None
        folder.save(update_fields=['delete_time', 'update_time'])
        
        for file in folder.files.filter(delete_time__isnull=False):
            file.delete_time = None
            file.save(update_fields=['delete_time', 'update_time'])
        
        for child_folder in folder.children.filter(delete_time__isnull=False):
            self.restore_folder_recursive(child_folder)


class RecycleBinClearView(BaseDiskView):
    """清空回收站视图"""
    
    def post(self, request):
        try:
            deleted_files = DiskFile.objects.filter(owner=request.user, delete_time__isnull=False)
            deleted_folders = DiskFolder.objects.filter(owner=request.user, delete_time__isnull=False)
            
            file_count = deleted_files.count()
            folder_count = deleted_folders.count()
            
            for disk_file in deleted_files:
                file_path = os.path.join(settings.MEDIA_ROOT, disk_file.file_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            deleted_files.delete()
            
            for folder in deleted_folders:
                self.permanent_delete_folder_recursive(folder)
            
            self.log_operation(request, 'delete', description=f'清空回收站，共删除 {file_count} 个文件，{folder_count} 个文件夹')
            
            return JsonResponse({'code': 0, 'msg': f'回收站已清空，共删除 {file_count} 个文件，{folder_count} 个文件夹'})
            
        except Exception as e:
            logger.error(f'清空回收站失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'清空失败: {str(e)}'})
    
    def permanent_delete_folder_recursive(self, folder):
        for file in folder.files.all():
            file_path = os.path.join(settings.MEDIA_ROOT, file.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
            file.delete()
        
        for child_folder in folder.children.all():
            self.permanent_delete_folder_recursive(child_folder)
        
        folder.delete()


class PermissionManageView(BaseDiskView):
    """权限管理视图"""
    
    def get(self, request):
        item_type = request.GET.get('type', 'file')
        item_id = request.GET.get('id', '')
        
        if not item_id or item_type not in ['file', 'folder']:
            return JsonResponse({'code': 1, 'msg': '参数错误'})
        
        if item_type == 'file':
            item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
            item_name = item.name
            item_type_name = '文件'
        else:
            item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
            item_name = item.name
            item_type_name = '文件夹'
        
        shared_users = item.shared_users.all()
        shared_departments = item.shared_departments.all()
        
        context = {
            'item': item,
            'item_type': item_type,
            'item_name': item_name,
            'item_type_name': item_type_name,
            'shared_users': shared_users,
            'shared_departments': shared_departments,
        }
        return render(request, 'disk/permission_manage.html', context)


class UserPermissionView(BaseDiskView):
    """用户权限管理视图"""
    
    def post(self, request):
        try:
            item_type = request.POST.get('item_type')
            item_id = request.POST.get('item_id')
            permissions = request.POST.get('permissions')
            
            if not all([item_type, item_id]) or item_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            if item_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
            
            if permissions:
                permission_list = json.loads(permissions)
                
                for perm in permission_list:
                    user_id = perm.get('user_id')
                    permission_level = perm.get('permission_level', 1)
                    
                    if user_id:
                        user = get_object_or_404(User, id=user_id)
                        
                        if user not in item.shared_users.all():
                            item.shared_users.add(user)
                        
                        self.log_operation(request, 'permission', 
                                         file=item if item_type == 'file' else None,
                                         folder=item if item_type == 'folder' else None,
                                         description=f'设置用户权限: {user.username}')
            else:
                user_id = request.POST.get('user_id')
                permission_level = int(request.POST.get('permission_level', 1))
                
                if not user_id:
                    return JsonResponse({'code': 1, 'msg': '参数错误'})
                
                user = get_object_or_404(User, id=user_id)
                
                if user not in item.shared_users.all():
                    item.shared_users.add(user)
                
                self.log_operation(request, 'permission', 
                                 file=item if item_type == 'file' else None,
                                 folder=item if item_type == 'folder' else None,
                                 description=f'设置用户权限: {user.username}')
            
            return JsonResponse({'code': 0, 'msg': '权限设置成功'})
            
        except Exception as e:
            logger.error(f'设置用户权限失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'设置失败: {str(e)}'})


class UserPermissionRemoveView(BaseDiskView):
    """移除用户权限视图"""
    
    def post(self, request):
        try:
            item_type = request.POST.get('item_type')
            item_id = request.POST.get('item_id')
            user_id = request.POST.get('user_id')
            
            if not all([item_type, item_id, user_id]) or item_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            if item_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
            
            user = get_object_or_404(User, id=user_id)
            
            item.shared_users.remove(user)
            
            self.log_operation(request, 'permission', 
                             file=item if item_type == 'file' else None,
                             folder=item if item_type == 'folder' else None,
                             description=f'移除用户权限: {user.username}')
            
            return JsonResponse({'code': 0, 'msg': '权限移除成功'})
            
        except Exception as e:
            logger.error(f'移除用户权限失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'移除失败: {str(e)}'})


class UserPermissionListView(BaseDiskView):
    """获取部门下用户列表视图"""
    
    def get(self, request):
        try:
            dept_id = request.GET.get('dept_id')
            
            if not dept_id:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            dept = get_object_or_404(Department, id=dept_id)
            
            users = User.objects.filter(did=dept_id)
            
            user_list = []
            for user in users:
                user_list.append({
                    'id': user.id,
                    'username': user.username,
                    'name': user.name,
                    'department': {
                        'id': dept.id,
                        'title': dept.name
                    }
                })
            
            return JsonResponse({
                'code': 0,
                'msg': 'success',
                'data': {
                    'users': user_list
                }
            })
            
        except Exception as e:
            logger.error(f'获取部门用户列表失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'获取部门用户列表失败: {str(e)}'})


class ExistingPermissionUsersView(BaseDiskView):
    """获取已有权限的用户列表视图"""
    
    def get(self, request):
        try:
            item_type = request.GET.get('item_type')
            item_id = request.GET.get('item_id')
            
            if not all([item_type, item_id]) or item_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            if item_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
                users = item.shared_users.all()
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
                users = item.shared_users.all()
            
            user_list = []
            for user in users:
                dept_name = '无部门'
                if user.did:
                    try:
                        dept = Department.objects.get(id=user.did)
                        dept_name = dept.name
                    except Department.DoesNotExist:
                        pass
                
                user_list.append({
                    'id': user.id,
                    'username': user.username,
                    'name': user.name,
                    'department': {
                        'id': user.did or 0,
                        'title': dept_name
                    }
                })
            
            return JsonResponse({
                'code': 0,
                'msg': 'success',
                'data': {
                    'users': user_list
                }
            })
            
        except Exception as e:
            logger.error(f'获取已有权限用户列表失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'获取已有权限用户列表失败: {str(e)}'})


class DeptPermissionView(BaseDiskView):
    """部门权限管理视图"""
    
    def post(self, request):
        try:
            item_type = request.POST.get('item_type')
            item_id = request.POST.get('item_id')
            permissions = request.POST.get('permissions')
            
            if not all([item_type, item_id]) or item_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            if item_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
            
            if permissions:
                permission_list = json.loads(permissions)
                
                for perm in permission_list:
                    dept_id = perm.get('dept_id')
                    permission_level = perm.get('permission_level', 1)
                    
                    if dept_id:
                        dept = get_object_or_404(Department, id=dept_id)
                        
                        if dept not in item.shared_departments.all():
                            item.shared_departments.add(dept)
                        
                        self.log_operation(request, 'permission', 
                                         file=item if item_type == 'file' else None,
                                         folder=item if item_type == 'folder' else None,
                                         description=f'设置部门权限: {dept.name}')
            else:
                dept_id = request.POST.get('dept_id')
                permission_level = int(request.POST.get('permission_level', 1))
                
                if not dept_id:
                    return JsonResponse({'code': 1, 'msg': '参数错误'})
                
                dept = get_object_or_404(Department, id=dept_id)
                
                if dept not in item.shared_departments.all():
                    item.shared_departments.add(dept)
                
                self.log_operation(request, 'permission', 
                                 file=item if item_type == 'file' else None,
                                 folder=item if item_type == 'folder' else None,
                                 description=f'设置部门权限: {dept.name}')
            
            return JsonResponse({'code': 0, 'msg': '权限设置成功'})
            
        except Exception as e:
            logger.error(f'设置部门权限失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'设置失败: {str(e)}'})


class DeptPermissionRemoveView(BaseDiskView):
    """移除部门权限视图"""
    
    def post(self, request):
        try:
            item_type = request.POST.get('item_type')
            item_id = request.POST.get('item_id')
            dept_id = request.POST.get('dept_id')
            
            if not all([item_type, item_id, dept_id]) or item_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            if item_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
            
            dept = get_object_or_404(Department, id=dept_id)
            
            item.shared_departments.remove(dept)
            
            self.log_operation(request, 'permission', 
                             file=item if item_type == 'file' else None,
                             folder=item if item_type == 'folder' else None,
                             description=f'移除部门权限: {dept.title}')
            
            return JsonResponse({'code': 0, 'msg': '权限移除成功'})
            
        except Exception as e:
            logger.error(f'移除部门权限失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'移除失败: {str(e)}'})


class ExistingPermissionDepartmentsView(BaseDiskView):
    """获取已有权限的部门列表视图"""
    
    def get(self, request):
        try:
            item_type = request.GET.get('item_type')
            item_id = request.GET.get('item_id')
            
            if not all([item_type, item_id]) or item_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            if item_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
                departments = item.shared_departments.all()
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
                departments = item.shared_departments.all()
            
            dept_list = []
            for dept in departments:
                dept_list.append({
                    'id': dept.id,
                    'name': dept.name,
                    'title': dept.name
                })
            
            return JsonResponse({
                'code': 0,
                'msg': 'success',
                'data': {
                    'departments': dept_list
                }
            })
            
        except Exception as e:
            logger.error(f'获取已有权限部门列表失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'获取已有权限部门列表失败: {str(e)}'})


class PermissionSaveView(BaseDiskView):
    """保存权限设置视图"""
    
    def post(self, request):
        try:
            item_type = request.POST.get('item_type')
            item_id = request.POST.get('item_id')
            is_public = request.POST.get('is_public') == 'true'
            
            if not all([item_type, item_id]) or item_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            if item_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
            
            item.is_public = is_public
            item.save(update_fields=['is_public', 'update_time'])
            
            self.log_operation(request, 'permission', 
                             file=item if item_type == 'file' else None,
                             folder=item if item_type == 'folder' else None,
                             description=f'更新权限设置: 公开={is_public}')
            
            return JsonResponse({'code': 0, 'msg': '权限设置保存成功'})
            
        except Exception as e:
            logger.error(f'保存权限设置失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'保存失败: {str(e)}'})


class UserPermissionAddView(BaseDiskView):
    """添加用户权限视图"""
    
    def get(self, request):
        item_type = request.GET.get('type')
        item_id = request.GET.get('id')
        
        if not item_id or item_type not in ['file', 'folder']:
            return JsonResponse({'code': 1, 'msg': '参数错误'})
        
        users = User.objects.exclude(id=request.user.id)
        departments = Department.objects.all()
        
        def build_dept_tree(dept_list, parent_id=0):
            tree = []
            for dept in dept_list:
                if dept.pid == parent_id:
                    children = build_dept_tree(dept_list, dept.id)
                    tree.append({
                        'id': dept.id,
                        'title': dept.name,
                        'spread': True,
                        'children': children
                    })
            return tree
        
        dept_tree = build_dept_tree(list(departments))
        
        context = {
            'item_type': item_type,
            'item_id': item_id,
            'users': users,
            'departments': json.dumps(dept_tree)
        }
        return render(request, 'disk/permission_add_user.html', context)


class DeptPermissionAddView(BaseDiskView):
    """添加部门权限视图"""
    
    def get(self, request):
        item_type = request.GET.get('type')
        item_id = request.GET.get('id')
        
        if not item_id or item_type not in ['file', 'folder']:
            return JsonResponse({'code': 1, 'msg': '参数错误'})
        
        departments = Department.objects.all()
        
        context = {
            'item_type': item_type,
            'item_id': item_id,
            'departments': departments
        }
        return render(request, 'disk/permission_add_dept.html', context)


@login_required
def disk_list(request):
    return redirect('disk:personal')


@login_required
def disk_add(request):
    return redirect('disk:personal')


@login_required
def disk_edit(request, id):
    return redirect('disk:personal')


@login_required
def disk_delete(request, id):
    return redirect('disk:personal')
