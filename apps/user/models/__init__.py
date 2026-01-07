# 明确导入需要的模型，避免通配符导入导致的冲突
from .admin import Admin
from .admin_log import AdminLog
from .menu import Menu
from .position import Position
from .department import Department

# 导入员工相关模型
from .employee import EmployeeFile, EmployeeTransfer, EmployeeDimission, RewardPunishment, EmployeeCare, EmployeeContract

# 导入系统相关模型（从system应用迁移）
from .system import SystemLog, SystemOperationLog, SystemConfiguration, SystemModule