"""
日志敏感信息屏蔽工具
确保操作日志中的敏感信息不会被泄露
"""

import re
from typing import Any, Dict, List, Optional

SENSITIVE_FIELDS = {
    'password', 'pwd', 'passwd', 'pass', 'secret', 'token', 'access_token',
    'refresh_token', 'api_key', 'apikey', 'private_key', 'secret_key',
    'authorization', 'auth_token', 'session_id', 'cookie', 'csrf_token',
    'credit_card', 'card_number', 'cvv', 'id_number', 'id_card',
    'mobile', 'phone', 'tel', 'telephone', 'email', 'address',
    'bank_account', 'account_number', 'bank_card', 'ssn',
}

SENSITIVE_PATTERNS = [
    r'(?i)(password[\s=:]+)[^\s\'",}]+',
    r'(?i)(pwd[\s=:]+)[^\s\'",}]+',
    r'(?i)(passwd[\s=:]+)[^\s\'",}]+',
    r'(?i)(token[\s=:]+)[^\s\'",}]+',
    r'(?i)(secret[\s=:]+)[^\s\'",}]+',
    r'(?i)(api[_-]?key[\s=:]+)[^\s\'",}]+',
    r'(?i)(access[_-]?token[\s=:]+)[^\s\'",}]+',
    r'(?i)(refresh[_-]?token[\s=:]+)[^\s\'",}]+',
    r'(?i)(authorization[\s=:]+)[^\s\'",}]+',
    r'\d{11}(?:\d{4})?',  # 手机号
    r'\d{6}(?:\d{6})?',  # 身份证号
    r'\d{16,19}',  # 银行卡号
    r'[A-Za-z0-9+/]{20,}={0,2}',  # Base64编码的token等
]


def mask_sensitive_value(value: str, mask_char: str = '*',
                         visible_count: int = 2) -> str:
    """
    遮蔽字符串中的敏感信息

    Args:
        value: 原始字符串
        mask_char: 遮蔽字符，默认为 '*'
        visible_count: 前后可见的字符数

    Returns:
        遮蔽后的字符串
    """
    if not value or not isinstance(value, str):
        return value

    length = len(value)
    if length <= visible_count * 2:
        return mask_char * length

    return value[:visible_count] + mask_char * \
        (length - visible_count * 2) + value[-visible_count:]


def mask_sensitive_field(field_name: str, field_value: Any) -> Any:
    """
    遮蔽敏感字段的值

    Args:
        field_name: 字段名
        field_value: 字段值

    Returns:
        遮蔽后的字段值
    """
    field_lower = field_name.lower()

    if field_lower in SENSITIVE_FIELDS:
        if isinstance(field_value, str):
            return mask_sensitive_value(field_value)
        elif isinstance(field_value, dict):
            return {k: mask_sensitive_field(
                f"{field_name}_{k}", v) for k, v in field_value.items()}
        elif isinstance(field_value, list):
            return [mask_sensitive_field(field_name, item)
                    for item in field_value]
        return field_value

    if isinstance(field_value, str):
        for pattern in SENSITIVE_PATTERNS:
            field_value = re.sub(
                pattern,
                lambda m: f"{m.group(1)}{mask_sensitive_value(m.group(2))}",
                field_value)

    return field_value


def sanitize_log_content(content: Any) -> Any:
    """
    清理日志内容中的敏感信息

    Args:
        content: 原始内容，可以是字符串、字典或列表

    Returns:
        清理后的内容
    """
    if content is None:
        return None

    if isinstance(content, str):
        result = content
        for pattern in SENSITIVE_PATTERNS:
            result = re.sub(
                pattern, lambda m: mask_sensitive_value(
                    m.group(0)), result)
        return result

    if isinstance(content, dict):
        return {k: sanitize_log_content(v) for k, v in content.items()}

    if isinstance(content, list):
        return [sanitize_log_content(item) for item in content]

    return content


def sanitize_log_record(
        record: Dict[str, Any], sensitive_fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    清理单条日志记录中的敏感信息

    Args:
        record: 日志记录字典
        sensitive_fields: 需要检查的敏感字段列表，默认为 None（使用默认敏感字段列表）

    Returns:
        清理后的日志记录
    """
    if not record or not isinstance(record, dict):
        return record

    sensitive_fields = sensitive_fields or list(SENSITIVE_FIELDS)

    result = {}
    for key, value in record.items():
        key_lower = key.lower()

        if key_lower in sensitive_fields:
            result[key] = mask_sensitive_field(key, value)
        elif key == 'content' or key_lower == 'details':
            result[key] = sanitize_log_content(value)
        elif isinstance(value, (dict, list)):
            result[key] = sanitize_log_content(value)
        else:
            result[key] = value

    return result


def sanitize_log_list(records: List[Dict[str, Any]],
                      sensitive_fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    批量清理日志记录中的敏感信息

    Args:
        records: 日志记录列表
        sensitive_fields: 需要检查的敏感字段列表

    Returns:
        清理后的日志记录列表
    """
    return [sanitize_log_record(record, sensitive_fields)
            for record in records]


def sanitize_dict_for_log(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    通用字典敏感信息清理
    用于清理任何可能包含敏感信息的字典数据

    Args:
        data: 待清理的字典

    Returns:
        清理后的字典
    """
    if not data or not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        key_lower = key.lower()

        if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS):
            if isinstance(value, str):
                result[key] = mask_sensitive_value(value)
            elif isinstance(value, dict):
                result[key] = sanitize_dict_for_log(value)
            else:
                result[key] = value
        elif isinstance(value, str):
            result[key] = value
            for pattern in SENSITIVE_PATTERNS:
                result[key] = re.sub(
                    pattern, lambda m: mask_sensitive_value(
                        m.group(0)), result[key])
        elif isinstance(value, dict):
            result[key] = sanitize_dict_for_log(value)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict_for_log(item) if isinstance(item, dict)
                else mask_sensitive_value(str(item)) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            result[key] = value

    return result


def sanitize_request_data(data: Any) -> Any:
    """
    清理请求数据中的敏感信息
    专门用于处理 request.POST, request.GET 等数据

    Args:
        data: 请求数据

    Returns:
        清理后的数据
    """
    if data is None:
        return None

    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            key_lower = key.lower()

            if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS):
                if isinstance(value, str):
                    result[key] = '***MASKED***'
                else:
                    result[key] = value
            elif isinstance(value, (dict, list)):
                result[key] = sanitize_request_data(value)
            else:
                result[key] = value

        return result

    if isinstance(data, (list, tuple)):
        return [sanitize_request_data(item) for item in data]

    return data
