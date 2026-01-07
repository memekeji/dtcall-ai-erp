"""
通用模型基类和工具类
"""
from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """基础模型类，统一时间字段"""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间', db_index=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间', db_index=True)
    
    class Meta:
        abstract = True


class SoftDeleteModel(BaseModel):
    """软删除模型类"""
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='删除时间', db_index=True)
    is_deleted = models.BooleanField(default=False, verbose_name='是否已删除', db_index=True)
    
    class Meta:
        abstract = True
    
    def delete(self, using=None, keep_parents=False):
        """软删除"""
        self.deleted_at = timezone.now()
        self.is_deleted = True
        self.save(using=using)
    
    def hard_delete(self, using=None, keep_parents=False):
        """物理删除"""
        super().delete(using=using, keep_parents=keep_parents)
    
    def restore(self):
        """恢复删除"""
        self.deleted_at = None
        self.is_deleted = False
        self.save()


class StatusChoices(models.TextChoices):
    """通用状态选择"""
    ACTIVE = 'active', '启用'
    INACTIVE = 'inactive', '禁用'
    PENDING = 'pending', '待审核'
    DELETED = 'deleted', '已删除'


class PriorityChoices(models.IntegerChoices):
    """优先级选择"""
    LOW = 1, '低'
    MEDIUM = 2, '中'
    HIGH = 3, '高'
    URGENT = 4, '紧急'


class ApprovalStatusChoices(models.TextChoices):
    """审批状态选择"""
    DRAFT = 'draft', '草稿'
    PENDING = 'pending', '待审核'
    IN_REVIEW = 'in_review', '审核中'
    APPROVED = 'approved', '已通过'
    REJECTED = 'rejected', '已拒绝'
    CANCELLED = 'cancelled', '已撤销'


class PaymentStatusChoices(models.TextChoices):
    """支付状态选择"""
    UNPAID = 'unpaid', '未支付'
    PARTIAL = 'partial', '部分支付'
    PAID = 'paid', '已支付'
    REFUNDED = 'refunded', '已退款'


class OrderStatusChoices(models.TextChoices):
    """订单状态选择"""
    PENDING = 'pending', '待处理'
    CONFIRMED = 'confirmed', '已确认'
    PROCESSING = 'processing', '处理中'
    SHIPPED = 'shipped', '已发货'
    DELIVERED = 'delivered', '已交付'
    COMPLETED = 'completed', '已完成'
    CANCELLED = 'cancelled', '已取消'


class ProjectStatusChoices(models.TextChoices):
    """项目状态选择"""
    NOT_STARTED = 'not_started', '未开始'
    IN_PROGRESS = 'in_progress', '进行中'
    COMPLETED = 'completed', '已完成'
    PAUSED = 'paused', '已暂停'
    CANCELLED = 'cancelled', '已取消'


class TaskStatusChoices(models.TextChoices):
    """任务状态选择"""
    TODO = 'todo', '待办'
    IN_PROGRESS = 'in_progress', '进行中'
    REVIEW = 'review', '待审核'
    COMPLETED = 'completed', '已完成'
    CANCELLED = 'cancelled', '已取消'


class GenderChoices(models.IntegerChoices):
    """性别选择"""
    UNKNOWN = 0, '未知'
    MALE = 1, '男'
    FEMALE = 2, '女'


class FileTypeChoices(models.TextChoices):
    """文件类型选择"""
    DOCUMENT = 'document', '文档'
    IMAGE = 'image', '图片'
    VIDEO = 'video', '视频'
    AUDIO = 'audio', '音频'
    ARCHIVE = 'archive', '压缩包'
    OTHER = 'other', '其他'


def get_upload_path(instance, filename):
    """生成文件上传路径"""
    import os
    from datetime import datetime
    
    # 获取文件扩展名
    ext = os.path.splitext(filename)[1]
    # 生成新文件名
    new_filename = f"{timezone.now().strftime('%Y%m%d_%H%M%S')}_{instance.id or 'new'}{ext}"
    # 按日期分目录
    date_path = timezone.now().strftime('%Y/%m/%d')
    
    return f"uploads/{date_path}/{new_filename}"


class TimestampMixin:
    """时间戳转换混合类"""
    
    @staticmethod
    def timestamp_to_datetime(timestamp):
        """时间戳转DateTime"""
        if timestamp and timestamp > 0:
            try:
                return timezone.datetime.fromtimestamp(timestamp, tz=timezone.get_current_timezone())
            except (ValueError, OSError):
                return None
        return None
    
    @staticmethod
    def datetime_to_timestamp(dt):
        """DateTime转时间戳"""
        if dt:
            return int(dt.timestamp())
        return 0