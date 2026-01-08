"""
权限节点配置
根据权限管理详细设计文档定义的所有权限节点
用于前端权限配置页面和后端权限控制

权限格式: {app_label}.{action}_{model}
例如: user.view_notice, user.add_department
"""

PERMISSION_NODES = {
    # 1. 工作台
    'workbench': {
        'name': '工作台',
        'icon': 'layui-icon-home',
        'permissions': [
            {'codename': 'view_workbench', 'name': '菜单查看'},
            {'codename': 'view_data_screen', 'name': '数据大屏查看'},
            {'codename': 'view_finance_screen', 'name': '财务大屏查看'},
            {'codename': 'view_business_screen', 'name': '经营大屏查看'},
            {'codename': 'view_production_screen', 'name': '生产大屏查看'},
        ]
    },

    # 2. 系统管理
    'system': {
        'name': '系统管理',
        'icon': 'layui-icon-set',
        'children': {
            'config': {
                'name': '系统配置',
                'permissions': [
                    {'codename': 'view_config', 'name': '菜单查看'},
                    {'codename': 'view_systemconfiguration', 'name': '系统配置查看'},
                    {'codename': 'add_config', 'name': '新增配置'},
                    {'codename': 'change_config', 'name': '编辑配置'},
                    {'codename': 'change_systemconfiguration', 'name': '系统配置编辑'},
                    {'codename': 'delete_systemconfiguration', 'name': '系统配置删除'},
                ]
            },
            'module': {
                'name': '功能模块',
                'permissions': [
                    {'codename': 'view_module', 'name': '菜单查看'},
                    {'codename': 'add_module', 'name': '新增模块'},
                    {'codename': 'change_module', 'name': '编辑模块'},
                ]
            },
            'menu': {
                'name': '菜单管理',
                'permissions': [
                    {'codename': 'view_menu', 'name': '菜单查看'},
                    {'codename': 'add_menu', 'name': '新增菜单'},
                    {'codename': 'change_menu', 'name': '编辑菜单'},
                    {'codename': 'delete_menu', 'name': '删除菜单'},
                    {'codename': 'order_menu', 'name': '菜单排序'},
                ]
            },
            'operation_log': {
                'name': '操作日志',
                'permissions': [
                    {'codename': 'view_operation_log', 'name': '菜单查看'},
                    {'codename': 'view_systemoperationlog', 'name': '系统操作日志查看'},
                    {'codename': 'view_operation_log_detail', 'name': '查看日志详情'},
                ]
            },
            'attachment': {
                'name': '附件管理',
                'permissions': [
                    {'codename': 'view_attachment', 'name': '菜单查看'},
                    {'codename': 'download_attachment', 'name': '下载附件'},
                    {'codename': 'delete_attachment', 'name': '删除附件'},
                ]
            },
            'backup': {
                'name': '备份数据',
                'permissions': [
                    {'codename': 'view_backup', 'name': '菜单查看'},
                    {'codename': 'add_backup', 'name': '新建备份'},
                    {'codename': 'change_backup', 'name': '编辑备份'},
                    {'codename': 'restore_backup', 'name': '还原备份'},
                    {'codename': 'download_backup', 'name': '下载备份'},
                    {'codename': 'delete_backup', 'name': '删除备份'},
                    {'codename': 'view_backup_policy', 'name': '自动备份策略'},
                    {'codename': 'batch_delete_backup', 'name': '批量删除'},
                ]
            },
        }
    },

    # 3. 人事管理
    'hr': {
        'name': '人事管理',
        'icon': 'layui-icon-group',
        'children': {
            'role': {
                'name': '角色管理',
                'permissions': [
                    {'codename': 'view_role', 'name': '菜单查看'},
                    {'codename': 'add_role', 'name': '新增角色'},
                    {'codename': 'change_role', 'name': '编辑角色'},
                    {'codename': 'config_role_permission', 'name': '权限配置'},
                    {'codename': 'toggle_role_status', 'name': '禁用/启用角色'},
                    {'codename': 'delete_role', 'name': '删除角色'},
                ]
            },
            'department': {
                'name': '部门管理',
                'permissions': [
                    {'codename': 'view_department', 'name': '菜单查看'},
                    {'codename': 'add_department', 'name': '新增部门'},
                    {'codename': 'change_department', 'name': '编辑部门'},
                    {'codename': 'delete_department', 'name': '删除部门'},
                    {'codename': 'toggle_department_status', 'name': '禁用/启用部门'},
                    {'codename': 'manage_department_role', 'name': '角色管理'},
                ]
            },
            'position': {
                'name': '岗位职称',
                'permissions': [
                    {'codename': 'view_position', 'name': '菜单查看'},
                    {'codename': 'add_position', 'name': '新增岗位'},
                    {'codename': 'change_position', 'name': '编辑岗位'},
                    {'codename': 'delete_position', 'name': '删除岗位'},
                    {'codename': 'toggle_position_status', 'name': '禁用/启用岗位'},
                ]
            },
            'employee': {
                'name': '员工管理',
                'permissions': [
                    {'codename': 'view_employee', 'name': '菜单查看'},
                    {'codename': 'add_employee', 'name': '新增员工'},
                    {'codename': 'change_employee', 'name': '编辑员工'},
                    {'codename': 'delete_employee', 'name': '删除员工'},
                    {'codename': 'batch_import_employee', 'name': '批量导入'},
                ]
            },
            'reward_punishment': {
                'name': '奖罚管理',
                'permissions': [
                    {'codename': 'view_reward_punishment', 'name': '菜单查看'},
                    {'codename': 'add_reward_punishment', 'name': '新增奖罚'},
                    {'codename': 'change_reward_punishment', 'name': '编辑奖罚'},
                    {'codename': 'delete_reward_punishment', 'name': '删除奖罚'},
                ]
            },
            'employee_care': {
                'name': '员工关怀',
                'permissions': [
                    {'codename': 'view_employee_care', 'name': '菜单查看'},
                    {'codename': 'add_employee_care', 'name': '新增关怀'},
                    {'codename': 'change_employee_care', 'name': '编辑关怀'},
                    {'codename': 'delete_employee_care', 'name': '删除关怀'},
                ]
            },
        }
    },

    # 4. 行政办公
    'admin': {
        'name': '行政办公',
        'icon': 'layui-icon-template-1',
        'children': {
            'assets': {
                'name': '固定资产',
                'children': {
                    'asset': {
                        'name': '资产管理',
                        'permissions': [
                            {'codename': 'view_asset', 'name': '菜单查看'},
                            {'codename': 'add_asset', 'name': '新增资产'},
                            {'codename': 'change_asset', 'name': '编辑资产'},
                            {'codename': 'delete_asset', 'name': '删除资产'},
                        ]
                    },
                    'asset_return': {
                        'name': '资产归还',
                        'permissions': [
                            {'codename': 'view_asset_return', 'name': '菜单查看'},
                            {'codename': 'add_asset_return', 'name': '新增归还'},
                            {'codename': 'change_asset_return', 'name': '编辑归还'},
                            {'codename': 'delete_asset_return', 'name': '删除归还'},
                        ]
                    },
                    'asset_repair': {
                        'name': '资产维修',
                        'permissions': [
                            {'codename': 'view_asset_repair', 'name': '菜单查看'},
                            {'codename': 'add_asset_repair', 'name': '新增维修'},
                            {'codename': 'change_asset_repair', 'name': '编辑维修'},
                            {'codename': 'delete_asset_repair', 'name': '删除维修'},
                        ]
                    },
                    'asset_scrap': {
                        'name': '资产报废',
                        'permissions': [
                            {'codename': 'view_asset_scrap', 'name': '菜单查看'},
                            {'codename': 'add_asset_scrap', 'name': '新增报废'},
                            {'codename': 'change_asset_scrap', 'name': '编辑报废'},
                            {'codename': 'delete_asset_scrap', 'name': '删除报废'},
                        ]
                    },
                }
            },
            'vehicle': {
                'name': '车辆管理',
                'children': {
                    'vehicle_info': {
                        'name': '车辆信息',
                        'permissions': [
                            {'codename': 'view_vehicle_info', 'name': '菜单查看'},
                            {'codename': 'add_vehicle_info', 'name': '新增车辆'},
                            {'codename': 'change_vehicle_info', 'name': '编辑车辆'},
                            {'codename': 'delete_vehicle_info', 'name': '删除车辆'},
                        ]
                    },
                    'vehicle_apply': {
                        'name': '用车申请',
                        'permissions': [
                            {'codename': 'view_vehicle_apply', 'name': '菜单查看'},
                            {'codename': 'add_vehicle_apply', 'name': '新增用车'},
                            {'codename': 'change_vehicle_apply', 'name': '编辑用车'},
                            {'codename': 'delete_vehicle_apply', 'name': '删除用车'},
                        ]
                    },
                    'vehicle_maintenance': {
                        'name': '车辆维修',
                        'permissions': [
                            {'codename': 'view_vehicle_maintenance', 'name': '菜单查看'},
                            {'codename': 'add_vehicle_maintenance', 'name': '新增维修'},
                            {'codename': 'change_vehicle_maintenance', 'name': '编辑维修'},
                            {'codename': 'delete_vehicle_maintenance', 'name': '删除维修'},
                        ]
                    },
                    'vehicle_dispatch': {
                        'name': '车辆调度',
                        'permissions': [
                            {'codename': 'view_vehicle_dispatch', 'name': '菜单查看'},
                            {'codename': 'add_vehicle_dispatch', 'name': '新增调度'},
                            {'codename': 'change_vehicle_dispatch', 'name': '编辑调度'},
                            {'codename': 'delete_vehicle_dispatch', 'name': '删除调度'},
                        ]
                    },
                    'vehicle_upkeep': {
                        'name': '车辆保养',
                        'permissions': [
                            {'codename': 'view_vehicle_upkeep', 'name': '菜单查看'},
                            {'codename': 'add_vehicle_upkeep', 'name': '新增保养'},
                            {'codename': 'change_vehicle_upkeep', 'name': '编辑保养'},
                            {'codename': 'delete_vehicle_upkeep', 'name': '删除保养'},
                        ]
                    },
                    'vehicle_fee': {
                        'name': '车辆费用',
                        'permissions': [
                            {'codename': 'view_vehicle_fee', 'name': '菜单查看'},
                            {'codename': 'add_vehicle_fee', 'name': '新增费用'},
                            {'codename': 'change_vehicle_fee', 'name': '编辑费用'},
                            {'codename': 'delete_vehicle_fee', 'name': '删除费用'},
                        ]
                    },
                    'vehicle_oil': {
                        'name': '车辆油耗',
                        'permissions': [
                            {'codename': 'view_vehicle_oil', 'name': '菜单查看'},
                            {'codename': 'add_vehicle_oil', 'name': '新增油耗'},
                            {'codename': 'change_vehicle_oil', 'name': '编辑油耗'},
                            {'codename': 'delete_vehicle_oil', 'name': '删除油耗'},
                        ]
                    },
                }
            },
            'meeting': {
                'name': '会议管理',
                'children': {
                    'meeting_room': {
                        'name': '会议室管理',
                        'permissions': [
                            {'codename': 'view_meeting_room', 'name': '菜单查看'},
                            {'codename': 'add_meeting_room', 'name': '新增会议室'},
                            {'codename': 'change_meeting_room', 'name': '编辑会议室'},
                            {'codename': 'delete_meeting_room', 'name': '删除会议室'},
                            {'codename': 'apply_meeting', 'name': '申请会议'},
                        ]
                    },
                    'meeting_record': {
                        'name': '会议记录',
                        'permissions': [
                            {'codename': 'view_meeting_record', 'name': '菜单查看'},
                            {'codename': 'add_meeting_minutes', 'name': '新增会议纪要'},
                            {'codename': 'change_meeting_record', 'name': '编辑记录'},
                            {'codename': 'delete_meeting_record', 'name': '删除记录'},
                        ]
                    },
                    'meeting_minutes': {
                        'name': '会议纪要',
                        'permissions': [
                            {'codename': 'view_meeting_minutes', 'name': '菜单查看'},
                            {'codename': 'add_meeting_minutes', 'name': '新增纪要'},
                            {'codename': 'change_meeting_minutes', 'name': '编辑纪要'},
                            {'codename': 'delete_meeting_minutes', 'name': '删除纪要'},
                        ]
                    },
                }
            },
            'document': {
                'name': '公文管理',
                'children': {
                    'document_draft': {
                        'name': '公文起草',
                        'permissions': [
                            {'codename': 'view_document_draft', 'name': '菜单查看'},
                            {'codename': 'add_document', 'name': '新增公文'},
                            {'codename': 'change_document', 'name': '编辑公文'},
                            {'codename': 'delete_document', 'name': '删除公文'},
                        ]
                    },
                    'document_approve': {
                        'name': '公文审核',
                        'permissions': [
                            {'codename': 'view_document_approve', 'name': '菜单查看'},
                            {'codename': 'add_document_approve', 'name': '新增审核'},
                            {'codename': 'change_document_approve', 'name': '编辑审核'},
                            {'codename': 'delete_document_approve', 'name': '删除审核'},
                        ]
                    },
                    'document_publish': {
                        'name': '公文发布',
                        'permissions': [
                            {'codename': 'view_document_publish', 'name': '菜单查看'},
                            {'codename': 'add_document_publish', 'name': '新增发布'},
                            {'codename': 'change_document_publish', 'name': '编辑发布'},
                            {'codename': 'delete_document_publish', 'name': '删除发布'},
                        ]
                    },
                    'document_view': {
                        'name': '公文查看',
                        'permissions': [
                            {'codename': 'view_document_view', 'name': '菜单查看'},
                            {'codename': 'view_document_detail', 'name': '查看详情'},
                        ]
                    },
                    'document_category': {
                        'name': '公文分类',
                        'permissions': [
                            {'codename': 'view_document_category', 'name': '菜单查看'},
                            {'codename': 'add_document_category', 'name': '新增分类'},
                            {'codename': 'change_document_category', 'name': '编辑分类'},
                            {'codename': 'delete_document_category', 'name': '删除分类'},
                        ]
                    },
                }
            },
            'seal': {
                'name': '用章管理',
                'children': {
                    'seal_management': {
                        'name': '印章管理',
                        'permissions': [
                            {'codename': 'view_seal_management', 'name': '菜单查看'},
                            {'codename': 'add_seal', 'name': '新增印章'},
                            {'codename': 'change_seal', 'name': '编辑印章'},
                            {'codename': 'delete_seal', 'name': '删除印章'},
                        ]
                    },
                    'seal_application': {
                        'name': '用章申请',
                        'permissions': [
                            {'codename': 'view_seal_application', 'name': '菜单查看'},
                            {'codename': 'add_seal_application', 'name': '新增申请'},
                            {'codename': 'change_seal_application', 'name': '编辑申请'},
                            {'codename': 'delete_seal_application', 'name': '删除申请'},
                        ]
                    },
                    'seal_record': {
                        'name': '用章记录',
                        'permissions': [
                            {'codename': 'view_seal_record', 'name': '菜单查看'},
                            {'codename': 'add_seal_record', 'name': '新增记录'},
                            {'codename': 'change_seal_record', 'name': '编辑记录'},
                            {'codename': 'delete_seal_record', 'name': '删除记录'},
                        ]
                    },
                }
            },
            'notice': {
                'name': '公告列表',
                'permissions': [
                    {'codename': 'view_notice', 'name': '菜单查看'},
                    {'codename': 'view_notice_detail', 'name': '查看公告'},
                    {'codename': 'add_notice', 'name': '新增公告'},
                    {'codename': 'change_notice', 'name': '编辑公告'},
                    {'codename': 'delete_notice', 'name': '删除公告'},
                ]
            },
            'company_news': {
                'name': '公司动态',
                'permissions': [
                    {'codename': 'view_company_news', 'name': '菜单查看'},
                    {'codename': 'view_company_news_detail', 'name': '查看动态'},
                    {'codename': 'add_company_news', 'name': '新增动态'},
                    {'codename': 'change_company_news', 'name': '编辑动态'},
                    {'codename': 'delete_company_news', 'name': '删除动态'},
                ]
            },
            'notice_type': {
                'name': '通知类型',
                'permissions': [
                    {'codename': 'view_notice_type', 'name': '菜单查看'},
                    {'codename': 'add_notice_type', 'name': '新增类型'},
                    {'codename': 'change_notice_type', 'name': '编辑类型'},
                    {'codename': 'delete_notice_type', 'name': '删除类型'},
                ]
            },
        }
    },

    # 5. 个人办公
    'personal': {
        'name': '个人办公',
        'icon': 'layui-icon-user',
        'children': {
            'schedule': {
                'name': '日程安排',
                'permissions': [
                    {'codename': 'view_schedule', 'name': '菜单查看'},
                    {'codename': 'add_schedule', 'name': '新增日程'},
                    {'codename': 'change_schedule', 'name': '编辑日程'},
                    {'codename': 'delete_schedule', 'name': '删除日程'},
                ]
            },
            'work_calendar': {
                'name': '工作日历',
                'permissions': [
                    {'codename': 'view_work_calendar', 'name': '菜单查看'},
                    {'codename': 'add_work_calendar', 'name': '新增日历'},
                    {'codename': 'change_work_calendar', 'name': '编辑日历'},
                    {'codename': 'delete_work_calendar', 'name': '删除日历'},
                ]
            },
            'report': {
                'name': '工作汇报',
                'permissions': [
                    {'codename': 'view_report', 'name': '菜单查看'},
                    {'codename': 'add_report', 'name': '新增汇报'},
                    {'codename': 'change_report', 'name': '编辑汇报'},
                    {'codename': 'delete_report', 'name': '删除汇报'},
                ]
            },
        }
    },

    # 6. 财务管理
    'finance': {
        'name': '财务管理',
        'icon': 'layui-icon-money',
        'children': {
            'reimbursement': {
                'name': '报销管理',
                'permissions': [
                    {'codename': 'view_reimbursement', 'name': '菜单查看'},
                    {'codename': 'add_reimbursement', 'name': '新增报销'},
                    {'codename': 'change_reimbursement', 'name': '编辑报销'},
                    {'codename': 'delete_reimbursement', 'name': '删除报销'},
                    {'codename': 'approve_reimbursement', 'name': '审核报销'},
                    {'codename': 'batch_approve_reimbursement', 'name': '批量审批'},
                    {'codename': 'export_reimbursement', 'name': '导出列表'},
                ]
            },
            'invoice': {
                'name': '开票管理',
                'permissions': [
                    {'codename': 'view_invoice', 'name': '菜单查看'},
                    {'codename': 'add_invoice', 'name': '新增开票'},
                    {'codename': 'change_invoice', 'name': '编辑开票'},
                    {'codename': 'delete_invoice', 'name': '删除开票'},
                    {'codename': 'view_invoice_detail', 'name': '查看开票详情'},
                    {'codename': 'export_invoice', 'name': '导出开票'},
                    {'codename': 'approve_invoice', 'name': '审核开票'},
                    {'codename': 'download_invoice', 'name': '下载发票'},
                ]
            },
            'receive_invoice': {
                'name': '收票管理',
                'permissions': [
                    {'codename': 'view_receive_invoice', 'name': '菜单查看'},
                    {'codename': 'add_receive_invoice', 'name': '新增收票'},
                    {'codename': 'change_receive_invoice', 'name': '编辑收票'},
                    {'codename': 'delete_receive_invoice', 'name': '删除收票'},
                    {'codename': 'view_receive_invoice_detail', 'name': '查看收票详情'},
                    {'codename': 'export_receive_invoice', 'name': '导出收票'},
                ]
            },
            'payment_receive': {
                'name': '回款管理',
                'permissions': [
                    {'codename': 'view_payment_receive', 'name': '菜单查看'},
                    {'codename': 'add_payment_receive', 'name': '新增回款'},
                    {'codename': 'change_payment_receive', 'name': '编辑回款'},
                    {'codename': 'delete_payment_receive', 'name': '删除回款'},
                    {'codename': 'view_payment_receive_detail', 'name': '查看回款详情'},
                    {'codename': 'export_payment_receive', 'name': '导出回款'},
                ]
            },
            'payment': {
                'name': '付款管理',
                'permissions': [
                    {'codename': 'view_payment', 'name': '菜单查看'},
                    {'codename': 'add_payment', 'name': '新增付款'},
                    {'codename': 'change_payment', 'name': '编辑付款'},
                    {'codename': 'delete_payment', 'name': '删除付款'},
                    {'codename': 'view_payment_detail', 'name': '查看付款详情'},
                    {'codename': 'export_payment', 'name': '导出付款'},
                ]
            },
            'reimbursement_type': {
                'name': '报销类型',
                'permissions': [
                    {'codename': 'view_reimbursement_type', 'name': '菜单查看'},
                    {'codename': 'add_reimbursement_type', 'name': '新增类型'},
                    {'codename': 'change_reimbursement_type', 'name': '编辑类型'},
                    {'codename': 'delete_reimbursement_type', 'name': '删除类型'},
                ]
            },
            'expense_type': {
                'name': '费用类型',
                'permissions': [
                    {'codename': 'view_expense_type', 'name': '菜单查看'},
                    {'codename': 'add_expense_type', 'name': '新增类型'},
                    {'codename': 'change_expense_type', 'name': '编辑类型'},
                    {'codename': 'delete_expense_type', 'name': '删除类型'},
                ]
            },
            'finance_statistics': {
                'name': '财务统计',
                'children': {
                    'reimbursement_record': {
                        'name': '报销记录',
                        'permissions': [
                            {'codename': 'view_reimbursement_record', 'name': '菜单查看'},
                            {'codename': 'view_reimbursement_record_detail', 'name': '查看记录'},
                        ]
                    },
                    'invoice_record': {
                        'name': '开票记录',
                        'permissions': [
                            {'codename': 'view_invoice_record', 'name': '菜单查看'},
                            {'codename': 'view_invoice_record_detail', 'name': '查看记录'},
                        ]
                    },
                    'receive_invoice_record': {
                        'name': '收票记录',
                        'permissions': [
                            {'codename': 'view_receive_invoice_record', 'name': '菜单查看'},
                            {'codename': 'view_receive_invoice_record_detail', 'name': '查看记录'},
                        ]
                    },
                    'payment_receive_record': {
                        'name': '回款记录',
                        'permissions': [
                            {'codename': 'view_payment_receive_record', 'name': '菜单查看'},
                            {'codename': 'view_payment_receive_record_detail', 'name': '查看记录'},
                        ]
                    },
                    'payment_record': {
                        'name': '付款记录',
                        'permissions': [
                            {'codename': 'view_payment_record', 'name': '菜单查看'},
                            {'codename': 'view_payment_record_detail', 'name': '查看记录'},
                        ]
                    },
                }
            },
        }
    },

    # 7. 客户管理
    'customer': {
        'name': '客户管理',
        'icon': 'layui-icon-group',
        'children': {
            'customer_list': {
                'name': '客户列表',
                'permissions': [
                    {'codename': 'view_customer', 'name': '菜单查看'},
                    {'codename': 'view_customer_detail', 'name': '查看客户详情'},
                    {'codename': 'add_customer', 'name': '新增客户'},
                    {'codename': 'change_customer', 'name': '编辑客户'},
                    {'codename': 'delete_customer', 'name': '删除客户'},
                    {'codename': 'batch_import_customer', 'name': '批量导入'},
                    {'codename': 'batch_delete_customer', 'name': '批量删除'},
                    {'codename': 'dial_customer', 'name': '拨号'},
                    {'codename': 'follow_customer', 'name': '跟进客户'},
                    {'codename': 'add_customer_order', 'name': '添加客户订单'},
                    {'codename': 'add_customer_contract', 'name': '添加客户合同'},
                    {'codename': 'add_customer_invoice', 'name': '添加客户发票'},
                    {'codename': 'add_customer_finance', 'name': '添加客户财务往来记录'},
                    {'codename': 'add_customer_project', 'name': '添加客户项目'},
                ]
            },
            'pool_list': {
                'name': '客户公海',
                'children': {
                    'public_customer': {
                        'name': '公海列表',
                        'permissions': [
                            {'codename': 'view_public_customer', 'name': '菜单查看'},
                            {'codename': 'add_public_customer', 'name': '新增公海客户'},
                            {'codename': 'claim_public_customer', 'name': '认领客户'},
                            {'codename': 'view_public_customer_detail', 'name': '公海客户详情'},
                            {'codename': 'discard_customer', 'name': '移入废弃客户'},
                        ]
                    },
                    'spider_task': {
                        'name': '爬虫任务',
                        'permissions': [
                            {'codename': 'view_spider_task', 'name': '菜单查看'},
                            {'codename': 'add_spider_task', 'name': '新增任务'},
                            {'codename': 'change_spider_task', 'name': '编辑任务'},
                            {'codename': 'delete_spider_task', 'name': '删除任务'},
                        ]
                    },
                    'ai_robot': {
                        'name': 'AI机器人',
                        'permissions': [
                            {'codename': 'view_ai_robot', 'name': '菜单查看'},
                            {'codename': 'config_ai_robot', 'name': '配置机器人'},
                        ]
                    },
                }
            },
            'abandoned_customer': {
                'name': '废弃客户',
                'permissions': [
                    {'codename': 'view_abandoned_customer', 'name': '菜单查看'},
                    {'codename': 'view_abandoned_customer_detail', 'name': '查看废弃客户'},
                    {'codename': 'restore_customer', 'name': '恢复客户'},
                ]
            },
            'customer_order': {
                'name': '客户订单',
                'permissions': [
                    {'codename': 'view_customer_order', 'name': '菜单查看'},
                    {'codename': 'view_customer_order_detail', 'name': '查看订单详情'},
                    {'codename': 'add_customer_order', 'name': '新增订单'},
                    {'codename': 'payment_customer_order', 'name': '收款订单'},
                    {'codename': 'change_customer_order', 'name': '编辑订单'},
                    {'codename': 'delete_customer_order', 'name': '删除订单'},
                ]
            },
            'follow_record': {
                'name': '跟进记录',
                'permissions': [
                    {'codename': 'view_follow_record', 'name': '菜单查看'},
                    {'codename': 'add_follow_record', 'name': '新增记录'},
                    {'codename': 'change_follow_record', 'name': '编辑记录'},
                    {'codename': 'delete_follow_record', 'name': '删除记录'},
                ]
            },
            'call_record': {
                'name': '拨号记录',
                'permissions': [
                    {'codename': 'view_call_record', 'name': '菜单查看'},
                ]
            },
            'customer_field': {
                'name': '客户字段',
                'permissions': [
                    {'codename': 'view_customer_field', 'name': '菜单查看'},
                    {'codename': 'add_customer_field', 'name': '新增字段'},
                    {'codename': 'change_customer_field', 'name': '编辑字段'},
                    {'codename': 'delete_customer_field', 'name': '删除字段'},
                ]
            },
            'customer_source': {
                'name': '客户来源',
                'permissions': [
                    {'codename': 'view_customer_source', 'name': '菜单查看'},
                    {'codename': 'add_customer_source', 'name': '新增来源'},
                    {'codename': 'change_customer_source', 'name': '编辑来源'},
                    {'codename': 'delete_customer_source', 'name': '删除来源'},
                ]
            },
            'customer_grade': {
                'name': '客户等级',
                'permissions': [
                    {'codename': 'view_customer_grade', 'name': '菜单查看'},
                    {'codename': 'add_customer_grade', 'name': '新增等级'},
                    {'codename': 'change_customer_grade', 'name': '编辑等级'},
                    {'codename': 'delete_customer_grade', 'name': '删除等级'},
                ]
            },
            'customer_intent': {
                'name': '客户意向',
                'permissions': [
                    {'codename': 'view_customer_intent', 'name': '菜单查看'},
                    {'codename': 'add_customer_intent', 'name': '新增意向'},
                    {'codename': 'change_customer_intent', 'name': '编辑意向'},
                    {'codename': 'delete_customer_intent', 'name': '删除意向'},
                ]
            },
            'follow_field': {
                'name': '跟进字段',
                'permissions': [
                    {'codename': 'view_follow_field', 'name': '菜单查看'},
                    {'codename': 'add_follow_field', 'name': '新增字段'},
                    {'codename': 'change_follow_field', 'name': '编辑字段'},
                    {'codename': 'delete_follow_field', 'name': '删除字段'},
                ]
            },
            'order_field': {
                'name': '订单字段',
                'permissions': [
                    {'codename': 'view_order_field', 'name': '菜单查看'},
                    {'codename': 'add_order_field', 'name': '新增字段'},
                    {'codename': 'change_order_field', 'name': '编辑字段'},
                    {'codename': 'delete_order_field', 'name': '删除字段'},
                ]
            },
        }
    },

    # 8. 合同管理
    'contract': {
        'name': '合同管理',
        'icon': 'layui-icon-template-1',
        'children': {
            'contract_list': {
                'name': '合同列表',
                'permissions': [
                    {'codename': 'view_contract', 'name': '菜单查看'},
                    {'codename': 'view_contract_detail', 'name': '查看合同'},
                    {'codename': 'add_contract', 'name': '新增合同'},
                    {'codename': 'change_contract', 'name': '编辑合同'},
                    {'codename': 'delete_contract', 'name': '删除合同'},
                    {'codename': 'approve_contract', 'name': '审核合同'},
                ]
            },
            'contract_template': {
                'name': '合同模板',
                'permissions': [
                    {'codename': 'view_contract_template', 'name': '菜单查看'},
                    {'codename': 'add_contract_template', 'name': '新增模板'},
                    {'codename': 'change_contract_template', 'name': '编辑模板'},
                    {'codename': 'delete_contract_template', 'name': '删除模板'},
                    {'codename': 'approve_contract_template', 'name': '审核模板'},
                ]
            },
            'contract_archive': {
                'name': '合同归档',
                'permissions': [
                    {'codename': 'view_contract_archive', 'name': '菜单查看'},
                    {'codename': 'archive_contract', 'name': '归档合同'},
                ]
            },
            'contract_category': {
                'name': '合同分类',
                'permissions': [
                    {'codename': 'view_contract_category', 'name': '菜单查看'},
                    {'codename': 'add_contract_category', 'name': '新增分类'},
                    {'codename': 'change_contract_category', 'name': '编辑分类'},
                    {'codename': 'delete_contract_category', 'name': '删除分类'},
                ]
            },
            'product': {
                'name': '产品管理',
                'permissions': [
                    {'codename': 'view_product', 'name': '菜单查看'},
                    {'codename': 'add_product', 'name': '新增产品'},
                    {'codename': 'change_product', 'name': '编辑产品'},
                    {'codename': 'delete_product', 'name': '删除产品'},
                ]
            },
            'service': {
                'name': '服务管理',
                'permissions': [
                    {'codename': 'view_service', 'name': '菜单查看'},
                    {'codename': 'add_service', 'name': '新增服务'},
                    {'codename': 'change_service', 'name': '编辑服务'},
                    {'codename': 'delete_service', 'name': '删除服务'},
                ]
            },
            'supplier': {
                'name': '供应商管理',
                'permissions': [
                    {'codename': 'view_supplier', 'name': '菜单查看'},
                    {'codename': 'add_supplier', 'name': '新增供应商'},
                    {'codename': 'change_supplier', 'name': '编辑供应商'},
                    {'codename': 'delete_supplier', 'name': '删除供应商'},
                ]
            },
            'purchase_category': {
                'name': '采购分类',
                'permissions': [
                    {'codename': 'view_purchase_category', 'name': '菜单查看'},
                    {'codename': 'add_purchase_category', 'name': '新增分类'},
                    {'codename': 'change_purchase_category', 'name': '编辑分类'},
                    {'codename': 'delete_purchase_category', 'name': '删除分类'},
                ]
            },
            'purchase_item': {
                'name': '采购项目',
                'permissions': [
                    {'codename': 'view_purchase_item', 'name': '菜单查看'},
                    {'codename': 'add_purchase_item', 'name': '新增项目'},
                    {'codename': 'change_purchase_item', 'name': '编辑项目'},
                    {'codename': 'delete_purchase_item', 'name': '删除项目'},
                ]
            },
        }
    },

    # 9. 项目管理
    'project': {
        'name': '项目管理',
        'icon': 'layui-icon-project',
        'children': {
            'project_list': {
                'name': '项目列表',
                'permissions': [
                    {'codename': 'view_project', 'name': '菜单查看'},
                    {'codename': 'view_project_detail', 'name': '查看项目'},
                    {'codename': 'add_project', 'name': '新增项目'},
                    {'codename': 'change_project', 'name': '编辑项目'},
                    {'codename': 'delete_project', 'name': '删除项目'},
                    {'codename': 'add_project_task', 'name': '新增项目任务'},
                    {'codename': 'add_project_document', 'name': '新增项目文档'},
                ]
            },
            'project_category': {
                'name': '项目分类',
                'permissions': [
                    {'codename': 'view_project_category', 'name': '菜单查看'},
                    {'codename': 'add_project_category', 'name': '新增分类'},
                    {'codename': 'change_project_category', 'name': '编辑分类'},
                    {'codename': 'delete_project_category', 'name': '删除分类'},
                ]
            },
            'task_list': {
                'name': '任务列表',
                'permissions': [
                    {'codename': 'view_task', 'name': '菜单查看'},
                    {'codename': 'add_task', 'name': '新增任务'},
                    {'codename': 'change_task', 'name': '编辑任务'},
                    {'codename': 'delete_task', 'name': '删除任务'},
                ]
            },
            'workhour': {
                'name': '工时管理',
                'permissions': [
                    {'codename': 'view_workhour', 'name': '菜单查看'},
                    {'codename': 'add_workhour', 'name': '新增工时'},
                    {'codename': 'change_workhour', 'name': '编辑工时'},
                    {'codename': 'delete_workhour', 'name': '删除工时'},
                ]
            },
            'project_document': {
                'name': '文档列表',
                'permissions': [
                    {'codename': 'view_project_document', 'name': '菜单查看'},
                    {'codename': 'add_project_document', 'name': '新增文档'},
                    {'codename': 'change_project_document', 'name': '编辑文档'},
                    {'codename': 'delete_project_document', 'name': '删除文档'},
                ]
            },
            'risk_prediction': {
                'name': '风险预测',
                'permissions': [
                    {'codename': 'view_risk_prediction', 'name': '菜单查看'},
                    {'codename': 'add_risk_prediction', 'name': '新增风险'},
                    {'codename': 'change_risk_prediction', 'name': '编辑风险'},
                    {'codename': 'delete_risk_prediction', 'name': '删除风险'},
                ]
            },
            'progress_analysis': {
                'name': '进度分析',
                'permissions': [
                    {'codename': 'view_progress_analysis', 'name': '菜单查看'},
                    {'codename': 'add_progress_analysis', 'name': '新增分析'},
                    {'codename': 'change_progress_analysis', 'name': '编辑分析'},
                    {'codename': 'delete_progress_analysis', 'name': '删除分析'},
                ]
            },
            'project_stage': {
                'name': '项目阶段',
                'permissions': [
                    {'codename': 'view_project_stage', 'name': '菜单查看'},
                    {'codename': 'add_project_stage', 'name': '新增阶段'},
                    {'codename': 'change_project_stage', 'name': '编辑阶段'},
                    {'codename': 'delete_project_stage', 'name': '删除阶段'},
                ]
            },
            'work_type': {
                'name': '工作类型',
                'permissions': [
                    {'codename': 'view_work_type', 'name': '菜单查看'},
                    {'codename': 'add_work_type', 'name': '新增类型'},
                    {'codename': 'change_work_type', 'name': '编辑类型'},
                    {'codename': 'delete_work_type', 'name': '删除类型'},
                ]
            },
        }
    },

    # 10. 生产管理
    'production': {
        'name': '生产管理',
        'icon': 'layui-icon-engine',
        'children': {
            'baseinfo': {
                'name': '基础信息',
                'children': {
                    'procedure': {
                        'name': '基本工序',
                        'permissions': [
                            {'codename': 'view_procedure', 'name': '菜单查看'},
                            {'codename': 'add_procedure', 'name': '新增工序'},
                            {'codename': 'change_procedure', 'name': '编辑工序'},
                            {'codename': 'delete_procedure', 'name': '删除工序'},
                        ]
                    },
                    'procedureset': {
                        'name': '工序集',
                        'permissions': [
                            {'codename': 'view_procedureset', 'name': '菜单查看'},
                            {'codename': 'add_procedureset', 'name': '新增工序集'},
                            {'codename': 'change_procedureset', 'name': '编辑工序集'},
                            {'codename': 'delete_procedureset', 'name': '删除工序集'},
                        ]
                    },
                    'bom': {
                        'name': 'BOM管理',
                        'permissions': [
                            {'codename': 'view_bom', 'name': '菜单查看'},
                            {'codename': 'add_bom', 'name': '新增BOM'},
                            {'codename': 'change_bom', 'name': '编辑BOM'},
                            {'codename': 'delete_bom', 'name': '删除BOM'},
                        ]
                    },
                    'equipment': {
                        'name': '设备管理',
                        'permissions': [
                            {'codename': 'view_equipment', 'name': '菜单查看'},
                            {'codename': 'add_equipment', 'name': '新增设备'},
                            {'codename': 'change_equipment', 'name': '编辑设备'},
                            {'codename': 'delete_equipment', 'name': '删除设备'},
                        ]
                    },
                    'datacollection': {
                        'name': '数据采集',
                        'permissions': [
                            {'codename': 'view_datacollection', 'name': '菜单查看'},
                            {'codename': 'add_datacollection', 'name': '新增采集'},
                            {'codename': 'change_datacollection', 'name': '编辑采集'},
                            {'codename': 'delete_datacollection', 'name': '删除采集'},
                        ]
                    },
                    'performance_analysis': {
                        'name': '性能分析',
                        'permissions': [
                            {'codename': 'view_performance_analysis', 'name': '菜单查看'},
                            {'codename': 'add_performance_analysis', 'name': '新增分析'},
                            {'codename': 'change_performance_analysis', 'name': '编辑分析'},
                            {'codename': 'delete_performance_analysis', 'name': '删除分析'},
                        ]
                    },
                    'sop': {
                        'name': 'SOP管理',
                        'permissions': [
                            {'codename': 'view_sop', 'name': '菜单查看'},
                            {'codename': 'add_sop', 'name': '新增SOP'},
                            {'codename': 'change_sop', 'name': '编辑SOP'},
                            {'codename': 'delete_sop', 'name': '删除SOP'},
                        ]
                    },
                    'production_product': {
                        'name': '产品管理',
                        'permissions': [
                            {'codename': 'view_production_product', 'name': '菜单查看'},
                            {'codename': 'add_production_product', 'name': '新增产品'},
                            {'codename': 'change_production_product', 'name': '编辑产品'},
                            {'codename': 'delete_production_product', 'name': '删除产品'},
                        ]
                    },
                    'process': {
                        'name': '工艺路线',
                        'permissions': [
                            {'codename': 'view_process', 'name': '菜单查看'},
                            {'codename': 'add_process', 'name': '新增路线'},
                            {'codename': 'change_process', 'name': '编辑路线'},
                            {'codename': 'delete_process', 'name': '删除路线'},
                        ]
                    },
                }
            },
            'production_task': {
                'name': '生产任务',
                'children': {
                    'production_plan': {
                        'name': '生产计划',
                        'permissions': [
                            {'codename': 'view_production_plan', 'name': '菜单查看'},
                            {'codename': 'add_production_plan', 'name': '新增计划'},
                            {'codename': 'change_production_plan', 'name': '编辑计划'},
                            {'codename': 'delete_production_plan', 'name': '删除计划'},
                        ]
                    },
                    'production_task': {
                        'name': '生产任务',
                        'permissions': [
                            {'codename': 'view_production_task', 'name': '菜单查看'},
                            {'codename': 'add_production_task', 'name': '新增任务'},
                            {'codename': 'change_production_task', 'name': '编辑任务'},
                            {'codename': 'delete_production_task', 'name': '删除任务'},
                        ]
                    },
                    'resource_dispatch': {
                        'name': '资源调度',
                        'permissions': [
                            {'codename': 'view_resource_dispatch', 'name': '菜单查看'},
                            {'codename': 'add_resource_dispatch', 'name': '新增调度'},
                            {'codename': 'change_resource_dispatch', 'name': '编辑调度'},
                            {'codename': 'delete_resource_dispatch', 'name': '删除调度'},
                        ]
                    },
                    'quality_check': {
                        'name': '质量管理',
                        'permissions': [
                            {'codename': 'view_quality_check', 'name': '菜单查看'},
                            {'codename': 'add_quality_check', 'name': '新增质量'},
                            {'codename': 'change_quality_check', 'name': '编辑质量'},
                            {'codename': 'delete_quality_check', 'name': '删除质量'},
                        ]
                    },
                    'equipment_monitor': {
                        'name': '设备监控',
                        'permissions': [
                            {'codename': 'view_equipment_monitor', 'name': '菜单查看'},
                            {'codename': 'add_equipment_monitor', 'name': '新增监控'},
                            {'codename': 'change_equipment_monitor', 'name': '编辑监控'},
                            {'codename': 'delete_equipment_monitor', 'name': '删除监控'},
                        ]
                    },
                }
            },
        }
    },

    # 11. AI智能中心
    'ai': {
        'name': 'AI智能中心',
        'icon': 'layui-icon-app',
        'children': {
            'knowledge_base': {
                'name': '知识库管理',
                'permissions': [
                    {'codename': 'view_knowledge_base', 'name': '菜单查看'},
                    {'codename': 'add_knowledge_base', 'name': '新增知识库'},
                    {'codename': 'change_knowledge_base', 'name': '编辑知识库'},
                    {'codename': 'delete_knowledge_base', 'name': '删除知识库'},
                ]
            },
            'model_config': {
                'name': 'AI模型配置',
                'permissions': [
                    {'codename': 'view_model_config', 'name': '菜单查看'},
                    {'codename': 'add_model_config', 'name': '新增模型'},
                    {'codename': 'change_model_config', 'name': '编辑模型'},
                    {'codename': 'delete_model_config', 'name': '删除模型'},
                ]
            },
            'task_management': {
                'name': 'AI任务管理',
                'permissions': [
                    {'codename': 'view_ai_task', 'name': '菜单查看'},
                    {'codename': 'view_ai_task_detail', 'name': '查看任务'},
                ]
            },
            'workflow': {
                'name': 'AI工作流',
                'permissions': [
                    {'codename': 'view_ai_workflow', 'name': '菜单查看'},
                    {'codename': 'add_ai_workflow', 'name': '新增工作流'},
                    {'codename': 'change_ai_workflow', 'name': '编辑工作流'},
                    {'codename': 'delete_ai_workflow', 'name': '删除工作流'},
                ]
            },
        }
    },

    # 12. 企业网盘
    'disk': {
        'name': '企业网盘',
        'icon': 'layui-icon-cloud',
        'children': {
            'disk_index': {
                'name': '网盘首页',
                'permissions': [
                    {'codename': 'view_disk', 'name': '菜单查看'},
                    {'codename': 'view_disk_file', 'name': '查看文件'},
                    {'codename': 'add_disk_file', 'name': '新增文件'},
                    {'codename': 'change_disk_file', 'name': '编辑文件'},
                    {'codename': 'delete_disk_file', 'name': '删除文件'},
                ]
            },
            'personal_file': {
                'name': '个人文件',
                'permissions': [
                    {'codename': 'view_personal_file', 'name': '菜单查看'},
                    {'codename': 'add_personal_file', 'name': '新增文件'},
                    {'codename': 'change_personal_file', 'name': '编辑文件'},
                    {'codename': 'delete_personal_file', 'name': '删除文件'},
                ]
            },
            'shared_file': {
                'name': '共享文件',
                'permissions': [
                    {'codename': 'view_shared_file', 'name': '菜单查看'},
                    {'codename': 'add_shared_file', 'name': '新增文件'},
                    {'codename': 'change_shared_file', 'name': '编辑文件'},
                    {'codename': 'delete_shared_file', 'name': '删除文件'},
                ]
            },
            'starred_file': {
                'name': '收藏文件',
                'permissions': [
                    {'codename': 'view_starred_file', 'name': '菜单查看'},
                    {'codename': 'add_starred_file', 'name': '新增文件'},
                    {'codename': 'change_starred_file', 'name': '编辑文件'},
                    {'codename': 'delete_starred_file', 'name': '删除文件'},
                ]
            },
            'share_management': {
                'name': '分享管理',
                'permissions': [
                    {'codename': 'view_share', 'name': '菜单查看'},
                    {'codename': 'add_share', 'name': '新增分享'},
                    {'codename': 'change_share', 'name': '编辑分享'},
                    {'codename': 'delete_share', 'name': '删除分享'},
                ]
            },
            'recycle': {
                'name': '回收站',
                'permissions': [
                    {'codename': 'view_recycle', 'name': '菜单查看'},
                    {'codename': 'view_recycle_list', 'name': '查看回收站'},
                    {'codename': 'clear_recycle', 'name': '清空回收站'},
                ]
            },
        }
    },
}


def get_all_permission_codenames():
    """获取所有权限节点的codename列表"""
    codenames = []
    for module_key, module_config in PERMISSION_NODES.items():
        if 'permissions' in module_config:
            for perm in module_config['permissions']:
                if perm.get('codename'):
                    codenames.append(perm['codename'])
        
        if 'children' in module_config:
            for child_key, child_config in module_config['children'].items():
                codenames.append(f'view_{child_key}')
                
                if 'permissions' in child_config:
                    for perm in child_config['permissions']:
                        if perm.get('codename'):
                            codenames.append(perm['codename'])
                
                if 'children' in child_config:
                    for sub_key, sub_config in child_config['children'].items():
                        codenames.append(f'view_{sub_key}')
                        
                        if 'permissions' in sub_config:
                            for perm in sub_config['permissions']:
                                if perm.get('codename'):
                                    codenames.append(perm['codename'])
    
    return codenames


def get_permission_name(codename):
    """根据codename获取权限名称"""
    for module_key, module_config in PERMISSION_NODES.items():
        if 'permissions' in module_config:
            for perm in module_config['permissions']:
                if perm.get('codename') == codename:
                    return perm.get('name', codename)
        
        if 'children' in module_config:
            for child_key, child_config in module_config['children'].items():
                if f'view_{child_key}' == codename:
                    return '菜单查看'
                
                if 'permissions' in child_config:
                    for perm in child_config['permissions']:
                        if perm.get('codename') == codename:
                            return perm.get('name', codename)
                
                if 'children' in child_config:
                    for sub_key, sub_config in child_config['children'].items():
                        if f'view_{sub_key}' == codename:
                            return '菜单查看'
                        
                        if 'permissions' in sub_config:
                            for perm in sub_config['permissions']:
                                if perm.get('codename') == codename:
                                    return perm.get('name', codename)
    
    return codename


def build_permission_tree():
    """构建权限树结构用于前端显示"""
    tree = []
    
    for module_key, module_config in PERMISSION_NODES.items():
        module_node = {
            'key': module_key,
            'title': module_config.get('name', module_key),
            'icon': module_config.get('icon', ''),
            'children': [],
            'type': 'module'
        }
        
        if 'children' in module_config:
            for child_key, child_config in module_config['children'].items():
                child_node = {
                    'key': child_key,
                    'title': child_config.get('name', child_key),
                    'children': [],
                    'type': 'menu'
                }
                
                if 'children' in child_config:
                    for sub_key, sub_config in child_config['children'].items():
                        sub_node = {
                            'key': sub_key,
                            'title': sub_config.get('name', sub_key),
                            'permissions': sub_config.get('permissions', []),
                            'type': 'submenu'
                        }
                        child_node['children'].append(sub_node)
                else:
                    child_node['permissions'] = child_config.get('permissions', [])
                
                module_node['children'].append(child_node)
        else:
            module_node['permissions'] = module_config.get('permissions', [])
        
        tree.append(module_node)
    
    return tree
