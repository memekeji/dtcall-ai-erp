"""
会议相关常量定义
统一会议类型、状态等枚举定义
"""
from django.db.models import TextChoices


class MeetingTypeChoices(TextChoices):
    """会议类型枚举"""
    REGULAR = 'regular', '例会'
    PROJECT = 'project', '项目会议'
    TRAINING = 'training', '培训会议'
    REVIEW = 'review', '评审会议'
    EMERGENCY = 'emergency', '紧急会议'
    OTHER = 'other', '其他'

    @classmethod
    def get_label(cls, value):
        return dict(cls.choices).get(value, '未知')


class MeetingStatusChoices(TextChoices):
    """会议状态枚举"""
    SCHEDULED = 'scheduled', '已安排'
    CONFIRMED = 'confirmed', '已确认'
    IN_PROGRESS = 'in_progress', '进行中'
    COMPLETED = 'completed', '已完成'
    CANCELLED = 'cancelled', '已取消'
    POSTPONED = 'postponed', '已延期'


class ReservationStatusChoices(TextChoices):
    """预订状态枚举"""
    PENDING = 'pending', '待审核'
    APPROVED = 'approved', '已通过'
    REJECTED = 'rejected', '已拒绝'
    CANCELLED = 'cancelled', '已取消'


# 文件上传配置
class FileUploadConfig:
    """文件上传配置常量"""
    AUDIO_ALLOWED_EXTENSIONS = ['.mp3', '.wav', '.flac', '.ogg', '.aac', '.wma']
    AUDIO_ALLOWED_MIME_TYPES = [
        'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav',
        'audio/flac', 'audio/ogg', 'audio/aac', 'audio/x-ms-wma'
    ]
    MAX_AUDIO_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    AUDIO_UPLOAD_DIR = 'meeting_recordings'

    THREAD_TIMEOUT = 30  # 线程超时时间（秒）
    AJAX_TIMEOUT = 90000  # AJAX请求超时（毫秒）
    CHUNK_SIZE = 8192  # 文件写入块大小
