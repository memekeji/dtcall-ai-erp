"""
条件判断节点处理器
"""

import re
import operator
from typing import Any, Dict, Set
from .base_processor import BaseNodeProcessor, NodeProcessorRegistry


class SafeExpressionEvaluator:
    """安全表达式评估器"""

    _allowed_ops = {
        # 比较运算符
        operator.eq: '==',
        operator.ne: '!=',
        operator.lt: '<',
        operator.le: '<=',
        operator.gt: '>',
        operator.ge: '>=',
        # 逻辑运算符
        'and': lambda a, b: a and b,
        'or': lambda a, b: a or b,
        'not': lambda a: not a,
        # 成员运算符
        'in': lambda a, b: a in b,
        'not in': lambda a, b: a not in b,
        # 一元运算符
        '+': operator.pos,
        '-': operator.neg,
    }

    _allowed_funcs: Set[str] = set()

    _allowed_names: Dict[str, Any] = {
        'True': True,
        'False': False,
        'None': None,
    }

    _dangerous_patterns = [
        r'import\s+',
        r'from\s+.*\s+import',
        r'exec\s*\(',
        r'eval\s*\(',
        r'compile\s*\(',
        r'open\s*\(',
        r'__',
        r'class\s+',
        r'def\s+',
        r'global\s+',
        r'nonlocal\s+',
        r'breakpoint\s*\(',
        r'help\s*\(',
    ]

    @classmethod
    def is_safe_expression(cls, expression: str) -> bool:
        """检查表达式是否安全"""
        expr_lower = expression.lower()
        for pattern in cls._dangerous_patterns:
            if re.search(pattern, expr_lower):
                return False
        return True

    @classmethod
    def safe_eval(cls,
                  expression: str,
                  context: Dict[str,
                                Any] = None) -> bool:
        """安全地评估布尔表达式"""
        if context is None:
            context = {}

        # 安全检查
        if not cls.is_safe_expression(expression):
            return False

        # 预处理：替换变量
        processed_expr = expression
        for key, value in context.items():
            placeholder = f'{{{{{key}}}}}'
            processed_expr = processed_expr.replace(placeholder, str(value))

        # 使用模式匹配进行安全评估
        return cls._evaluate_safe(processed_expr, context)

    @classmethod
    def _evaluate_safe(cls, expression: str, context: Dict[str, Any]) -> bool:
        """安全地评估表达式"""
        try:
            expr = expression.strip()

            # 布尔值直接匹配
            expr_lower = expr.lower()
            if expr_lower in ('true', '1', 'yes', '是', '真'):
                return True
            if expr_lower in ('false', '0', 'no', '否', '假'):
                return False

            # 模式匹配评估
            return cls._pattern_evaluation(expr, context)
        except Exception:
            return False

    @classmethod
    def _pattern_evaluation(cls, expression: str,
                            context: Dict[str, Any]) -> bool:
        """使用模式匹配评估表达式"""
        # 比较运算符模式
        comparison_patterns = [
            (r'(\w+)\s*>\s*(\w+)', lambda x,
             y: cls._compare(x, y, context, operator.gt)),
            (r'(\w+)\s*<\s*(\w+)', lambda x,
             y: cls._compare(x, y, context, operator.lt)),
            (r'(\w+)\s*>=\s*(\w+)', lambda x,
             y: cls._compare(x, y, context, operator.ge)),
            (r'(\w+)\s*<=\s*(\w+)', lambda x,
             y: cls._compare(x, y, context, operator.le)),
            (r'(\w+)\s*==\s*(\w+)', lambda x,
             y: cls._compare(x, y, context, operator.eq)),
            (r'(\w+)\s*!=\s*(\w+)', lambda x,
             y: cls._compare(x, y, context, operator.ne)),
        ]

        for pattern, evaluator in comparison_patterns:
            match = re.search(pattern, expression)
            if match:
                try:
                    left = match.group(1)
                    right = match.group(2)
                    return evaluator(left, right)
                except (ValueError, TypeError):
                    continue

        # 成员运算符模式
        in_pattern = r'(\w+)\s+in\s+\[(.*?)\]'
        in_match = re.search(in_pattern, expression)
        if in_match:
            try:
                left = in_match.group(1)
                right_items = [item.strip().strip("'\"")
                               for item in in_match.group(2).split(',')]
                left_val = cls._get_value(left, context)
                return left_val in right_items
            except Exception:
                pass

        # contains模式
        contains_pattern = r'(\w+)\s+contains\s+(\w+)'
        contains_match = re.search(contains_pattern, expression)
        if contains_match:
            try:
                left = contains_match.group(1)
                right = contains_match.group(2)
                left_val = cls._get_value(left, context)
                right_val = cls._get_value(right, context)
                return str(right_val) in str(left_val)
            except Exception:
                pass

        return False

    @classmethod
    def _compare(cls, left: str, right: str,
                 context: Dict[str, Any], op) -> bool:
        """比较两个值"""
        left_val = cls._get_value(left, context)
        right_val = cls._get_value(right, context)

        # 尝试转换为数字
        try:
            left_val = float(left_val)
            right_val = float(right_val)
        except (ValueError, TypeError):
            pass

        try:
            return op(left_val, right_val)
        except (TypeError, ValueError):
            return False

    @classmethod
    def _get_value(cls, name: str, context: Dict[str, Any]) -> Any:
        """获取变量的值"""
        # 尝试从上下文获取
        if name in context:
            return context[name]

        # 尝试转换为布尔值
        name_lower = name.lower()
        if name_lower in ('true', 'yes', '是', '真', '1'):
            return True
        if name_lower in ('false', 'no', '否', '假', '0'):
            return False

        return name


@NodeProcessorRegistry.register('condition')
class ConditionProcessor(BaseNodeProcessor):
    """条件判断节点处理器"""

    @classmethod
    def get_display_name(cls):
        return "条件判断节点"

    @classmethod
    def get_icon(cls):
        return "layui-icon-vercode"

    @classmethod
    def get_description(cls):
        return "根据条件判断执行不同的分支"

    def _get_config_schema(self) -> dict:
        """获取条件判断节点的配置模式"""
        return {
            'condition_type': {
                'type': 'string',
                'required': True,
                'label': '条件类型',
                'default': 'if_else',
                'options': [
                    {'value': 'if_else', 'label': '如果-否则'},
                    {'value': 'switch', 'label': '多条件分支'},
                    {'value': 'comparison', 'label': '比较判断'},
                    {'value': 'logical', 'label': '逻辑判断'}
                ],
                'description': '选择条件判断的类型'
            },
            'condition_expression': {
                'type': 'string',
                'required': True,
                'label': '条件表达式',
                'placeholder': '例如：{{age}} > 18',
                'description': '条件判断表达式，支持变量替换和基本运算符'
            },
            'true_branch_label': {
                'type': 'string',
                'required': False,
                'label': '真值分支标签',
                'default': '是',
                'description': '条件为真时的分支标签'
            },
            'false_branch_label': {
                'type': 'string',
                'required': False,
                'label': '假值分支标签',
                'default': '否',
                'description': '条件为假时的分支标签'
            },
            'strict_mode': {
                'type': 'boolean',
                'required': False,
                'label': '严格模式',
                'default': False,
                'description': '启用严格模式，表达式必须完全匹配'
            }
        }

    def execute(self, config: dict, context: dict) -> dict:
        """执行条件判断节点逻辑"""
        condition_type = config.get('condition_type', 'if_else')
        condition_expression = config.get('condition_expression', '')
        strict_mode = config.get('strict_mode', False)

        # 替换表达式中的变量
        expression = condition_expression
        for key, value in context.items():
            placeholder = f'{{{{{key}}}}}'
            expression = expression.replace(placeholder, str(value))

        # 评估条件表达式
        condition_result = self._evaluate_condition(expression, strict_mode)

        return {
            'condition_result': condition_result,
            'condition_expression': expression,
            'branch_selected': 'true' if condition_result else 'false',
            'true_branch_label': config.get('true_branch_label', '是'),
            'false_branch_label': config.get('false_branch_label', '否')
        }

    def _evaluate_condition(self, expression: str, strict_mode: bool) -> bool:
        """评估条件表达式"""
        try:
            # 使用安全评估器替代eval
            return SafeExpressionEvaluator.safe_eval(expression, {})
        except Exception as e:
            # 表达式评估失败，返回False
            return False


@NodeProcessorRegistry.register('multi_condition')
class MultiConditionProcessor(ConditionProcessor):
    """多条件分支节点处理器"""

    @classmethod
    def get_display_name(cls):
        return "多条件分支节点"

    @classmethod
    def get_icon(cls):
        return "layui-icon-senior"

    @classmethod
    def get_description(cls):
        return "支持多个条件分支的判断节点"

    def _get_config_schema(self) -> dict:
        """获取多条件分支节点的配置模式"""
        base_schema = super()._get_config_schema()

        # 为多条件分支添加特定配置
        base_schema.update({
            'conditions': {
                'type': 'array',
                'required': True,
                'label': '条件列表',
                'description': '多个条件分支配置',
                'items': {
                    'type': 'object',
                    'properties': {
                        'condition': {
                            'type': 'string',
                            'required': True,
                            'label': '条件表达式'
                        },
                        'branch_label': {
                            'type': 'string',
                            'required': True,
                            'label': '分支标签'
                        }
                    }
                }
            },
            'default_branch': {
                'type': 'string',
                'required': False,
                'label': '默认分支',
                'description': '当所有条件都不满足时的默认分支'
            }
        })

        return base_schema

    def execute(self, config: dict, context: dict) -> dict:
        """执行多条件分支节点逻辑"""
        conditions = config.get('conditions', [])
        default_branch = config.get('default_branch', 'default')

        selected_branch = default_branch
        matched_condition = None

        # 遍历所有条件
        for condition_config in conditions:
            condition_expression = condition_config.get('condition', '')
            branch_label = condition_config.get('branch_label', '')

            # 替换表达式中的变量
            expression = condition_expression
            for key, value in context.items():
                placeholder = f'{{{{{key}}}}}'
                expression = expression.replace(placeholder, str(value))

            # 评估条件
            if self._evaluate_condition(expression, False):
                selected_branch = branch_label
                matched_condition = condition_expression
                break

        return {
            'selected_branch': selected_branch,
            'matched_condition': matched_condition,
            'total_conditions': len(conditions),
            'default_branch_used': selected_branch == default_branch
        }


@NodeProcessorRegistry.register('switch')
class SwitchProcessor(MultiConditionProcessor):
    """多条件分支节点处理器（switch类型）"""

    @classmethod
    def get_display_name(cls):
        return "多条件分支节点"

    @classmethod
    def get_icon(cls):
        return "layui-icon-list"

    @classmethod
    def get_description(cls):
        return "支持多个条件分支的判断节点"

    def _get_config_schema(self) -> dict:
        """获取多条件分支节点的配置模式"""
        return super()._get_config_schema()

    def execute(self, config: dict, context: dict) -> dict:
        """执行多条件分支节点逻辑"""
        return super().execute(config, context)
