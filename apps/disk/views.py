from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, Http404, FileResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.urls import reverse
from .models import DiskFile, DiskFolder, DiskShare, DiskOperation, Disk
from apps.user.models import Admin as User
from apps.department.models import Department

import os
import json
import uuid
import mimetypes
import logging
import urllib.parse
import html



logger = logging.getLogger(__name__)


class DiskIndexView(LoginRequiredMixin, View):
    """网盘首页"""
    login_url = '/user/login/'
    
    def get(self, request):
        # 获取用户统计信息
        user_files = DiskFile.objects.filter(owner=request.user, delete_time__isnull=True)
        user_folders = DiskFolder.objects.filter(owner=request.user, delete_time__isnull=True)
        
        # 计算存储使用情况
        total_size = user_files.aggregate(total=Sum('file_size'))['total'] or 0
        file_count = user_files.count()
        folder_count = user_folders.count()
        
        # 最近文件
        recent_files = user_files.order_by('-update_time')[:10]
        
        # 收藏文件
        starred_files = user_files.filter(is_starred=True)[:10]
        
        context = {
            'total_size': total_size,
            'file_count': file_count,
            'folder_count': folder_count,
            'recent_files': recent_files,
            'starred_files': starred_files
        }
        
        return render(request, 'disk/index.html', context)


class StarredFilesView(LoginRequiredMixin, View):
    """收藏文件页面"""
    login_url = '/user/login/'
    
    def get(self, request):
        # 获取用户所有收藏的文件
        starred_files = DiskFile.objects.filter(
            owner=request.user, 
            delete_time__isnull=True,
            is_starred=True
        ).order_by('-update_time')
        
        context = {
            'starred_files': starred_files
        }
        
        return render(request, 'disk/starred_files.html', context)


class PersonalDiskView(LoginRequiredMixin, View):
    """个人文件视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        folder_id = request.GET.get('folder_id', '')
        search_term = request.GET.get('search', '')
        
        # 获取当前文件夹
        current_folder = None
        if folder_id:
            current_folder = get_object_or_404(DiskFolder, id=folder_id, owner=request.user, delete_time__isnull=True)
        
        # 获取面包屑导航
        breadcrumbs = []
        if current_folder:
            folder = current_folder
            while folder:
                breadcrumbs.insert(0, folder)
                folder = folder.parent
        
        # 构建文件夹查询条件
        folder_conditions = Q(owner=request.user, parent=current_folder, delete_time__isnull=True)
        
        # 构建文件查询条件
        file_conditions = Q(owner=request.user, folder=current_folder, delete_time__isnull=True)
        
        # 添加搜索条件
        if search_term:
            # 支持模糊匹配文件名
            folder_conditions &= Q(name__icontains=search_term)
            file_conditions &= Q(name__icontains=search_term)
        
        # 获取子文件夹
        folders = DiskFolder.objects.filter(folder_conditions).order_by('name')
        
        # 获取排序参数
        sort_by = request.GET.get('sort', 'update_time')
        order = request.GET.get('order', 'desc')
        
        # 映射排序字段
        sort_field_mapping = {
            'upload_time': 'update_time',
            'size': 'file_size',
            'views': 'view_count',
            'downloads': 'download_count'
        }
        
        # 验证排序字段
        sort_field = sort_field_mapping.get(sort_by, 'update_time')
        
        # 构建排序表达式
        if order == 'asc':
            order_by = sort_field
        else:
            order_by = f'-{sort_field}'
        
        # 获取文件
        files = DiskFile.objects.filter(file_conditions).order_by(order_by)
        
        context = {
            'current_folder': current_folder,
            'breadcrumbs': breadcrumbs,
            'folders': folders,
            'files': files,
        }
        return render(request, 'disk/personal.html', context)


class SharedDiskView(LoginRequiredMixin, View):
    """共享文件视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        # 获取用户有权限访问的共享文件
        shared_files = DiskFile.objects.filter(
            Q(shared_users=request.user) | 
            Q(shared_departments__id=request.user.did) |
            Q(is_public=True),
            delete_time__isnull=True
        ).distinct().order_by('-update_time')
        
        # 获取用户有权限访问的共享文件夹
        shared_folders = DiskFolder.objects.filter(
            Q(shared_users=request.user) | 
            Q(shared_departments__id=request.user.did) |
            Q(is_public=True),
            delete_time__isnull=True
        ).distinct().order_by('name')
        
        context = {
            'shared_files': shared_files,
            'shared_folders': shared_folders,
        }
        return render(request, 'disk/shared.html', context)


class RecycleBinView(LoginRequiredMixin, View):
    """回收站视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        # 获取已删除的文件和文件夹
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


class FileSearchView(LoginRequiredMixin, View):
    """文件搜索视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        query = request.GET.get('q', '').strip()
        file_type = request.GET.get('type', '')
        
        if not query:
            return JsonResponse({'code': 1, 'msg': '搜索关键词不能为空'})
        
        # 构建搜索条件
        search_conditions = Q(owner=request.user, delete_time__isnull=True)
        search_conditions &= (
            Q(name__icontains=query) |
            Q(original_name__icontains=query)
        )
        
        # 文件类型过滤
        if file_type:
            search_conditions &= Q(file_type=file_type)
        
        # 搜索文件
        files = DiskFile.objects.filter(search_conditions).order_by('-update_time')[:50]
        
        # 搜索文件夹
        folder_conditions = Q(owner=request.user, delete_time__isnull=True)
        folder_conditions &= Q(name__icontains=query)
        folders = DiskFolder.objects.filter(folder_conditions).order_by('-update_time')[:20]
        
        # 构建返回数据
        results = []
        
        # 添加文件夹结果
        for folder in folders:
            results.append({
                'type': 'folder',
                'id': folder.id,
                'name': folder.name,
                'path': folder.get_full_path(),
                'create_time': folder.create_time.strftime('%Y-%m-%d %H:%M'),
                'update_time': folder.update_time.strftime('%Y-%m-%d %H:%M')
            })
        
        # 添加文件结果
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


class FileShareCreateView(LoginRequiredMixin, View):
    """创建文件分享视图"""
    login_url = '/user/login/'
    
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
            
            # 新增的权限控制参数
            permission_type = request.POST.get('permission_type', 'download')
            allow_download = request.POST.get('allow_download') == 'on'
            access_limit = int(request.POST.get('access_limit', 0))
            download_limit = int(request.POST.get('download_limit', 0))
            
            if not item_id or share_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            # 验证权限
            if share_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
            
            # 生成分享码
            import random
            import string
            share_code = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            
            # 计算过期时间
            expire_time = None
            if expire_days > 0:
                from datetime import timedelta
                expire_time = timezone.now() + timedelta(days=expire_days)
            
            # 创建分享记录
            share_data = {
                'share_type': share_type,
                'share_code': share_code,
                'password': password,
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
            
            # 记录操作日志
            self.log_operation(request, 'share', 
                             file=item if share_type == 'file' else None,
                             folder=item if share_type == 'folder' else None,
                             description=f'创建分享: {item.name}')
            
            # 生成分享链接
            share_url = request.build_absolute_uri(f'/disk/share/view/{share_code}/')
            
            return JsonResponse({
                'code': 0,
                'msg': '分享创建成功',
                'data': {
                    'share_code': share_code,
                    'share_url': share_url,
                    'password': password,
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
        except Exception as e:
            logger.error(f'记录操作日志失败: {str(e)}')


class FileShareView(View):
    """查看分享文件视图"""
    
    def get(self, request, share_code):
        try:
            share = get_object_or_404(DiskShare, share_code=share_code, is_active=True)
            
            # 检查是否过期
            if share.is_expired():
                return render(request, 'disk/share_expired.html', {'share': share})
            
            # 检查访问限制
            if not share.can_access():
                return render(request, 'disk/share_error.html', {'error': '访问次数已达上限'})
            
            # 检查是否需要密码
            if share.password and not request.session.get(f'share_auth_{share_code}'):
                return render(request, 'disk/share_password.html', {'share': share})
            
            # 记录访问
            client_ip = self.get_client_ip(request)
            share.record_access(client_ip)
            
            # 获取分享内容
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
        """验证分享密码"""
        try:
            share = get_object_or_404(DiskShare, share_code=share_code, is_active=True)
            password = request.POST.get('password', '')
            
            if share.password == password:
                request.session[f'share_auth_{share_code}'] = True
                return JsonResponse({'code': 0, 'msg': '验证成功'})
            else:
                return JsonResponse({'code': 1, 'msg': '密码错误'})
                
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'验证失败: {str(e)}'})
    
    def get_client_ip(self, request):
        """获取客户端IP地址"""
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
            
            # 获取分享记录
            share = get_object_or_404(DiskShare, share_code=share_code, is_active=True)
            
            # 检查权限
            if not share.can_preview():
                return JsonResponse({'code': 1, 'msg': '没有预览权限'})
            
            # 检查密码验证
            if share.password and not request.session.get(f'share_auth_{share_code}'):
                return JsonResponse({'code': 1, 'msg': '请先验证密码'})
            
            # 获取文件
            disk_file = get_object_or_404(DiskFile, id=file_id, delete_time__isnull=True)
            
            # 验证文件是否属于分享内容
            if share.share_type == 'file':
                if disk_file.id != share.file.id:
                    return JsonResponse({'code': 1, 'msg': '文件不属于此分享'})
            else:
                # 检查文件是否在分享的文件夹中
                if not self.is_file_in_folder(disk_file, share.folder):
                    return JsonResponse({'code': 1, 'msg': '文件不属于此分享'})
            
            # 记录预览
            share.record_preview()
            
            # 创建文件预览视图实例并处理预览
            preview_view = FilePreviewView()
            preview_data = preview_view._get_preview_content(disk_file, request)
            
            if preview_data:
                return JsonResponse({
                    'code': 0,
                    'msg': 'success',
                    'data': preview_data
                })
            else:
                return JsonResponse({
                    'code': 1,
                    'msg': '文件预览暂不支持此格式'
                })
            
        except Exception as e:
            logger.error(f'分享预览失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'预览失败: {str(e)}'})
    
    def is_file_in_folder(self, file, folder):
        """检查文件是否在文件夹中"""
        current_folder = file.folder
        while current_folder:
            if current_folder.id == folder.id:
                return True
            current_folder = current_folder.parent
        return False





import os
import time
import base64

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
    
    # 使用集合提高查找效率
    TEXT_TYPES = {'txt', 'csv', 'json', 'xml', 'html', 'css', 'js', 'py', 'java', 'cpp', 'c', 'h'}
    IMAGE_TYPES = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'}
    OFFICE_TYPES = {'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'}
    AUDIO_TYPES = {'mp3', 'wav', 'ogg', 'flac'}
    VIDEO_TYPES = {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm'}
    
    # 缓存配置
    PREVIEW_CACHE = {}
    CACHE_TIMEOUT = 3600  # 1小时
    
    def get(self, request, file_id):
        """获取文件预览内容"""
        try:
            # 获取文件
            file_obj = get_object_or_404(DiskFile, id=file_id, owner=request.user, delete_time__isnull=True)
            
            # 更新查看次数
            file_obj.view_count += 1
            file_obj.save()
            
            # 检查文件是否存在
            import os
            from django.conf import settings
            full_file_path = os.path.join(settings.MEDIA_ROOT, file_obj.file_path)
            if not os.path.exists(full_file_path):
                return JsonResponse({
                    'code': 1,
                    'msg': '文件不存在'
                }, json_dumps_params={'ensure_ascii': False})
            
            # 生成缓存键
            cache_key = f"preview_{file_id}_{file_obj.update_time.timestamp()}"
            
            # 检查缓存
            if cache_key in self.PREVIEW_CACHE:
                cached_time, preview_data = self.PREVIEW_CACHE[cache_key]
                if time.time() - cached_time < self.CACHE_TIMEOUT:
                    return JsonResponse({
                        'code': 0,
                        'msg': 'success (from cache)',
                        'data': preview_data
                    }, json_dumps_params={'ensure_ascii': False})
            
            # 根据文件类型选择预览方式
            preview_data = self._get_preview_content(file_obj, request)
            
            if preview_data:
                # 缓存结果
                self.PREVIEW_CACHE[cache_key] = (time.time(), preview_data)
                
                # 控制缓存大小
                self._cleanup_cache()
                
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
            return JsonResponse({
                'code': 1,
                'msg': '文件不存在'
            }, json_dumps_params={'ensure_ascii': False})
        except PermissionError:
            logger.error(f'没有权限访问文件: {file_id}')
            return JsonResponse({
                'code': 1,
                'msg': '没有权限访问文件'
            }, json_dumps_params={'ensure_ascii': False})
        except MemoryError:
            logger.error(f'文件过大导致内存不足: {file_id}')
            return JsonResponse({
                'code': 1,
                'msg': '文件过大，无法在线预览，请下载后查看'
            }, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            logger.error(f'文件预览失败: {str(e)}')
            return JsonResponse({
                'code': 1,
                'msg': f'文件预览失败: {str(e)}'
            }, json_dumps_params={'ensure_ascii': False})
    
    def _cleanup_cache(self):
        """清理过期缓存和控制缓存大小"""
        # 保持缓存大小不超过100个条目
        if len(self.PREVIEW_CACHE) > 100:
            # 按照缓存时间排序，删除最旧的一半
            sorted_cache = sorted(self.PREVIEW_CACHE.items(), key=lambda x: x[1][0])
            for key, _ in sorted_cache[:50]:
                if key in self.PREVIEW_CACHE:
                    del self.PREVIEW_CACHE[key]
        
        # 清理过期缓存
        current_time = time.time()
        expired_keys = [k for k, v in self.PREVIEW_CACHE.items() 
                        if current_time - v[0] >= self.CACHE_TIMEOUT]
        for key in expired_keys:
            if key in self.PREVIEW_CACHE:
                del self.PREVIEW_CACHE[key]
                
    def _get_preview_content(self, file_obj, request):
        """根据文件类型获取预览内容"""
        # 获取文件扩展名（去掉点号）
        file_ext = file_obj.file_ext.lstrip('.').lower()
        
        # 使用集合提高查找效率
        if file_ext in self.TEXT_TYPES:
            return self._preview_text_file(file_obj)
        elif file_ext in self.IMAGE_TYPES:
            return self._preview_image_file(file_obj, request)
        elif file_ext in self.OFFICE_TYPES:
            return self._preview_office_file(file_obj, request)
        elif file_ext == 'pdf':
            return self._preview_pdf_file(file_obj, request)
        elif file_ext in self.AUDIO_TYPES:
            return self._preview_audio_file(file_obj, request)
        elif file_ext in self.VIDEO_TYPES:
            return self._preview_video_file(file_obj, request)
        
        return None
    
    def _preview_text_file(self, file_obj):
        """预览文本文件"""
        try:
            # 读取文件内容（限制大小，避免大文件导致性能问题）
            max_size = 1024 * 1024  # 1MB
            max_lines = 1000  # 最多读取1000行
            max_chars = 500000  # 最多读取50万个字符
            
            # 尝试不同的编码
            import os
            from django.conf import settings
            full_file_path = os.path.join(settings.MEDIA_ROOT, file_obj.file_path)
            
            # 增加文件存在性检查的健壮性
            if not os.path.exists(full_file_path):
                logger.error(f'文件不存在: {full_file_path}')
                return {
                    'type': 'text',
                    'content': '文件不存在或无法访问',
                    'error': 'file_not_found',
                    'name': file_obj.name
                }
            
            # 检查文件是否为普通文件（非目录、非符号链接等）
            if not os.path.isfile(full_file_path):
                logger.error(f'路径不是文件: {full_file_path}')
                return {
                    'type': 'text',
                    'content': '路径不是有效的文件',
                    'error': 'not_a_file',
                    'name': file_obj.name
                }
            
            # 获取文件大小
            file_size = os.path.getsize(full_file_path)
            if file_size > max_size:
                return {
                    'type': 'text',
                    'content': f'文件过大（{file_size}字节），请下载后查看',
                    'truncated': True,
                    'name': file_obj.name
                }
            
            # 扩展编码列表，增加更多可能的编码格式
            encodings = [
                'utf-8', 'gbk', 'gb2312', 'gb18030',  # 中文常用编码
                'latin-1', 'cp1252',  # 西方字符编码
                'utf-16', 'utf-16le', 'utf-16be',  # Unicode编码变体
                'big5', 'shift_jis', 'euc-jp'  # 其他亚洲语言编码
            ]
            content = None
            encoding_used = 'utf-8'
            line_count = 0
            char_count = 0
            
            # 逐行读取，避免一次性加载大文件
            for encoding in encodings:
                try:
                    content_lines = []
                    current_line_count = 0
                    current_char_count = 0
                    
                    # 使用上下文管理器安全读取文件
                    with open(full_file_path, 'r', encoding=encoding, errors='replace') as f:
                        for line in f:
                            line_length = len(line)
                            # 检查是否超过字符限制
                            if current_char_count + line_length > max_chars:
                                # 截断该行以保持在字符限制内
                                remaining_chars = max_chars - current_char_count
                                line = line[:remaining_chars]
                                content_lines.append(line)
                                current_char_count = max_chars
                                current_line_count += 1
                                break
                            
                            content_lines.append(line)
                            current_line_count += 1
                            current_char_count += line_length
                            
                            # 限制读取行数
                            if current_line_count >= max_lines:
                                break
                    
                    if content_lines:
                        content = ''.join(content_lines)
                        line_count = current_line_count
                        char_count = current_char_count
                        encoding_used = encoding
                        
                        # 质量检查：如果有实际内容而不仅仅是空白字符，就使用这个编码
                        if content.strip():
                            break
                except Exception as encoding_error:
                    logger.debug(f'编码{encoding}尝试失败: {str(encoding_error)}')
                    continue
            
            if content is None or not content.strip():
                # 如果所有编码都失败或内容为空，使用二进制模式读取
                try:
                    with open(full_file_path, 'rb') as f:
                        raw_content = f.read(max_size)
                    
                    # 检查文件是否为空
                    if not raw_content:
                        return {
                            'type': 'text',
                            'content': '[文件内容为空]',
                            'encoding': 'empty',
                            'name': file_obj.name
                        }
                    
                    # 尝试多种解码策略
                    try:
                        # 尝试检测BOM
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
                            # 使用replace错误处理模式
                            content = raw_content.decode('utf-8', errors='replace')
                            encoding_used = 'binary-fallback'
                    except Exception:
                        # 最后的回退方案
                        content = repr(raw_content[:1000]) + '\n\n[文件可能不是文本格式或编码无法识别]'
                        encoding_used = 'repr-fallback'
                except Exception as binary_error:
                    logger.error(f'二进制读取失败: {str(binary_error)}')
                    content = '[无法读取文件内容]'
                    encoding_used = 'error'
            
            # 清理内容，移除控制字符但保留换行符
            import re
            # 使用更安全的正则表达式移除ASCII控制字符
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', content)
            
            # 确保内容非空
            if not content.strip():
                content = '[文件内容为空或仅包含空白字符]'
            
            # 构建返回结果，确保字段名统一
            return {
                'type': 'text',
                'content': content,
                'truncated': char_count >= max_chars or line_count >= max_lines,
                'encoding': encoding_used,
                'name': file_obj.name,
                'file_ext': file_obj.file_ext,
                'file_id': file_obj.id  # 确保前端可以访问file_id
            }
            
        except PermissionError:
            logger.error(f'没有权限读取文件: {full_file_path}')
            return {
                'type': 'text',
                'content': '没有权限读取文件',
                'error': 'permission_denied',
                'name': file_obj.name
            }
        except MemoryError:
            logger.error(f'内存不足，无法读取文件: {full_file_path}')
            return {
                'type': 'text',
                'content': '内存不足，无法读取文件',
                'error': 'memory_error',
                'name': file_obj.name
            }
        except Exception as e:
            logger.error(f'文本文件预览失败: {str(e)}')
            return {
                'type': 'text',
                'content': f'读取文本文件失败: {str(e)}',
                'error': 'read_error',
                'name': file_obj.name
            }
    
    def _preview_image_file(self, file_obj, request):
        """预览图片文件"""
        try:
            # 构建图片URL，使用download URL，但确保前端通过我们的预览功能处理
            image_url = request.build_absolute_uri(
                reverse('disk:file_download', kwargs={'file_id': file_obj.id})
            )
            
            return {
                'type': 'image',
                'url': image_url,
                'name': file_obj.name,
                'file_id': file_obj.id
            }
            
        except Exception as e:
            logger.error(f'图片文件预览失败: {str(e)}')
            return None
    
    def _preview_office_file(self, file_obj, request):
        """预览Office文档（使用Python原生库直接处理）"""
        try:
            from .utils.office_preview import OfficePreviewHandler
            import os
            from django.conf import settings
            
            # 构建完整的文件路径
            full_file_path = os.path.join(settings.MEDIA_ROOT, file_obj.file_path)
            
            # 获取转换格式参数
            conversion_format = request.GET.get('format')
            
            # 使用新的Office预览处理器
            result = OfficePreviewHandler.preview_office_file(full_file_path, conversion_format)
            
            # 添加文件ID和下载URL
            result['file_id'] = file_obj.id
            result['download_url'] = request.build_absolute_uri(
                reverse('disk:file_download', kwargs={'file_id': file_obj.id})
            )
            
            # 记录简洁的调试信息，不记录完整的result对象以避免大型字符串问题
            logger.info(f"Office preview completed for {file_obj.name}: type={result.get('type')}, office_type={result.get('office_type')}, format={conversion_format}")
            
            return result
                
        except Exception as e:
            logger.error(f'Office文件预览失败: {str(e)}')
            return {
                'type': 'error',
                'message': f'Office文档预览失败: {str(e)}'
            }
    
    def _preview_pdf_file(self, file_obj, request):
        """预览PDF文件（使用本地PDF处理）"""
        try:
            import os
            from django.conf import settings
            
            # 构建完整的文件路径
            full_file_path = os.path.join(settings.MEDIA_ROOT, file_obj.file_path)
            
            # 检查文件是否存在
            if not os.path.exists(full_file_path):
                return {
                    'type': 'error',
                    'message': 'PDF文件不存在'
                }
            
            # 返回PDF文件信息，让前端处理预览
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
        """预览音频文件"""
        try:
            # 构建音频URL
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
        """预览视频文件"""
        try:
            # 构建视频URL
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





class ShareDownloadView(View):
    """分享下载视图"""
    
    def post(self, request):
        try:
            share_code = request.POST.get('share_code')
            file_id = request.POST.get('file_id')
            
            if not share_code or not file_id:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            # 获取分享记录
            share = get_object_or_404(DiskShare, share_code=share_code, is_active=True)
            
            # 检查权限
            if not share.can_download():
                return JsonResponse({'code': 1, 'msg': '没有下载权限或已达下载限制'})
            
            # 检查密码验证
            if share.password and not request.session.get(f'share_auth_{share_code}'):
                return JsonResponse({'code': 1, 'msg': '请先验证密码'})
            
            # 获取文件
            disk_file = get_object_or_404(DiskFile, id=file_id, delete_time__isnull=True)
            
            # 验证文件是否属于分享内容
            if share.share_type == 'file':
                if disk_file.id != share.file.id:
                    return JsonResponse({'code': 1, 'msg': '文件不属于此分享'})
            else:
                # 检查文件是否在分享的文件夹中
                if not self.is_file_in_folder(disk_file, share.folder):
                    return JsonResponse({'code': 1, 'msg': '文件不属于此分享'})
            
            # 记录下载
            share.record_download()
            
            return JsonResponse({'code': 0, 'msg': '下载授权成功'})
            
        except Exception as e:
            logger.error(f'分享下载失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'下载失败: {str(e)}'})
    
    def is_file_in_folder(self, file, folder):
        """检查文件是否在指定文件夹中（递归检查）"""
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
            
            # 获取分享记录
            share = get_object_or_404(DiskShare, share_code=share_code, is_active=True)
            
            # 检查权限
            if not share.can_access():
                return JsonResponse({'code': 1, 'msg': '没有访问权限'})
            
            # 检查密码验证
            if share.password and not request.session.get(f'share_auth_{share_code}'):
                return JsonResponse({'code': 1, 'msg': '请先验证密码'})
            
            # 确保是文件夹分享
            if share.share_type != 'folder':
                return JsonResponse({'code': 1, 'msg': '此分享不是文件夹'})
            
            # 获取目标文件夹
            if folder_id:
                target_folder = get_object_or_404(DiskFolder, id=folder_id, delete_time__isnull=True)
                # 验证文件夹是否在分享范围内
                if not self.is_folder_in_share(target_folder, share.folder):
                    return JsonResponse({'code': 1, 'msg': '文件夹不在分享范围内'})
            else:
                target_folder = share.folder
            
            # 获取子文件夹
            folders = DiskFolder.objects.filter(
                parent=target_folder,
                delete_time__isnull=True
            ).order_by('name')
            
            # 获取文件
            files = DiskFile.objects.filter(
                folder=target_folder,
                delete_time__isnull=True
            ).order_by('-update_time')
            
            # 构建返回数据
            folder_data = []
            for folder in folders:
                folder_data.append({
                    'id': folder.id,
                    'name': folder.name,
                    'update_time': folder.update_time.strftime('%Y-%m-%d %H:%i')
                })
            
            file_data = []
            for file in files:
                file_data.append({
                    'id': file.id,
                    'name': file.name,
                    'size': file.get_size_display(),
                    'file_type': file.file_type,
                    'update_time': file.update_time.strftime('%Y-%m-%d %H:%i')
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
        """检查文件夹是否在分享范围内"""
        if folder.id == share_folder.id:
            return True
        
        current_folder = folder.parent
        while current_folder:
            if current_folder.id == share_folder.id:
                return True
            current_folder = current_folder.parent
        return False


class FileStarToggleView(LoginRequiredMixin, View):
    """切换文件收藏状态视图"""
    login_url = '/user/login/'
    
    def post(self, request, file_id):
        try:
            disk_file = get_object_or_404(DiskFile, id=file_id, owner=request.user, delete_time__isnull=True)
            
            # 切换收藏状态
            disk_file.is_starred = not disk_file.is_starred
            disk_file.save()
            
            action = '收藏' if disk_file.is_starred else '取消收藏'
            
            # 记录操作日志
            self.log_operation(request, 'star' if disk_file.is_starred else 'unstar', 
                             file=disk_file, description=f'{action}文件: {disk_file.name}')
            
            return JsonResponse({
                'code': 0,
                'msg': f'{action}成功',
                'data': {'is_starred': disk_file.is_starred}
            })
            
        except Exception as e:
            logger.error(f'切换收藏状态失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'操作失败: {str(e)}'})
    
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
        except Exception as e:
            logger.error(f'记录操作日志失败: {str(e)}')


class FileUploadView(LoginRequiredMixin, View):
    """文件上传视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        """处理GET请求，根据路径区分是渲染上传页面还是检查文件是否存在"""
        # 检查请求路径
        if '/upload/check/' in request.path:
            # 检查文件是否存在
            folder_id = request.GET.get('folder_id', '')
            file_name = request.GET.get('file_name', '')
            
            if not file_name:
                return JsonResponse({'code': 1, 'msg': '文件名不能为空'})
            
            # 获取目标文件夹
            target_folder = None
            if folder_id:
                target_folder = get_object_or_404(DiskFolder, id=folder_id, owner=request.user)
            
            # 检查文件是否已存在
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
            # 渲染上传页面
            return render(request, 'disk/upload.html')
    
    def post(self, request):
        try:
            folder_id = request.POST.get('folder_id', '')
            uploaded_file = request.FILES.get('file')
            action = request.POST.get('action', 'upload')  # upload, overwrite, rename
            file_id = request.POST.get('file_id', '')
            
            if not uploaded_file:
                return JsonResponse({'code': 1, 'msg': '没有选择文件'})
            
            # 检查文件大小（100MB限制）
            if uploaded_file.size > 100 * 1024 * 1024:
                return JsonResponse({'code': 1, 'msg': '文件大小不能超过100MB'})
            
            # 获取目标文件夹
            target_folder = None
            if folder_id:
                target_folder = get_object_or_404(DiskFolder, id=folder_id, owner=request.user)
            
            # 处理不同的上传动作
            if action == 'overwrite' and file_id:
                # 覆盖已有文件
                existing_file = get_object_or_404(DiskFile, id=file_id, owner=request.user, delete_time__isnull=True)
                
                # 删除旧文件
                if os.path.exists(os.path.join(settings.MEDIA_ROOT, existing_file.file_path)):
                    os.remove(os.path.join(settings.MEDIA_ROOT, existing_file.file_path))
                
                # 生成唯一文件名
                file_ext = os.path.splitext(uploaded_file.name)[1]
                unique_filename = f"{uuid.uuid4().hex}{file_ext}"
                
                # 创建上传目录
                upload_dir = f'disk/{request.user.id}'
                if not os.path.exists(os.path.join(settings.MEDIA_ROOT, upload_dir)):
                    os.makedirs(os.path.join(settings.MEDIA_ROOT, upload_dir))
                
                # 保存新文件
                file_path = os.path.join(upload_dir, unique_filename)
                saved_path = default_storage.save(file_path, ContentFile(uploaded_file.read()))
                
                # 更新现有文件记录
                existing_file.file_path = saved_path
                existing_file.file_size = uploaded_file.size
                existing_file.update_time = timezone.now()
                existing_file.save()
                
                # 记录操作日志
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
            
            # 默认上传或重命名上传
            if action == 'rename':
                # 重命名上传，添加序号后缀
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
                # 直接上传，检查是否已存在
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
            
            # 生成唯一文件名
            file_ext = os.path.splitext(new_file_name)[1]
            unique_filename = f"{uuid.uuid4().hex}{file_ext}"
            
            # 创建上传目录
            upload_dir = f'disk/{request.user.id}'
            if not os.path.exists(os.path.join(settings.MEDIA_ROOT, upload_dir)):
                os.makedirs(os.path.join(settings.MEDIA_ROOT, upload_dir))
            
            # 保存文件
            file_path = os.path.join(upload_dir, unique_filename)
            saved_path = default_storage.save(file_path, ContentFile(uploaded_file.read()))
            
            # 获取用户所属部门
            user_department = None
            if hasattr(request.user, 'did') and request.user.did > 0:
                try:
                    from apps.department.models import Department
                    user_department = Department.objects.get(id=request.user.did)
                except Department.DoesNotExist:
                    pass
            
            # 创建文件记录
            disk_file = DiskFile.objects.create(
                name=new_file_name,
                original_name=uploaded_file.name,
                file_path=saved_path,
                file_size=uploaded_file.size,
                folder=target_folder,
                owner=request.user,
                department=user_department
            )
            
            # 记录操作日志
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
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


class FileDownloadView(LoginRequiredMixin, View):
    """文件下载视图"""
    login_url = '/user/login/'
    
    # 定义可以在iframe中预览的文件类型
    PREVIEWABLE_TYPES = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
    
    def get(self, request, file_id):
        try:
            disk_file = get_object_or_404(DiskFile, id=file_id, delete_time__isnull=True)
            
            # 检查权限
            if not self.has_permission(request.user, disk_file):
                return JsonResponse({'code': 1, 'msg': '没有权限下载此文件'})
            
            # 检查文件是否存在
            file_path = os.path.join(settings.MEDIA_ROOT, disk_file.file_path)
            if not os.path.exists(file_path):
                return JsonResponse({'code': 1, 'msg': '文件不存在'})
            
            # 更新下载次数
            disk_file.download_count += 1
            disk_file.save()
            
            # 记录操作日志
            self.log_operation(request, 'download', file=disk_file, description=f'下载文件: {disk_file.name}')
            
            # 检查文件类型是否可以预览
            file_ext = disk_file.file_ext.lower()
            is_previewable = file_ext in self.PREVIEWABLE_TYPES
            
            # 设置响应头
            response = FileResponse(
                open(file_path, 'rb'),
                as_attachment=not is_previewable,  # 可预览的文件不作为附件下载
                filename=disk_file.original_name
            )
            
            # 为可预览文件设置合适的Content-Type
            if is_previewable:
                if file_ext == '.pdf':
                    response['Content-Type'] = 'application/pdf'
                elif file_ext.startswith(('.jpg', '.jpeg')):
                    response['Content-Type'] = 'image/jpeg'
                elif file_ext == '.png':
                    response['Content-Type'] = 'image/png'
                elif file_ext == '.gif':
                    response['Content-Type'] = 'image/gif'
                elif file_ext == '.webp':
                    response['Content-Type'] = 'image/webp'
                elif file_ext == '.bmp':
                    response['Content-Type'] = 'image/bmp'
                elif file_ext == '.svg':
                    response['Content-Type'] = 'image/svg+xml'
                elif file_ext in ['.doc', '.docx']:
                    response['Content-Type'] = 'application/msword' if file_ext == '.doc' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                elif file_ext in ['.xls', '.xlsx']:
                    response['Content-Type'] = 'application/vnd.ms-excel' if file_ext == '.xls' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                elif file_ext in ['.ppt', '.pptx']:
                    response['Content-Type'] = 'application/vnd.ms-powerpoint' if file_ext == '.ppt' else 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            
            # 添加X-Frame-Options允许iframe嵌入
            response['X-Frame-Options'] = 'SAMEORIGIN'
            
            return response
            
        except Exception as e:
            logger.error(f'文件下载失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'下载失败: {str(e)}'})
    
    def has_permission(self, user, disk_file):
        """检查用户是否有权限访问文件"""
        if user == disk_file.owner:
            return True
        if disk_file.is_public:
            return True
        if user in disk_file.shared_users.all():
            return True
        if hasattr(user, 'did') and user.did and disk_file.shared_departments.filter(id=user.did).exists():
            return True
        return False
    
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
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








# urlquote导入已移除，避免URL双重编码问题
from django.db.models import F


      
  
class FolderCreateView(LoginRequiredMixin, View):
    """创建文件夹视图"""
    login_url = '/user/login/'
    
    def post(self, request):
        try:
            folder_name = request.POST.get('name', '').strip()
            parent_id = request.POST.get('parent_id', '')
            
            if not folder_name:
                return JsonResponse({'code': 1, 'msg': '文件夹名称不能为空'})
            
            # 获取父文件夹
            parent_folder = None
            if parent_id:
                parent_folder = get_object_or_404(DiskFolder, id=parent_id, owner=request.user)
            
            # 检查同级目录下是否已存在同名文件夹
            if DiskFolder.objects.filter(
                owner=request.user,
                parent=parent_folder,
                name=folder_name,
                delete_time__isnull=True
            ).exists():
                return JsonResponse({'code': 1, 'msg': '文件夹名称已存在'})
            
            # 创建文件夹
            folder = DiskFolder.objects.create(
                name=folder_name,
                parent=parent_folder,
                owner=request.user,
                department_id=request.user.did if hasattr(request.user, 'did') else None
            )
            
            # 记录操作日志
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
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


class FileDeleteView(LoginRequiredMixin, View):
    """删除文件视图"""
    login_url = '/user/login/'
    
    def post(self, request, file_id):
        try:
            # 检查是否为永久删除
            is_permanent = request.POST.get('permanent') == 'true'
            
            # 根据是否永久删除，调整查询条件
            if is_permanent:
                # 永久删除：允许删除已被软删除的文件
                disk_file = get_object_or_404(DiskFile, id=file_id, owner=request.user)
                # 物理删除文件
                disk_file.delete()
                msg = '文件已永久删除'
            else:
                # 软删除：只允许删除未被删除的文件
                disk_file = get_object_or_404(DiskFile, id=file_id, owner=request.user, delete_time__isnull=True)
                # 软删除文件
                disk_file.delete_time = timezone.now()
                disk_file.save()
                msg = '文件已移至回收站'
            
            # 记录操作日志
            self.log_operation(request, 'delete', file=disk_file, description=f'{msg}: {disk_file.name}')
            
            return JsonResponse({'code': 0, 'msg': msg})
            
        except Exception as e:
            logger.error(f'删除文件失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})
    
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
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


class FileRestoreView(LoginRequiredMixin, View):
    """恢复文件视图"""
    login_url = '/user/login/'
    
    def post(self, request, file_id):
        try:
            disk_file = get_object_or_404(DiskFile, id=file_id, owner=request.user, delete_time__isnull=False)
            
            # 恢复文件
            disk_file.delete_time = None
            disk_file.save()
            
            # 记录操作日志
            self.log_operation(request, 'restore', file=disk_file, description=f'恢复文件: {disk_file.name}')
            
            return JsonResponse({'code': 0, 'msg': '文件已恢复'})
            
        except Exception as e:
            logger.error(f'恢复文件失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'恢复失败: {str(e)}'})
    
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
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


class FolderDeleteView(LoginRequiredMixin, View):
    """删除文件夹视图"""
    login_url = '/user/login/'
    
    def post(self, request, folder_id):
        try:
            # 检查是否为永久删除
            is_permanent = request.POST.get('permanent') == 'true'
            
            if is_permanent:
                # 永久删除：允许删除已被软删除的文件夹
                folder = get_object_or_404(DiskFolder, id=folder_id, owner=request.user)
                # 递归永久删除文件夹及其内容
                self.permanent_delete_folder_recursive(folder)
                msg = '文件夹已永久删除'
            else:
                # 软删除：只允许删除未被删除的文件夹
                folder = get_object_or_404(DiskFolder, id=folder_id, owner=request.user, delete_time__isnull=True)
                # 递归软删除文件夹及其内容
                self.soft_delete_folder_recursive(folder)
                msg = '文件夹已移至回收站'
            
            # 记录操作日志
            self.log_operation(request, 'delete', folder=folder, description=f'{msg}: {folder.name}')
            
            return JsonResponse({'code': 0, 'msg': msg})
            
        except Exception as e:
            logger.error(f'删除文件夹失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})
    
    def soft_delete_folder_recursive(self, folder):
        """递归软删除文件夹及其内容"""
        # 软删除文件夹中的文件
        for file in folder.files.filter(delete_time__isnull=True):
            file.delete_time = timezone.now()
            file.save()
        
        # 递归软删除子文件夹
        for child_folder in folder.children.filter(delete_time__isnull=True):
            self.soft_delete_folder_recursive(child_folder)
        
        # 软删除文件夹本身
        folder.delete_time = timezone.now()
        folder.save()
    
    def permanent_delete_folder_recursive(self, folder):
        """递归永久删除文件夹及其内容"""
        # 永久删除文件夹中的文件
        for file in folder.files.all():
            file.delete()
        
        # 递归永久删除子文件夹
        for child_folder in folder.children.all():
            self.permanent_delete_folder_recursive(child_folder)
        
        # 永久删除文件夹本身
        folder.delete()
    
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
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


class FolderRestoreView(LoginRequiredMixin, View):
    """恢复文件夹视图"""
    login_url = '/user/login/'
    
    def post(self, request, folder_id):
        try:
            folder = get_object_or_404(DiskFolder, id=folder_id, owner=request.user, delete_time__isnull=False)
            
            # 递归恢复文件夹及其内容
            self.restore_folder_recursive(folder)
            
            # 记录操作日志
            self.log_operation(request, 'restore', folder=folder, description=f'恢复文件夹: {folder.name}')
            
            return JsonResponse({'code': 0, 'msg': '文件夹已恢复'})
            
        except Exception as e:
            logger.error(f'恢复文件夹失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'恢复失败: {str(e)}'})
    
    def restore_folder_recursive(self, folder):
        """递归恢复文件夹及其内容"""
        # 恢复文件夹本身
        folder.delete_time = None
        folder.save()
        
        # 恢复文件夹中的文件
        for file in folder.files.filter(delete_time__isnull=False):
            file.delete_time = None
            file.save()
        
        # 递归恢复子文件夹
        for child_folder in folder.children.filter(delete_time__isnull=False):
            self.restore_folder_recursive(child_folder)
    
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
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


class RecycleBinClearView(LoginRequiredMixin, View):
    """清空回收站视图"""
    login_url = '/user/login/'
    
    def post(self, request):
        try:
            # 获取用户所有已被软删除的文件和文件夹
            deleted_files = DiskFile.objects.filter(owner=request.user, delete_time__isnull=False)
            deleted_folders = DiskFolder.objects.filter(owner=request.user, delete_time__isnull=False)
            
            # 记录删除的数量
            file_count = deleted_files.count()
            folder_count = deleted_folders.count()
            
            # 永久删除所有已被软删除的文件
            deleted_files.delete()
            
            # 递归永久删除所有已被软删除的文件夹
            for folder in deleted_folders:
                self.permanent_delete_folder_recursive(folder)
            
            # 记录操作日志
            self.log_operation(request, 'delete', description=f'清空回收站，共删除 {file_count} 个文件，{folder_count} 个文件夹')
            
            return JsonResponse({'code': 0, 'msg': f'回收站已清空，共删除 {file_count} 个文件，{folder_count} 个文件夹'})
            
        except Exception as e:
            logger.error(f'清空回收站失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'清空失败: {str(e)}'})
    
    def permanent_delete_folder_recursive(self, folder):
        """递归永久删除文件夹及其内容"""
        # 永久删除文件夹中的文件
        for file in folder.files.all():
            file.delete()
        
        # 递归永久删除子文件夹
        for child_folder in folder.children.all():
            self.permanent_delete_folder_recursive(child_folder)
        
        # 永久删除文件夹本身
        folder.delete()
    
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
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


# 兼容原有功能的视图函数
@login_required
def disk_list(request):
    """原有的网盘列表视图"""
    return redirect('disk:personal')


@login_required
def disk_add(request):
    """原有的添加文件视图"""
    return redirect('disk:personal')


@login_required
def disk_edit(request, id):
    """原有的编辑文件视图"""
    return redirect('disk:personal')


@login_required
def disk_delete(request, id):
    """原有的删除文件视图"""
    return redirect('disk:personal')





# 保持原有的视图函数以兼容现有代码
@login_required
def disk_list(request):
    user = request.user
    user_did = user.did if hasattr(user, 'did') else 0
    user_id = user.id
    
    # 筛选条件：用户是创建者 或 用户所在部门在共享部门 或 用户ID在共享人员
    disks = Disk.objects.filter(
        Q(delete_time=0) &
        (Q(admin_id=user_id) | Q(share_dids__contains=str(user_did)) | Q(share_ids__contains=str(user_id)))
    ).order_by('-create_time')
    
    return render(request, 'disk/disk_list.html', {'disks': disks})


@login_required
def disk_add(request):
    if request.method == 'POST':
        data = request.POST.dict()
        data['admin_id'] = request.user.id
        data['did'] = getattr(request.user, 'did', 0)
        data['create_time'] = timezone.now().timestamp()
        data['update_time'] = data['create_time']
        
        try:
            disk = Disk.objects.create(**data)
            logger.info(f'新增磁盘文件成功，ID：{disk.id}')
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'新增磁盘文件失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': str(e)})
    
    return render(request, 'disk/disk_add.html')


@login_required
def disk_edit(request, id):
    disk = get_object_or_404(Disk, id=id, delete_time=0)
    
    if request.method == 'POST':
        data = request.POST.dict()
        for key, value in data.items():
            if hasattr(disk, key):
                setattr(disk, key, value)
        disk.update_time = timezone.now().timestamp()
        disk.save()
        
        logger.info(f'编辑磁盘文件成功，ID：{id}')
        return JsonResponse({'code': 0, 'msg': '保存成功'})
    
    return render(request, 'disk/disk_edit.html', {'disk': disk})


@login_required
def disk_delete(request, id):
    disk = get_object_or_404(Disk, id=id, delete_time=0)
    disk.delete_time = timezone.now().timestamp()
    disk.save()
    
    logger.info(f'删除磁盘文件成功，ID：{id}')
    return JsonResponse({'code': 0, 'msg': '删除成功'})

class PermissionManageView(LoginRequiredMixin, View):
    """权限管理视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        item_type = request.GET.get('type', 'file')
        item_id = request.GET.get('id', '')
        
        if not item_id or item_type not in ['file', 'folder']:
            return JsonResponse({'code': 1, 'msg': '参数错误'})
        
        # 获取项目
        if item_type == 'file':
            item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
            item_name = item.name
            item_type_name = '文件'
        else:
            item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
            item_name = item.name
            item_type_name = '文件夹'
        
        # 获取共享用户和部门
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


class UserPermissionView(LoginRequiredMixin, View):
    """用户权限管理视图"""
    login_url = '/user/login/'
    
    def post(self, request):
        try:
            item_type = request.POST.get('item_type')
            item_id = request.POST.get('item_id')
            permissions = request.POST.get('permissions')
            
            if not all([item_type, item_id]) or item_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            # 获取项目
            if item_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
            
            # 处理批量权限设置
            if permissions:
                import json
                permission_list = json.loads(permissions)
                
                for perm in permission_list:
                    user_id = perm.get('user_id')
                    permission_level = perm.get('permission_level', 1)
                    
                    if user_id:
                        # 获取用户
                        user = get_object_or_404(User, id=user_id)
                        
                        # 添加或更新权限
                        if user not in item.shared_users.all():
                            item.shared_users.add(user)
                        
                        # 记录操作日志
                        self.log_operation(request, 'permission', 
                                         file=item if item_type == 'file' else None,
                                         folder=item if item_type == 'folder' else None,
                                         description=f'设置用户权限: {user.username}')
            else:
                # 处理单个权限设置
                user_id = request.POST.get('user_id')
                permission_level = int(request.POST.get('permission_level', 1))
                
                if not user_id:
                    return JsonResponse({'code': 1, 'msg': '参数错误'})
                
                # 获取用户
                user = get_object_or_404(User, id=user_id)
                
                # 添加或更新权限
                if user not in item.shared_users.all():
                    item.shared_users.add(user)
                
                # 记录操作日志
                self.log_operation(request, 'permission', 
                                 file=item if item_type == 'file' else None,
                                 folder=item if item_type == 'folder' else None,
                                 description=f'设置用户权限: {user.username}')
            
            return JsonResponse({'code': 0, 'msg': '权限设置成功'})
            
        except Exception as e:
            logger.error(f'设置用户权限失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'设置失败: {str(e)}'})
    
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
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


class UserPermissionRemoveView(LoginRequiredMixin, View):
    """移除用户权限视图"""
    login_url = '/user/login/'
    
    def post(self, request):
        try:
            item_type = request.POST.get('item_type')
            item_id = request.POST.get('item_id')
            user_id = request.POST.get('user_id')
            
            if not all([item_type, item_id, user_id]) or item_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            # 获取项目
            if item_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
            
            # 获取用户
            user = get_object_or_404(User, id=user_id)
            
            # 移除权限
            item.shared_users.remove(user)
            
            # 记录操作日志
            self.log_operation(request, 'permission', 
                             file=item if item_type == 'file' else None,
                             folder=item if item_type == 'folder' else None,
                             description=f'移除用户权限: {user.username}')
            
            return JsonResponse({'code': 0, 'msg': '权限移除成功'})
            
        except Exception as e:
            logger.error(f'移除用户权限失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'移除失败: {str(e)}'})
    
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
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


class DeptPermissionView(LoginRequiredMixin, View):
    """部门权限管理视图"""
    login_url = '/user/login/'
    
    def post(self, request):
        try:
            item_type = request.POST.get('item_type')
            item_id = request.POST.get('item_id')
            permissions = request.POST.get('permissions')
            
            if not all([item_type, item_id]) or item_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            # 获取项目
            if item_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
            
            # 处理批量权限设置
            if permissions:
                import json
                permission_list = json.loads(permissions)
                
                for perm in permission_list:
                    dept_id = perm.get('dept_id')
                    permission_level = perm.get('permission_level', 1)
                    
                    if dept_id:
                        # 获取部门
                        from apps.department.models import Department
                        dept = get_object_or_404(Department, id=dept_id)
                        
                        # 添加或更新权限
                        if dept not in item.shared_departments.all():
                            item.shared_departments.add(dept)
                        
                        # 记录操作日志
                        self.log_operation(request, 'permission', 
                                         file=item if item_type == 'file' else None,
                                         folder=item if item_type == 'folder' else None,
                                         description=f'设置部门权限: {dept.title}')
            else:
                # 处理单个权限设置
                dept_id = request.POST.get('dept_id')
                permission_level = int(request.POST.get('permission_level', 1))
                
                if not dept_id:
                    return JsonResponse({'code': 1, 'msg': '参数错误'})
                
                # 获取部门
                from apps.department.models import Department
                dept = get_object_or_404(Department, id=dept_id)
                
                # 添加或更新权限
                if dept not in item.shared_departments.all():
                    item.shared_departments.add(dept)
                
                # 记录操作日志
                self.log_operation(request, 'permission', 
                                 file=item if item_type == 'file' else None,
                                 folder=item if item_type == 'folder' else None,
                                 description=f'设置部门权限: {dept.title}')
            
            return JsonResponse({'code': 0, 'msg': '权限设置成功'})
            
        except Exception as e:
            logger.error(f'设置部门权限失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'设置失败: {str(e)}'})
    
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
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


class DeptPermissionRemoveView(LoginRequiredMixin, View):
    """移除部门权限视图"""
    login_url = '/user/login/'
    
    def post(self, request):
        try:
            item_type = request.POST.get('item_type')
            item_id = request.POST.get('item_id')
            dept_id = request.POST.get('dept_id')
            
            if not all([item_type, item_id, dept_id]) or item_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            # 获取项目
            if item_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
            
            # 获取部门
            from apps.department.models import Department
            dept = get_object_or_404(Department, id=dept_id)
            
            # 移除权限
            item.shared_departments.remove(dept)
            
            # 记录操作日志
            self.log_operation(request, 'permission', 
                             file=item if item_type == 'file' else None,
                             folder=item if item_type == 'folder' else None,
                             description=f'移除部门权限: {dept.title}')
            
            return JsonResponse({'code': 0, 'msg': '权限移除成功'})
            
        except Exception as e:
            logger.error(f'移除部门权限失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'移除失败: {str(e)}'})
    
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
        except Exception as e:
            logger.error(f'记录操作日志失败: {str(e)}')


class UserPermissionListView(LoginRequiredMixin, View):
    """获取部门下用户列表视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        try:
            dept_id = request.GET.get('dept_id')
            
            if not dept_id:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            # 获取部门
            from apps.department.models import Department
            dept = get_object_or_404(Department, id=dept_id)
            
            # 获取部门下的所有用户（使用did字段而不是department字段）
            users = User.objects.filter(did=dept_id)
            
            # 构建用户列表
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


class ExistingPermissionUsersView(LoginRequiredMixin, View):
    """获取已有权限的用户列表视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        try:
            item_type = request.GET.get('item_type')
            item_id = request.GET.get('item_id')
            
            if not all([item_type, item_id]) or item_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            # 获取项目
            if item_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
                # 获取已有权限的用户
                users = item.shared_users.all()
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
                # 获取已有权限的用户
                users = item.shared_users.all()
            
            # 构建用户列表
            user_list = []
            for user in users:
                user_list.append({
                    'id': user.id,
                    'username': user.username,
                    'name': user.name,
                    'department': {
                        'id': user.did,
                        'title': Department.objects.get(id=user.did).name if user.did else '无部门'
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


class ExistingPermissionDepartmentsView(LoginRequiredMixin, View):
    """获取已有权限的部门列表视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        try:
            item_type = request.GET.get('item_type')
            item_id = request.GET.get('item_id')
            
            if not all([item_type, item_id]) or item_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            # 获取项目
            if item_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
                # 获取已有权限的部门
                departments = item.shared_departments.all()
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
                # 获取已有权限的部门
                departments = item.shared_departments.all()
            
            # 构建部门列表
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
    
    def get_client_ip(self, request):
        """获取客户端IP地址"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class PermissionSaveView(LoginRequiredMixin, View):
    """保存权限设置视图"""
    login_url = '/user/login/'
    
    def post(self, request):
        try:
            item_type = request.POST.get('item_type')
            item_id = request.POST.get('item_id')
            is_public = request.POST.get('is_public') == 'true'
            inherit_permission = request.POST.get('inherit_permission') == 'true'
            
            if not all([item_type, item_id]) or item_type not in ['file', 'folder']:
                return JsonResponse({'code': 1, 'msg': '参数错误'})
            
            # 获取项目
            if item_type == 'file':
                item = get_object_or_404(DiskFile, id=item_id, owner=request.user, delete_time__isnull=True)
            else:
                item = get_object_or_404(DiskFolder, id=item_id, owner=request.user, delete_time__isnull=True)
            
            # 更新公开设置
            item.is_public = is_public
            item.save()
            
            # 记录操作日志
            self.log_operation(request, 'permission', 
                             file=item if item_type == 'file' else None,
                             folder=item if item_type == 'folder' else None,
                             description=f'更新权限设置: 公开={is_public}')
            
            return JsonResponse({'code': 0, 'msg': '权限设置保存成功'})
            
        except Exception as e:
            logger.error(f'保存权限设置失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'保存失败: {str(e)}'})
    
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
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
        except Exception as e:
            logger.error(f'记录操作日志失败: {str(e)}')


class UserPermissionAddView(LoginRequiredMixin, View):
    """添加用户权限视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        item_type = request.GET.get('item_type')
        item_id = request.GET.get('item_id')
        
        if not item_id or item_type not in ['file', 'folder']:
            return JsonResponse({'code': 1, 'msg': '参数错误'})
        
        # 获取所有用户（排除当前用户）
        users = User.objects.exclude(id=request.user.id)
        
        # 获取所有部门
        departments = Department.objects.all()
        
        # 构建部门树形结构
        def build_dept_tree(dept_list, parent_id=0):
            tree = []
            for dept in dept_list:
                if dept.pid == parent_id:
                    children = build_dept_tree(dept_list, dept.id)
                    tree.append({
                        'id': dept.id,
                        'title': dept.name,  # 使用name字段作为title
                        'spread': True,
                        'children': children
                    })
            return tree
        
        dept_tree = build_dept_tree(list(departments))
        
        context = {
            'item_type': item_type,
            'item_id': item_id,
            'users': users,
            'departments': json.dumps(dept_tree)  # 转换为JSON字符串
        }
        return render(request, 'disk/permission_add_user.html', context)


class DeptPermissionAddView(LoginRequiredMixin, View):
    """添加部门权限视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        item_type = request.GET.get('item_type')
        item_id = request.GET.get('item_id')
        
        if not item_id or item_type not in ['file', 'folder']:
            return JsonResponse({'code': 1, 'msg': '参数错误'})
        
        # 获取所有部门
        from apps.department.models import Department
        departments = Department.objects.all()
        
        context = {
            'item_type': item_type,
            'item_id': item_id,
            'departments': departments
        }
        return render(request, 'disk/permission_add_dept.html', context)
    
    def get_client_ip(self, request):
        """获取客户端IP地址"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip