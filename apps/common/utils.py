"""
公共工具模块
提供通用的工具函数，消除重复代码
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.http import JsonResponse

logger = logging.getLogger(__name__)


def timestamp_to_date(
        timestamp: Optional[int],
        format_str: str = '%Y-%m-%d %H:%M') -> str:
    """将时间戳转换为日期字符串

    Args:
        timestamp: 时间戳（秒）
        format_str: 日期格式字符串

    Returns:
        格式化后的日期字符串，若无效则返回空字符串
    """
    if timestamp and timestamp > 0:
        try:
            return datetime.fromtimestamp(timestamp).strftime(format_str)
        except (ValueError, OSError):
            return ''
    return ''


def timestamp_to_datetime(timestamp: Optional[int]) -> Optional[datetime]:
    """将时间戳转换为datetime对象

    Args:
        timestamp: 时间戳（秒）

    Returns:
        datetime对象，若无效则返回None
    """
    if timestamp and timestamp > 0:
        try:
            return datetime.fromtimestamp(timestamp)
        except (ValueError, OSError):
            return None
    return None


def datetime_to_timestamp(dt: Optional[datetime]) -> int:
    """将datetime对象转换为时间戳

    Args:
        dt: datetime对象

    Returns:
        时间戳（秒），若无效则返回当前时间戳
    """
    if dt:
        try:
            return int(dt.timestamp())
        except (ValueError, AttributeError):
            return int(time.time())
    return int(time.time())


def date_to_timestamp(date_str: str, format_str: str = '%Y-%m-%d') -> int:
    """将日期字符串转换为时间戳

    Args:
        date_str: 日期字符串
        format_str: 日期格式

    Returns:
        时间戳（秒）
    """
    try:
        dt = datetime.strptime(date_str, format_str)
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return 0


def parse_date_range(date_range_str: str) -> tuple:
    """解析日期范围字符串

    Args:
        date_range_str: 格式如 '2024-01-01 - 2024-01-31'

    Returns:
        (开始时间戳, 结束时间戳) 元组
    """
    if not date_range_str or ' - ' not in date_range_str:
        return (0, 0)

    try:
        start_str, end_str = date_range_str.split(' - ')
        start_dt = datetime.strptime(start_str.strip(), '%Y-%m-%d')
        # 结束日期设置为当天23:59:59
        end_dt = datetime.strptime(end_str.strip(), '%Y-%m-%d')
        end_dt = end_dt.replace(hour=23, minute=59, second=59)

        return (int(start_dt.timestamp()), int(end_dt.timestamp()))
    except (ValueError, TypeError):
        return (0, 0)


def safe_int(value: Any, default: int = 0) -> int:
    """安全转换为整数

    Args:
        value: 要转换的值
        default: 转换失败时的默认值

    Returns:
        整数
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换为浮点数

    Args:
        value: 要转换的值
        default: 转换失败时的默认值

    Returns:
        浮点数
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_str(value: Any, default: str = '') -> str:
    """安全转换为字符串

    Args:
        value: 要转换的值
        default: 转换失败时的默认值

    Returns:
        字符串
    """
    if value is None:
        return default
    try:
        return str(value)
    except Exception:
        return default


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """安全解析JSON字符串

    Args:
        json_str: JSON字符串
        default: 解析失败时的默认值

    Returns:
        解析后的对象
    """
    if not json_str:
        return default
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def build_pagination_response(
    queryset,
    page: int = 1,
    limit: int = 20,
    data_builder: callable = None
) -> Dict:
    """构建分页响应数据

    Args:
        queryset: Django查询集
        page: 当前页码
        limit: 每页数量
        data_builder: 数据构建回调函数

    Returns:
        包含分页信息的字典
    """
    from django.core.paginator import Paginator

    paginator = Paginator(queryset, limit)
    page_obj = paginator.get_page(page)

    if data_builder:
        data = [data_builder(item) for item in page_obj]
    else:
        data = list(page_obj)

    return {
        'code': 0,
        'msg': '',
        'count': paginator.count,
        'data': data
    }


def build_error_response(message: str, code: int = 1) -> JsonResponse:
    """构建错误响应

    Args:
        message: 错误消息
        code: 错误码

    Returns:
        JsonResponse对象
    """
    return JsonResponse({
        'code': code,
        'msg': message,
        'count': 0,
        'data': []
    })


def build_success_response(
        data: Any = None,
        message: str = '',
        count: int = 0) -> JsonResponse:
    """构建成功响应

    Args:
        data: 响应数据
        message: 成功消息
        count: 数据总数

    Returns:
        JsonResponse对象
    """
    response_data = {
        'code': 0,
        'msg': message or 'success',
    }

    if data is not None:
        response_data['data'] = data

    if count > 0:
        response_data['count'] = count

    return JsonResponse(response_data)


def get_client_ip(request) -> str:
    """获取客户端IP地址

    Args:
        request: Django请求对象

    Returns:
        IP地址字符串
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


def format_timestamp(ts: Optional[int]) -> str:
    """格式化时间戳为可读字符串

    Args:
        ts: 时间戳

    Returns:
        格式化后的时间字符串
    """
    if not ts:
        return ''

    try:
        dt = datetime.fromtimestamp(ts)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, OSError):
        return ''


def generate_invoice_code(prefix: str = 'INV') -> str:
    """生成发票编号

    Args:
        prefix: 编号前缀

    Returns:
        发票编号字符串
    """
    return f'{prefix}{int(time.time())}'


def generate_order_number(prefix: str = 'ORD') -> str:
    """生成订单编号

    Args:
        prefix: 编号前缀

    Returns:
        订单编号字符串
    """
    import uuid
    unique_id = str(uuid.uuid4()).replace('-', '')[:8].upper()
    return f'{prefix}-{unique_id}'


def generate_contract_number(prefix: str = 'CONT') -> str:
    """生成合同编号

    Args:
        prefix: 编号前缀

    Returns:
        合同编号字符串
    """
    return f'{prefix}-{int(time.time())}'


def get_date_range_filter(field_name: str, date_range_str: str):
    """构建日期范围过滤条件

    Args:
        field_name: 字段名
        date_range_str: 日期范围字符串

    Returns:
        Django Q对象
    """
    from django.db.models import Q

    if not date_range_str or ' - ' not in date_range_str:
        return Q()

    try:
        start_str, end_str = date_range_str.split(' - ')
        start_timestamp = int(
            datetime.strptime(
                start_str.strip(),
                '%Y-%m-%d').timestamp())
        end_timestamp = int(
            datetime.strptime(
                end_str.strip() + ' 23:59:59',
                '%Y-%m-%d %H:%M:%S').timestamp())

        return Q(**{f'{field_name}__gte': start_timestamp}
                 ) & Q(**{f'{field_name}__lte': end_timestamp})
    except (ValueError, TypeError):
        return Q()


def contains_user_id(field_value: str, user_id: int) -> bool:
    """检查字段值是否包含指定用户ID

    Args:
        field_value: 字段值（如逗号分隔的ID字符串）
        user_id: 用户ID

    Returns:
        是否包含
    """
    if not field_value:
        return False

    str_user_id = str(user_id)
    id_list = [x.strip() for x in field_value.split(',') if x.strip()]
    return str_user_id in id_list


def add_user_to_field(field_value: str, user_id: int) -> str:
    """将用户ID添加到字段值中

    Args:
        field_value: 原有字段值
        user_id: 用户ID

    Returns:
        更新后的字段值
    """
    if not field_value:
        return str(user_id)

    str_user_id = str(user_id)
    id_list = [x.strip() for x in field_value.split(',') if x.strip()]

    if str_user_id not in id_list:
        id_list.append(str_user_id)

    return ','.join(id_list)


class PaginationHelper:
    """分页辅助类"""

    def __init__(
            self,
            request,
            default_page: int = 1,
            default_limit: int = 20):
        """初始化

        Args:
            request: Django请求对象
            default_page: 默认页码
            default_limit: 默认每页数量
        """
        self.page = safe_int(request.GET.get('page'), default_page)
        self.limit = safe_int(request.GET.get('limit'), default_limit)
        self.offset = (self.page - 1) * self.limit

    def get_queryset_slice(self, queryset):
        """获取查询集切片

        Args:
            queryset: Django查询集

        Returns:
            切片后的查询集
        """
        return queryset[self.offset:self.offset + self.limit]

    def get_response_data(self, queryset, serializer=None):
        """获取分页响应数据

        Args:
            queryset: Django查询集
            serializer: 序列化器（可选）

        Returns:
            响应数据字典
        """
        total = queryset.count()
        data = self.get_queryset_slice(queryset)

        if serializer:
            data = serializer(data, many=True).data

        return {
            'code': 0,
            'msg': '',
            'count': total,
            'data': data
        }


class StatusCodeMapper:
    """状态码映射类"""

    _mappings = {}

    @classmethod
    def register(cls, name: str, mapping: Dict[int, str]):
        """注册状态映射

        Args:
            name: 映射名称
            mapping: 状态码到描述的映射字典
        """
        cls._mappings[name] = mapping

    @classmethod
    def get_display(
            cls,
            name: str,
            status_code: int,
            default: str = '未知') -> str:
        """获取状态描述

        Args:
            name: 映射名称
            status_code: 状态码
            default: 默认描述

        Returns:
            状态描述字符串
        """
        mapping = cls._mappings.get(name, {})
        return mapping.get(status_code, default)

    @classmethod
    def get_mapping(cls, name: str) -> Dict[int, str]:
        """获取完整映射

        Args:
            name: 映射名称

        Returns:
            映射字典
        """
        return cls._mappings.get(name, {})


# 注册常用状态映射
StatusCodeMapper.register('check_status', {
    0: '待审核',
    1: '审核中',
    2: '审核通过',
    3: '审核不通过',
    4: '撤销审核'
})

StatusCodeMapper.register('pay_status', {
    0: '待打款',
    1: '已打款'
})

StatusCodeMapper.register('open_status', {
    0: '未开票',
    1: '已开票',
    2: '已作废'
})

StatusCodeMapper.register('enter_status', {
    0: '未回款',
    1: '部分回款',
    2: '全部回款'
})

StatusCodeMapper.register('invoice_type', {
    1: '增值税专用发票',
    2: '普通发票',
    3: '专用发票'
})


def get_status_display(status_type: str, status_code: int) -> str:
    """获取状态显示文本（便捷函数）

    Args:
        status_type: 状态类型
        status_code: 状态码

    Returns:
        显示文本
    """
    return StatusCodeMapper.get_display(status_type, status_code)


def get_client_info(request) -> Dict[str, str]:
    """获取客户端信息

    Args:
        request: Django请求对象

    Returns:
        客户端信息字典
    """
    return {
        'ip_address': get_client_ip(request),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
    }


def truncate_text(
        text: str,
        max_length: int = 100,
        suffix: str = '...') -> str:
    """截断文本

    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的文本
    """
    if not text or len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def batch_process(
        items: List,
        processor: callable,
        batch_size: int = 50) -> Dict:
    """批量处理数据

    Args:
        items: 数据列表
        processor: 处理函数
        batch_size: 每批数量

    Returns:
        处理结果统计
    """
    results = {
        'total': len(items),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'errors': []
    }

    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        for item in batch:
            try:
                result = processor(item)
                if result is True:
                    results['success'] += 1
                elif result is False:
                    results['skipped'] += 1
                else:
                    results['success'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'item': str(item),
                    'error': str(e)
                })
                logger.error(f"批量处理失败: {str(e)}")

    return results
