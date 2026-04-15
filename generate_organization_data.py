#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成组织架构测试数据
覆盖：部门、岗位、职称、角色、员工等
"""
import os
import sys
import random
from datetime import datetime, timedelta

# 设置 Django 环境
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.contrib.auth import get_user_model
from apps.department.models import Department
from apps.user.models import Admin, Position
from apps.user.models.permission import DepartmentGroup

User = get_user_model()


class OrganizationDataGenerator:
    """组织架构测试数据生成器"""
    
    def __init__(self):
        self.departments = []
        self.positions = []
        self.employees = []
        self.department_groups = []
        
    def generate_departments(self):
        """生成部门数据"""
        print("\n[1/5] 生成部门数据...")
        
        # 公司架构树
        department_structure = [
            {
                'name': '总公司',
                'children': [
                    {
                        'name': '总经办',
                        'children': [
                            {'name': '总裁办'},
                            {'name': '战略发展部'},
                        ]
                    },
                    {
                        'name': '研发中心',
                        'children': [
                            {'name': '产品部'},
                            {'name': '技术部', 'children': [
                                {'name': '前端组'},
                                {'name': '后端组'},
                                {'name': '测试组'},
                                {'name': '运维组'},
                            ]},
                            {'name': '设计部'},
                        ]
                    },
                    {
                        'name': '营销中心',
                        'children': [
                            {'name': '市场部'},
                            {'name': '销售部', 'children': [
                                {'name': '销售一部'},
                                {'name': '销售二部'},
                                {'name': '销售三部'},
                            ]},
                            {'name': '客服部'},
                        ]
                    },
                    {
                        'name': '运营中心',
                        'children': [
                            {'name': '运营部'},
                            {'name': '内容部'},
                            {'name': '数据分析部'},
                        ]
                    },
                    {
                        'name': '职能中心',
                        'children': [
                            {'name': '人力资源部', 'children': [
                                {'name': '招聘组'},
                                {'name': '培训组'},
                                {'name': '薪酬绩效组'},
                            ]},
                            {'name': '财务部', 'children': [
                                {'name': '会计组'},
                                {'name': '出纳组'},
                            ]},
                            {'name': '行政部'},
                            {'name': '法务部'},
                        ]
                    },
                ]
            }
        ]
        
        def create_department(structure, parent_id=0, level=0):
            dept = Department.objects.create(
                name=structure['name'],
                pid=parent_id,
                level=level,
                sort=random.randint(1, 100),
                status=1,
            )
            self.departments.append(dept)
            
            if 'children' in structure:
                for child in structure['children']:
                    create_department(child, parent_id=dept.id, level=level + 1)
        
        # 创建部门结构
        for root in department_structure:
            create_department(root)
        
        print(f"  [OK] 部门生成完成：{len(self.departments)} 个")
        self._print_department_tree()
    
    def _print_department_tree(self):
        """打印部门树形结构"""
        print("\n  部门结构:")
        root_depts = [d for d in self.departments if d.pid == 0]
        
        def print_tree(dept, indent=0):
            prefix = "  " * indent + "└─ " if indent > 0 else ""
            print(f"  {prefix}{dept.name} (ID: {dept.id}, PID: {dept.pid})")
            children = [d for d in self.departments if d.pid == dept.id]
            for child in children:
                print_tree(child, indent + 1)
        
        for dept in root_depts[:1]:  # 只打印第一个根部门
            print_tree(dept)
    
    def generate_positions(self):
        """生成岗位数据"""
        print("\n[2/5] 生成岗位数据...")
        
        positions_data = [
            # 管理层
            '总经理', '副总经理', '总监', '副总监', '经理', '副经理', '主管', '副主管',
            # 技术岗
            '架构师', '高级工程师', '工程师', '助理工程师', '技术员',
            # 产品岗
            '产品总监', '产品经理', '产品助理',
            # 设计岗
            '设计总监', '资深设计师', '设计师', '助理设计师',
            # 销售岗
            '销售总监', '销售经理', '销售主管', '销售代表', '销售助理',
            # 客服岗
            '客服经理', '客服主管', '客服专员',
            # 运营岗
            '运营总监', '运营经理', '运营专员',
            # 职能岗
            '人力资源总监', '人力资源经理', '招聘专员', '培训专员', '薪酬专员',
            '财务总监', '财务经理', '会计', '出纳',
            '行政经理', '行政专员', '法务经理', '法务专员',
        ]
        
        for pos_name in positions_data:
            position = Position.objects.create(
                title=pos_name,
                did=0,  # 不指定部门
                desc=f"{pos_name}岗位",
                sort=random.randint(1, 100),
                status=1,
            )
            self.positions.append(position)
        
        print(f"  [OK] 岗位生成完成：{len(self.positions)} 个")
    
    def generate_employees(self, count=150):
        """生成员工数据"""
        print(f"\n[5/5] 生成员工数据（目标：{count} 个）...")
        
        # 姓氏和名字
        surnames = ['赵', '钱', '孙', '李', '周', '吴', '郑', '王', '冯', '陈', 
                   '褚', '卫', '蒋', '沈', '韩', '杨', '朱', '秦', '尤', '许',
                   '何', '吕', '施', '张', '孔', '曹', '严', '华', '金', '魏']
        
        given_names_male = ['伟', '强', '磊', '军', '勇', '杰', '涛', '明', '超', '鹏',
                           '辉', '阳', '斌', '俊', '博', '文', '建', '志', '成', '浩']
        
        given_names_female = ['芳', '娜', '敏', '静', '丽', '秀', '娟', '英', '华', '慧',
                             '巧', '美', '燕', '玲', '萍', '红', '霞', '青', '兰', '琴']
        
        # 部门列表（排除总公司）
        working_depts = [d for d in self.departments if d.name != '总公司']
        
        # 岗位列表（简化，随机分配）
        all_positions = self.positions
        
        for i in range(count):
            # 生成姓名
            surname = random.choice(surnames)
            is_male = random.random() > 0.4  # 60% 男性
            given_name = random.choice(given_names_male if is_male else given_names_female)
            name = surname + given_name
            
            # 生成用户名
            username = f"{surname.lower()}{given_name.lower()}{random.randint(100, 999)}"
            
            # 分配部门
            dept = random.choice(working_depts)
            
            # 分配岗位（根据部门层级）
            position = random.choice(all_positions) if all_positions else None
            
            # 生成手机号
            phone_prefix = random.choice(['139', '138', '137', '159', '158', '150', '151', '152'])
            phone = phone_prefix + ''.join([str(random.randint(0, 9)) for _ in range(8)])
            
            # 生成邮箱
            email = f"{username}@company.com"
            
            # 生成入职时间
            entry_date = datetime.now() - timedelta(days=random.randint(0, 1000))
            
            # 创建员工
            try:
                employee = Admin.objects.create(
                    username=username,
                    name=name,
                    email=email,
                    phone=phone,
                    department=dept,
                    position=position,
                    job_title=None,  # 可选
                    entry_date=entry_date.date(),
                    status=1,
                    is_active=True,
                    is_superuser=(i == 0),  # 第一个员工是超级管理员
                    gender='male' if is_male else 'female',
                    id_number=f"110101{random.randint(1980, 2000)}{random.randint(1000, 9999)}{random.randint(1000, 9999)}",
                    emergency_contact=f"{surname}先生/女士",
                    emergency_phone=f"138{random.randint(10000000, 99999999)}",
                    address=f"{random.choice(['北京市', '上海市', '广州市', '深圳市'])}{random.choice(['朝阳区', '浦东新区', '天河区', '南山区'])}{random.randint(1, 999)}号",
                    remark=f'测试员工 {i + 1}',
                )
                
                self.employees.append(employee)
                
                if (i + 1) % 30 == 0:
                    print(f"  已生成 {i + 1}/{count} 个员工")
            
            except Exception as e:
                print(f"  [WARN] 创建员工 {name} 失败：{e}")
                continue
        
        print(f"  [OK] 员工生成完成：{len(self.employees)} 个")
    
    def print_summary(self):
        """打印数据摘要"""
        print("\n" + "=" * 60)
        print("组织架构测试数据生成完成！")
        print("=" * 60)
        print(f"\n生成的数据：")
        print(f"  [OK] 部门：{len(self.departments)} 个")
        print(f"  [OK] 岗位：{len(self.positions)} 个")
        print(f"\n详细统计：")
        print(f"  部门层级分布:")
        dept_levels = {}
        for dept in self.departments:
            level = dept.level
            dept_levels[level] = dept_levels.get(level, 0) + 1
        for level in sorted(dept_levels.keys()):
            print(f"    - 第{level}级：{dept_levels[level]} 个")
        print(f"  岗位统计：{len(self.positions)} 个")
        print("=" * 60)


def main():
    """主函数"""
    print("=" * 60)
    print("组织架构测试数据生成器")
    print("=" * 60)
    
    generator = OrganizationDataGenerator()
    
    # 生成部门
    generator.generate_departments()
    
    # 生成岗位
    generator.generate_positions()
    
    # 打印摘要
    generator.print_summary()


if __name__ == '__main__':
    main()
