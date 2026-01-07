"""
权限管理工具模块
提供统一的权限处理、分组和显示逻辑
"""
from django.contrib.auth.models import Permission
from typing import Dict, List, Any


class PermissionManager:
    """权限管理器，提供权限分组和处理功能"""
    
    # 菜单分组映射表
    MENU_GROUP_MAP = {
        'dashboard': '工作台',
        'adminlog': '工作台',
        'systemlog': '工作台',
        'log': '工作台',
        
        'system': '系统管理',
        'user': '系统管理',
        'auth': '系统管理',
        'contenttypes': '系统管理',
        'sessions': '系统管理',
        'sites': '系统管理',
        'menu': '系统管理',
        'config': '系统管理',
        'module': '系统管理',
        'permission': '系统管理',
        'group': '系统管理',
        
        'department': '人事管理',
        'position': '人事管理',
        'employee': '人事管理',
        'staffing': '人事管理',
        'reward': '人事管理',
        'punishment': '人事管理',
        
        'oa': '行政办公',
        'assets': '行政办公',
        'asset': '行政办公',
        'vehicle': '行政办公',
        'meeting': '行政办公',
        'document': '行政办公',
        'seal': '行政办公',
        'notice': '行政办公',
        
        'personal': '个人办公',
        'schedule': '个人办公',
        'report': '个人办公',
        
        'finance': '财务管理',
        'reimbursement': '财务管理',
        'invoice': '财务管理',
        'payable': '财务管理',
        'receivable': '财务管理',
        'expense': '财务管理',
        
        'customer': '客户管理',
        'client': '客户管理',
        'followup': '客户管理',
        'callrecord': '客户管理',
        'order': '客户管理',
        'source': '客户管理',
        
        'contract': '合同管理',
        'salescontract': '合同管理',
        'purchasecontract': '合同管理',
        'contracttemplate': '合同管理',
        'supplier': '合同管理',
        'product': '合同管理',
        
        'project': '项目管理',
        'task': '项目管理',
        'work': '项目管理',
        'time': '项目管理',
        'document': '项目管理',
        'category': '项目管理',
        
        'production': '生产管理',
        'baseinfo': '生产管理',
        'procedure': '生产管理',
        'bom': '生产管理',
        'equipment': '生产管理',
        
        'ai': 'AI智能中心',
        'knowledgebase': 'AI智能中心',
        'workflow': 'AI智能中心',
        'config': 'AI智能中心',
        
        'disk': '企业网盘',
        'file': '企业网盘',
        'folder': '企业网盘',
        'share': '企业网盘',
        'attachment': '企业网盘'
    }
    
    # 模型名称映射表
    MODEL_NAME_MAP = {
        'user': '用户',
        'usernew': '用户',
        'group': '角色',
        'permission': '权限',
        'department': '部门',
        'departmentgroup': '部门角色',
        'menu': '菜单',
        'config': '配置',
        'systemconfig': '系统配置',
        'module': '模块',
        'log': '日志',
        'adminlog': '操作日志',
        'systemlog': '系统日志',
        'systemoperationlog': '系统操作日志',
        'button': '按钮',
        'attachment': '附件',
        'systemattachment': '系统附件',
        'groupmenu': '角色菜单',
        'menupermission': '菜单权限',
        'rolemenupremission': '角色菜单权限',
        'pagepermission': '页面权限',
        'rolepagepremission': '角色页面权限',
        'buttonpermission': '按钮权限',
        'rolebuttonpermission': '角色按钮权限',
        'systemconfiguration': '系统配置',
        'systemmodule': '系统模块',
        'systemnode': '系统节点',
        'systembackup': '系统备份',
        'backuppolicy': '备份策略',
        'systemtask': '系统任务',
        'authgroup': '权限组',
        'authgrouppermissions': '权限组权限',
        'authpermission': '权限',
        'admin': '管理员',
        'contenttype': '内容类型',
        'session': '会话',
        'nodeexecution': '节点执行',
        'qualitycheck': '质量检查',
        'rewardpunishmenttype': '奖惩类型',
        'income': '收入',
        'payment': '付款',
        'followrecord': '跟进记录',
        'followrecordcustomfieldvalue': '跟进记录自定义字段值',
        'car': '车辆',
        'caretype': '关怀类型',
        'carefeetype': '关怀费用类型',
        'duty': '职责',
        'enterprise': '企业',
        'followfield': '跟进字段',
        'joblevel': '职位级别',
        'region': '地区',
        'capability': '能力',
        'capabilityscore': '能力评分',
        'cooperation': '合作',
        'cooperationcontract': '合作合同',
        'cooperationcustomer': '合作客户',
        'company': '公司',
        'mimucate': 'Mimu分类',
        'mimuflow': 'Mimu流程',
        'mimuflowcate': 'Mimu流程分类',
        'mimuflowrecord': 'Mimu流程记录',
        'mimuflowstep': 'Mimu流程步骤',
        'mimuvoice': 'Mimu语音',
        'mimuadminprofiles': 'Mimu管理员资料',
        'mimulaborcontract': 'Mimu劳动合同',
        'mimumeetingroom': 'Mimu会议室',
        'mimposition': 'Mimu职位',
        'mimuproject': 'Mimu项目',
        'mimuprojectcate': 'Mimu项目分类',
        'mimuprojectstep': 'Mimu项目步骤',
        'mimurewards': 'Mimu奖励',
        'mimurewardscate': 'Mimu奖励分类',
        'optimizecapability': '优化能力',
        'optimizecooperation': '优化合作',
        'optimizecooperationcontract': '优化合作合同',
        'optimizecooperationcustomer': '优化合作客户',
        'optimizecompany': '优化公司',
        'assets': '资产',
        'asset': '资产',
        'admasset': '资产',
        'admassetrepair': '资产维修',
        'assetcategory': '资产分类',
        'assetbrand': '资产品牌',
        'assetrepair': '资产维修',
        'basedataassetbrand': '基础数据资产品牌',
        'basedataassetcategory': '基础数据资产分类',
        'basedataassetunit': '基础数据资产单位',
        'vehicle': '车辆',
        'admvehicle': '车辆',
        'vehiclemaintenance': '车辆维修',
        'admvehiclemaintenance': '车辆维修',
        'vehiclefee': '车辆费用',
        'admvehiclefee': '车辆费用',
        'vehicleoil': '车辆油耗',
        'admvehicleoil': '车辆油耗',
        'meeting': '会议',
        'meetingroom': '会议室',
        'admmeetingroom': '会议室',
        'meetingminutes': '会议纪要',
        'meetingregistration': '会议登记',
        'meetingreservation': '会议预约',
        'admmeetingreservation': '会议预约',
        'document': '公文',
        'admdocument': '公文',
        'documentcategory': '公文分类',
        'admdocumentcategory': '公文分类',
        'documenttag': '公文标签',
        'documenttagcategory': '公文标签分类',
        'documentreview': '公文审核',
        'admdocumentreview': '公文审核',
        'documentread': '公文已读',
        'admdocumentread': '公文已读',
        'documenttargetdepartment': '公文目标部门',
        'documenttargetuser': '公文目标用户',
        'seal': '印章',
        'admseal': '印章',
        'sealapplication': '用章申请',
        'admsealapplication': '用章申请',
        'notice': '公告',
        'admnotice': '公告',
        'noticeread': '公告已读',
        'admnoticeread': '公告已读',
        'noticetargetdepartment': '公告目标部门',
        'noticetargetuser': '公告目标用户',
        'adminoffice': '行政办公',
        'employee': '员工',
        'employeefile': '员工档案',
        'admemployeefile': '员工档案',
        'employeetransfer': '员工调动',
        'admemployeetransfer': '员工调动',
        'employeedimission': '员工离职',
        'admemployeedimission': '员工离职',
        'rewardpunishment': '奖惩记录',
        'admrewardpunishment': '奖惩记录',
        'employeecare': '员工关怀',
        'admemployeecare': '员工关怀',
        'employeecontract': '员工合同',
        'admemployeecontract': '员工合同',
        'position': '职位',
        'staffing': '人员编制',
        'reward': '奖励',
        'punishment': '惩罚',
        'personal': '个人办公',
        'schedule': '日程',
        'report': '工作汇报',
        'finance': '财务',
        'reimbursement': '报销',
        'invoice': '发票',
        'payable': '付款',
        'receivable': '回款',
        'expense': '费用类型',
        'reimbursementtype': '报销类型',
        'basedataexpensetype': '基础数据费用类型',
        'basedatareimbursementtype': '基础数据报销类型',
        'customer': '客户',
        'client': '客户',
        'followup': '跟进记录',
        'callrecord': '拨号记录',
        'order': '客户订单',
        'source': '客户来源',
        'grade': '客户等级',
        'intent': '客户意向',
        'customerfield': '客户字段',
        'customercontract': '客户合同',
        'customercustomfieldvalue': '客户自定义字段值',
        'customergrade': '客户等级',
        'customerintent': '客户意向',
        'customerinvoice': '客户发票',
        'customerorder': '客户订单',
        'customerordercustomfieldvalue': '客户订单自定义字段值',
        'customersource': '客户来源',
        'followfield': '跟进字段',
        'followrecord': '跟进记录',
        'followrecordcustomfieldvalue': '跟进记录自定义字段值',
        'callrecord': '通话记录',
        'contact': '联系人',
        'contract': '合同',
        'salescontract': '销售合同',
        'purchasecontract': '采购合同',
        'contracttemplate': '合同模板',
        'contractcategory': '合同分类',
        'contractcate': '合同分类',
        'productcate': '产品分类',
        'purchasecategory': '采购分类',
        'purchaseitem': '采购项',
        'services': '服务',
        'projectcategory': '项目分类',
        'projectstage': '项目阶段',
        'projectdocument': '项目文档',
        'worktype': '工作类型',
        'workhour': '工时',
        'workrecord': '工作记录',
        'workreport': '工作汇报',
        'production': '生产',
        'baseinfo': '基础信息',
        'procedure': '工序',
        'procedureset': '工序集',
        'proceduresetitem': '工序集项',
        'productiondatapoint': '生产数据点',
        'productionplan': '生产计划',
        'productionprocedure': '生产工序',
        'productiontask': '生产任务',
        'qualitycheck': '质量检查',
        'sop': '标准作业程序',
        'diskfile': '网盘文件',
        'diskfolder': '网盘文件夹',
        'diskoperation': '网盘操作',
        'diskshare': '网盘共享',
        'approvalflow': '审批流程',
        'approvalstep': '审批步骤',
        'approvaltype': '审批类型',
        'approvalrecord': '审批记录',
        'approvalrequest': '审批申请',
        'caretype': '关怀类型',
        'duty': '职责',
        'joblevel': '职位级别',
        'carfeetype': '车辆费用类型',
        'noticetype': '公告类型',
        'rewardpunishmenttype': '奖惩类型',
        'datacollection': '数据采集',
        'datacollectionrecord': '数据采集记录',
        'datacollectiontask': '数据采集任务',
        'datamapping': '数据映射',
        'datasource': '数据源',
        'userloginlog': '用户登录日志',
        'usernew': '新用户',
        'announcement': '公告',
        'announcementreadrecord': '公告阅读记录',
        'meetingminutes': '会议纪要',
        'meetingrecord': '会议记录',
        'meetingrecordattendee': '会议记录参与者',
        'meetingrecordparticipant': '会议记录参与者',
        'meetingrecordshareduser': '会议记录共享用户',
        'messagereadrecord': '消息阅读记录',
        'noticetargetdepartment': '通知目标部门',
        'noticetargetuser': '通知目标用户',
        'noticetype': '通知类型',
        'orderfield': '订单字段',
        'orderfinancerecord': '订单财务记录',
        'positionnew': '新职位',
        'departmentnew': '新部门',
        'captchastore': '验证码存储',
        'workcate': '工作分类',
        'ai': 'AI',
        'knowledge': '知识',
        'base': '基础',
        'workflow': '工作流',
        'disk': '网盘',
        'file': '文件',
        'folder': '文件夹',
        'share': '共享',
        'attachment': '附件',
        'approval': '审批',
        'message': '消息',
        'data': '数据',
        'contenttype': '内容类型',
        'session': '会话',
        'site': '站点',
        'node': '节点',
        'backup': '备份',
        'policy': '策略',
        'step': '步骤',
        'record': '记录',
        'field': '字段',
        'value': '值',
        'login': '登录',
        'profile': '资料',
        'contract': '合同',
        'labor': '劳动',
        'meeting': '会议',
        'position': '职位',
        'reward': '奖励',
        'punishment': '惩罚',
        'type': '类型',
        'category': '分类',
        'item': '项',
        'vector': '向量',
        'config': '配置',
        'model': '模型',
        'trigger': '触发器',
        'rule': '规则',
        'analysis': '分析',
        'feedback': '反馈',
        'intent': '意图',
        'strategy': '策略',
        'test': '测试',
        'variant': '变体',
        'result': '结果',
        'flow': '流程',
        'node': '节点',
        'connection': '连接',
        'chat': '聊天',
        'history': '历史',
        'admin': '管理员',
        'optimize': '优化',
        'company': '公司',
        'enterprise': '企业',
        'aiactiontrigger': 'AI自动行动触发器',
        'aibatchtest': 'AI批量测试',
        'aibatchtestresult': 'AI批量测试结果',
        'aibatchtestvariant': 'AI批量测试变体',
        'aichat': 'AI聊天',
        'aichatmessage': 'AI聊天消息',
        'aicompliancerule': 'AI合规规则',
        'aiemotionanalysis': 'AI情感分析',
        'aifeedback': 'AI反馈',
        'aiintentrecognition': 'AI意图识别',
        'aiknowledgebase': 'AI知识库',
        'aiknowledgeitem': 'AI知识项',
        'aiknowledgevector': 'AI知识向量',
        'ailog': 'AI日志',
        'aimodelconfig': 'AI模型配置',
        'aisalesstrategy': 'AI销售策略',
        'aiworkflow': 'AI工作流',
        'aiworkflowexecution': 'AI工作流执行',
        'workflowconnection': '工作流连接',
        'workflownode': '工作流节点',
        'admasset': '行政资产',
        'admassetrepair': '资产维修',
        'admborrow': '借用',
        'admreturn': '归还',
        'admscrap': '报废',
        'admassetcategory': '资产分类',
        'admassetbrand': '资产品牌',
        'admassetunit': '资产单位',
        'admvehicle': '行政车辆',
        'admvehiclemaintenance': '车辆维修',
        'admvehiclefee': '车辆费用',
        'admvehicleoil': '车辆油耗',
        'admmeeting': '会议',
        'admmeetingroom': '会议室',
        'admmeetingreservation': '会议预约',
        'admdocument': '公文',
        'admdocumentcategory': '公文分类',
        'admdocumenttag': '公文标签',
        'admdocumentreview': '公文审核',
        'admdocumentread': '公文已读',
        'admdocumenttargetdepartment': '公文目标部门',
        'admdocumenttargetuser': '公文目标用户',
        'admseal': '印章',
        'admsealapplication': '印章申请',
        'admnotice': '公告',
        'admemployeefile': '员工档案',
        'admemployeetransfer': '员工调动',
        'admemployeedimission': '员工离职',
        'admemployeecare': '员工关怀',
        'admemployeecontract': '员工合同',
        'admrewardpunishmenttype': '奖惩类型',
        'admposition': '职位',
        'admstaffing': '人员编制',
        'personalschedule': '个人日程',
        'personalreport': '工作汇报',
        'personalcontact': '个人联系人',
        'personalnote': '个人笔记',
        'personaltask': '个人任务',
        'expensetype': '费用类型',
        'reimbursementtype': '报销类型',
        'income': '收入',
        'payment': '付款',
        'customerfield': '客户字段',
        'customercontract': '客户合同',
        'customercustomfieldvalue': '客户自定义字段值',
        'customergrade': '客户等级',
        'customerintent': '客户意向',
        'customerinvoice': '客户发票',
        'customerorder': '客户订单',
        'customerordercustomfieldvalue': '客户订单自定义字段值',
        'customersource': '客户来源',
        'followfield': '跟进字段',
        'followrecord': '跟进记录',
        'followrecordcustomfieldvalue': '跟进记录自定义字段值',
        'callrecord': '通话记录',
        'contact': '联系人',
        'contractcategory': '合同分类',
        'contractcate': '合同分类',
        'productcate': '产品分类',
        'purchasecategory': '采购分类',
        'purchaseitem': '采购项',
        'services': '服务',
        'projectcategory': '项目分类',
        'projectstage': '项目阶段',
        'projectdocument': '项目文档',
        'worktype': '工作类型',
        'workhour': '工时',
        'workrecord': '工作记录',
        'workreport': '工作汇报',
        'procedureset': '工序集',
        'proceduresetitem': '工序集项',
        'productiondatapoint': '生产数据点',
        'productionplan': '生产计划',
        'productionprocedure': '生产工序',
        'productiontask': '生产任务',
        'qualitycheck': '质量检查',
        'sop': '标准作业程序',
        'diskfile': '网盘文件',
        'diskfolder': '网盘文件夹',
        'diskoperation': '网盘操作',
        'diskshare': '网盘共享',
        'approvalflow': '审批流程',
        'approvalstep': '审批步骤',
        'approvaltype': '审批类型',
        'approvalrecord': '审批记录',
        'approvalrequest': '审批申请',
        'caretype': '关怀类型',
        'duty': '职责',
        'joblevel': '职位级别',
        'carfeetype': '车辆费用类型',
        'noticetype': '公告类型',
        'rewardpunishmenttype': '奖惩类型',
        'datacollection': '数据采集',
        'datacollectionrecord': '数据采集记录',
        'datacollectiontask': '数据采集任务',
        'datamapping': '数据映射',
        'datasource': '数据源',
        'userloginlog': '用户登录日志',
        'usernew': '新用户',
        'announcement': '公告',
        'announcementreadrecord': '公告阅读记录',
        'meetingminutes': '会议纪要',
        'meetingrecord': '会议记录',
        'meetingrecordattendee': '会议记录参与者',
        'meetingrecordparticipant': '会议记录参与者',
        'meetingrecordshareduser': '会议记录共享用户',
        'messagereadrecord': '消息阅读记录',
        'noticetargetdepartment': '通知目标部门',
        'noticetargetuser': '通知目标用户',
        'noticetype': '通知类型',
        'orderfield': '订单字段',
        'orderfinancerecord': '订单财务记录',
        'positionnew': '新职位',
        'departmentnew': '新部门',
        'captchastore': '验证码存储',
        'workcate': '工作分类',
        'message': '消息',
        'optimizedadmin': '优化管理员',
        'djangocontenttype': 'Django内容类型'
    }
    
    # 菜单顺序
    MENU_ORDER = [
        '工作台', '系统管理', '人事管理', '行政办公', '个人办公', '财务管理', 
        '客户管理', '合同管理', '项目管理', '生产管理', 'AI智能中心', '企业网盘', '其他权限'
    ]
    
    @classmethod
    def get_permission_data(cls, permissions: List[Permission]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        获取分组后的权限数据
        
        Args:
            permissions: 权限列表
            
        Returns:
            分组后的权限数据字典
        """
        permission_data = {
            '工作台': {},
            '系统管理': {},
            '人事管理': {},
            '行政办公': {},
            '个人办公': {},
            '财务管理': {},
            '客户管理': {},
            '合同管理': {},
            '项目管理': {},
            '生产管理': {},
            'AI智能中心': {},
            '企业网盘': {},
            '其他权限': {}
        }
        
        unique_permissions = {perm.id: perm for perm in permissions}
        used_display_names = {}
        
        for perm_id, perm in unique_permissions.items():
            app_label = perm.content_type.app_label
            model = perm.content_type.model
            
            model_display_name = cls.MODEL_NAME_MAP.get(model, model.capitalize())
            menu_group = cls._get_menu_group(app_label, model)
            action = cls._get_action_type(perm.name)
            display_name = cls._get_unique_display_name(action, model_display_name, perm_id, used_display_names)
            
            perm_copy = {
                'id': perm_id,
                'name': display_name,
                'codename': perm.codename,
                'content_type_id': perm.content_type_id,
                'app_label': app_label,
                'model': model
            }
            
            if model_display_name not in permission_data[menu_group]:
                permission_data[menu_group][model_display_name] = []
            
            permission_data[menu_group][model_display_name].append(perm_copy)
        
        return cls._sort_permission_data(permission_data)
    
    @classmethod
    def _get_menu_group(cls, app_label: str, model: str) -> str:
        """获取权限所属的菜单分组"""
        if app_label in ['contenttypes', 'auth', 'sessions', 'sites']:
            return '系统管理'
        elif app_label in cls.MENU_GROUP_MAP:
            return cls.MENU_GROUP_MAP[app_label]
        elif model in cls.MENU_GROUP_MAP and app_label not in ['system', 'admin', 'basedata']:
            return cls.MENU_GROUP_MAP[model]
        
        for prefix, group in cls.MENU_GROUP_MAP.items():
            if app_label.startswith(prefix):
                return group
        
        for prefix, group in cls.MENU_GROUP_MAP.items():
            if model.startswith(prefix):
                return group
        
        return '其他权限'
    
    @classmethod
    def _get_action_type(cls, perm_name: str) -> str:
        """获取权限的操作类型"""
        if 'Can add' in perm_name:
            return '添加'
        elif 'Can change' in perm_name:
            return '修改'
        elif 'Can delete' in perm_name:
            return '删除'
        elif 'Can view' in perm_name:
            return '查看'
        elif 'Can create' in perm_name:
            return '创建'
        elif 'Can manage' in perm_name:
            return '管理'
        elif 'Can' in perm_name:
            return '操作'
        else:
            return '操作'
    
    @classmethod
    def _get_unique_display_name(cls, action: str, model_display_name: str, perm_id: int, used_display_names: Dict[str, int]) -> str:
        """获取唯一的显示名称"""
        base_display_name = f"{action} {model_display_name}"
        display_name = base_display_name
        
        counter = 1
        while display_name in used_display_names:
            display_name = f"{base_display_name} ({perm_id})"
            counter += 1
        
        used_display_names[display_name] = perm_id
        return display_name
    
    @classmethod
    def _sort_permission_data(cls, permission_data: Dict[str, Dict[str, List[Dict[str, Any]]]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """按预设的菜单顺序排序权限数据"""
        sorted_permission_data = {}
        
        for menu in cls.MENU_ORDER:
            if menu in permission_data and permission_data[menu]:
                sorted_permission_data[menu] = permission_data[menu]
        
        return sorted_permission_data
