"""
URL configuration for dtcall project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.urls import path, include, re_path
from django.views.generic import RedirectView, TemplateView
import apps.user.views.captcha_views
from apps.user.views import admin_views
from apps.project import views as project_views
from django.conf import settings
from django.conf.urls.static import static
from apps.home import views as home_views
# JWT认证视图
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url='/static/img/favicon.ico')),
    # 根路径重定向到登录页面
    path('', RedirectView.as_view(url='/user/login/', permanent=False), name='home'),
    # 测试页面
    path('test-jquery/', TemplateView.as_view(template_name='test_jquery.html'), name='test_jquery'),
    
    # 第三方应用
    path('captcha/', include('captcha.urls')),
    path('get-new-captcha/', 
         apps.user.views.captcha_views.GetNewCaptchaView.as_view(), 
         name='get-new-captcha'),
    
    # 核心应用路由
    path('user/', include('apps.user.urls', namespace='user')),  # 用户相关（登录、注册等）
    path('home/', include('apps.home.urls', namespace='home')),  # 首页相关
    
    # 业务应用路由
    path('adm/task/workhour/', RedirectView.as_view(url='/task/workhour/', permanent=True)),
    path('adm/task/workhour/datalist/', RedirectView.as_view(url='/task/workhour/datalist/', permanent=True)),
    path('adm/task/workhour/add/', RedirectView.as_view(url='/task/workhour/add/', permanent=True)),
    path('adm/task/workhour/edit/<int:workhour_id>/', RedirectView.as_view(url='/task/workhour/edit/%(workhour_id)s/', permanent=True)),
    path('adm/task/workhour/delete/<int:workhour_id>/', RedirectView.as_view(url='/task/workhour/delete/%(workhour_id)s/', permanent=True)),
    path('adm/task/workhour/stats/', RedirectView.as_view(url='/task/workhour/stats/', permanent=True)),
    path('adm/', RedirectView.as_view(url='/system/', permanent=True)),  # 将adm应用重定向到system应用
    path('oa/', include('apps.oa.urls')),  # OA系统
    # path('', include('apps.department.urls')),  # 部门管理 - 已迁移到adm应用
    
    # 云盘模块
    path('disk/', include('apps.disk.urls', namespace='disk')),
    # 客户模块
    path('customer/', include('apps.customer.urls', namespace='customer')),
    # 财务模块
    path('finance/', include('apps.finance.urls', namespace='finance')),
    # 财务模块 - adm前缀（兼容旧路径）
    path('adm/finance/', include('apps.finance.urls', namespace='adm_finance')),
    # 生产模块
    path('production/', include('apps.production.urls', namespace='production')),
    # 系统模块
    path('system/', include('apps.system.urls')),
    # 个人办公
    path('personal/', include('apps.personal.urls', namespace='personal')),
    path('position/', include('apps.position.urls')),
    # 部门管理API - 配置为system/department前缀
    path('system/department/', include('apps.department.urls')),
    # 合同管理
    path('contract/', include('apps.contract.urls', namespace='contract')),
    # 项目管理
    path('project/', include('apps.project.urls', namespace='project')),
    # 任务管理
    path('task/', include('apps.task.urls', namespace='task')),
    path('project/task/', include('apps.task.urls', namespace='project_task')),
    
    # 项目管理前端路由
    path('project-mgmt/', TemplateView.as_view(template_name='project-mgmt/index.html'), name='project-mgmt'),
    path('project-mgmt/<path:path>', TemplateView.as_view(template_name='project-mgmt/index.html'), name='project-mgmt-path'),
    
    # 审批流程模块
    path('approval/', include('apps.approval.urls', namespace='approval')),
    
    # 消息通知模块
    path('message/', include('apps.message.urls', namespace='message')),
    
    # 登出
    path('logout/', admin_views.logout_view, name='logout'),
    
    # AI智能服务
    path('ai/', include('apps.ai.urls', namespace='ai')),
    
    # 修复dashboard路径重定向
    path('dashboard/', RedirectView.as_view(url='/home/dashboard/', permanent=True)),
    path('dashboard/finance/', RedirectView.as_view(url='/home/dashboard/finance/', permanent=True)),
    path('dashboard/business/', RedirectView.as_view(url='/home/dashboard/business/', permanent=True)),
    path('dashboard/production/', RedirectView.as_view(url='/home/dashboard/production/', permanent=True)),
    # 修复角色管理页面404错误
    path('system/permission/role/', RedirectView.as_view(url='/system/permission/roles/', permanent=True)),
    # 修复角色管理页面404错误 - 重定向到user应用
    path('system/permission/roles/', RedirectView.as_view(url='/user/group/', permanent=True)),
    # 修复部门角色管理页面无法打开问题 - 重定向到user应用
    re_path(r'^system/permission/departments/(?P<department_id>\d+)/roles/$', RedirectView.as_view(url='/user/department/%(department_id)s/roles/', permanent=True)),
    
    # 基础数据模块路径重定向 - 已迁移到各功能模块
    path('basedata/', RedirectView.as_view(url='/contract/category/', permanent=True)),
    path('adm/basic/', RedirectView.as_view(url='/contract/category/', permanent=True)),
    path('basedata/contract/', RedirectView.as_view(url='/contract/category/', permanent=True)),
    path('basedata/customer/', RedirectView.as_view(url='/customer/source/', permanent=True)),
    path('basedata/finance/', RedirectView.as_view(url='/finance/expense/', permanent=True)),
    path('basedata/project/', RedirectView.as_view(url='/project/stage/', permanent=True)),
    path('basedata/hr/', RedirectView.as_view(url='/user/employee/', permanent=True)),
    
    # 人力资源路径重定向
    path('hr/', RedirectView.as_view(url='/user/employee/', permanent=True)),
    
    # OA模块路径 - 添加特定的重定向规则修复404错误
    path('oa/assets/register/', RedirectView.as_view(url='/system/admin_office/asset/create/', permanent=True)),
    path('oa/assets/repair/', RedirectView.as_view(url='/system/admin_office/asset_repair/create/', permanent=True)),
    path('oa/assets/borrow/', RedirectView.as_view(url='/system/admin_office/asset/', permanent=True)),
    path('oa/assets/return/', RedirectView.as_view(url='/system/admin_office/asset/', permanent=True)),
    path('oa/assets/scrap/', RedirectView.as_view(url='/system/admin_office/asset/', permanent=True)),
    path('oa/vehicle/info/', RedirectView.as_view(url='/system/admin_office/vehicle/', permanent=True)),
    path('oa/vehicle/apply/', RedirectView.as_view(url='/system/admin_office/vehicle/', permanent=True)),
    path('oa/vehicle/maintain/', RedirectView.as_view(url='/system/admin_office/vehicle_maintenance/', permanent=True)),
    path('oa/vehicle/dispatch/', RedirectView.as_view(url='/system/admin_office/vehicle/', permanent=True)),
    # 修复车辆费用和油耗页面404错误
    path('oa/vehicle/fee/', RedirectView.as_view(url='/system/admin_office/vehicle_fee/', permanent=True)),
    path('oa/vehicle/oil/', RedirectView.as_view(url='/system/admin_office/vehicle_oil/', permanent=True)),
    # 修复车辆模块根路径404错误
    path('oa/vehicle/', RedirectView.as_view(url='/system/admin_office/vehicle/', permanent=True)),
    # 修复会议记录页面404错误
    path('oa/meeting/', RedirectView.as_view(url='/oa/meeting/list/', permanent=True)),
    # 修复公文分类页面404错误
    path('oa/document/', RedirectView.as_view(url='/system/admin_office/document/', permanent=True)),
    path('oa/document/category/', RedirectView.as_view(url='/system/admin_office/document_category/', permanent=True)),
    path('oa/meeting/info/', RedirectView.as_view(url='/system/admin_office/meeting_room/', permanent=True)),
    path('oa/seal/info/', RedirectView.as_view(url='/system/admin_office/seal/', permanent=True)),
    path('oa/seal/manage/', RedirectView.as_view(url='/system/admin_office/seal/', permanent=True)),
    path('oa/seal/apply/', RedirectView.as_view(url='/system/admin_office/seal_application/create/', permanent=True)),
    path('oa/seal/record/', RedirectView.as_view(url='/system/admin_office/seal_application/', permanent=True)),
    path('oa/document/info/', RedirectView.as_view(url='/system/admin_office/document/', permanent=True)),
    path('oa/document/draft/', RedirectView.as_view(url='/system/admin_office/document/create/', permanent=True)),
    path('oa/document/check/', RedirectView.as_view(url='/system/admin_office/document/', permanent=True)),
    path('oa/document/publish/', RedirectView.as_view(url='/system/admin_office/document/', permanent=True)),
    path('oa/document/view/', RedirectView.as_view(url='/system/admin_office/document/', permanent=True)),
    
    # 系统管理路径重定向
    path('adm/log/', RedirectView.as_view(url='/system/log/', permanent=True)),
    path('adm/config/', RedirectView.as_view(url='/system/config/', permanent=True)),
    
    # 员工关怀管理重定向
    path('adm/basedata/hr/care/', RedirectView.as_view(url='/basedata/hr/care/', permanent=True)),
    
    # 奖罚管理重定向 - 修复菜单跳转问题
    path('adm/rewardpunish/', RedirectView.as_view(url='/user/reward-punishment/', permanent=True)),
    
    # 员工关怀重定向 - 修复菜单跳转问题
    path('adm/care/', RedirectView.as_view(url='/user/employee-care/', permanent=True)),
    
    # 基础数据模块重定向 - 修复系统管理资产分类、资产品牌、通知类型无法打开问题
    path('adm/basedata/admin/assetcategory/', RedirectView.as_view(url='/system/admin_office/asset/', permanent=True)),
    path('adm/basedata/admin/assetbrand/', RedirectView.as_view(url='/system/admin_office/asset/', permanent=True)),
    path('adm/basedata/admin/assetunit/', RedirectView.as_view(url='/system/admin_office/asset/', permanent=True)),
    path('adm/basedata/admin/carfee/', RedirectView.as_view(url='/system/admin_office/vehicle_fee/', permanent=True)),
    path('adm/basedata/admin/notice/', RedirectView.as_view(url='/system/admin_office/notice/', permanent=True)),
    
    # 兼容旧路径 - 系统管理模块
    path('system/notice/', RedirectView.as_view(url='/system/admin_office/notice/', permanent=True)),
    path('system/assetcategory/', RedirectView.as_view(url='/system/admin_office/asset/', permanent=True)),
    path('system/assetbrand/', RedirectView.as_view(url='/system/admin_office/asset/', permanent=True)),
    
    # 任务管理重定向规则
    path('adm/task/datalist/', RedirectView.as_view(url='/task/', permanent=True)),
    
    # 兼容旧路径 - 合同模块基础数据
    path('basedata/contract/category/', RedirectView.as_view(url='/contract/category/', permanent=True)),
    path('basedata/contract/productcategory/', RedirectView.as_view(url='/contract/productcategory/', permanent=True)),
    path('basedata/contract/product/', RedirectView.as_view(url='/contract/product/', permanent=True)),
    path('basedata/contract/service/', RedirectView.as_view(url='/contract/servicecategory/', permanent=True)),
    path('basedata/contract/supplier/', RedirectView.as_view(url='/contract/supplier/', permanent=True)),
    path('basedata/contract/purchasecategory/', RedirectView.as_view(url='/contract/purchasecategory/', permanent=True)),
    path('basedata/contract/purchase/', RedirectView.as_view(url='/contract/purchase/', permanent=True)),
    
    # 兼容旧路径 - 项目模块基础数据
    path('basedata/project/stage/', RedirectView.as_view(url='/project/stage/', permanent=True)),
    path('basedata/project/category/', RedirectView.as_view(url='/project/category/', permanent=True)),
    path('basedata/project/worktype/', RedirectView.as_view(url='/project/worktype/', permanent=True)),
    path('adm/basedata/project/stage/', RedirectView.as_view(url='/project/stage/', permanent=True)),
    path('adm/basedata/project/category/', RedirectView.as_view(url='/project/category/', permanent=True)),
    path('adm/basedata/project/worktype/', RedirectView.as_view(url='/project/worktype/', permanent=True)),
    
    # 兼容旧路径 - 任务管理
    path('adm/task/datalist/', RedirectView.as_view(url='/task/datalist/', permanent=True)),
    path('adm/task/', RedirectView.as_view(url='/task/', permanent=True, query_string=True)),
    
    # 个人办公重定向
    path('personal/log/', RedirectView.as_view(url='/system/log/', permanent=True)),
    path('personal/info/', RedirectView.as_view(url='/personal/schedule/', permanent=True)),
    path('personal/setting/', RedirectView.as_view(url='/personal/schedule/', permanent=True)),
    path('personal/message/', RedirectView.as_view(url='/message/list/', permanent=True)),
    path('personal/contacts/', RedirectView.as_view(url='/personal/schedule/', permanent=True)),
    
    # 财务模块重定向规则 - 修复报销管理菜单跳转问题
    # 保留原有的重定向
    path('finance/expense/', RedirectView.as_view(url='/reimbursement/', permanent=True)),
    # 直接映射报销管理视图，避免URL包含冲突
    path('reimbursement/', include('apps.finance.urls', namespace='reimbursement')),
    path('finance/ai_expense_review/', RedirectView.as_view(url='/ai/', permanent=True)),
    # 修复所有财务相关URL的重定向规则
    path('finance/receive_invoice/', RedirectView.as_view(url='/finance/receiveinvoice/', permanent=True)),
    path('finance/receivable/', RedirectView.as_view(url='/finance/paymentreceive/', permanent=True)),
    path('finance/payable/', RedirectView.as_view(url='/finance/payment/', permanent=True)),
    # 修复财务统计相关的重定向规则
    path('adm/finance/statistics/reimbursement/', RedirectView.as_view(url='/finance/statistics/reimbursement/', permanent=True)),
    path('adm/finance/statistics/invoice/', RedirectView.as_view(url='/finance/statistics/invoice/', permanent=True)),
    path('adm/finance/statistics/receiveinvoice/', RedirectView.as_view(url='/finance/statistics/receiveinvoice/', permanent=True)),
    path('adm/finance/statistics/paymentreceive/', RedirectView.as_view(url='/finance/statistics/paymentreceive/', permanent=True)),
    path('adm/finance/statistics/payment/', RedirectView.as_view(url='/finance/statistics/payment/', permanent=True)),
    
    # 客户模块重定向 - 修复客户相关菜单跳转问题
    path('customer/list/', RedirectView.as_view(url='/customer/', permanent=True)),
    path('customer/order/', RedirectView.as_view(url='/customer/orders/', permanent=True)),
    path('customer/discard/', RedirectView.as_view(url='/customer/abandoned/list/', permanent=True)),
    path('customer/ai_classification/', RedirectView.as_view(url='/customer/public/ai-robot/', permanent=True)),
    path('customer/ai_profile/', RedirectView.as_view(url='/customer/public/ai-robot/', permanent=True)),
    path('adm/customer/opportunity/', RedirectView.as_view(url='/customer/public/list/', permanent=True)),
    path('adm/customer/callrecord/', RedirectView.as_view(url='/customer/callrecord/', permanent=True)),
    path('adm/customer/followup/', RedirectView.as_view(url='/customer/followup/', permanent=True)),
    path('adm/basedata/customer/field/', RedirectView.as_view(url='/basedata/', permanent=True)),
    path('adm/basedata/customer/grade/', RedirectView.as_view(url='/basedata/', permanent=True)),
    path('adm/basedata/customer/source/', RedirectView.as_view(url='/basedata/', permanent=True)),
    path('adm/basedata/customer/intent/', RedirectView.as_view(url='/basedata/', permanent=True)),
    path('adm/basedata/customer/follow/', RedirectView.as_view(url='/basedata/', permanent=True)),
    
    # 修复基础数据模块404错误 - 移除循环重定向
    
    # 修复财务发票数据列表404错误
    path('adm/finance/invoice/datalist/', RedirectView.as_view(url='/finance/invoice/datalist/', permanent=True)),
    
    # 修复404错误的专项规则 - 整合所有规则
    # 基础数据模块
    path('basedata/public/enterprise/datalist/', RedirectView.as_view(url='/basedata/public/enterprise/', permanent=True)),
    path('basedata/hr/duty/datalist/', RedirectView.as_view(url='/basedata/hr/duty/', permanent=True)),
    path('basedata/hr/level/datalist/', RedirectView.as_view(url='/basedata/hr/level/', permanent=True)),
    path('basedata/hr/care/datalist/', RedirectView.as_view(url='/basedata/hr/care/', permanent=True)),
    path('basedata/hr/reward/datalist/', RedirectView.as_view(url='/basedata/hr/reward/', permanent=True)),
    
    # 财务模块
    path('finance/invoice/datalist/', RedirectView.as_view(url='/finance/invoice/', permanent=True)),
    path('finance/receiveinvoice/datalist/', RedirectView.as_view(url='/finance/receiveinvoice/', permanent=True)),
    path('finance/reimbursement/datalist/', RedirectView.as_view(url='/finance/reimbursement/datalist/', permanent=True)),
    path('finance/payment/datalist/', RedirectView.as_view(url='/finance/payment/datalist/', permanent=True)),
    path('finance/paymentreceive/datalist/', RedirectView.as_view(url='/finance/paymentreceive/datalist/', permanent=True)),
    
    # 合同模块
    path('contract/archive/datalist/', RedirectView.as_view(url='/contract/archive/', permanent=True)),
    
    # 项目模块
    path('project/category/datalist/', RedirectView.as_view(url='/project/category/', permanent=True)),
    path('project/datalist/', RedirectView.as_view(url='/project/datalist/', permanent=True)),
    path('adm/project/document/datalist/', RedirectView.as_view(url='/project/document/datalist/', permanent=True)),
    
    # 生产模块
    path('production/baseinfo/datalist/', RedirectView.as_view(url='/production/baseinfo/', permanent=True)),
    path('production/procedure/datalist/', RedirectView.as_view(url='/production/procedure/', permanent=True)),
    path('production/procedureset/datalist/', RedirectView.as_view(url='/production/procedureset/', permanent=True)),
    path('production/bom/datalist/', RedirectView.as_view(url='/production/bom/', permanent=True)),
    path('production/equipment/datalist/', RedirectView.as_view(url='/production/equipment/', permanent=True)),
    
    # OA模块
    path('oa/approval/list/', RedirectView.as_view(url='/oa/approval/list/', permanent=True)),
      
    # 修复合同归档数据列表404错误
    path('adm/contract/archive/datalist/', RedirectView.as_view(url='/contract/archive/datalist/', permanent=True)),
    
    # 修复项目分类数据列表404错误
    path('adm/project/category/datalist/', RedirectView.as_view(url='/project/category/', permanent=True)),
    
    # 修复合同管理相关路由404错误
    path('contract/list/', RedirectView.as_view(url='/contract/sales/', permanent=True)),
    path('contract/template/', RedirectView.as_view(url='/contract/sales/', permanent=True)),
    path('contract/audit/', RedirectView.as_view(url='/contract/sales/', permanent=True)),
    path('contract/execution/', RedirectView.as_view(url='/contract/sales/', permanent=True)),
    path('adm/contract/sales/', RedirectView.as_view(url='/contract/sales/', permanent=True)),
    path('adm/contract/sales/add/', RedirectView.as_view(url='/contract/sales/add/', permanent=True)),
    path('adm/contract/sales/view/<int:id>/', RedirectView.as_view(url='/contract/sales/view/%(id)s/', permanent=True)),
    # 修复合同创建重定向问题 - 将旧的分类选择页面跳转重定向到新的合同创建页面
    path('adm/contract/create/', RedirectView.as_view(url='/contract/add/', permanent=True)),
    path('adm/contract/sales/edit/<int:id>/', RedirectView.as_view(url='/contract/sales/edit/%(id)s/', permanent=True)),

    path('adm/contract/purchase/', RedirectView.as_view(url='/contract/purchase/', permanent=True)),
    path('adm/contract/terminate/', RedirectView.as_view(url='/contract/terminate/', permanent=True)),
    path('adm/contract/cancel/', RedirectView.as_view(url='/contract/cancel/', permanent=True)),
    
    # 修复基础数据模块相关路由404错误
    path('adm/basedata/customer/order/', RedirectView.as_view(url='/basedata/', permanent=True)),
    
    # 修复客户管理相关路由404错误
    path('customer/datalist/', RedirectView.as_view(url='/customer/', permanent=True)),
    path('customer/contact/datalist/', RedirectView.as_view(url='/customer/contact/', permanent=True)),
    path('customer/address/datalist/', RedirectView.as_view(url='/customer/address/', permanent=True)),
    path('customer/visit/datalist/', RedirectView.as_view(url='/customer/visit/', permanent=True)),
    
    # 修复其他可能的404错误
    path('project/task/datalist/', RedirectView.as_view(url='/project/task/', permanent=True)),
    path('oa/meeting/datalist/', RedirectView.as_view(url='/oa/meeting/datalist/', permanent=True)),
    path('adm/basedata/contract/productcategory/', RedirectView.as_view(url='/basedata/', permanent=True)),
    path('adm/basedata/contract/product/', RedirectView.as_view(url='/basedata/', permanent=True)),
    path('adm/basedata/contract/service/', RedirectView.as_view(url='/basedata/', permanent=True)),
    path('adm/basedata/contract/supplier/', RedirectView.as_view(url='/basedata/', permanent=True)),
    path('adm/basedata/contract/purchase/', RedirectView.as_view(url='/basedata/', permanent=True)),
    path('adm/basedata/contract/purchasecategory/', RedirectView.as_view(url='/basedata/', permanent=True)),
    
    # 修复项目列表404错误
    path('project/list/', RedirectView.as_view(url='/project/', permanent=True)),
    
    # 额外的重定向规则以解决404错误
    # 项目分类数据列表重定向
    path('project/category/datalist/', RedirectView.as_view(url='/project/category/', permanent=True)),

    # 项目相关重定向 - 修正为正确的目标路径
    path('project/task/', RedirectView.as_view(url='/project/task/', permanent=True)),
    path('project/time/', RedirectView.as_view(url='/project/time/', permanent=True)),
    path('project/ai_risk_prediction/', RedirectView.as_view(url='/project/ai_risk_prediction/', permanent=True)),
    path('project/ai_progress_analysis/', RedirectView.as_view(url='/project/ai_progress_analysis/', permanent=True)),
    path('adm/project/document/datalist/', RedirectView.as_view(url='/project/document/', permanent=True)),
    # 生产模块重定向 - 修正为正确的路径格式，避免与production应用路由冲突
    path('adm/production/procedure/', RedirectView.as_view(url='/production/procedure/', permanent=False)),
    path('adm/production/bom/', RedirectView.as_view(url='/production/bom/', permanent=False)),
    path('adm/production/equipment/', RedirectView.as_view(url='/production/equipment/', permanent=False)),
    path('adm/production/procedureset/', RedirectView.as_view(url='/production/procedureset/', permanent=False)),
    path('adm/production/staff/', RedirectView.as_view(url='/production/staff/', permanent=False)),
    path('adm/production/technology/', RedirectView.as_view(url='/production/technology/', permanent=False)),
    path('adm/production/task/execution/', RedirectView.as_view(url='/production/task/execution/', permanent=False)),
    path('adm/production/quality/', RedirectView.as_view(url='/production/quality/', permanent=False)),
    path('adm/production/monitor/', RedirectView.as_view(url='/production/equipment/monitor/', permanent=False)),
    # 修复菜单中的生产监控路由错误
    path('production/monitor/', RedirectView.as_view(url='/production/equipment/monitor/', permanent=True)),
    # 修复合同模块产品管理路由错误
    path('basedata/contract/product/', RedirectView.as_view(url='/contract/product/', permanent=True)),
    # 云盘模块重定向
    # 通用重定向规则：将所有/adm/disk/xxx请求重定向到/disk/xxx
    re_path(r'^adm/disk/$', RedirectView.as_view(url='/disk/', permanent=True, query_string=True)),
    re_path(r'^adm/disk/(?P<path>.*)$', RedirectView.as_view(url='/disk/%(path)s', permanent=True, query_string=True)),
    # AI模块重定向规则 - 修复404错误
    path('ai/config/models/', RedirectView.as_view(url='/ai/model-config/list/', permanent=True)),
    re_path(r'^ai/config/models/(?P<pk>\d+)/validate/$', RedirectView.as_view(url='/ai/model-config/validate/%(pk)s/', permanent=True)),
    path('ai/workflow/', RedirectView.as_view(url='/ai/workflow/list/', permanent=True)),
    # 已由上方 include('apps.ai.urls') 提供入口，移除到自身的冗余重定向
    # 合同数据列表相关重定向
    path('adm/contract/sales/datalist/', RedirectView.as_view(url='/contract/sales/datalist/', permanent=True)),
    path('adm/contract/purchase/datalist/', RedirectView.as_view(url='/contract/purchase/datalist/', permanent=True)),
    path('adm/contract/terminate/datalist/', RedirectView.as_view(url='/contract/terminate/datalist/', permanent=True)),
    path('adm/contract/cancel/datalist/', RedirectView.as_view(url='/contract/cancel/datalist/', permanent=True)),
    
    # 修复项目相关404错误
    path('adm/project/', RedirectView.as_view(url='/project/', permanent=True)),
    path('adm/project/datalist/', RedirectView.as_view(url='/project/datalist/', permanent=True)),
    path('adm/project/category/datalist/', RedirectView.as_view(url='/project/category/', permanent=True)),
    path('adm/project/task/', RedirectView.as_view(url='/project/task/', permanent=True)),
    path('adm/project/task/datalist/', RedirectView.as_view(url='/project/task/', permanent=True)),
    path('adm/project/document/', RedirectView.as_view(url='/project/document/', permanent=True)),
    path('adm/project/document/datalist/', RedirectView.as_view(url='/project/document/', permanent=True)),
    path('adm/project/detail/<int:project_id>/', RedirectView.as_view(url='/project/detail/%(project_id)s/', permanent=True)),
    path('adm/project/edit/<int:project_id>/', RedirectView.as_view(url='/project/edit/%(project_id)s/', permanent=True)),
    path('adm/project/add/', RedirectView.as_view(url='/project/add/', permanent=True, query_string=True)),
    path('adm/project/document/', project_views.ProjectDocumentListView.as_view(), name='adm_project_document'),
    path('adm/project/document/datalist/', project_views.ProjectDocumentListView.as_view(), name='adm_project_document_datalist'),
    path('adm/project/document/add/', project_views.ProjectDocumentAddView.as_view(), name='adm_project_document_add'),
    path('adm/project/document/upload/', project_views.ProjectDocumentUploadView.as_view(), name='adm_project_document_upload'),
    path('adm/project/document/edit/<int:doc_id>/', project_views.ProjectDocumentEditView.as_view(), name='adm_project_document_edit'),
    path('adm/project/document/delete/<int:doc_id>/', project_views.ProjectDocumentDeleteView.as_view(), name='adm_project_document_delete'),
    path('adm/project/document/detail/<int:doc_id>/', project_views.ProjectDocumentDetailView.as_view(), name='adm_project_document_detail'),
    
    # 修复任务相关404错误
    # 新增任务URL重定向，使用path替代re_path以正确保留query_string
    path('adm/task/add/', RedirectView.as_view(url='/task/add/', permanent=True, query_string=True)),
    path('adm/task/', RedirectView.as_view(url='/task/', permanent=True, query_string=True)),
    path('adm/task/edit/<int:task_id>/', RedirectView.as_view(url='/task/edit/%(task_id)s/', permanent=True, query_string=True)),
    
    # 修复生产模块404错误
    path('adm/production/', RedirectView.as_view(url='/production/', permanent=True)),
    path('adm/production/baseinfo/', RedirectView.as_view(url='/production/baseinfo/', permanent=True)),
    path('adm/production/baseinfo/datalist/', RedirectView.as_view(url='/production/baseinfo/', permanent=True)),
    path('adm/production/procedure/datalist/', RedirectView.as_view(url='/production/procedure/', permanent=True)),
    path('adm/production/procedureset/datalist/', RedirectView.as_view(url='/production/procedureset/', permanent=True)),
    path('adm/production/bom/datalist/', RedirectView.as_view(url='/production/bom/', permanent=True)),
    path('adm/production/equipment/datalist/', RedirectView.as_view(url='/production/equipment/', permanent=True)),
    path('adm/production/technology/datalist/', RedirectView.as_view(url='/production/technology/', permanent=True)),
    path('adm/production/staff/datalist/', RedirectView.as_view(url='/production/staff/', permanent=True)),
    path('adm/production/task/', RedirectView.as_view(url='/production/task/', permanent=False)),
    path('adm/production/task/plan/', RedirectView.as_view(url='/production/task/plan/', permanent=False)),
    path('adm/production/task/execution/', RedirectView.as_view(url='/production/task/execution/', permanent=False)),
    path('adm/production/quality/datalist/', RedirectView.as_view(url='/production/quality/', permanent=True)),
    
    # 行政办公旧路径映射到新系统管理的行政办公模块
    path('adm/meeting/room/', RedirectView.as_view(url='/system/admin_office/meeting_room/', permanent=True)),
    path('adm/meeting/room/add/', RedirectView.as_view(url='/system/admin_office/meeting_room/create/', permanent=True)),
    path('adm/meeting/room/edit/<int:id>/', RedirectView.as_view(url='/system/admin_office/meeting_room/update/%(id)s/', permanent=True)),
    path('adm/meeting/room/delete/<int:id>/', RedirectView.as_view(url='/system/admin_office/meeting_room/delete/%(id)s/', permanent=True)),
    path('adm/meeting/reservation/', RedirectView.as_view(url='/system/admin_office/meeting_reservation/', permanent=True)),
    path('adm/meeting/reservation/add/', RedirectView.as_view(url='/system/admin_office/meeting_reservation/create/', permanent=True)),
    path('adm/meeting/reservation/edit/<int:id>/', RedirectView.as_view(url='/system/admin_office/meeting_reservation/update/%(id)s/', permanent=True)),
    path('adm/meeting/reservation/view/<int:id>/', RedirectView.as_view(url='/system/admin_office/meeting_reservation/update/%(id)s/', permanent=True)),
    path('adm/meeting/reservation/approve/<int:id>/', RedirectView.as_view(url='/system/admin_office/meeting_reservation/approve/%(id)s/', permanent=True)),
    path('adm/meeting/reservation/reject/<int:id>/', RedirectView.as_view(url='/system/admin_office/meeting_reservation/reject/%(id)s/', permanent=True)),
    path('adm/meeting/reservation/delete/<int:id>/', RedirectView.as_view(url='/system/admin_office/meeting_reservation/delete/%(id)s/', permanent=True)),
    # 仍保留OA相关旧路径的兼容重定向
    path('adm/meeting/', RedirectView.as_view(url='/oa/meeting/', permanent=True)),
    path('adm/meeting/datalist/', RedirectView.as_view(url='/oa/meeting/datalist/', permanent=True)),
    # 人事管理旧路径映射
    path('adm/employee_management/', RedirectView.as_view(url='/user/employee/', permanent=True)),
    path('adm/department/', RedirectView.as_view(url='/user/department/', permanent=True)),
    path('adm/position/', RedirectView.as_view(url='/position/', permanent=True)),
    # 行政办公印章旧路径映射
    path('adm/seal/', RedirectView.as_view(url='/system/admin_office/seal/', permanent=True)),
    path('adm/seal/add/', RedirectView.as_view(url='/system/admin_office/seal/create/', permanent=True)),
    path('adm/seal/edit/<int:id>/', RedirectView.as_view(url='/system/admin_office/seal/update/%(id)s/', permanent=True)),
    path('adm/seal/delete/<int:id>/', RedirectView.as_view(url='/system/admin_office/seal/delete/%(id)s/', permanent=True)),
    path('adm/seal/application/', RedirectView.as_view(url='/system/admin_office/seal_application/', permanent=True)),
    path('adm/seal/application/add/', RedirectView.as_view(url='/system/admin_office/seal_application/create/', permanent=True)),
    path('adm/seal/application/edit/<int:id>/', RedirectView.as_view(url='/system/admin_office/seal_application/update/%(id)s/', permanent=True)),
    path('adm/seal/application/delete/<int:id>/', RedirectView.as_view(url='/system/admin_office/seal_application/delete/%(id)s/', permanent=True)),
    
    # 修复基础数据模块更多404错误
    path('adm/basedata/', RedirectView.as_view(url='/basedata/', permanent=True)),
    path('adm/basedata/project/', RedirectView.as_view(url='/basedata/project/', permanent=True)),
    path('adm/basedata/project/datalist/', RedirectView.as_view(url='/basedata/project/', permanent=True)),
    path('adm/basedata/project/category/', RedirectView.as_view(url='/basedata/project/category/', permanent=True)),
    path('adm/basedata/project/category/datalist/', RedirectView.as_view(url='/basedata/project/category/', permanent=True)),
    
    # 修复客户模块更多404错误
    path('adm/customer/', RedirectView.as_view(url='/customer/', permanent=True)),
    path('adm/customer/spider_task/', RedirectView.as_view(url='/customer/spider_task/', permanent=True)),
    path('adm/customer/spider_task/data/', RedirectView.as_view(url='/customer/spider_task/data/', permanent=True)),
    path('adm/customer/spider_task/create/', RedirectView.as_view(url='/customer/spider_task/create/', permanent=True)),
    path('adm/customer/spider_task/<int:pk>/edit/', RedirectView.as_view(url='/customer/spider_task/<int:pk>/edit/', permanent=True)),
    path('adm/customer/spider_task/<int:pk>/delete/', RedirectView.as_view(url='/customer/spider_task/<int:pk>/delete/', permanent=True)),
    path('adm/customer/spider_task/<int:pk>/action/', RedirectView.as_view(url='/customer/spider_task/<int:pk>/action/', permanent=True)),
    path('adm/customer/list/', RedirectView.as_view(url='/customer/public/list/', permanent=True)),
    path('adm/customer/contact/datalist/', RedirectView.as_view(url='/customer/contact/', permanent=True)),
    path('adm/customer/address/datalist/', RedirectView.as_view(url='/customer/address/', permanent=True)),
    path('adm/customer/visit/datalist/', RedirectView.as_view(url='/customer/visit/', permanent=True)),
    
    # 修复合同模块更多404错误
    path('adm/contract/', RedirectView.as_view(url='/contract/', permanent=True)),
    path('adm/contract/archive/', RedirectView.as_view(url='/contract/archive/', permanent=True)),
    path('adm/contract/archive/datalist/', RedirectView.as_view(url='/contract/archive/datalist/', permanent=True)),
    
    # 修复财务模块更多404错误
    path('adm/finance/', RedirectView.as_view(url='/finance/', permanent=True)),
    path('adm/finance/invoice/', RedirectView.as_view(url='/finance/invoice/', permanent=True)),
    path('adm/finance/reimbursement/', RedirectView.as_view(url='/finance/reimbursement/', permanent=True)),
    path('adm/finance/payment/', RedirectView.as_view(url='/finance/payment/', permanent=True)),
    path('adm/finance/paymentreceive/', RedirectView.as_view(url='/finance/paymentreceive/', permanent=True)),
    path('adm/finance/invoice/datalist/', RedirectView.as_view(url='/finance/invoice/datalist/', permanent=True)),
    path('adm/finance/reimbursement/datalist/', RedirectView.as_view(url='/finance/reimbursement/datalist/', permanent=True)),
    path('adm/finance/payment/datalist/', RedirectView.as_view(url='/finance/payment/datalist/', permanent=True)),
    path('adm/finance/paymentreceive/datalist/', RedirectView.as_view(url='/finance/paymentreceive/datalist/', permanent=True)),
    path('adm/finance/receiveinvoice/datalist/', RedirectView.as_view(url='/finance/receiveinvoice/datalist/', permanent=True)),
    
    # API路由
    path('api/', include('apps.contract.api_urls')),
    path('api/project/', include('apps.project.api_urls')),
    # 通用API路由
    path('api/common/', include('apps.common.urls')),
    # JWT认证路由
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # 修复项目基础数据相关404错误
    path('adm/basedata/project/worktype/', RedirectView.as_view(url='/project/stage/', permanent=True)),
    path('adm/basedata/project/stage/', RedirectView.as_view(url='/project/stage/', permanent=True)),
    
    # 修复生产模块数据和分析相关404错误
    path('adm/production/data/', RedirectView.as_view(url='/production/data/', permanent=False)),
    path('adm/production/analysis/', RedirectView.as_view(url='/production/analysis/', permanent=False)),
    path('adm/production/process/', RedirectView.as_view(url='/production/process/', permanent=False)),
    path('adm/production/task/plan/', RedirectView.as_view(url='/production/task/plan/', permanent=False)),
    
    # 修复OA会议记录相关404错误
    
    # 修复项目任务相关404错误 - 移除循环重定向，项目任务使用task应用
    # path('project/task/', RedirectView.as_view(url='/task/', permanent=True)),
    
    # 修复项目工时管理页面 - 移除循环重定向，添加实际路由
    # path('project/time/', RedirectView.as_view(url='/task/', permanent=True)),
    
    # 修复项目AI分析页面 - 移除循环重定向，添加实际路由
    # path('project/ai_progress_analysis/', RedirectView.as_view(url='/project/', permanent=True)),
    # path('project/ai_risk_prediction/', RedirectView.as_view(url='/project/', permanent=True)),
    
    # 修复项目阶段和工作类型 - 使用project应用的正确路由
    path('project/stage/', RedirectView.as_view(url='/project/stage/', permanent=True)),
    path('project/worktype/', RedirectView.as_view(url='/project/worktype/', permanent=True)),
    path('adm/basedata/project/stage/', RedirectView.as_view(url='/project/stage/', permanent=True)),
    path('adm/basedata/project/worktype/', RedirectView.as_view(url='/project/worktype/', permanent=True)),
    
    # 生产模块更多重定向规则
    path('adm/production/plan/', RedirectView.as_view(url='/production/task/plan/', permanent=True)),
    path('adm/production/quality/', RedirectView.as_view(url='/production/quality/', permanent=True)),
    path('adm/production/equipment/', RedirectView.as_view(url='/production/equipment/', permanent=True)),
    # 修复生产管理模块无法打开的页面
    path('adm/production/data/', RedirectView.as_view(url='/production/data/', permanent=False)),
    path('adm/production/analysis/', RedirectView.as_view(url='/production/analysis/', permanent=False)),
    path('adm/production/sop/', RedirectView.as_view(url='/production/sop/', permanent=True)),
    path('adm/production/product/', RedirectView.as_view(url='/basedata/contract/product/', permanent=True)),
    path('adm/production/technology/', RedirectView.as_view(url='/production/technology/', permanent=True)),
    path('adm/production/plan/', RedirectView.as_view(url='/production/task/plan/', permanent=True)),
    
    # OA系统更多重定向规则
    path('adm/oa/', RedirectView.as_view(url='/oa/', permanent=True)),
    path('adm/oa/approval/', RedirectView.as_view(url='/oa/approval/', permanent=True)),
    path('adm/oa/notice/', RedirectView.as_view(url='/oa/notice/', permanent=True)),
    
    # 财务系统更多重定向规则
    path('adm/finance/budget/', RedirectView.as_view(url='/finance/', permanent=True)),
    path('adm/finance/report/', RedirectView.as_view(url='/finance/', permanent=True)),
    
    # 客户管理更多重定向规则
    path('adm/customer/contact/', RedirectView.as_view(url='/customer/', permanent=True)),
    path('adm/customer/followup/', RedirectView.as_view(url='/customer/', permanent=True)),
    
    # 云盘相关重定向规则
    path('adm/cloud/', RedirectView.as_view(url='/cloud/', permanent=True)),
    path('adm/cloud/file/', RedirectView.as_view(url='/cloud/file/', permanent=True)),
    
    # AI相关重定向规则
    path('adm/ai/', RedirectView.as_view(url='/ai/', permanent=True)),
    path('adm/ai/chat/', RedirectView.as_view(url='/ai/chat/', permanent=True)),
    
    # 删除指向自身的冗余重定向，避免循环与错误跳转
    
    # 数据列表和详情页面通用重定向规则
    # 基础数据
    path('basedata/datalist/', RedirectView.as_view(url='/basedata/', permanent=True)),
    path('basedata/detail/', RedirectView.as_view(url='/basedata/', permanent=True)),
    
    # 项目管理
    path('project/detail/', RedirectView.as_view(url='/project/', permanent=True)),
    path('project/list/', RedirectView.as_view(url='/project/', permanent=True)),
    path('project/task/list/', RedirectView.as_view(url='/project/task/', permanent=True)),
    path('project/task/detail/', RedirectView.as_view(url='/project/task/', permanent=True)),
    path('project/document/list/', RedirectView.as_view(url='/project/document/', permanent=True)),
    path('project/document/detail/', RedirectView.as_view(url='/project/document/', permanent=True)),
    
    # 生产管理
    path('production/datalist/', RedirectView.as_view(url='/production/', permanent=True)),
    path('production/detail/', RedirectView.as_view(url='/production/', permanent=True)),
    path('production/procedure/detail/', RedirectView.as_view(url='/production/procedure/', permanent=True)),
    
    # 客户管理
    path('customer/list/', RedirectView.as_view(url='/customer/', permanent=True)),
    
    # 合同管理模块重定向规则 - 修复basedata路径
    path('basedata/contract/category/', RedirectView.as_view(url='/contract/category/', permanent=True)),
    path('basedata/contract/productcategory/', RedirectView.as_view(url='/contract/productcategory/', permanent=True)),
    path('basedata/contract/product/', RedirectView.as_view(url='/contract/product/', permanent=True)),
    path('basedata/contract/service/', RedirectView.as_view(url='/contract/servicecategory/', permanent=True)),
    path('basedata/contract/supplier/', RedirectView.as_view(url='/contract/supplier/', permanent=True)),
    path('basedata/contract/purchasecategory/', RedirectView.as_view(url='/contract/purchasecategory/', permanent=True)),
    path('basedata/contract/purchase/', RedirectView.as_view(url='/contract/purchase/', permanent=True)),
    
    # 合同模块原有路由
    path('contract/datalist/', RedirectView.as_view(url='/contract/', permanent=True)),
    path('contract/detail/', RedirectView.as_view(url='/contract/', permanent=True)),
    path('contract/archive/detail/', RedirectView.as_view(url='/contract/archive/', permanent=True)),
    
    # 财务管理
    path('finance/detail/', RedirectView.as_view(url='/finance/', permanent=True)),
    path('finance/invoice/detail/', RedirectView.as_view(url='/finance/invoice/', permanent=True)),
    path('finance/payment/detail/', RedirectView.as_view(url='/finance/payment/', permanent=True)),
    
    # OA系统
    path('oa/datalist/', RedirectView.as_view(url='/oa/', permanent=True)),
    path('oa/detail/', RedirectView.as_view(url='/oa/', permanent=True)),
    path('oa/approval/detail/', RedirectView.as_view(url='/oa/approval/', permanent=True)),
    path('oa/meeting/detail/', RedirectView.as_view(url='/oa/meeting/', permanent=True)),
    
    # 移除过度通用的重定向，保留明确的 include 与必要的旧路径映射
    
    # 详细页面通用规则
    # path('<path:app>/detail/<path:pk>/', RedirectView.as_view(url='/', permanent=True)),
    # path('<path:app>/info/<path:pk>/', RedirectView.as_view(url='/', permanent=True)),
    # path('<path:app>/edit/<path:pk>/', RedirectView.as_view(url='/', permanent=True)),
    # path('<path:app>/add/', RedirectView.as_view(url='/', permanent=True)),
    # path('<path:app>/delete/', RedirectView.as_view(url='/', permanent=True)),
    
    # 数据操作通用规则
    # path('<path:app>/save/', RedirectView.as_view(url='/', permanent=True)),
    # path('<path:app>/update/', RedirectView.as_view(url='/', permanent=True)),
    # path('<path:app>/submit/', RedirectView.as_view(url='/', permanent=True)),
    # path('<path:app>/cancel/', RedirectView.as_view(url='/', permanent=True)),
    
    # 模块子页面通用规则
    # path('<path:module>/<path:submodule>/list/', RedirectView.as_view(url='/', permanent=True)),
    # path('<path:module>/<path:submodule>/data/', RedirectView.as_view(url='/', permanent=True)),
    # path('<path:module>/<path:submodule>/manage/', RedirectView.as_view(url='/', permanent=True)),
    # path('<path:module>/<path:submodule>/setting/', RedirectView.as_view(url='/', permanent=True)),
    
    # adm前缀的详细规则
    # path('adm/<path:app>/detail/<path:pk>/', RedirectView.as_view(url='/', permanent=True)),
    # path('adm/<path:app>/info/<path:pk>/', RedirectView.as_view(url='/', permanent=True)),
    # path('adm/<path:app>/edit/<path:pk>/', RedirectView.as_view(url='/', permanent=True)),
    # path('adm/<path:app>/add/', RedirectView.as_view(url='/', permanent=True)),
    # path('adm/<path:app>/delete/', RedirectView.as_view(url='/', permanent=True)),
    
    # 移除根路径及全局捕获重定向，避免错误重定向与循环

] + static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0]) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + static(settings.TEMP_URL, document_root=settings.TEMP_DIR)
