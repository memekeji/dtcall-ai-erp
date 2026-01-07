from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.user.models import Admin as User
from apps.department.models import Department
import os
import mimetypes


class DiskFolder(models.Model):
    """网盘文件夹模型"""
    name = models.CharField(max_length=200, verbose_name='文件夹名称')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name='父文件夹')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_folders', verbose_name='所有者')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='所属部门')
    
    # 权限设置
    is_public = models.BooleanField(default=False, verbose_name='是否公开')
    shared_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='shared_folders', verbose_name='共享用户')
    shared_departments = models.ManyToManyField(Department, blank=True, related_name='shared_folders', verbose_name='共享部门')
    
    # 权限级别：1-只读，2-读写，3-管理
    permission_level = models.IntegerField(default=1, choices=[(1, '只读'), (2, '读写'), (3, '管理')], verbose_name='权限级别')
    
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.DateTimeField(null=True, blank=True, verbose_name='删除时间')
    
    class Meta:
        db_table = 'disk_folder'
        verbose_name = '网盘文件夹'
        verbose_name_plural = verbose_name
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_full_path(self):
        """获取完整路径"""
        if self.parent:
            return f"{self.parent.get_full_path()}/{self.name}"
        return self.name
    
    def is_deleted(self):
        return self.delete_time is not None


class DiskFile(models.Model):
    """网盘文件模型"""
    FILE_TYPES = (
        ('document', '文档'),
        ('image', '图片'),
        ('video', '视频'),
        ('audio', '音频'),
        ('archive', '压缩包'),
        ('other', '其他'),
    )
    
    name = models.CharField(max_length=200, verbose_name='文件名称')
    original_name = models.CharField(max_length=200, verbose_name='原始文件名')
    file_path = models.CharField(max_length=500, verbose_name='文件路径')
    file_size = models.BigIntegerField(default=0, verbose_name='文件大小(字节)')
    file_ext = models.CharField(max_length=20, default='', verbose_name='文件扩展名')
    file_type = models.CharField(max_length=20, choices=FILE_TYPES, default='other', verbose_name='文件类型')
    mime_type = models.CharField(max_length=100, default='', verbose_name='MIME类型')
    
    folder = models.ForeignKey(DiskFolder, on_delete=models.CASCADE, null=True, blank=True, related_name='files', verbose_name='所在文件夹')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_files', verbose_name='所有者')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='所属部门')
    
    # 权限设置
    is_public = models.BooleanField(default=False, verbose_name='是否公开')
    shared_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='shared_files', verbose_name='共享用户')
    shared_departments = models.ManyToManyField(Department, blank=True, related_name='shared_files', verbose_name='共享部门')
    
    # 文件属性
    is_starred = models.BooleanField(default=False, verbose_name='是否收藏')
    download_count = models.IntegerField(default=0, verbose_name='下载次数')
    view_count = models.IntegerField(default=0, verbose_name='查看次数')
    
    # 版本控制
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本号')
    parent_file = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='versions', verbose_name='父文件')
    
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.DateTimeField(null=True, blank=True, verbose_name='删除时间')
    
    class Meta:
        db_table = 'disk_file'
        verbose_name = '网盘文件'
        verbose_name_plural = verbose_name
        ordering = ['-update_time']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.file_ext and self.original_name:
            self.file_ext = os.path.splitext(self.original_name)[1].lower()
        
        if not self.mime_type and self.original_name:
            self.mime_type = mimetypes.guess_type(self.original_name)[0] or 'application/octet-stream'
        
        # 根据文件扩展名确定文件类型
        if not self.file_type or self.file_type == 'other':
            self.file_type = self.get_file_type_by_ext()
        
        super().save(*args, **kwargs)
    
    def get_file_type_by_ext(self):
        """根据文件扩展名确定文件类型"""
        ext = self.file_ext.lower()
        
        if ext in ['.doc', '.docx', '.pdf', '.txt', '.rtf', '.odt', '.xls', '.xlsx', '.ppt', '.pptx']:
            return 'document'
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp']:
            return 'image'
        elif ext in ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm']:
            return 'video'
        elif ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma']:
            return 'audio'
        elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2']:
            return 'archive'
        else:
            return 'other'
    
    def get_size_display(self):
        """获取文件大小的友好显示"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def is_deleted(self):
        return self.delete_time is not None
    



class DiskShare(models.Model):
    """文件分享模型"""
    SHARE_TYPES = (
        ('file', '文件'),
        ('folder', '文件夹'),
    )
    
    PERMISSION_TYPES = (
        ('view', '仅查看'),
        ('download', '可下载'),
        ('edit', '可编辑'),
    )
    
    share_type = models.CharField(max_length=10, choices=SHARE_TYPES, verbose_name='分享类型')
    file = models.ForeignKey(DiskFile, on_delete=models.CASCADE, null=True, blank=True, verbose_name='分享文件')
    folder = models.ForeignKey(DiskFolder, on_delete=models.CASCADE, null=True, blank=True, verbose_name='分享文件夹')
    
    share_code = models.CharField(max_length=20, unique=True, verbose_name='分享码')
    password = models.CharField(max_length=20, blank=True, verbose_name='提取密码')
    
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='创建者')
    expire_time = models.DateTimeField(null=True, blank=True, verbose_name='过期时间')
    
    # 权限控制
    permission_type = models.CharField(max_length=10, choices=PERMISSION_TYPES, default='download', verbose_name='权限类型')
    allow_download = models.BooleanField(default=True, verbose_name='允许下载')

    
    # 访问限制
    access_limit = models.IntegerField(default=0, verbose_name='访问次数限制(0为无限制)')
    access_count = models.IntegerField(default=0, verbose_name='访问次数')
    download_limit = models.IntegerField(default=0, verbose_name='下载限制(0为无限制)')
    download_count = models.IntegerField(default=0, verbose_name='下载次数')
    
    # 访问者信息记录
    visitor_ips = models.TextField(blank=True, verbose_name='访问者IP记录')
    
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'disk_share'
        verbose_name = '文件分享'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"分享码: {self.share_code}"
    
    def is_expired(self):
        """检查是否过期"""
        if self.expire_time:
            return timezone.now() > self.expire_time
        return False
    
    def can_access(self):
        """检查是否可以访问"""
        if not self.is_active or self.is_expired():
            return False
        if self.access_limit > 0 and self.access_count >= self.access_limit:
            return False
        return True
    
    def can_download(self):
        """检查是否可以下载"""
        if not self.can_access() or not self.allow_download:
            return False
        if self.download_limit > 0 and self.download_count >= self.download_limit:
            return False
        return True
    
    def can_preview(self):
        """检查是否可以预览"""
        # 预览权限与下载权限相同
        return self.can_download()
    
    def record_preview(self):
        """记录预览"""
        # 预览也计入访问次数
        self.access_count += 1
        self.save()
    

    
    def record_access(self, ip_address):
        """记录访问"""
        self.access_count += 1
        if ip_address:
            ips = self.visitor_ips.split(',') if self.visitor_ips else []
            if ip_address not in ips:
                ips.append(ip_address)
                self.visitor_ips = ','.join(ips[-100:])  # 只保留最近100个IP
        self.save()
    
    def record_download(self):
        """记录下载"""
        self.download_count += 1
        self.save()
    
    def get_item(self):
        """获取分享的项目"""
        if self.share_type == 'file':
            return self.file
        else:
            return self.folder
    
    def get_item_name(self):
        """获取分享项目名称"""
        item = self.get_item()
        return item.name if item else '未知'


class DiskOperation(models.Model):
    """文件操作日志模型"""
    OPERATION_TYPES = (
        ('upload', '上传'),
        ('download', '下载'),
        ('delete', '删除'),
        ('share', '分享'),
        ('move', '移动'),
        ('copy', '复制'),
        ('rename', '重命名'),

    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='操作用户')
    operation_type = models.CharField(max_length=20, choices=OPERATION_TYPES, verbose_name='操作类型')
    file = models.ForeignKey(DiskFile, on_delete=models.CASCADE, null=True, blank=True, verbose_name='操作文件')
    folder = models.ForeignKey(DiskFolder, on_delete=models.CASCADE, null=True, blank=True, verbose_name='操作文件夹')
    
    description = models.CharField(max_length=500, verbose_name='操作描述')
    ip_address = models.GenericIPAddressField(verbose_name='IP地址')
    user_agent = models.CharField(max_length=500, verbose_name='用户代理')
    
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')
    
    class Meta:
        db_table = 'disk_operation'
        verbose_name = '文件操作日志'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_operation_type_display()}"


# 保持原有的Disk模型以兼容现有代码
class Disk(models.Model):
    pid = models.PositiveIntegerField(default=0, verbose_name='所在文件夹目录ID')
    types = models.PositiveSmallIntegerField(default=0, verbose_name='类型', help_text='0文件,1在线文档,2文件夹')
    action_id = models.PositiveIntegerField(default=0, verbose_name='相关联id')
    name = models.CharField(max_length=200, default='', verbose_name='文件名称')
    file_ext = models.CharField(max_length=200, default='', verbose_name='文件后缀名称')
    file_size = models.PositiveBigIntegerField(default=0, verbose_name='文件大小')
    is_star = models.PositiveSmallIntegerField(default=0, verbose_name='重要与否')
    is_share = models.PositiveSmallIntegerField(default=0, verbose_name='共享与否')
    share_dids = models.CharField(max_length=200, default='', verbose_name='共享部门')
    share_ids = models.CharField(max_length=200, default='', verbose_name='共享人')
    admin_id = models.PositiveIntegerField(default=0, verbose_name='创建人')
    did = models.PositiveIntegerField(default=0, verbose_name='所属部门')
    create_time = models.PositiveBigIntegerField(default=0, verbose_name='创建时间')
    update_time = models.PositiveBigIntegerField(default=0, verbose_name='修改时间')
    delete_time = models.PositiveBigIntegerField(default=0, verbose_name='删除时间')
    clear_time = models.PositiveBigIntegerField(default=0, verbose_name='清除时间')

    class Meta:
        db_table = 'mimu_disk'
        verbose_name = '网盘表'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name