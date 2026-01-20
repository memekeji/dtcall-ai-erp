"""
增强的节点配置Schema
支持用户交互、工作流控制等高级功能
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class InteractionField:
    """交互字段定义"""
    name: str
    label: str
    field_type: str
    required: bool = False
    placeholder: str = ""
    help_text: str = ""
    default_value: Any = None
    options: List[Dict] = field(default_factory=list)
    validation: Dict = field(default_factory=dict)
    conditional_display: Dict = field(default_factory=dict)


@dataclass
class InteractionConfig:
    """交互配置"""
    enabled: bool = False
    interaction_type: str = "approval"
    title: str = ""
    description: str = ""
    timeout: int = 3600
    fields: List[InteractionField] = field(default_factory=list)
    allow_skip: bool = False
    skip_value: Any = None
    notification: Dict = field(default_factory=dict)


@dataclass
class BranchConfig:
    """分支配置"""
    condition: str
    label: str
    color: str = "#52c41a"
    icon: str = ""
    priority: int = 0


@dataclass
class EnhancedNodeConfig:
    """增强节点配置"""
    
    basic_info: Dict = field(default_factory=dict)
    
    input_config: Dict = field(default_factory=dict)
    
    output_config: Dict = field(default_factory=dict)
    
    interaction_config: InteractionConfig = field(default_factory=lambda: InteractionConfig())
    
    branch_config: List[BranchConfig] = field(default_factory=list)
    
    error_handling: Dict = field(default_factory=dict)
    
    performance: Dict = field(default_factory=dict)
    
    visibility: Dict = field(default_factory=dict)


class EnhancedNodeConfigSchema:
    """增强节点配置Schema管理器"""
    
    @classmethod
    def get_approval_node_schema(cls) -> Dict[str, Any]:
        """审批节点配置Schema"""
        return {
            'name': '审批节点',
            'description': '需要用户审批的工作流节点',
            'category': 'interaction',
            'icon': 'check-circle',
            'config': {
                'basic_info': {
                    'node_name': {
                        'type': 'string',
                        'required': True,
                        'label': '节点名称',
                        'default': '审批节点',
                        'placeholder': '请输入节点名称'
                    },
                    'description': {
                        'type': 'textarea',
                        'required': False,
                        'label': '描述',
                        'placeholder': '请输入节点描述'
                    }
                },
                'interaction': {
                    'enabled': {
                        'type': 'switch',
                        'required': True,
                        'label': '需要审批',
                        'default': True
                    },
                    'approval_type': {
                        'type': 'select',
                        'required': True,
                        'label': '审批类型',
                        'default': 'single',
                        'options': [
                            {'value': 'single', 'label': '单人审批'},
                            {'value': 'multi', 'label': '多人会签'},
                            {'value': 'or', 'label': '或签（任一人通过）'},
                            {'value': 'sequential', 'label': '依次审批'}
                        ],
                        'depends_on': {'interaction.enabled': True}
                    },
                    'approvers': {
                        'type': 'user_selector',
                        'required': True,
                        'label': '审批人',
                        'placeholder': '请选择审批人',
                        'mode': 'multiple',
                        'depends_on': {'interaction.enabled': True}
                    },
                    'approval_timeout': {
                        'type': 'number',
                        'required': False,
                        'label': '审批超时时间(秒)',
                        'default': 3600,
                        'min': 60,
                        'depends_on': {'interaction.enabled': True}
                    },
                    'approval_title': {
                        'type': 'string',
                        'required': True,
                        'label': '审批请求标题',
                        'default': '审批请求',
                        'placeholder': '请输入审批请求标题',
                        'depends_on': {'interaction.enabled': True}
                    },
                    'approval_description': {
                        'type': 'richtext',
                        'required': False,
                        'label': '审批请求描述',
                        'placeholder': '请输入审批请求描述',
                        'depends_on': {'interaction.enabled': True}
                    },
                    'allow_rejection_reason': {
                        'type': 'switch',
                        'required': False,
                        'label': '允许填写驳回原因',
                        'default': True,
                        'depends_on': {'interaction.enabled': True}
                    },
                    'notify_on_complete': {
                        'type': 'switch',
                        'required': False,
                        'label': '审批完成后通知',
                        'default': True,
                        'depends_on': {'interaction.enabled': True}
                    }
                },
                'branch': {
                    'enable_branch': {
                        'type': 'switch',
                        'required': True,
                        'label': '启用分支',
                        'default': False
                    },
                    'branches': {
                        'type': 'branch_config',
                        'required': False,
                        'label': '分支配置',
                        'options': [
                            {
                                'condition': 'input.approved == true',
                                'label': '通过',
                                'color': '#52c41a',
                                'default': True
                            },
                            {
                                'condition': 'input.approved == false',
                                'label': '驳回',
                                'color': '#ff4d4f'
                            }
                        ],
                        'depends_on': {'branch.enable_branch': True}
                    }
                },
                'error_handling': {
                    'on_timeout': {
                        'type': 'select',
                        'required': True,
                        'label': '超时处理',
                        'default': 'auto_approve',
                        'options': [
                            {'value': 'auto_approve', 'label': '自动通过'},
                            {'value': 'auto_reject', 'label': '自动驳回'},
                            {'value': 'skip', 'label': '跳过节点'},
                            {'value': 'error', 'label': '报错终止'}
                        ]
                    },
                    'on_approver_unavailable': {
                        'type': 'select',
                        'required': True,
                        'label': '审批人不可用',
                        'default': 'error',
                        'options': [
                            {'value': 'skip', 'label': '跳过节点'},
                            {'value': 'error', 'label': '报错终止'},
                            {'value': 'notify_admin', 'label': '通知管理员'}
                        ]
                    }
                }
            }
        }
    
    @classmethod
    def get_form_input_node_schema(cls) -> Dict[str, Any]:
        """表单输入节点配置Schema"""
        return {
            'name': '表单输入节点',
            'description': '需要用户填写表单的节点',
            'category': 'interaction',
            'icon': 'form',
            'config': {
                'basic_info': {
                    'node_name': {
                        'type': 'string',
                        'required': True,
                        'label': '节点名称',
                        'default': '表单输入',
                        'placeholder': '请输入节点名称'
                    },
                    'description': {
                        'type': 'textarea',
                        'required': False,
                        'label': '描述',
                        'placeholder': '请输入节点描述'
                    }
                },
                'interaction': {
                    'enabled': {
                        'type': 'switch',
                        'required': True,
                        'label': '需要用户输入',
                        'default': True
                    },
                    'input_title': {
                        'type': 'string',
                        'required': True,
                        'label': '输入表单标题',
                        'default': '请输入信息',
                        'placeholder': '请输入表单标题',
                        'depends_on': {'interaction.enabled': True}
                    },
                    'input_description': {
                        'type': 'textarea',
                        'required': False,
                        'label': '表单描述',
                        'placeholder': '请输入表单描述',
                        'depends_on': {'interaction.enabled': True}
                    },
                    'input_timeout': {
                        'type': 'number',
                        'required': False,
                        'label': '输入超时时间(秒)',
                        'default': 3600,
                        'min': 60,
                        'depends_on': {'interaction.enabled': True}
                    },
                    'fields': {
                        'type': 'form_builder',
                        'required': True,
                        'label': '表单字段',
                        'depends_on': {'interaction.enabled': True},
                        'field_types': [
                            {'type': 'text', 'label': '单行文本', 'icon': 'font-size'},
                            {'type': 'textarea', 'label': '多行文本', 'icon': 'file-text'},
                            {'type': 'number', 'label': '数字', 'icon': 'number'},
                            {'type': 'select', 'label': '下拉选择', 'icon': 'down'},
                            {'type': 'radio', 'label': '单选', 'icon': 'radio'},
                            {'type': 'checkbox', 'label': '复选框', 'icon': 'check-square'},
                            {'type': 'date', 'label': '日期', 'icon': 'calendar'},
                            {'type': 'datetime', 'label': '日期时间', 'icon': 'clock-circle'},
                            {'type': 'file', 'label': '文件上传', 'icon': 'upload'},
                            {'type': 'richtext', 'label': '富文本', 'icon': 'edit'}
                        ],
                        'validation_types': ['required', 'optional', 'email', 'phone', 'number', 'regex']
                    }
                },
                'output': {
                    'output_variable': {
                        'type': 'string',
                        'required': True,
                        'label': '输出变量名',
                        'default': 'form_data',
                        'placeholder': '请输入输出变量名'
                    },
                    'output_format': {
                        'type': 'select',
                        'required': True,
                        'label': '输出格式',
                        'default': 'json',
                        'options': [
                            {'value': 'json', 'label': 'JSON对象'},
                            {'value': 'flat', 'label': '扁平化'}
                        ]
                    }
                },
                'error_handling': {
                    'on_timeout': {
                        'type': 'select',
                        'required': True,
                        'label': '超时处理',
                        'default': 'error',
                        'options': [
                            {'value': 'use_default', 'label': '使用默认值'},
                            {'value': 'skip', 'label': '跳过节点'},
                            {'value': 'error', 'label': '报错终止'}
                        ]
                    },
                    'default_values': {
                        'type': 'object',
                        'required': False,
                        'label': '默认值'
                    }
                }
            }
        }
    
    @classmethod
    def get_confirmation_node_schema(cls) -> Dict[str, Any]:
        """确认节点配置Schema"""
        return {
            'name': '确认节点',
            'description': '需要用户确认的操作节点',
            'category': 'interaction',
            'icon': 'question-circle',
            'config': {
                'basic_info': {
                    'node_name': {
                        'type': 'string',
                        'required': True,
                        'label': '节点名称',
                        'default': '确认操作',
                        'placeholder': '请输入节点名称'
                    },
                    'description': {
                        'type': 'textarea',
                        'required': False,
                        'label': '描述',
                        'placeholder': '请输入节点描述'
                    }
                },
                'interaction': {
                    'enabled': {
                        'type': 'switch',
                        'required': True,
                        'label': '需要确认',
                        'default': True
                    },
                    'confirmation_message': {
                        'type': 'richtext',
                        'required': True,
                        'label': '确认消息',
                        'default': '确定要执行此操作吗？',
                        'placeholder': '请输入确认消息',
                        'depends_on': {'interaction.enabled': True}
                    },
                    'confirmation_timeout': {
                        'type': 'number',
                        'required': False,
                        'label': '确认超时时间(秒)',
                        'default': 300,
                        'min': 30,
                        'depends_on': {'interaction.enabled': True}
                    },
                    'show_cancel_button': {
                        'type': 'switch',
                        'required': False,
                        'label': '显示取消按钮',
                        'default': True,
                        'depends_on': {'interaction.enabled': True}
                    },
                    'default_action': {
                        'type': 'select',
                        'required': False,
                        'label': '默认操作',
                        'default': 'confirm',
                        'options': [
                            {'value': 'confirm', 'label': '确认'},
                            {'value': 'cancel', 'label': '取消'}
                        ],
                        'depends_on': {'interaction.confirmation_timeout': {'$exists': True}}
                    }
                },
                'branch': {
                    'enable_branch': {
                        'type': 'switch',
                        'required': True,
                        'label': '启用分支',
                        'default': True
                    },
                    'branches': {
                        'type': 'branch_config',
                        'required': False,
                        'label': '分支配置',
                        'options': [
                            {
                                'condition': 'input.confirmed == true',
                                'label': '确认',
                                'color': '#52c41a',
                                'default': True
                            },
                            {
                                'condition': 'input.confirmed == false',
                                'label': '取消',
                                'color': '#ff4d4f'
                            }
                        ],
                        'depends_on': {'branch.enable_branch': True}
                    }
                },
                'error_handling': {
                    'on_timeout': {
                        'type': 'select',
                        'required': True,
                        'label': '超时处理',
                        'default': 'cancel',
                        'options': [
                            {'value': 'confirm', 'label': '自动确认'},
                            {'value': 'cancel', 'label': '自动取消'},
                            {'value': 'error', 'label': '报错终止'}
                        ]
                    }
                }
            }
        }
    
    @classmethod
    def get_selection_node_schema(cls) -> Dict[str, Any]:
        """选择节点配置Schema"""
        return {
            'name': '选择节点',
            'description': '需要用户从多个选项中选择',
            'category': 'interaction',
            'icon': 'unordered-list',
            'config': {
                'basic_info': {
                    'node_name': {
                        'type': 'string',
                        'required': True,
                        'label': '节点名称',
                        'default': '选择',
                        'placeholder': '请输入节点名称'
                    }
                },
                'interaction': {
                    'enabled': {
                        'type': 'switch',
                        'required': True,
                        'label': '需要选择',
                        'default': True
                    },
                    'selection_title': {
                        'type': 'string',
                        'required': True,
                        'label': '选择标题',
                        'default': '请选择',
                        'placeholder': '请输入选择标题',
                        'depends_on': {'interaction.enabled': True}
                    },
                    'selection_mode': {
                        'type': 'select',
                        'required': True,
                        'label': '选择模式',
                        'default': 'single',
                        'options': [
                            {'value': 'single', 'label': '单选'},
                            {'value': 'multiple', 'label': '多选'}
                        ],
                        'depends_on': {'interaction.enabled': True}
                    },
                    'selection_options': {
                        'type': 'dynamic_option',
                        'required': True,
                        'label': '选择选项',
                        'depends_on': {'interaction.enabled': True},
                        'option_sources': [
                            {'type': 'static', 'label': '静态选项'},
                            {'type': 'variable', 'label': '从变量获取'},
                            {'type': 'api', 'label': '从API获取'}
                        ]
                    },
                    'selection_timeout': {
                        'type': 'number',
                        'required': False,
                        'label': '选择超时时间(秒)',
                        'default': 3600,
                        'min': 60
                    },
                    'allow_custom_option': {
                        'type': 'switch',
                        'required': False,
                        'label': '允许自定义选项',
                        'default': False
                    }
                },
                'output': {
                    'output_variable': {
                        'type': 'string',
                        'required': True,
                        'label': '输出变量名',
                        'default': 'selected_option'
                    },
                    'output_format': {
                        'type': 'select',
                        'required': True,
                        'label': '输出格式',
                        'default': 'value',
                        'options': [
                            {'value': 'value', 'label': '选项值'},
                            {'value': 'label', 'label': '选项标签'},
                            {'value': 'object', 'label': '完整对象'}
                        ]
                    }
                },
                'branch': {
                    'enable_branch': {
                        'type': 'switch',
                        'required': True,
                        'label': '根据选项分支',
                        'default': False
                    },
                    'option_branches': {
                        'type': 'option_branch_config',
                        'required': False,
                        'label': '选项分支',
                        'depends_on': {'branch.enable_branch': True}
                    }
                }
            }
        }
    
    @classmethod
    def get_human_review_node_schema(cls) -> Dict[str, Any]:
        """人工审核节点配置Schema"""
        return {
            'name': '人工审核节点',
            'description': '需要人工审核的节点',
            'category': 'interaction',
            'icon': 'audit',
            'config': {
                'basic_info': {
                    'node_name': {
                        'type': 'string',
                        'required': True,
                        'label': '节点名称',
                        'default': '人工审核',
                        'placeholder': '请输入节点名称'
                    },
                    'review_content': {
                        'type': 'richtext',
                        'required': True,
                        'label': '审核内容',
                        'placeholder': '请输入需要审核的内容模板'
                    }
                },
                'interaction': {
                    'enabled': {
                        'type': 'switch',
                        'required': True,
                        'label': '需要审核',
                        'default': True
                    },
                    'review_type': {
                        'type': 'select',
                        'required': True,
                        'label': '审核类型',
                        'default': 'approve_reject',
                        'options': [
                            {'value': 'approve_reject', 'label': '通过/驳回'},
                            {'value': 'pass_fail', 'label': '合格/不合格'},
                            {'value': 'custom', 'label': '自定义选项'}
                        ],
                        'depends_on': {'interaction.enabled': True}
                    },
                    'review_options': {
                        'type': 'array',
                        'required': False,
                        'label': '审核选项',
                        'depends_on': {'interaction.review_type': 'custom'}
                    },
                    'reviewers': {
                        'type': 'user_selector',
                        'required': True,
                        'label': '审核人',
                        'mode': 'multiple',
                        'depends_on': {'interaction.enabled': True}
                    },
                    'review_timeout': {
                        'type': 'number',
                        'required': False,
                        'label': '审核超时时间(秒)',
                        'default': 86400
                    },
                    'require_comment': {
                        'type': 'switch',
                        'required': False,
                        'label': '必须填写意见',
                        'default': True
                    },
                    'allow_attach_file': {
                        'type': 'switch',
                        'required': False,
                        'label': '允许上传附件',
                        'default': False
                    }
                },
                'output': {
                    'output_variable': {
                        'type': 'string',
                        'required': True,
                        'label': '输出变量名',
                        'default': 'review_result'
                    }
                },
                'branch': {
                    'enable_branch': {
                        'type': 'switch',
                        'required': True,
                        'label': '启用分支',
                        'default': True
                    },
                    'branches': {
                        'type': 'branch_config',
                        'required': False,
                        'label': '分支配置',
                        'options': [
                            {
                                'condition': "input.review_result in ['approved', 'pass', '合格', '通过']",
                                'label': '通过',
                                'color': '#52c41a',
                                'default': True
                            },
                            {
                                'condition': "input.review_result in ['rejected', 'fail', '不合格', '驳回']",
                                'label': '不通过',
                                'color': '#ff4d4f'
                            }
                        ]
                    }
                }
            }
        }
    
    @classmethod
    def get_all_interaction_node_schemas(cls) -> Dict[str, Dict]:
        """获取所有交互节点配置Schema"""
        return {
            'approval': cls.get_approval_node_schema(),
            'form_input': cls.get_form_input_node_schema(),
            'confirmation': cls.get_confirmation_node_schema(),
            'selection': cls.get_selection_node_schema(),
            'human_review': cls.get_human_review_node_schema()
        }
    
    @classmethod
    def get_enhanced_ai_generation_schema(cls) -> Dict[str, Any]:
        """增强的AI生成节点配置"""
        base_schema = {
            'name': 'AI生成节点',
            'description': '调用AI模型生成内容',
            'category': 'ai',
            'icon': 'robot',
            'config': {
                'basic_info': {
                    'node_name': {
                        'type': 'string',
                        'required': True,
                        'label': '节点名称',
                        'default': 'AI生成'
                    }
                },
                'model': {
                    'model_id': {
                        'type': 'select',
                        'required': True,
                        'label': 'AI模型',
                        'default': 'gpt-4'
                    }
                },
                'prompt': {
                    'prompt': {
                        'type': 'richtext',
                        'required': True,
                        'label': '提示词',
                        'placeholder': '请根据以下信息生成内容：\n\n输入数据：${input_data}'
                    },
                    'prompt_type': {
                        'type': 'select',
                        'required': False,
                        'label': '提示词类型',
                        'default': 'free',
                        'options': [
                            {'value': 'free', 'label': '自由格式'},
                            {'value': 'structured', 'label': '结构化输出'}
                        ]
                    }
                },
                'parameters': {
                    'temperature': {
                        'type': 'number',
                        'required': False,
                        'label': 'Temperature',
                        'default': 0.7,
                        'min': 0,
                        'max': 2
                    },
                    'max_tokens': {
                        'type': 'number',
                        'required': False,
                        'label': '最大输出Token',
                        'default': 2000
                    }
                },
                'interaction': {
                    'enable_review': {
                        'type': 'switch',
                        'required': False,
                        'label': '启用人工审核',
                        'default': False
                    },
                    'review_before_output': {
                        'type': 'switch',
                        'required': False,
                        'label': '输出前审核',
                        'default': False,
                        'depends_on': {'interaction.enable_review': True}
                    },
                    'max_review_iterations': {
                        'type': 'number',
                        'required': False,
                        'label': '最大审核迭代次数',
                        'default': 3,
                        'min': 1,
                        'max': 10,
                        'depends_on': {'interaction.enable_review': True}
                    },
                    'output_variable': {
                        'type': 'string',
                        'required': True,
                        'label': '输出变量名',
                        'default': 'ai_output'
                    },
                    'fallback_on_error': {
                        'type': 'select',
                        'required': False,
                        'label': '错误处理',
                        'default': 'retry',
                        'options': [
                            {'value': 'retry', 'label': '重试'},
                            {'value': 'use_cache', 'label': '使用缓存'},
                            {'value': 'skip', 'label': '跳过'},
                            {'value': 'error', 'label': '报错'}
                        ]
                    }
                }
            }
        }
        
        return base_schema
    
    @classmethod
    def get_enhanced_condition_schema(cls) -> Dict[str, Any]:
        """增强的条件节点配置"""
        return {
            'name': '条件判断节点',
            'description': '根据条件进行分支判断',
            'category': 'logic',
            'icon': 'fork',
            'config': {
                'basic_info': {
                    'node_name': {
                        'type': 'string',
                        'required': True,
                        'label': '节点名称',
                        'default': '条件判断'
                    }
                },
                'condition': {
                    'condition_type': {
                        'type': 'select',
                        'required': True,
                        'label': '条件类型',
                        'default': 'if_else',
                        'options': [
                            {'value': 'if_else', 'label': 'IF-ELSE'},
                            {'value': 'switch', 'label': 'SWITCH'},
                            {'value': 'expression', 'label': '表达式'}
                        ]
                    },
                    'conditions': {
                        'type': 'condition_builder',
                        'required': True,
                        'label': '条件设置'
                    },
                    'default_branch': {
                        'type': 'string',
                        'required': False,
                        'label': '默认分支'
                    }
                },
                'branch_config': {
                    'branches': {
                        'type': 'branch_config',
                        'required': True,
                        'label': '分支配置',
                        'support_visual_editor': True
                    }
                }
            }
        }
    
    @classmethod
    def get_enhanced_parallel_schema(cls) -> Dict[str, Any]:
        """增强的并行处理节点配置"""
        return {
            'name': '并行处理节点',
            'description': '并行执行多个任务',
            'category': 'logic',
            'icon': 'block',
            'config': {
                'basic_info': {
                    'node_name': {
                        'type': 'string',
                        'required': True,
                        'label': '节点名称',
                        'default': '并行处理'
                    }
                },
                'parallel': {
                    'execution_mode': {
                        'type': 'select',
                        'required': True,
                        'label': '执行模式',
                        'default': 'all',
                        'options': [
                            {'value': 'all', 'label': '全部执行'},
                            {'value': 'any', 'label': '任一完成'},
                            {'value': 'custom', 'label': '自定义'}
                        ]
                    },
                    'max_workers': {
                        'type': 'number',
                        'required': False,
                        'label': '最大并发数',
                        'default': 5,
                        'min': 1,
                        'max': 20
                    },
                    'timeout': {
                        'type': 'number',
                        'required': False,
                        'label': '超时时间(秒)',
                        'default': 300
                    },
                    'tasks': {
                        'type': 'task_config',
                        'required': True,
                        'label': '并行任务'
                    }
                },
                'error_handling': {
                    'on_task_error': {
                        'type': 'select',
                        'required': True,
                        'label': '任务错误处理',
                        'default': 'continue',
                        'options': [
                            {'value': 'continue', 'label': '继续执行其他任务'},
                            {'value': 'stop_all', 'label': '停止所有任务'},
                            {'value': 'retry', 'label': '重试'}
                        ]
                    }
                }
            }
        }
    
    @classmethod
    def get_enhanced_loop_schema(cls) -> Dict[str, Any]:
        """增强的循环节点配置"""
        return {
            'name': '循环处理节点',
            'description': '循环执行某项操作',
            'category': 'logic',
            'icon': 'reload',
            'config': {
                'basic_info': {
                    'node_name': {
                        'type': 'string',
                        'required': True,
                        'label': '节点名称',
                        'default': '循环处理'
                    }
                },
                'loop': {
                    'loop_type': {
                        'type': 'select',
                        'required': True,
                        'label': '循环类型',
                        'default': 'for',
                        'options': [
                            {'value': 'for', 'label': '计数循环'},
                            {'value': 'while', 'label': '条件循环'},
                            {'value': 'foreach', 'label': '遍历循环'}
                        ]
                    },
                    'loop_config': {
                        'type': 'loop_config_builder',
                        'required': True,
                        'label': '循环配置'
                    },
                    'max_iterations': {
                        'type': 'number',
                        'required': False,
                        'label': '最大迭代次数',
                        'default': 100,
                        'min': 1,
                        'max': 10000
                    },
                    'break_condition': {
                        'type': 'text',
                        'required': False,
                        'label': '中断条件',
                        'placeholder': '满足条件时中断循环'
                    }
                },
                'error_handling': {
                    'on_iteration_error': {
                        'type': 'select',
                        'required': True,
                        'label': '迭代错误处理',
                        'default': 'continue',
                        'options': [
                            {'value': 'continue', 'label': '继续下一次迭代'},
                            {'value': 'break', 'label': '中断循环'},
                            {'value': 'error', 'label': '报错终止'}
                        ]
                    }
                },
                'output': {
                    'collect_results': {
                        'type': 'switch',
                        'required': False,
                        'label': '收集每次结果',
                        'default': True
                    },
                    'output_variable': {
                        'type': 'string',
                        'required': True,
                        'label': '输出变量名',
                        'default': 'loop_results'
                    }
                }
            }
        }


def get_enhanced_node_config(node_type: str) -> Optional[Dict]:
    """获取增强节点配置"""
    schemas = EnhancedNodeConfigSchema.get_all_interaction_node_schemas()
    
    enhanced_schemas = {
        'ai_generation': EnhancedNodeConfigSchema.get_enhanced_ai_generation_schema(),
        'condition': EnhancedNodeConfigSchema.get_enhanced_condition_schema(),
        'parallel': EnhancedNodeConfigSchema.get_enhanced_parallel_schema(),
        'loop': EnhancedNodeConfigSchema.get_enhanced_loop_schema()
    }
    
    enhanced_schemas.update(schemas)
    
    return enhanced_schemas.get(node_type)
