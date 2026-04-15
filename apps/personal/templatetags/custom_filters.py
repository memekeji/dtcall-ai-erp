from django import template

register = template.Library()


@register.filter(name='splitlines')
def splitlines(value):
    """将文本按换行符分割成列表"""
    if not value:
        return []
    # 处理不同系统的换行符
    return value.replace('\r\n', '\n').replace('\r', '\n').split('\n')
