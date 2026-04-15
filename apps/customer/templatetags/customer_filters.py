from django import template
import os
import json

register = template.Library()

# 这里可以添加自定义过滤器和标签


@register.filter(name='get_item')
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter(name='basename')
def basename(path):
    """从文件路径中提取文件名"""
    if path:
        return os.path.basename(path)
    return ''


@register.filter(name='json_load')
def json_load(value):
    try:
        return json.loads(value)
    except BaseException:
        return {}


@register.filter(name='parse_json')
def parse_json(value):
    """解析JSON字符串为Python对象"""
    try:
        return json.loads(value)
    except BaseException:
        return []


@register.filter(name='split')
def split(value, separator=','):
    """分割字符串为列表"""
    if not value:
        return []
    return value.split(separator)
