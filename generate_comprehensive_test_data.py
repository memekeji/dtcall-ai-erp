#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import random
import time
from datetime import timedelta, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if len(sys.argv) > 1 and sys.argv[1].startswith('--settings='):
    settings_module = sys.argv[1].split('=')[1]
    os.environ['DJANGO_SETTINGS_MODULE'] = settings_module
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group, Permission
from django.utils import timezone
from django.db import transaction

from apps.user.models import Admin, Position as UserPosition, Department as UserDeptModel
from apps.customer.models import Customer, Contact, CustomerSource, CustomerGrade, CustomerIntent
from apps.project.models import Project, ProjectCategory, Task, ProjectStage
from apps.system.models import (
    Notice as SystemNotice, Vehicle, AssetCategory, AssetBrand, Asset,
    VehicleMaintenance, Seal, SealApplication, DocumentCategory, Document
)
from apps.oa.models import MeetingRoom, MeetingRecord, ApprovalFlow, ApprovalRequest, ApprovalRecord, ApprovalStep, Schedule
from apps.personal.models import PersonalSchedule, WorkRecord, WorkReport
from apps.message.models import Message as UserMessage
from apps.finance.models import Expense, Income, Invoice, Payment, InvoiceRequest
from apps.contract.models import Contract, ContractCategory, Supplier, Purchase, Product, ProductCate
from apps.production.models import (
    ProductionPlan, ProductionTask, ProductionProcedure, BOM, BOMItem,
    ProcedureSet, ProcessRoute, Equipment, QualityCheck, MaterialRequest,
    ResourceConsumption, WorkCompletionReport, ProductReceipt
)
from apps.ai.models import AIWorkflow, WorkflowNode, WorkflowConnection


class ComprehensiveTestDataGenerator:
    def __init__(self):
        self.current_time = int(time.time())
        self.now = timezone.now()
        self.departments = {}
        self.positions = {}
        self.users = {}
        self.customers = {}
        self.suppliers = {}
        self.projects = {}
        self.workflows = []

    def generate_random_phone(self):
        prefixes = ['130', '131', '132', '133', '134', '135', '136', '137', '138', '139', '150', '151', '152', '153', '155', '156', '157', '158', '159', '180', '181', '182', '183', '184', '185', '186', '187', '188', '189']
        return random.choice(prefixes) + ''.join(random.choices('0123456789', k=8))

    def generate_random_date(self, days_back=365, days_forward=0):
        if days_back > 0:
            start = self.now - timedelta(days=days_back)
        else:
            start = self.now
        if days_forward > 0:
            end = self.now + timedelta(days=days_forward)
        else:
            end = self.now
        random_seconds = random.randint(0, int((end - start).total_seconds()))
        return start + timedelta(seconds=random_seconds)

    def generate_random_date_field(self, days_back=365, days_forward=0):
        dt = self.generate_random_date(days_back, days_forward)
        return dt.date() if hasattr(dt, 'date') else dt

    def bigint_time(self, dt=None):
        if dt is None:
            dt = self.now
        return int(dt.timestamp())

    def get_dept_id_by_name(self, name):
        dept = self.departments.get(name)
        return dept.id if dept else 0

    def generate_all_test_data(self):
        print("=" * 80)
        print("开始生成全面系统测试数据")
        print("=" * 80)

        try:
            with transaction.atomic():
                self.generate_organization_data()
                self.generate_resource_data()
                self.generate_work_data()
                self.generate_project_data()

            self.print_summary()
            print("\n✅ 测试数据生成成功！")
            print("（业务数据、项目生产、AI工作流模块待完善）")
        except Exception as e:
            print(f"\n❌ 生成数据时出错: {e}")
            import traceback
            traceback.print_exc()

    def generate_organization_data(self):
        print("\n[1/6] 生成组织架构数据...")

        dept_data = [
            {'name': '总公司', 'pid': 0, 'sort': 1, 'desc': '公司总部'},
            {'name': '研发中心', 'pid': 1, 'sort': 1, 'desc': '产品研发与技术开发'},
            {'name': '产品设计部', 'pid': 2, 'sort': 1, 'desc': '产品设计与规划'},
            {'name': '技术开发部', 'pid': 2, 'sort': 2, 'desc': '技术研发与实现'},
            {'name': '测试部', 'pid': 2, 'sort': 3, 'desc': '质量测试与保障'},
            {'name': '运营中心', 'pid': 1, 'sort': 2, 'desc': '市场运营与推广'},
            {'name': '市场部', 'pid': 6, 'sort': 1, 'desc': '市场开拓与品牌建设'},
            {'name': '销售部', 'pid': 6, 'sort': 2, 'desc': '产品销售与客户服务'},
            {'name': '客服部', 'pid': 6, 'sort': 3, 'desc': '客户服务与支持'},
            {'name': '财务中心', 'pid': 1, 'sort': 3, 'desc': '财务管理与核算'},
            {'name': '人力资源部', 'pid': 1, 'sort': 4, 'desc': '人力资源管理'},
            {'name': '行政部', 'pid': 1, 'sort': 5, 'desc': '行政后勤管理'},
            {'name': '生产中心', 'pid': 1, 'sort': 6, 'desc': '生产制造管理'},
            {'name': '生产车间一', 'pid': 13, 'sort': 1, 'desc': '主要生产线'},
            {'name': '生产车间二', 'pid': 13, 'sort': 2, 'desc': '次要生产线'},
            {'name': '质量管理部', 'pid': 13, 'sort': 3, 'desc': '质量检验与控制'},
            {'name': '采购部', 'pid': 1, 'sort': 7, 'desc': '物资采购与供应'},
            {'name': '仓储部', 'pid': 1, 'sort': 8, 'desc': '物资仓储与物流'},
        ]

        for dept in dept_data:
            d, created = UserDeptModel.objects.update_or_create(
                title=dept['name'],
                defaults={
                    'pid': 0,
                    'sort': dept['sort'],
                    'status': 1,
                }
            )
            self.departments[dept['name']] = d

        self.departments = {d.title: d for d in UserDeptModel.objects.all()}

        pid_map = {
            '总公司': 0,
            '研发中心': 1,
            '产品设计部': 2,
            '技术开发部': 2,
            '测试部': 2,
            '运营中心': 1,
            '市场部': 6,
            '销售部': 6,
            '客服部': 6,
            '财务中心': 1,
            '人力资源部': 1,
            '行政部': 1,
            '生产中心': 1,
            '生产车间一': 13,
            '生产车间二': 13,
            '质量管理部': 13,
            '采购部': 1,
            '仓储部': 1,
        }

        for dept_name, parent_name in pid_map.items():
            if dept_name != '总公司':
                dept = self.departments.get(dept_name)
                parent = self.departments.get(parent_name)
                if dept and parent:
                    dept.pid = parent.id
                    dept.save()

        self.departments = {d.title: d for d in UserDeptModel.objects.all()}

        print(f"  - 已创建 {len(self.departments)} 个部门")

        position_data = [
            {'title': '总经理', 'did_name': '总公司', 'desc': '公司最高管理者'},
            {'title': '副总经理', 'did_name': '总公司', 'desc': '协助总经理工作'},
            {'title': '技术总监', 'did_name': '研发中心', 'desc': '技术研发负责人'},
            {'title': '产品总监', 'did_name': '产品设计部', 'desc': '产品规划负责人'},
            {'title': '产品经理', 'did_name': '产品设计部', 'desc': '产品设计与管理'},
            {'title': 'UI设计师', 'did_name': '产品设计部', 'desc': '用户界面设计'},
            {'title': '前端开发工程师', 'did_name': '技术开发部', 'desc': '前端开发与维护'},
            {'title': '后端开发工程师', 'did_name': '技术开发部', 'desc': '后端开发与维护'},
            {'title': '全栈工程师', 'did_name': '技术开发部', 'desc': '全栈开发'},
            {'title': '测试工程师', 'did_name': '测试部', 'desc': '软件测试与质量保障'},
            {'title': '自动化测试工程师', 'did_name': '测试部', 'desc': '自动化测试脚本开发'},
            {'title': '市场总监', 'did_name': '市场部', 'desc': '市场营销负责人'},
            {'title': '市场专员', 'did_name': '市场部', 'desc': '市场推广活动执行'},
            {'title': '销售总监', 'did_name': '销售部', 'desc': '销售团队负责人'},
            {'title': '销售经理', 'did_name': '销售部', 'desc': '销售业务管理'},
            {'title': '销售代表', 'did_name': '销售部', 'desc': '产品销售'},
            {'title': '客服经理', 'did_name': '客服部', 'desc': '客服团队管理'},
            {'title': '客服专员', 'did_name': '客服部', 'desc': '客户咨询与支持'},
            {'title': '财务总监', 'did_name': '财务中心', 'desc': '财务管理负责人'},
            {'title': '会计', 'did_name': '财务中心', 'desc': '财务核算'},
            {'title': '出纳', 'did_name': '财务中心', 'desc': '资金管理'},
            {'title': 'HR总监', 'did_name': '人力资源部', 'desc': '人力资源负责人'},
            {'title': '招聘专员', 'did_name': '人力资源部', 'desc': '人才招聘'},
            {'title': '行政经理', 'did_name': '行政部', 'desc': '行政后勤管理'},
            {'title': '行政专员', 'did_name': '行政部', 'desc': '行政事务处理'},
            {'title': '生产总监', 'did_name': '生产中心', 'desc': '生产管理负责人'},
            {'title': '生产主管', 'did_name': '生产车间一', 'desc': '生产车间管理'},
            {'title': '生产工人', 'did_name': '生产车间一', 'desc': '产品生产制造'},
            {'title': '质量经理', 'did_name': '质量管理部', 'desc': '质量管理负责人'},
            {'title': '质检员', 'did_name': '质量管理部', 'desc': '产品质量检验'},
            {'title': '采购经理', 'did_name': '采购部', 'desc': '采购管理'},
            {'title': '采购专员', 'did_name': '采购部', 'desc': '物资采购执行'},
            {'title': '仓库主管', 'did_name': '仓储部', 'desc': '仓储管理'},
            {'title': '仓库管理员', 'did_name': '仓储部', 'desc': '仓库物资管理'},
        ]

        for i, pos in enumerate(position_data):
            did = self.get_dept_id_by_name(pos['did_name'])
            p, created = UserPosition.objects.update_or_create(
                title=pos['title'],
                defaults={
                    'did': did,
                    'desc': pos['desc'],
                    'status': 1,
                    'sort': i + 1
                }
            )
            self.positions[pos['title']] = p

        print(f"  - 已创建 {len(self.positions)} 个岗位")

        roles_data = [
            {'name': '系统管理员', 'permissions': ['all']},
            {'name': '部门经理', 'permissions': ['department_manage']},
            {'name': '普通员工', 'permissions': ['basic_access']},
            {'name': '财务人员', 'permissions': ['finance_access']},
            {'name': '销售人员', 'permissions': ['sales_access']},
            {'name': '项目管理人员', 'permissions': ['project_access']},
            {'name': '生产人员', 'permissions': ['production_access']},
        ]

        for role in roles_data:
            g, created = Group.objects.update_or_create(
                name=role['name'],
                defaults={}
            )

        print(f"  - 已创建 {len(roles_data)} 个角色")

        user_data = [
            {'username': 'admin', 'did_name': '总公司', 'pid_title': '总经理', 'realname': '系统管理员', 'email': 'admin@dtcall.com', 'phone': '13800138000', 'status': 1},
            {'username': 'zhangwei', 'did_name': '总公司', 'pid_title': '副总经理', 'realname': '张伟', 'email': 'zhangwei@dtcall.com', 'phone': '13800138001', 'status': 1},
            {'username': 'liuxiang', 'did_name': '研发中心', 'pid_title': '技术总监', 'realname': '刘翔', 'email': 'liuxiang@dtcall.com', 'phone': '13800138002', 'status': 1},
            {'username': 'wangfang', 'did_name': '产品设计部', 'pid_title': '产品总监', 'realname': '王芳', 'email': 'wangfang@dtcall.com', 'phone': '13800138003', 'status': 1},
            {'username': 'zhaoli', 'did_name': '产品设计部', 'pid_title': '产品经理', 'realname': '赵丽', 'email': 'zhaoli@dtcall.com', 'phone': '13800138004', 'status': 1},
            {'username': 'sunming', 'did_name': '技术开发部', 'pid_title': '后端开发工程师', 'realname': '孙明', 'email': 'sunming@dtcall.com', 'phone': '13800138005', 'status': 1},
            {'username': 'zhouqiang', 'did_name': '技术开发部', 'pid_title': '前端开发工程师', 'realname': '周强', 'email': 'zhouqiang@dtcall.com', 'phone': '13800138006', 'status': 1},
            {'username': 'wujun', 'did_name': '测试部', 'pid_title': '测试工程师', 'realname': '吴军', 'email': 'wujun@dtcall.com', 'phone': '13800138007', 'status': 1},
            {'username': 'zhenghong', 'did_name': '市场部', 'pid_title': '市场总监', 'realname': '郑红', 'email': 'zhenghong@dtcall.com', 'phone': '13800138008', 'status': 1},
            {'username': 'huangjie', 'did_name': '销售部', 'pid_title': '销售总监', 'realname': '黄洁', 'email': 'huangjie@dtcall.com', 'phone': '13800138009', 'status': 1},
            {'username': 'xuli', 'did_name': '销售部', 'pid_title': '销售经理', 'realname': '徐丽', 'email': 'xuli@dtcall.com', 'phone': '13800138010', 'status': 1},
            {'username': 'caoyun', 'did_name': '财务中心', 'pid_title': '财务总监', 'realname': '曹云', 'email': 'caoyun@dtcall.com', 'phone': '13800138011', 'status': 1},
            {'username': 'lixin', 'did_name': '财务中心', 'pid_title': '会计', 'realname': '李欣', 'email': 'lixin@dtcall.com', 'phone': '13800138012', 'status': 1},
            {'username': 'majun', 'did_name': '人力资源部', 'pid_title': 'HR总监', 'realname': '马军', 'email': 'majun@dtcall.com', 'phone': '13800138013', 'status': 1},
            {'username': 'yangli', 'did_name': '生产中心', 'pid_title': '生产总监', 'realname': '杨莉', 'email': 'yangli@dtcall.com', 'phone': '13800138014', 'status': 1},
            {'username': 'tangcheng', 'did_name': '生产车间一', 'pid_title': '生产主管', 'realname': '唐成', 'email': 'tangcheng@dtcall.com', 'phone': '13800138015', 'status': 1},
            {'username': 'songgang', 'did_name': '质量管理部', 'pid_title': '质量经理', 'realname': '宋刚', 'email': 'songgang@dtcall.com', 'phone': '13800138016', 'status': 1},
            {'username': 'duanbin', 'did_name': '采购部', 'pid_title': '采购经理', 'realname': '段斌', 'email': 'duanbin@dtcall.com', 'phone': '13800138017', 'status': 1},
            {'username': 'panyong', 'did_name': '仓储部', 'pid_title': '仓库主管', 'realname': '潘勇', 'email': 'panyong@dtcall.com', 'phone': '13800138018', 'status': 1},
            {'username': 'luona', 'did_name': '客服部', 'pid_title': '客服经理', 'realname': '罗娜', 'email': 'luona@dtcall.com', 'phone': '13800138019', 'status': 1},
        ]

        for user_info in user_data:
            dept = self.departments.get(user_info['did_name'])
            position = self.positions.get(user_info['pid_title'])
            u, created = Admin.objects.update_or_create(
                username=user_info['username'],
                defaults={
                    'did': dept.id if dept else 0,
                    'pid': position.id if position else 0,
                    'name': user_info['realname'],
                    'email': user_info['email'],
                    'mobile': user_info['phone'],
                    'pwd': make_password('123456'),
                    'status': user_info['status'],
                    'create_time': self.current_time,
                    'update_time': self.current_time,
                }
            )
            self.users[user_info['username']] = u

        print(f"  - 已创建 {len(self.users)} 个用户")

    def generate_resource_data(self):
        print("\n[2/6] 生成资源管理数据...")

        asset_categories = [
            {'name': '电子设备', 'code': 'ELEC'},
            {'name': '办公家具', 'code': 'FURN'},
            {'name': '生产设备', 'code': 'PROD'},
            {'name': '运输设备', 'code': 'TRANS'},
            {'name': '房屋建筑', 'code': 'BUILD'},
        ]

        for cat in asset_categories:
            AssetCategory.objects.update_or_create(
                code=cat['code'],
                defaults={'name': cat['name'], 'is_active': True}
            )

        asset_brands = [
            {'name': '联想', 'code': 'LENOVO'},
            {'name': '戴尔', 'code': 'DELL'},
            {'name': '惠普', 'code': 'HP'},
            {'name': '苹果', 'code': 'APPLE'},
            {'name': '华为', 'code': 'HUAWEI'},
        ]

        for brand in asset_brands:
            AssetBrand.objects.update_or_create(
                code=brand['code'],
                defaults={'name': brand['name']}
            )

        categories = list(AssetCategory.objects.all())
        brands = list(AssetBrand.objects.all())
        users_list = list(self.users.values())

        asset_names = [
            'ThinkPad X1 Carbon笔记本电脑', 'iMac台式机', '戴尔显示器27寸',
            '办公桌', '办公椅', '文件柜', '会议桌', '投影仪',
            'CNC数控机床', '激光切割机', '冲压机', '焊接设备',
            '商务用车', '货车', '叉车'
        ]

        for i, name in enumerate(asset_names[:25]):
            Asset.objects.update_or_create(
                asset_number=f'AST{random.randint(10000, 99999)}',
                defaults={
                    'name': name,
                    'category': random.choice(categories) if categories else None,
                    'brand': random.choice(brands) if brands else None,
                    'model': f'Model-{random.randint(1000, 9999)}',
                    'purchase_date': self.generate_random_date_field(days_back=730),
                    'purchase_price': Decimal(random.randint(1000, 100000)),
                    'status': random.choice(['normal', 'repair', 'scrap']),
                    'location': f'办公楼{random.randint(1, 5)}层{random.randint(101, 599)}室',
                    'responsible_person': random.choice(users_list) if users_list else None,
                }
            )

        print(f"  - 已创建 {Asset.objects.count()} 条固定资产记录")

        vehicle_names = ['商务MPV GL8', '商务轿车帕萨特', '货车东风', '货车解放', '商务轿车奥迪A6', '商务SUV']

        for name in vehicle_names:
            Vehicle.objects.update_or_create(
                license_plate=f'{random.choice(["京", "沪", "粤", "川"])}{random.choice(["A", "B", "C", "D"])}{random.randint(10000, 99999)}',
                defaults={
                    'brand': name.split()[0] if name.split() else '未知',
                    'model': f'{random.choice(["舒适版", "豪华版", "旗舰版"])}',
                    'color': random.choice(['黑色', '白色', '灰色', '银色', '蓝色']),
                    'engine_number': f'ENG{random.randint(100000, 999999)}',
                    'frame_number': f'VIN{random.randint(100000, 999999)}',
                    'purchase_date': self.generate_random_date_field(days_back=1095),
                    'purchase_price': Decimal(random.randint(100000, 500000)),
                    'status': random.choice(['normal', 'repair', 'scrap']),
                    'insurance_expire': self.generate_random_date_field(days_forward=365),
                    'annual_inspection': self.generate_random_date_field(days_forward=365),
                    'driver': random.choice(users_list) if users_list else None,
                }
            )

        print(f"  - 已创建 {Vehicle.objects.count()} 条车辆记录")

        meeting_rooms = [
            {'name': '一楼会议室A', 'capacity': 20, 'location': '办公楼1层'},
            {'name': '二楼会议室B', 'capacity': 15, 'location': '办公楼2层'},
            {'name': '三楼会议室C', 'capacity': 30, 'location': '办公楼3层'},
            {'name': 'VIP会议室', 'capacity': 10, 'location': '办公楼5层'},
            {'name': '培训室', 'capacity': 50, 'location': '办公楼4层'},
        ]

        for room in meeting_rooms:
            MeetingRoom.objects.update_or_create(
                name=room['name'],
                defaults={
                    'code': f'ROOM{random.randint(100, 999)}',
                    'capacity': room['capacity'],
                    'location': room['location'],
                    'has_projector': True,
                    'has_whiteboard': True,
                    'has_tv': False,
                    'has_phone': False,
                    'has_wifi': True,
                    'status': 'active',
                }
            )

        rooms = list(MeetingRoom.objects.all())

        for i in range(15):
            start_time = self.generate_random_date(days_back=90, days_forward=30)
            end_time = start_time + timedelta(hours=random.randint(1, 3))
            meeting, created = MeetingRecord.objects.update_or_create(
                title=f'{random.choice(["周例会", "项目评审会", "头脑风暴", "月度总结会", "培训会", "客户洽谈会"])} {i+1}次',
                defaults={
                    'meeting_type': random.choice(['regular', 'project', 'training', 'customer']),
                    'meeting_date': start_time,
                    'meeting_end_time': end_time,
                    'duration': int((end_time - start_time).total_seconds() / 60),
                    'room': random.choice(rooms) if rooms else None,
                    'location': random.choice(rooms).location if rooms else '',
                    'host': random.choice(users_list) if users_list else None,
                    'recorder': random.choice(users_list) if users_list else None,
                    'department': random.choice(list(self.departments.values())) if self.departments else None,
                    'status': random.choice(['scheduled', 'in_progress', 'completed', 'cancelled']),
                    'content': f'会议讨论内容{i+1}',
                    'summary': f'会议总结{i+1}',
                }
            )

        print(f"  - 已创建 {MeetingRecord.objects.count()} 条会议记录")

        doc_categories = [
            {'name': '公司制度', 'code': 'POLICY'},
            {'name': '通知公告', 'code': 'NOTICE'},
            {'name': '合同文档', 'code': 'CONTRACT'},
            {'name': '技术文档', 'code': 'TECH'},
            {'name': '人事文档', 'code': 'HR'},
        ]

        for cat in doc_categories:
            DocumentCategory.objects.update_or_create(
                code=cat['code'],
                defaults={'name': cat['name'], 'is_active': True}
            )

        categories = list(DocumentCategory.objects.all())

        for i in range(20):
            if categories:
                Document.objects.update_or_create(
                    document_number=f'DOC{self.now.year}{random.randint(1000, 9999)}',
                    defaults={
                        'title': f'公文{i+1}',
                        'category': random.choice(categories),
                        'content': f'公文内容{i+1}',
                        'summary': f'公文摘要{i+1}',
                        'author': random.choice(users_list) if users_list else None,
                        'status': random.choice(['draft', 'pending', 'approved', 'published']),
                        'urgency': random.choice(['normal', 'urgent', 'very_urgent']),
                        'security_level': random.choice(['public', 'internal', 'confidential']),
                    }
                )

        print(f"  - 已创建 {Document.objects.count()} 条公文记录")

        seal_types = ['公司公章', '财务章', '合同章', '法人章']

        for seal_name in seal_types:
            Seal.objects.update_or_create(
                name=seal_name,
                defaults={
                    'seal_type': random.choice(['company', 'contract', 'finance', 'legal']),
                    'is_active': True,
                    'keeper': random.choice(users_list) if users_list else None,
                }
            )

        print(f"  - 已创建 {Seal.objects.count()} 条印章记录")

    def generate_work_data(self):
        print("\n[3/6] 生成工作管理数据...")

        users_list = list(self.users.values())

        for i in range(30):
            start_date = self.generate_random_date(days_back=90)
            end_date = start_date + timedelta(hours=random.randint(1, 8))
            PersonalSchedule.objects.update_or_create(
                title=f'日程安排 {i+1}',
                defaults={
                    'user': random.choice(users_list) if users_list else None,
                    'start_time': start_date,
                    'end_time': end_date,
                    'content': f'日程内容{i+1}',
                    'location': f'地点{random.randint(1, 10)}',
                    'reminder_time': start_date - timedelta(minutes=random.choice([15, 30, 60])),
                    'status': random.choice(['pending', 'in_progress', 'completed']),
                }
            )

        print(f"  - 已创建 {PersonalSchedule.objects.count()} 条日程记录")

        for i in range(25):
            work_date = self.generate_random_date(days_back=60)
            if users_list:
                WorkRecord.objects.update_or_create(
                    title=f'工作记录 {i+1}',
                    defaults={
                        'content': f'工作内容{i+1}',
                        'work_type': random.choice(['daily', 'project', 'meeting', 'training']),
                        'work_date': work_date.date(),
                        'start_time': f'{random.randint(7, 9)}:{random.randint(0, 59):02d}',
                        'end_time': f'{random.randint(17, 19)}:{random.randint(0, 59):02d}',
                        'duration': random.randint(8, 10),
                        'progress': random.randint(0, 100),
                        'user': random.choice(users_list),
                    }
                )

        print(f"  - 已创建 {WorkRecord.objects.count()} 条工作记录")

        for i in range(20):
            report_date = self.generate_random_date_field(days_back=30)
            if users_list:
                WorkReport.objects.update_or_create(
                    title=f'工作汇报 {i+1}',
                    defaults={
                        'report_type': random.choice(['daily', 'weekly', 'monthly']),
                        'report_date': report_date,
                        'summary': f'工作总结{i+1}',
                        'completed_work': f'已完成工作{i+1}',
                        'next_work': f'下期工作计划{i+1}',
                        'problems': f'存在问题{i+1}' if random.random() > 0.5 else '',
                        'user': random.choice(users_list),
                        'is_submitted': random.choice([True, False]),
                    }
                )

        print(f"  - 已创建 {WorkReport.objects.count()} 条工作汇报")

        print(f"  - 审批流程数据已跳过")

    def generate_project_data(self):
        print("\n[4/6] 生成项目管理数据...")

        users_list = list(self.users.values())

        project_categories = [
            {'name': '软件开发', 'code': 'SOFTWARE'},
            {'name': '系统集成', 'code': 'INTEGRATION'},
            {'name': '产品设计', 'code': 'DESIGN'},
            {'name': '咨询服务', 'code': 'CONSULTING'},
            {'name': '运维服务', 'code': 'OPERATION'},
        ]

        for cat in project_categories:
            ProjectCategory.objects.update_or_create(
                code=cat['code'],
                defaults={'name': cat['name'], 'is_active': True}
            )

        categories = list(ProjectCategory.objects.all())

        for i in range(15):
            start_date = self.generate_random_date(days_back=180)
            end_date = start_date + timedelta(days=random.randint(30, 180))
            if users_list and categories:
                Project.objects.update_or_create(
                    code=f'PRJ{self.now.year}{random.randint(1000, 9999)}',
                    defaults={
                        'name': f'项目 {i+1}',
                        'description': f'项目描述{i+1}',
                        'category': random.choice(categories),
                        'manager': random.choice(users_list),
                        'start_date': start_date.date(),
                        'end_date': end_date.date(),
                        'budget': Decimal(random.randint(50000, 5000000)),
                        'status': random.choice([1, 2, 3, 4, 5]),
                        'priority': random.choice([1, 2, 3, 4]),
                        'progress': random.randint(0, 100),
                        'creator': random.choice(users_list),
                    }
                )

        projects = list(Project.objects.all())

        for i in range(40):
            start_date = self.generate_random_date(days_back=90)
            end_date = start_date + timedelta(days=random.randint(7, 60))
            if users_list and projects:
                Task.objects.update_or_create(
                    title=f'任务 {i+1}',
                    defaults={
                        'description': f'任务描述{i+1}',
                        'project': random.choice(projects),
                        'assignee': random.choice(users_list),
                        'start_date': start_date.date(),
                        'end_date': end_date.date(),
                        'estimated_hours': random.randint(8, 80),
                        'actual_hours': random.randint(0, 80),
                        'status': random.choice([1, 2, 3, 4, 5]),
                        'priority': random.choice([1, 2, 3, 4]),
                        'progress': random.randint(0, 100),
                        'creator': random.choice(users_list),
                    }
                )

        print(f"  - 已创建 {Project.objects.count()} 个项目")
        print(f"  - 已创建 {Task.objects.count()} 个任务")

    def generate_business_data(self):
        print("\n[4/6] 生成业务数据...")

        users_list = list(self.users.values())

        customer_sources = ['电话营销', '网络推广', '客户推荐', '展会', '合作伙伴']
        for source in customer_sources:
            CustomerSource.objects.update_or_create(name=source, defaults={'status': 1})

        customer_grades = ['A', 'B', 'C', 'D']
        for grade in customer_grades:
            CustomerGrade.objects.update_or_create(name=grade, defaults={'status': 1})

        customer_intents = ['高', '中', '低']
        for intent in customer_intents:
            CustomerIntent.objects.update_or_create(name=intent, defaults={'status': 1})

        sources = list(CustomerSource.objects.all())
        grades = list(CustomerGrade.objects.all())
        intents = list(CustomerIntent.objects.all())

        for i in range(30):
            customer, created = Customer.objects.update_or_create(
                name=f'客户公司 {i+1}',
                defaults={
                    'customer_type': random.choice(['enterprise', 'individual']),
                    'source': random.choice(sources) if sources else None,
                    'grade': random.choice(grades) if grades else None,
                    'intent': random.choice(intents) if intents else None,
                    'contact': f'联系人{i+1}',
                    'phone': self.generate_random_phone(),
                    'email': f'customer{i+1}@example.com',
                    'address': f'地址{i+1}',
                    'status': 1,
                    'create_user': random.choice(users_list) if users_list else None,
                }
            )
            self.customers[f'客户公司 {i+1}'] = customer

        print(f"  - 已创建 {Customer.objects.count()} 条客户记录")

        for i in range(20):
            Contact.objects.update_or_create(
                name=f'联系人 {i+1}',
                defaults={
                    'customer': random.choice(list(self.customers.values())) if self.customers else None,
                    'name': f'联系人{i+1}',
                    'phone': self.generate_random_phone(),
                    'email': f'contact{i+1}@example.com',
                    'position': random.choice(['总经理', '经理', '主管', '员工']),
                    'is_primary': random.choice([True, False]),
                }
            )

        print(f"  - 已创建 {Contact.objects.count()} 条联系人记录")

        supplier_names = [f'供应商{i+1}' for i in range(20)]
        for name in supplier_names:
            Supplier.objects.update_or_create(
                name=name,
                defaults={
                    'contact': f'联系人{name}',
                    'phone': self.generate_random_phone(),
                    'address': f'地址{name}',
                    'status': 1,
                }
            )

        suppliers = list(Supplier.objects.all())

        for i in range(15):
            Contract.objects.update_or_create(
                number=f'CT{self.now.year}{random.randint(10000, 99999)}',
                defaults={
                    'title': f'合同 {i+1}',
                    'supplier': random.choice(suppliers) if suppliers else None,
                    'contract_type': random.choice(['purchase', 'sales', 'service']),
                    'amount': Decimal(random.randint(10000, 1000000)),
                    'sign_date': self.generate_random_date_field(days_back=365),
                    'start_date': self.generate_random_date_field(days_back=180),
                    'end_date': self.generate_random_date_field(days_forward=365),
                    'status': random.choice(['draft', 'active', 'completed', 'cancelled']),
                    'create_user': random.choice(users_list) if users_list else None,
                }
            )

        print(f"  - 已创建 {Contract.objects.count()} 条合同记录")

        for i in range(25):
            Expense.objects.update_or_create(
                title=f'费用支出 {i+1}',
                defaults={
                    'type': random.choice(['travel', 'office', 'communication', 'entertainment']),
                    'amount': Decimal(random.randint(100, 50000)),
                    'apply_user': random.choice(users_list) if users_list else None,
                    'apply_date': self.generate_random_date_field(days_back=90),
                    'status': random.choice(['pending', 'approved', 'paid']),
                    'description': f'费用描述{i+1}',
                }
            )

        print(f"  - 已创建 {Expense.objects.count()} 条费用记录")

        for i in range(20):
            Income.objects.update_or_create(
                title=f'收入 {i+1}',
                defaults={
                    'type': random.choice(['sales', 'service', 'investment']),
                    'amount': Decimal(random.randint(1000, 500000)),
                    'customer': random.choice(list(self.customers.values())) if self.customers else None,
                    'income_date': self.generate_random_date_field(days_back=90),
                    'status': random.choice(['pending', 'confirmed']),
                    'description': f'收入描述{i+1}',
                }
            )

        print(f"  - 已创建 {Income.objects.count()} 条收入记录")

        for i in range(15):
            Invoice.objects.update_or_create(
                number=f'INV{self.now.year}{random.randint(10000, 99999)}',
                defaults={
                    'type': random.choice(['VAT', '普通发票']),
                    'amount': Decimal(random.randint(1000, 100000)),
                    'tax_rate': random.choice([0, 3, 6, 13]),
                    'customer': random.choice(list(self.customers.values())) if self.customers else None,
                    'invoice_date': self.generate_random_date_field(days_back=90),
                    'status': random.choice(['pending', 'issued']),
                }
            )

        print(f"  - 已创建 {Invoice.objects.count()} 条发票记录")

    def generate_project_production_data(self):
        print("\n[5/6] 生成项目与生产数据...")

        users_list = list(self.users.values())

        project_categories = ['软件开发', '系统集成', '产品设计', '咨询服务']
        for cat in project_categories:
            ProjectCategory.objects.update_or_create(name=cat, defaults={'status': 1})

        categories = list(ProjectCategory.objects.all())

        for i in range(15):
            start_date = self.generate_random_date(days_back=180)
            end_date = start_date + timedelta(days=random.randint(30, 180))
            project, created = Project.objects.update_or_create(
                name=f'项目 {i+1}',
                defaults={
                    'category': random.choice(categories) if categories else None,
                    'description': f'项目描述{i+1}',
                    'start_date': start_date.date(),
                    'end_date': end_date.date(),
                    'budget': Decimal(random.randint(50000, 5000000)),
                    'status': random.choice(['planning', 'in_progress', 'completed', 'suspended']),
                    'manager': random.choice(users_list) if users_list else None,
                }
            )
            self.projects[f'项目 {i+1}'] = project

        print(f"  - 已创建 {Project.objects.count()} 条项目记录")

        for i in range(40):
            project = random.choice(list(self.projects.values())) if self.projects else None
            Task.objects.update_or_create(
                name=f'任务 {i+1}',
                defaults={
                    'project': project,
                    'description': f'任务描述{i+1}',
                    'start_date': self.generate_random_date_field(days_back=90),
                    'end_date': self.generate_random_date_field(days_forward=90),
                    'progress': random.randint(0, 100),
                    'status': random.choice(['todo', 'in_progress', 'completed']),
                    'assignee': random.choice(users_list) if users_list else None,
                    'priority': random.choice(['low', 'medium', 'high']),
                }
            )

        print(f"  - 已创建 {Task.objects.count()} 条任务记录")

        for i in range(10):
            ProductionPlan.objects.update_or_create(
                plan_number=f'PP{self.now.year}{random.randint(1000, 9999)}',
                defaults={
                    'name': f'生产计划 {i+1}',
                    'product_name': f'产品{random.randint(1, 20)}',
                    'quantity': random.randint(100, 10000),
                    'start_date': self.generate_random_date_field(days_back=30),
                    'end_date': self.generate_random_date_field(days_forward=60),
                    'status': random.choice(['draft', 'confirmed', 'in_progress', 'completed']),
                    'create_user': random.choice(users_list) if users_list else None,
                }
            )

        print(f"  - 已创建 {ProductionPlan.objects.count()} 条生产计划记录")

        equipment_names = ['CNC数控机床', '激光切割机', '冲压机', '焊接设备', '喷涂设备', '检测设备']
        for name in equipment_names:
            Equipment.objects.update_or_create(
                name=name,
                defaults={
                    'model': f'Model-{random.randint(100, 999)}',
                    'status': random.choice(['normal', 'maintenance', 'faulty']),
                    'location': f'车间{random.randint(1, 3)}',
                    'purchase_date': self.generate_random_date_field(days_back=730),
                }
            )

        print(f"  - 已创建 {Equipment.objects.count()} 条设备记录")

    def generate_ai_workflow_data(self):
        print("\n[6/6] 生成AI工作流数据...")

        users_list = list(self.users.values())

        workflow_templates = [
            {'name': '智能客服工作流', 'description': '自动化客户咨询处理流程'},
            {'name': '合同审核工作流', 'description': 'AI辅助合同风险评估'},
            {'name': '智能招聘工作流', 'description': '简历筛选与面试安排'},
            {'name': '数据分析工作流', 'description': '业务数据自动分析与报表生成'},
        ]

        for wf_data in workflow_templates:
            workflow, created = AIWorkflow.objects.update_or_create(
                name=wf_data['name'],
                defaults={
                    'description': wf_data['description'],
                    'category': random.choice(['customer_service', 'contract', 'hr', 'analytics']),
                    'status': random.choice(['draft', 'active', 'paused']),
                    'version': '1.0',
                    'create_user': random.choice(users_list) if users_list else None,
                }
            )
            self.workflows.append(workflow)

        print(f"  - 已创建 {len(self.workflows)} 个AI工作流")

        for workflow in self.workflows:
            node_count = random.randint(3, 6)
            for i in range(node_count):
                WorkflowNode.objects.update_or_create(
                    workflow=workflow,
                    name=f'节点{i+1}',
                    defaults={
                        'node_type': random.choice(['trigger', 'action', 'condition', 'ai_process']),
                        'config': '{"key": "value"}',
                        'position_x': random.randint(100, 500),
                        'position_y': random.randint(100, 500),
                    }
                )

        print(f"  - 已创建 {WorkflowNode.objects.count()} 个工作流节点")

    def print_summary(self):
        print("\n" + "=" * 80)
        print("数据生成摘要")
        print("=" * 80)

        print(f"  组织架构: {UserDeptModel.objects.count()} 部门, {UserPosition.objects.count()} 岗位, {Admin.objects.count()} 用户")
        print(f"  客户管理: {Customer.objects.count()} 客户, {Contact.objects.count()} 联系人")
        print(f"  项目管理: {Project.objects.count()} 项目, {Task.objects.count()} 任务")
        print(f"  资产管理: {Asset.objects.count()} 资产, {Vehicle.objects.count()} 车辆")
        print(f"  会议管理: {MeetingRoom.objects.count()} 会议室, {MeetingRecord.objects.count()} 会议")
        print(f"  文档管理: {Document.objects.count()} 文档")
        print(f"  合同管理: {Contract.objects.count()} 合同, {Supplier.objects.count()} 供应商")
        print(f"  财务管理: {Expense.objects.count()} 支出, {Income.objects.count()} 收入, {Invoice.objects.count()} 发票")
        print(f"  生产管理: {ProductionPlan.objects.count()} 生产计划, {Equipment.objects.count()} 设备")
        print(f"  AI工作流: {AIWorkflow.objects.count()} 工作流, {WorkflowNode.objects.count()} 节点")


if __name__ == '__main__':
    generator = ComprehensiveTestDataGenerator()
    generator.generate_all_test_data()
