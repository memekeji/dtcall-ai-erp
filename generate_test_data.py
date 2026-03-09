#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成系统测试数据 - 极简版本
"""
import os
import sys
import random
import time
from datetime import timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 支持命令行指定 settings 参数
if len(sys.argv) > 1 and sys.argv[1].startswith('--settings='):
    settings_module = sys.argv[1].split('=')[1]
    os.environ['DJANGO_SETTINGS_MODULE'] = settings_module
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.utils import timezone

from apps.user.models import Admin, Position as UserPosition
from apps.department.models import Department as DeptModel
from apps.customer.models import (
    Customer, Contact, CustomerSource, CustomerGrade, CustomerIntent,
    CustomerField, CustomerOrder
)
from apps.project.models import Project, ProjectCategory, Task
from apps.system.models import Notice as SystemNotice, Vehicle, AssetCategory

class TestDataGenerator:
    def __init__(self):
        self.current_time = int(time.time())
        
    def generate_random_phone(self):
        prefixes = ['130', '131', '132', '133', '134', '135', '136', '137', '138', '139']
        return random.choice(prefixes) + ''.join(random.choices('0123456789', k=8))
        
    def generate_random_email(self, name=None):
        if name is None:
            names = ['test', 'user', 'demo', 'admin']
            name = random.choice(names)
        return f"{name}{random.randint(1, 9999)}@test.com"
        
    def generate_random_date(self, days_back=365):
        start = timezone.now() - timedelta(days=days_back)
        return start + timedelta(seconds=random.randint(0, int(365 * 86400)))
        
    def generate_all_test_data(self):
        print("=" * 70)
        print("开始生成系统测试数据")
        print("=" * 70)
        
        self.generate_user_data()
        self.generate_customer_data()
        self.generate_project_data()
        self.generate_system_data()
        self.print_summary()
        
    def generate_user_data(self):
        print("\n[1/4] 生成用户与权限模块测试数据...")
        
        for i, name in enumerate(['总公司', '技术研发部', '产品部', '市场部', '销售部', '财务部']):
            DeptModel.objects.get_or_create(
                name=name,
                defaults={'pid': 0, 'sort': i+1, 'status': 1}
            )
        
        for i, title in enumerate(['总经理', '技术总监', '产品经理', '开发工程师', '销售代表', '财务专员']):
            UserPosition.objects.get_or_create(
                title=title,
                defaults={'sort': i+1, 'status': 1}
            )
        
        employee_group = Group.objects.get_or_create(name='普通员工')[0]
        
        for i, (username, name) in enumerate([
            ('zhangsan', '张三'), ('lisi', '李四'), ('wangwu', '王五'),
            ('zhaoliu', '赵六'), ('qianqi', '钱七')
        ]):
            password = make_password('Test1234')
            admin, _ = Admin.objects.update_or_create(
                username=username,
                defaults={
                    'password': password,
                    'is_superuser': False,
                    'is_active': 1,
                    'is_staff': 1,
                    'name': name,
                    'email': self.generate_random_email(username),
                    'mobile': self.generate_random_phone(),
                    'status': 1,
                    'entry_time': self.current_time - random.randint(30, 365) * 86400,
                    'create_time': self.current_time - random.randint(30, 365) * 86400,
                    'update_time': self.current_time,
                }
            )
            admin.groups.add(employee_group)
        
        print(f"  ✓ 部门: {DeptModel.objects.count()} 个")
        print(f"  ✓ 职位: {UserPosition.objects.count()} 个")
        print(f"  ✓ 用户: {Admin.objects.count()} 个")
        
    def generate_customer_data(self):
        print("\n[2/4] 生成客户管理模块测试数据...")
        
        for name in ['官网', '百度推广', '朋友介绍', '展会', '广告']:
            CustomerSource.objects.get_or_create(title=name, defaults={'sort': 1, 'status': 1})
        
        for name in ['VIP客户', '重要客户', '普通客户', '潜在客户']:
            CustomerGrade.objects.get_or_create(title=name, defaults={'sort': 1, 'status': 1})
        
        for name in ['高意向', '中意向', '低意向', '已成交']:
            CustomerIntent.objects.get_or_create(name=name, defaults={'sort': 1, 'status': 1})
        
        for name, field_name in [('客户规模', 'company_size'), ('行业', 'industry'), ('年营收', 'annual_revenue')]:
            CustomerField.objects.get_or_create(
                field_name=field_name,
                defaults={'name': name, 'field_type': 'text', 'is_required': False, 'status': True}
            )
        
        admin = Admin.objects.first()
        source = CustomerSource.objects.first()
        
        for i in range(20):
            customer = Customer.objects.create(
                name=f'客户公司-{i+1}',
                customer_source=source,
                province='北京', city='海淀', address=f'中关村大街{i+1}号',
                admin_id=admin.id if admin else 1,
                create_time=self.generate_random_date(180),
            )
            
            Contact.objects.create(
                customer=customer,
                contact_person=f'联系人{i+1}',
                phone=self.generate_random_phone(),
                email=self.generate_random_email(),
                is_primary=True,
            )
        
        for i in range(10):
            customer = random.choice(Customer.objects.all()[:10])
            CustomerOrder.objects.create(
                customer=customer,
                order_number=f'ORD{self.current_time}{random.randint(1000, 9999)}{i}',
                product_name=f'产品-{i+1}',
                amount=Decimal(random.randint(10000, 500000)),
                order_date=self.generate_random_date(90).date(),
                create_user=admin,
                create_time=self.generate_random_date(90),
            )
        
        print(f"  ✓ 客户来源: {CustomerSource.objects.count()} 个")
        print(f"  ✓ 客户等级: {CustomerGrade.objects.count()} 个")
        print(f"  ✓ 客户: {Customer.objects.count()} 个")
        print(f"  ✓ 联系人: {Contact.objects.count()} 个")
        print(f"  ✓ 订单: {CustomerOrder.objects.count()} 个")
        
    def generate_project_data(self):
        print("\n[3/4] 生成项目管理模块测试数据...")
        
        for i, name in enumerate(['IT项目', '研发项目', '运营项目', '推广项目']):
            ProjectCategory.objects.get_or_create(
                code=f'PC{str(i+1).zfill(3)}',
                defaults={'name': name, 'sort_order': i+1, 'is_active': True}
            )
        
        admin = Admin.objects.first()
        category = ProjectCategory.objects.first()
        
        for i in range(15):
            project = Project.objects.create(
                name=f'项目-{i+1}',
                code=f'PJ{self.current_time}{random.randint(100, 999)}{i}',
                category=category,
                manager=admin,
                progress=random.randint(0, 100),
                start_date=self.generate_random_date(180).date(),
                end_date=self.generate_random_date(180).date() + timedelta(days=90),
                create_time=self.generate_random_date(180),
            )
            
            for j in range(3):
                Task.objects.create(
                    project=project,
                    title=f'任务-{j+1}',
                    assignee=admin,
                    status=random.randint(1, 4),
                    start_date=self.generate_random_date(30).date(),
                    end_date=self.generate_random_date(60).date(),
                )
        
        print(f"  ✓ 项目分类: {ProjectCategory.objects.count()} 个")
        print(f"  ✓ 项目: {Project.objects.count()} 个")
        print(f"  ✓ 任务: {Task.objects.count()} 个")
        
    def generate_system_data(self):
        print("\n[4/4] 生成系统管理模块测试数据...")
        
        for i, name in enumerate(['办公设备', '电子设备', '交通工具']):
            AssetCategory.objects.get_or_create(
                code=f'AC{str(i+1).zfill(3)}',
                defaults={'name': name, 'sort_order': i+1, 'is_active': True}
            )
        
        for i, (plate, model) in enumerate([('京A12345', '大众帕萨特'), ('京B67890', '丰田埃尔法')]):
            Vehicle.objects.get_or_create(
                license_plate=plate,
                defaults={
                    'model': model,
                    'status': 1,
                    'purchase_date': self.generate_random_date(365).date(),
                    'purchase_price': Decimal(random.randint(100000, 500000))
                }
            )
        
        print(f"  ✓ 资产分类: {AssetCategory.objects.count()} 个")
        print(f"  ✓ 车辆: {Vehicle.objects.count()} 个")
        
    def print_summary(self):
        print("\n" + "=" * 70)
        print("测试数据生成完成！")
        print("=" * 70)
        
        models = [
            (Admin, '管理员用户'),
            (DeptModel, '部门'),
            (UserPosition, '职位'),
            (Group, '角色'),
            (Customer, '客户'),
            (Project, '项目'),
            (AssetCategory, '资产分类'),
            (Vehicle, '车辆'),
        ]
        
        print("\n数据统计:")
        for model, name in models:
            count = model.objects.count()
            print(f"  - {name}: {count}")
        
        print("\n" + "=" * 70)
        print("测试账号:")
        print("  超级管理员: mimukeji / MImu123...")
        print("  测试用户: zhangsan / Test1234")
        print("=" * 70)


if __name__ == '__main__':
    generator = TestDataGenerator()
    generator.generate_all_test_data()
