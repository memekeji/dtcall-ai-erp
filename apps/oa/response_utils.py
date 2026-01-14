"""
API响应工具模块
统一API响应格式，提供标准的成功/失败响应方法
"""
import logging
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class ApiResponseCode:
    """API响应状态码定义"""
    SUCCESS = 0
    ERROR = 1
    VALIDATION_ERROR = 2
    NOT_FOUND = 3
    PERMISSION_DENIED = 4
    SERVER_ERROR = 500


def success_response(data=None, message='操作成功'):
    """
    成功响应
    :param data: 响应数据
    :param message: 响应消息
    :return: JsonResponse
    """
    response_data = {
        'code': ApiResponseCode.SUCCESS,
        'msg': message,
    }
    if data is not None:
        response_data['data'] = data
    return JsonResponse(response_data, json_dumps_params={'ensure_ascii': False})


def error_response(message='操作失败', code=ApiResponseCode.ERROR, data=None):
    """
    错误响应
    :param message: 错误消息
    :param code: 错误码
    :param data: 附加数据
    :return: JsonResponse
    """
    response_data = {
        'code': code,
        'msg': message,
    }
    if data is not None:
        response_data['data'] = data
    logger.warning(f"API错误响应: {message} (code: {code})")
    return JsonResponse(response_data, json_dumps_params={'ensure_ascii': False})


def validation_error_response(message='参数验证失败'):
    """
    参数验证错误响应
    :param message: 错误消息
    :return: JsonResponse
    """
    return error_response(message, code=ApiResponseCode.VALIDATION_ERROR)


def not_found_response(message='资源不存在'):
    """
    资源不存在响应
    :param message: 错误消息
    :return: JsonResponse
    """
    return error_response(message, code=ApiResponseCode.NOT_FOUND)


def permission_denied_response(message='无权限访问'):
    """
    权限拒绝响应
    :param message: 错误消息
    :return: JsonResponse
    """
    return error_response(message, code=ApiResponseCode.PERMISSION_DENIED)


def server_error_response(message='服务器内部错误'):
    """
    服务器错误响应
    :param message: 错误消息
    :return: JsonResponse
    """
    return error_response(message, code=ApiResponseCode.SERVER_ERROR)


def ajax_success_response(data=None, message='操作成功'):
    """
    兼容旧的AJAX成功响应格式
    :param data: 响应数据
    :param message: 响应消息
    :return: JsonResponse
    """
    response_data = {
        'success': True,
        'message': message,
    }
    if data is not None:
        response_data['data'] = data
    return JsonResponse(response_data, json_dumps_params={'ensure_ascii': False})


def ajax_error_response(message='操作失败', data=None):
    """
    兼容旧的AJAX错误响应格式
    :param message: 错误消息
    :param data: 附加数据
    :return: JsonResponse
    """
    response_data = {
        'success': False,
        'message': message,
    }
    if data is not None:
        response_data['data'] = data
    return JsonResponse(response_data, json_dumps_params={'ensure_ascii': False})
