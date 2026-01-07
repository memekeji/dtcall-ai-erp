"""
条件判断节点处理器
"""

import re
from .base_processor import BaseNodeProcessor, NodeProcessorRegistry


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
            # 简单的表达式解析和评估
            if strict_mode:
                # 严格模式：使用eval评估
                # 注意：在生产环境中应该使用更安全的表达式评估方法
                return bool(eval(expression, {}, {}))
            else:
                # 宽松模式：使用简单的模式匹配
                return self._simple_condition_evaluation(expression)
        except Exception as e:
            # 表达式评估失败，返回False
            return False
    
    def _simple_condition_evaluation(self, expression: str) -> bool:
        """简单的条件表达式评估"""
        # 支持常见的比较运算符
        patterns = [
            (r'(\w+)\s*>\s*(\w+)', lambda x, y: str(x) > str(y)),
            (r'(\w+)\s*<\s*(\w+)', lambda x, y: str(x) < str(y)),
            (r'(\w+)\s*>=\s*(\w+)', lambda x, y: str(x) >= str(y)),
            (r'(\w+)\s*<=\s*(\w+)', lambda x, y: str(x) <= str(y)),
            (r'(\w+)\s*==\s*(\w+)', lambda x, y: str(x) == str(y)),
            (r'(\w+)\s*!=\s*(\w+)', lambda x, y: str(x) != str(y)),
            (r'(\w+)\s*contains\s*(\w+)', lambda x, y: str(y) in str(x)),
            (r'(\w+)\s*in\s*\[(.*?)\]', lambda x, y: str(x) in [item.strip() for item in y.split(',')])
        ]
        
        for pattern, evaluator in patterns:
            match = re.search(pattern, expression)
            if match:
                try:
                    left = match.group(1)
                    right = match.group(2)
                    return evaluator(left, right)
                except:
                    continue
        
        # 如果无法匹配任何模式，尝试布尔值判断
        expression_lower = expression.lower().strip()
        if expression_lower in ('true', '1', 'yes', '是', '真'):
            return True
        elif expression_lower in ('false', '0', 'no', '否', '假'):
            return False
        
        # 默认返回False
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