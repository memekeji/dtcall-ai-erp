"""
公共常量模块
用于存储项目中的所有常量定义，避免硬编码和魔法数字
"""

# ==================== 财务模块常量 ====================
class FinanceStatus:
    """财务相关状态常量"""
    
    # 报销状态
    EXPENSE_CHECK_PENDING = 0      # 待审核
    EXPENSE_CHECK_PROCESSING = 1   # 审核中
    EXPENSE_CHECK_APPROVED = 2     # 审核通过
    EXPENSE_CHECK_REJECTED = 3     # 审核不通过
    EXPENSE_CHECK_CANCELLED = 4    # 撤销审核
    
    # 支付状态
    PAY_STATUS_PENDING = 0         # 待打款
    PAY_STATUS_PAID = 1            # 已打款
    
    # 开票状态
    INVOICE_OPEN_STATUS_NOT = 0    # 未开票
    INVOICE_OPEN_STATUS_DONE = 1   # 已开票
    INVOICE_OPEN_STATUS_VOID = 2   # 已作废
    
    # 回款状态
    ENTER_STATUS_NOT = 0           # 未回款
    ENTER_STATUS_PARTIAL = 1       # 部分回款
    ENTER_STATUS_FULL = 2          # 全部回款
    
    # 发票类型
    INVOICE_TYPE_SPECIAL = 1       # 增值税专用发票
    INVOICE_TYPE_ORDINARY = 2      # 普通发票
    INVOICE_TYPE_ELECTRONIC = 3    # 电子发票


class FinanceStatusMapping:
    """财务状态映射字典"""
    
    CHECK_STATUS_MAP = {
        0: '待审核',
        1: '审核中',
        2: '审核通过',
        3: '审核不通过',
        4: '撤销审核'
    }
    
    PAY_STATUS_MAP = {
        0: '待打款',
        1: '已打款'
    }
    
    OPEN_STATUS_MAP = {
        0: '未开票',
        1: '已开票',
        2: '已作废'
    }
    
    ENTER_STATUS_MAP = {
        0: '未回款',
        1: '部分回款',
        2: '全部回款'
    }
    
    INVOICE_TYPE_MAP = {
        1: '增值税专用发票',
        2: '普通发票',
        3: '专用发票'
    }


# ==================== 客户模块常量 ====================
class CustomerStatus:
    """客户相关状态常量"""
    
    # 客户状态
    STATUS_NORMAL = 1              # 正常
    STATUS_DISABLED = 0            # 禁用
    STATUS_LEAVE = 2               # 离职
    STATUS_WAIT_JOIN = -1          # 待入职
    
    # 删除状态
    NOT_DELETED = 0                # 未删除
    DELETED = 1                    # 已删除


class CustomerIntentStatus:
    """客户意向状态常量"""
    
    STATUS_ACTIVE = 1              # 启用
    STATUS_INACTIVE = 0            # 禁用


# ==================== 项目模块常量 ====================
class ProjectStatus:
    """项目状态常量"""
    
    STATUS_INIT = 0                # 初始
    STATUS_PLANNING = 1            # 计划中
    STATUS_EXECUTING = 2           # 执行中
    STATUS_COMPLETED = 3           # 已完成
    STATUS_SUSPENDED = 4           # 暂停
    STATUS_TERMINATED = 5          # 终止


class TaskStatus:
    """任务状态常量"""
    
    STATUS_PENDING = 1             # 待开始
    STATUS_IN_PROGRESS = 2         # 进行中
    STATUS_COMPLETED = 3           # 已完成


# ==================== 合同模块常量 ====================
class ContractStatus:
    """合同状态常量"""
    
    STATUS_DRAFT = 0               # 草稿
    STATUS_PENDING = 1             # 待审核
    STATUS_APPROVED = 2            # 已审核
    STATUS_SIGNED = 3              # 已签订
    STATUS_EXECUTING = 4           # 执行中
    STATUS_COMPLETED = 5           # 已完成
    STATUS_TERMINATED = 6          # 已终止
    STATUS_VOID = 7                # 已作废
    STATUS_ARCHIVED = 8            # 已归档


class ContractType:
    """合同类型常量"""
    
    TYPE_SALES = 'sales'           # 销售合同
    TYPE_SERVICE = 'service'       # 服务合同
    TYPE_MAINTENANCE = 'maintenance'  # 维护合同
    TYPE_CONSULTING = 'consulting' # 咨询合同
    TYPE_OTHER = 'other'           # 其他


# ==================== 生产模块常量 ====================
class ProductionStatus:
    """生产相关状态常量"""
    
    STATUS_INACTIVE = 0            # 禁用
    STATUS_ACTIVE = 1              # 启用


# ==================== 审批模块常量 ====================
class ApprovalStatus:
    """审批状态常量"""
    
    STATUS_PENDING = 'pending'     # 待审批
    STATUS_APPROVED = 'approved'   # 已批准
    STATUS_REJECTED = 'rejected'   # 已拒绝
    STATUS_CANCELLED = 'cancelled' # 已取消


# ==================== 通用常量 ====================
class CommonConstant:
    """通用常量"""
    
    # 默认分页大小
    DEFAULT_PAGE_SIZE = 20
    DEFAULT_LIST_LIMIT = 10
    
    # 时间格式
    DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
    DATE_FORMAT = '%Y-%m-%d'
    TIME_FORMAT = '%H:%M:%S'
    
    # 缓存时间（秒）
    CACHE_1_HOUR = 3600
    CACHE_1_DAY = 86400
    CACHE_1_WEEK = 604800
    
    # 每批处理数量
    BATCH_PROCESS_LIMIT = 50
    
    # 状态有效值
    STATUS_VALUES = [0, 1]
    DELETE_TIME_ZERO = 0


# ==================== API响应常量 ====================
class ApiResponseCode:
    """API响应状态码"""
    
    CODE_SUCCESS = 0               # 成功
    CODE_ERROR = 1                 # 错误
    CODE_SERVER_ERROR = 500        # 服务器错误
    
    MSG_SUCCESS = 'success'
    MSG_ERROR = 'error'


class ApiResponseMsg:
    """API响应消息"""
    
    GET_DATA_SUCCESS = '获取数据成功'
    GET_DATA_ERROR = '获取数据失败: {}'
    CREATE_SUCCESS = '创建成功'
    CREATE_ERROR = '创建失败: {}'
    UPDATE_SUCCESS = '更新成功'
    UPDATE_ERROR = '更新失败: {}'
    DELETE_SUCCESS = '删除成功'
    DELETE_ERROR = '删除失败: {}'
    SERVER_ERROR = '服务器错误: {}'
    PARAM_ERROR = '参数错误'
    PERMISSION_DENIED = '权限不足'
    NOT_FOUND = '资源不存在'
