#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
资产管理测试数据创建脚本
用于生成资产管理相关的全面测试数据
"""

import os
import sys
import random
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_path)

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from apps.system.models import AssetCategory, AssetBrand, Asset, AssetRepair
from apps.department.models import Department

User = get_user_model()

# 随机数种子
random.seed(42)


def create_asset_categories():
    """创建资产分类测试数据"""
    print("=" * 60)
    print("创建资产分类数据")
    print("=" * 60)
    
    categories_data = [
        # 一级分类
        {'code': 'CAT_ELECTRONIC', 'name': '电子设备', 'description': '包括电脑、打印机、扫描仪等电子设备', 'sort_order': 1, 'is_active': True, 'parent': None},
        {'code': 'CAT_OFFICE', 'name': '办公家具', 'description': '包括桌椅、柜子、沙发等办公家具', 'sort_order': 2, 'is_active': True, 'parent': None},
        {'code': 'CAT_VEHICLE', 'name': '交通运输设备', 'description': '包括汽车、电动车等交通工具', 'sort_order': 3, 'is_active': True, 'parent': None},
        {'code': 'CAT_NETWORK', 'name': '网络设备', 'description': '包括路由器、交换机、服务器等网络设备', 'sort_order': 4, 'is_active': True, 'parent': None},
        {'code': 'CAT_AUDIO', 'name': '音视频设备', 'description': '包括投影仪、音响、电视等音视频设备', 'sort_order': 5, 'is_active': True, 'parent': None},
        {'code': 'CAT_SECURITY', 'name': '安全设备', 'description': '包括监控设备、门禁系统等安全设备', 'sort_order': 6, 'is_active': True, 'parent': None},
        {'code': 'CAT_TOOLS', 'name': '工具设备', 'description': '包括维修工具、测量仪器等工具设备', 'sort_order': 7, 'is_active': True, 'parent': None},
        {'code': 'CAT_OTHER', 'name': '其他资产', 'description': '其他无法归类的资产', 'sort_order': 99, 'is_active': True, 'parent': None},
        
        # 二级分类 - 电子设备
        {'code': 'CAT_PC', 'name': '计算机设备', 'description': '台式电脑、笔记本电脑、工作站等', 'sort_order': 1, 'is_active': True, 'parent_code': 'CAT_ELECTRONIC'},
        {'code': 'CAT_PRINTER', 'name': '打印设备', 'description': '打印机、复印机、传真机等', 'sort_order': 2, 'is_active': True, 'parent_code': 'CAT_ELECTRONIC'},
        {'code': 'CAT_SCAN', 'name': '扫描设备', 'description': '扫描仪、高拍仪等', 'sort_order': 3, 'is_active': True, 'parent_code': 'CAT_ELECTRONIC'},
        {'code': 'CAT_DISPLAY', 'name': '显示设备', 'description': '显示器、投影仪等', 'sort_order': 4, 'is_active': True, 'parent_code': 'CAT_ELECTRONIC'},
        
        # 二级分类 - 办公家具
        {'code': 'CAT_DESK', 'name': '桌椅类', 'description': '办公桌、办公椅、会议桌等', 'sort_order': 1, 'is_active': True, 'parent_code': 'CAT_OFFICE'},
        {'code': 'CAT_CABINET', 'name': '柜子类', 'description': '文件柜、更衣柜、书架等', 'sort_order': 2, 'is_active': True, 'parent_code': 'CAT_OFFICE'},
        {'code': 'CAT_SOFA', 'name': '沙发茶几', 'description': '接待沙发、茶几等', 'sort_order': 3, 'is_active': True, 'parent_code': 'CAT_OFFICE'},
        
        # 二级分类 - 网络设备
        {'code': 'CAT_SERVER', 'name': '服务器', 'description': '物理服务器、存储设备等', 'sort_order': 1, 'is_active': True, 'parent_code': 'CAT_NETWORK'},
        {'code': 'CAT_SWITCH', 'name': '网络交换设备', 'description': '交换机、路由器、防火墙等', 'sort_order': 2, 'is_active': True, 'parent_code': 'CAT_NETWORK'},
        {'code': 'CAT_WIFI', 'name': '无线网络设备', 'description': '无线AP、无线控制器等', 'sort_order': 3, 'is_active': True, 'parent_code': 'CAT_NETWORK'},
    ]
    
    created_count = 0
    parent_map = {}
    
    for cat_data in categories_data:
        parent_code = cat_data.pop('parent_code', None)
        
        if parent_code:
            parent = parent_map.get(parent_code)
            if parent:
                cat_data['parent'] = parent
        
        # 检查是否已存在
        exists = AssetCategory.objects.filter(code=cat_data['code']).exists()
        if exists:
            print(f"  跳过: {cat_data['code']} - {cat_data['name']} (已存在)")
            parent = AssetCategory.objects.get(code=cat_data['code'])
            parent_map[cat_data['code']] = parent
            continue
        
        category = AssetCategory.objects.create(**cat_data)
        parent_map[cat_data['code']] = category
        created_count += 1
        print(f"  创建: {category.code} - {category.name}")
    
    print(f"\n资产分类创建完成! 共创建 {created_count} 条记录")
    return parent_map


def create_asset_brands():
    """创建资产品牌测试数据"""
    print("\n" + "=" * 60)
    print("创建资产品牌数据")
    print("=" * 60)
    
    brands_data = [
        {'code': 'BRAND_DELL', 'name': '戴尔 (Dell)', 'description': '全球知名的电脑科技公司', 'is_active': True},
        {'code': 'BRAND_HP', 'name': '惠普 (HP)', 'description': '全球最大的信息技术公司之一', 'is_active': True},
        {'code': 'BRAND_LENOVO', 'name': '联想 (Lenovo)', 'description': '全球知名的电脑制造商', 'is_active': True},
        {'code': 'BRAND_HUAWEI', 'name': '华为 (Huawei)', 'description': '全球领先的信息与通信技术解决方案供应商', 'is_active': True},
        {'code': 'BRAND_HIKVISION', 'name': '海康威视', 'description': '全球领先的以视频为核心的智能物联解决方案提供商', 'is_active': True},
        {'code': 'BRAND_DAHUA', 'name': '大华股份', 'description': '全球领先的以视频为核心的智慧物联解决方案提供商', 'is_active': True},
        {'code': 'BRAND_CISCO', 'name': '思科 (Cisco)', 'description': '全球领先的网络设备供应商', 'is_active': True},
        {'code': 'BRAND_H3C', 'name': '新华三', 'description': '数字化解决方案领导者', 'is_active': True},
        {'code': 'BRAND_MICROSOFT', 'name': '微软 (Microsoft)', 'description': '全球最大的电脑软件提供商', 'is_active': True},
        {'code': 'BRAND_APPLE', 'name': '苹果 (Apple)', 'description': '全球知名的科技公司', 'is_active': True},
        {'code': 'BRAND_SAMSUNG', 'name': '三星 (Samsung)', 'description': '全球知名的电子产品制造商', 'is_active': True},
        {'code': 'BRAND_SONY', 'name': '索尼 (Sony)', 'description': '全球知名的电子娱乐公司', 'is_active': True},
        {'code': 'BRAND_PANASONIC', 'name': '松下 (Panasonic)', 'description': '全球知名的电器制造商', 'is_active': True},
        {'code': 'BRAND_BROTHER', 'name': '兄弟 (Brother)', 'description': '全球知名的打印机及办公设备制造商', 'is_active': True},
        {'code': 'BRAND_CANON', 'name': '佳能 (Canon)', 'description': '全球知名的光学产品制造商', 'is_active': True},
        {'code': 'BRAND_XIAOMI', 'name': '小米 (Xiaomi)', 'description': '全球知名的智能硬件和消费电子产品制造商', 'is_active': True},
        {'code': 'BRAND_AIGO', 'name': '爱国者', 'description': '国内知名的数码品牌', 'is_active': True},
        {'code': 'BRAND_TP_LINK', 'name': 'TP-LINK', 'description': '全球领先的网络通讯设备供应商', 'is_active': True},
        {'code': 'BRAND_RUIJIE', 'name': '锐捷网络', 'description': '中国领先的网络设备及解决方案供应商', 'is_active': True},
        {'code': 'BRAND_UNI', 'name': '宇视科技', 'description': '全球领先的AIoT产品及解决方案提供商', 'is_active': True},
    ]
    
    created_count = 0
    for brand_data in brands_data:
        exists = AssetBrand.objects.filter(code=brand_data['code']).exists()
        if exists:
            print(f"  跳过: {brand_data['code']} - {brand_data['name']} (已存在)")
            continue
        
        brand = AssetBrand.objects.create(**brand_data)
        created_count += 1
        print(f"  创建: {brand.code} - {brand.name}")
    
    print(f"\n资产品牌创建完成! 共创建 {created_count} 条记录")
    return AssetBrand.objects.all()


def create_departments_if_needed():
    """确保存在部门数据"""
    print("\n" + "=" * 60)
    print("检查部门数据")
    print("=" * 60)
    
    departments_data = [
        {'name': '总经理办公室', 'code': 'DEPT_001', 'sort': 1},
        {'name': '行政部', 'code': 'DEPT_002', 'sort': 2},
        {'name': '人力资源部', 'code': 'DEPT_003', 'sort': 3},
        {'name': '财务部', 'code': 'DEPT_004', 'sort': 4},
        {'name': '信息技术部', 'code': 'DEPT_005', 'sort': 5},
        {'name': '市场部', 'code': 'DEPT_006', 'sort': 6},
        {'name': '销售部', 'code': 'DEPT_007', 'sort': 7},
        {'name': '研发部', 'code': 'DEPT_008', 'sort': 8},
        {'name': '产品部', 'code': 'DEPT_009', 'sort': 9},
        {'name': '客服部', 'code': 'DEPT_010', 'sort': 10},
    ]
    
    created_count = 0
    for dept_data in departments_data:
        exists = Department.objects.filter(code=dept_data['code']).exists()
        if not exists:
            try:
                dept = Department.objects.create(**dept_data)
                created_count += 1
                print(f"  创建: {dept.name}")
            except Exception as e:
                print(f"  跳过: {dept_data['name']} - {e}")
        else:
            print(f"  跳过: {dept_data['name']} (已存在)")
    
    print(f"\n部门检查完成! 新建 {created_count} 条记录")
    return Department.objects.all()


def ensure_users_exist():
    """确保存在测试用户"""
    print("\n" + "=" * 60)
    print("检查用户数据")
    print("=" * 60)
    
    users_data = [
        {'username': 'admin', 'first_name': '系统', 'last_name': '管理员', 'is_superuser': True, 'is_staff': True},
        {'username': 'zhangsan', 'first_name': '三', 'last_name': '张', 'is_superuser': False, 'is_staff': False},
        {'username': 'lisi', 'first_name': '四', 'last_name': '李', 'is_superuser': False, 'is_staff': False},
        {'username': 'wangwu', 'first_name': '五', 'last_name': '王', 'is_superuser': False, 'is_staff': False},
        {'username': 'zhaoliu', 'first_name': '六', 'last_name': '赵', 'is_superuser': False, 'is_staff': False},
    ]
    
    created_count = 0
    for user_data in users_data:
        exists = User.objects.filter(username=user_data['username']).exists()
        if not exists:
            try:
                user = User.objects.create_user(
                    username=user_data['username'],
                    password='password123',
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                    is_superuser=user_data['is_superuser'],
                    is_staff=user_data['is_staff'],
                )
                created_count += 1
                print(f"  创建用户: {user.username}")
            except Exception as e:
                print(f"  跳过: {user_data['username']} - {e}")
        else:
            print(f"  跳过: {user_data['username']} (已存在)")
    
    print(f"\n用户检查完成! 新建 {created_count} 条记录")
    return User.objects.filter(is_superuser=False)


def generate_asset_number(index):
    """生成资产编号"""
    return f'ZC{datetime.now().strftime("%Y%m%d")}{str(index).zfill(4)}'


def create_assets(categories, brands, departments, users):
    """创建资产测试数据"""
    print("\n" + "=" * 60)
    print("创建资产数据")
    print("=" * 60)
    
    asset_templates = [
        # 计算机设备
        {'name': '戴尔OptiPlex 7090台式电脑', 'model': 'OptiPlex 7090', 'category_code': 'CAT_PC', 'brand_code': 'BRAND_DELL', 'specs': 'Intel Core i7-11700, 16GB DDR4, 512GB SSD, 23.8寸显示器'},
        {'name': '联想ThinkCentre M720台式电脑', 'model': 'ThinkCentre M720', 'category_code': 'CAT_PC', 'brand_code': 'BRAND_LENOVO', 'specs': 'Intel Core i5-11400, 8GB DDR4, 256GB SSD, 21.5寸显示器'},
        {'name': '苹果iMac 24寸一体机', 'model': 'iMac 24"', 'category_code': 'CAT_PC', 'brand_code': 'BRAND_APPLE', 'specs': 'Apple M1芯片, 8GB RAM, 256GB SSD, 4.5K Retina显示屏'},
        {'name': '戴尔XPS 15笔记本电脑', 'model': 'XPS 15 9500', 'category_code': 'CAT_PC', 'brand_code': 'BRAND_DELL', 'specs': 'Intel Core i7-10750H, 16GB RAM, 512GB SSD, 15.6寸4K显示屏'},
        {'name': '联想ThinkPad X1 Carbon笔记本电脑', 'model': 'ThinkPad X1 Carbon', 'category_code': 'CAT_PC', 'brand_code': 'BRAND_LENOVO', 'specs': 'Intel Core i7-1165G7, 16GB RAM, 512GB SSD, 14寸显示屏'},
        
        # 打印设备
        {'name': '惠普LaserJet Pro M404dn打印机', 'model': 'LaserJet Pro M404dn', 'category_code': 'CAT_PRINTER', 'brand_code': 'BRAND_HP', 'specs': 'A4黑白激光打印机, 38ppm, 双面打印'},
        {'name': '佳能imageRunner 2520复印机', 'model': 'imageRunner 2520', 'category_code': 'CAT_PRINTER', 'brand_code': 'BRAND_CANON', 'specs': 'A3黑白复印机, 20ppm, 打印/复印/扫描'},
        {'name': '兄弟HL-5590DN打印机', 'model': 'HL-5590DN', 'category_code': 'CAT_PRINTER', 'brand_code': 'BRAND_BROTHER', 'specs': 'A4黑白激光打印机, 40ppm, 双面打印, 网络打印'},
        
        # 服务器设备
        {'name': '戴尔PowerEdge R740服务器', 'model': 'PowerEdge R740', 'category_code': 'CAT_SERVER', 'brand_code': 'BRAND_DELL', 'specs': '双路Intel Xeon Gold 5218, 256GB RAM, 8TB SSD, 2U机架式'},
        {'name': '华为FusionServer Pro 2288H V5服务器', 'model': 'FusionServer Pro 2288H V5', 'category_code': 'CAT_SERVER', 'brand_code': 'BRAND_HUAWEI', 'specs': '双路Intel Xeon Silver 4210, 128GB RAM, 4TB SSD, 2U机架式'},
        
        # 网络设备
        {'name': '思科Catalyst 9200交换机', 'model': 'Catalyst 9200', 'category_code': 'CAT_SWITCH', 'brand_code': 'BRAND_CISCO', 'specs': '48口千兆以太网交换机, PoE+, Layer 3'},
        {'name': '华为AR2220路由器', 'model': 'AR2220', 'category_code': 'CAT_SWITCH', 'brand_code': 'BRAND_HUAWEI', 'specs': '企业级路由器, 5个GE口, 支持VPN'},
        {'name': 'TP-LINK TL-SG5428交换机', 'model': 'TL-SG5428', 'category_code': 'CAT_SWITCH', 'brand_code': 'BRAND_TP_LINK', 'specs': '24口千兆+4口万兆交换机, Layer 2'},
        {'name': '锐捷RG-AP720-A无线AP', 'model': 'RG-AP720-A', 'category_code': 'CAT_WIFI', 'brand_code': 'BRAND_RUIJIE', 'specs': '企业级无线AP, 802.11ac, 双频, 最高1167Mbps'},
        
        # 安全设备
        {'name': '海康威视DS-7732N-I4监控主机', 'model': 'DS-7732N-I4', 'category_code': 'CAT_SECURITY', 'brand_code': 'BRAND_HIKVISION', 'specs': '32路网络硬盘录像机, 4盘位, 支持4K输出'},
        {'name': '大华DH-NVR4216-16P监控主机', 'model': 'DH-NVR4216-16P', 'category_code': 'CAT_SECURITY', 'brand_code': 'BRAND_DAHUA', 'specs': '16路网络硬盘录像机, 2盘位, 16口PoE'},
        {'name': '海康威视DS-2CD3T46WD-I3摄像头', 'model': 'DS-2CD3T46WD-I3', 'category_code': 'CAT_SECURITY', 'brand_code': 'BRAND_HIKVISION', 'specs': '400万像素网络摄像机, 红外距离50米'},
        
        # 办公家具
        {'name': '赫曼米勒Aeron人体工学椅', 'model': 'Aeron', 'category_code': 'CAT_DESK', 'brand_code': 'BRAND_OTHER', 'specs': '人体工学设计, 8Z Pellicle网布, 倾仰支撑'},
        {'name': '震旦AOC1899办公桌', 'model': 'AOC1899', 'category_code': 'CAT_DESK', 'brand_code': 'BRAND_OTHER', 'specs': '1400*700*750mm, 环保板材, 钢制框架'},
        {'name': '震旦AOC1988铁皮柜', 'model': 'AOC1988', 'category_code': 'CAT_CABINET', 'brand_code': 'BRAND_OTHER', 'specs': '1850*900*400mm, 钢制, 四门玻璃柜'},
        
        # 音视频设备
        {'name': '明基MX3291+投影仪', 'model': 'MX3291+', 'category_code': 'CAT_DISPLAY', 'brand_code': 'BRAND_OTHER', 'specs': '商务投影仪, 3300流明, 1024*768分辨率'},
        {'name': '索尼HT-S350回音壁', 'model': 'HT-S350', 'category_code': 'CAT_AUDIO', 'brand_code': 'BRAND_SONY', 'specs': '2.1声道回音壁, 320W功率, 无线低音炮'},
    ]
    
    locations = [
        '总部大楼5层A区', '总部大楼5层B区', '总部大楼6层东侧', 
        '总部大楼6层西侧', '研发中心3楼', '数据中心机房',
        '会议室501', '会议室502', '贵宾接待室', '培训教室'
    ]
    
    suppliers = [
        '戴尔官方旗舰店', '联想授权经销商', '惠普金牌代理商',
        '华为企业业务部', '京东企业购', '天猫官方旗舰店'
    ]
    
    created_count = 0
    categories_map = {cat.code: cat for cat in categories}
    brands_map = {brand.code: brand for brand in brands}
    departments_list = list(departments)
    users_list = list(users)
    
    for i, template in enumerate(asset_templates):
        category = categories_map.get(template['category_code'])
        brand = brands_map.get(template['brand_code'])
        
        if not category or not brand:
            print(f"  跳过: {template['name']} (缺少分类或品牌)")
            continue
        
        asset_number = generate_asset_number(i + 1)
        
        # 检查是否已存在
        if Asset.objects.filter(asset_number=asset_number).exists():
            print(f"  跳过: {asset_number} (已存在)")
            continue
        
        purchase_date = datetime.now() - timedelta(days=random.randint(30, 730))
        purchase_price = round(random.uniform(1000, 50000), 2)
        
        asset = Asset.objects.create(
            asset_number=asset_number,
            name=template['name'],
            category=category,
            brand=brand,
            model=template['model'],
            specification=template['specs'],
            purchase_date=purchase_date.date(),
            purchase_price=purchase_price,
            supplier=random.choice(suppliers),
            warranty_period=random.choice([12, 24, 36]),
            location=random.choice(locations),
            responsible_person=None,
            department=None,
            status=random.choice(['normal', 'normal', 'normal', 'repair', 'scrap']),
            description=f'{template["name"]}测试资产'
        )
        created_count += 1
        print(f"  创建: {asset_number} - {asset.name}")
    
    print(f"\n资产创建完成! 共创建 {created_count} 条记录")
    return Asset.objects.filter(status='normal')


def create_asset_repairs(assets, users):
    """创建资产维修测试数据"""
    print("\n" + "=" * 60)
    print("创建资产维修数据")
    print("=" * 60)
    
    fault_descriptions = [
        '电脑无法开机，电源指示灯不亮',
        '显示器出现花屏现象',
        '打印机卡纸，进纸不畅',
        '网络连接不稳定，经常掉线',
        '服务器风扇噪音过大',
        '键盘按键失灵',
        '鼠标滚轮无法滚动',
        '硬盘出现坏道，数据读取缓慢',
        'USB接口接触不良',
        '系统运行缓慢，死机频繁',
        '投影仪灯泡亮度不足',
        '摄像头图像模糊',
        '交换机端口损坏',
        '路由器无法拨号上网',
        '空调制冷效果差'
    ]
    
    repair_descriptions = [
        '已更换电源适配器，测试正常',
        '已更换显示屏总成，测试正常',
        '已清洁进纸通道，调整传感器',
        '已更换网线，配置网络参数',
        '已更换故障风扇，清理灰尘',
        '已更换键盘，测试所有按键正常',
        '已更换鼠标，滚轮功能正常',
        '已备份数据，更换硬盘，重装系统',
        '已更换USB接口板，测试正常',
        '已重装系统，清理灰尘，优化启动项',
        '已更换灯泡，清洁光路',
        '已调整镜头焦距，清洁镜头',
        '已更换故障端口，配置VLAN',
        '已重置路由器，更新固件',
        '已添加制冷剂，清洁滤网'
    ]
    
    created_count = 0
    users_list = list(users)
    assets_list = list(assets)
    
    for i in range(min(20, len(assets_list))):
        asset = random.choice(assets_list)
        reporter = random.choice(users_list) if users_list else None
        
        report_time = datetime.now() - timedelta(days=random.randint(1, 180))
        status = random.choice(['pending', 'processing', 'completed', 'completed', 'completed'])
        
        repair = AssetRepair.objects.create(
            asset=asset,
            reporter=reporter,
            repair_person=reporter if status in ['processing', 'completed'] else None,
            fault_description=random.choice(fault_descriptions),
            repair_description=random.choice(repair_descriptions) if status == 'completed' else '',
            repair_cost=round(random.uniform(0, 2000), 2) if status == 'completed' else None,
            status=status,
            report_time=report_time,
            start_time=report_time + timedelta(hours=random.randint(1, 24)) if status in ['processing', 'completed'] else None,
            complete_time=report_time + timedelta(days=random.randint(1, 7)) if status == 'completed' else None
        )
        created_count += 1
        print(f"  创建: {repair.asset.name} - {repair.get_status_display()}")
        
        # 避免重复使用同一资产
        if asset in assets_list:
            assets_list.remove(asset)
    
    print(f"\n资产维修创建完成! 共创建 {created_count} 条记录")


@transaction.atomic
def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  资产管理测试数据创建脚本")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    # 创建资产分类
    categories = AssetCategory.objects.all()
    if categories.count() == 0:
        categories_map = create_asset_categories()
        categories = AssetCategory.objects.all()
    else:
        print("\n资产分类已存在，跳过创建")
        categories_map = {cat.code: cat for cat in categories}
    
    # 创建资产品牌
    brands = AssetBrand.objects.all()
    if brands.count() == 0:
        brands = create_asset_brands()
    else:
        print("\n资产品牌已存在，跳过创建")
    
    # 确保部门存在
    departments = Department.objects.all()
    if departments.count() == 0:
        departments = create_departments_if_needed()
    else:
        print("\n部门数据已存在，跳过创建")
    
    # 确保用户存在
    users = ensure_users_exist()
    
    # 创建资产
    assets = Asset.objects.all()
    if assets.count() == 0:
        normal_assets = create_assets(categories, brands, departments, users)
    else:
        print("\n资产数据已存在，跳过创建")
        normal_assets = Asset.objects.filter(status='normal')
    
    # 创建资产维修记录
    repairs = AssetRepair.objects.all()
    if repairs.count() == 0 and normal_assets.count() > 0:
        create_asset_repairs(normal_assets, users)
    else:
        print("\n资产维修数据已存在，跳过创建")
    
    # 输出统计信息
    print("\n" + "=" * 60)
    print("  数据统计")
    print("=" * 60)
    print(f"  资产分类: {AssetCategory.objects.count()} 条")
    print(f"  资产品牌: {AssetBrand.objects.count()} 条")
    print(f"  资产总数: {Asset.objects.count()} 条")
    print(f"  - 正常状态: {Asset.objects.filter(status='normal').count()} 条")
    print(f"  - 维修中: {Asset.objects.filter(status='repair').count()} 条")
    print(f"  - 已报废: {Asset.objects.filter(status='scrap').count()} 条")
    print(f"  维修记录: {AssetRepair.objects.count()} 条")
    print(f"  - 待处理: {AssetRepair.objects.filter(status='pending').count()} 条")
    print(f"  - 处理中: {AssetRepair.objects.filter(status='processing').count()} 条")
    print(f"  - 已完成: {AssetRepair.objects.filter(status='completed').count()} 条")
    print("=" * 60)
    print("  测试数据创建完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
