from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.department.models import Department
import os
import mimetypes


class DiskFolder(models.Model):
    """网盘文件夹模型"""
    PERMISSION_LEVELS = (
        (1, '只读'),
        (2, '读写'),
        (3, '管理'),
    )

    name = models.CharField(max_length=200, verbose_name='文件夹名称')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='父文件夹')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_folders',
        verbose_name='所有者')
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='所属部门')

    is_public = models.BooleanField(default=False, verbose_name='是否公开')
    shared_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='shared_folders',
        verbose_name='共享用户')
    shared_departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name='shared_folders',
        verbose_name='共享部门')

    permission_level = models.IntegerField(
        default=1, choices=PERMISSION_LEVELS, verbose_name='权限级别')

    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.DateTimeField(
        null=True, blank=True, verbose_name='删除时间')

    class Meta:
        db_table = 'disk_folder'
        verbose_name = '网盘文件夹'
        verbose_name_plural = verbose_name
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_full_path(self):
        if self.parent:
            return f"{self.parent.get_full_path()}/{self.name}"
        return self.name

    @property
    def is_deleted(self):
        return self.delete_time is not None

    def get_all_files(self):
        """获取文件夹下所有文件（包括子文件夹中的文件）"""
        files = list(self.files.filter(delete_time__isnull=True))
        for child in self.children.filter(delete_time__isnull=True):
            files.extend(child.get_all_files())
        return files


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
    file_ext = models.CharField(
        max_length=20,
        default='',
        verbose_name='文件扩展名')
    file_type = models.CharField(
        max_length=20,
        choices=FILE_TYPES,
        default='other',
        verbose_name='文件类型')
    mime_type = models.CharField(
        max_length=100,
        default='',
        verbose_name='MIME类型')

    folder = models.ForeignKey(
        DiskFolder,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='files',
        verbose_name='所在文件夹')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_files',
        verbose_name='所有者')
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='所属部门')

    is_public = models.BooleanField(default=False, verbose_name='是否公开')
    shared_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='shared_files',
        verbose_name='共享用户')
    shared_departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name='shared_files',
        verbose_name='共享部门')

    is_starred = models.BooleanField(default=False, verbose_name='是否收藏')
    download_count = models.IntegerField(default=0, verbose_name='下载次数')
    view_count = models.IntegerField(default=0, verbose_name='查看次数')
    preview_count = models.IntegerField(default=0, verbose_name='预览次数')
    last_preview_time = models.DateTimeField(
        null=True, blank=True, verbose_name='最后预览时间')

    version = models.CharField(
        max_length=20,
        default='1.0',
        verbose_name='版本号')
    parent_file = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='versions',
        verbose_name='父文件')

    # AI 增强功能
    ai_summary = models.TextField(blank=True, null=True, verbose_name='AI智能摘要')
    ai_tags = models.CharField(max_length=500, blank=True, null=True, verbose_name='AI智能标签')
    ai_content_text = models.TextField(blank=True, null=True, verbose_name='AI提取文本(OCR/解析)')
    ai_status = models.IntegerField(default=0, verbose_name='AI处理状态:0未处理,1处理中,2已完成,3失败')

    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.DateTimeField(
        null=True, blank=True, verbose_name='删除时间')

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
            mime = mimetypes.guess_type(self.original_name)[0]
            self.mime_type = mime or 'application/octet-stream'

        if not self.file_type or self.file_type == 'other':
            self.file_type = self.get_file_type_by_ext()

        super().save(*args, **kwargs)

    def get_file_type_by_ext(self):
        ext = self.file_ext.lower()

        document_exts = [
            '.doc',
            '.docx',
            '.pdf',
            '.txt',
            '.rtf',
            '.odt',
            '.xls',
            '.xlsx',
            '.ppt',
            '.pptx']
        image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp']
        video_exts = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm']
        audio_exts = ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma']
        archive_exts = ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2']

        if ext in document_exts:
            return 'document'
        elif ext in image_exts:
            return 'image'
        elif ext in video_exts:
            return 'video'
        elif ext in audio_exts:
            return 'audio'
        elif ext in archive_exts:
            return 'archive'
        else:
            return 'other'

    def get_size_display(self):
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    @property
    def is_deleted(self):
        return self.delete_time is not None

    def get_full_path(self):
        if self.folder:
            return f"{self.folder.get_full_path()}/{self.name}"
        return self.name


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

    share_type = models.CharField(
        max_length=10,
        choices=SHARE_TYPES,
        verbose_name='分享类型')
    file = models.ForeignKey(
        DiskFile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='分享文件')
    folder = models.ForeignKey(
        DiskFolder,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='分享文件夹')

    share_code = models.CharField(
        max_length=32,
        unique=True,
        verbose_name='分享码')
    password = models.CharField(
        max_length=128,
        blank=True,
        verbose_name='提取密码（已哈希存储）')

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='创建者')
    expire_time = models.DateTimeField(
        null=True, blank=True, verbose_name='过期时间')

    permission_type = models.CharField(
        max_length=10,
        choices=PERMISSION_TYPES,
        default='download',
        verbose_name='权限类型')
    allow_download = models.BooleanField(default=True, verbose_name='允许下载')

    access_limit = models.IntegerField(default=0, verbose_name='访问次数限制(0为无限制)')
    access_count = models.IntegerField(default=0, verbose_name='访问次数')
    download_limit = models.IntegerField(default=0, verbose_name='下载限制(0为无限制)')
    download_count = models.IntegerField(default=0, verbose_name='下载次数')

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
        if self.expire_time:
            return timezone.now() > self.expire_time
        return False

    def can_access(self):
        if not self.is_active or self.is_expired():
            return False
        if self.access_limit > 0 and self.access_count >= self.access_limit:
            return False
        return True

    def can_download(self):
        if not self.can_access() or not self.allow_download:
            return False
        if self.download_limit > 0 and self.download_count >= self.download_limit:
            return False
        return True

    def can_preview(self):
        return self.can_download()

    def record_preview(self):
        self.access_count += 1
        self.save(update_fields=['access_count', 'update_time'])

    def record_access(self, ip_address):
        self.access_count += 1
        if ip_address:
            ips = self.visitor_ips.split(',') if self.visitor_ips else []
            if ip_address not in ips:
                ips.append(ip_address)
                self.visitor_ips = ','.join(ips[-100:])
        self.save(update_fields=['access_count', 'visitor_ips', 'update_time'])

    def record_download(self):
        self.download_count += 1
        self.save(update_fields=['download_count', 'update_time'])

    def get_item(self):
        if self.share_type == 'file':
            return self.file
        else:
            return self.folder

    def get_item_name(self):
        item = self.get_item()
        return item.name if item else '未知'

    def contains_file(self, file_id):
        """检查分享是否包含指定文件"""
        if self.share_type == 'file':
            return self.file_id == file_id
        elif self.share_type == 'folder' and self.folder:
            file = DiskFile.objects.filter(
                id=file_id, delete_time__isnull=True).first()
            if file:
                current_folder = file.folder
                while current_folder:
                    if current_folder.id == self.folder.id:
                        return True
                    current_folder = current_folder.parent
        return False


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
        ('restore', '恢复'),
        ('star', '收藏'),
        ('unstar', '取消收藏'),
        ('permission', '权限设置'),
        ('overwrite', '覆盖'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='操作用户')
    operation_type = models.CharField(
        max_length=20,
        choices=OPERATION_TYPES,
        verbose_name='操作类型')
    file = models.ForeignKey(
        DiskFile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='操作文件')
    folder = models.ForeignKey(
        DiskFolder,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='操作文件夹')

    description = models.CharField(max_length=500, verbose_name='操作描述')
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, verbose_name='IP地址')
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='用户代理')

    create_time = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')

    class Meta:
        db_table = 'disk_operation'
        verbose_name = '文件操作日志'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.user.username} - {self.get_operation_type_display()}"
