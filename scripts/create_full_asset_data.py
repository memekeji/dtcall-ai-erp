"""
资产管理测试数据创建脚本
创建全面的资产分类和资产品牌数据
"""
import os
import sys

sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from apps.system.models import AssetCategory, AssetBrand


def create_categories():
    """创建资产分类数据"""
    print("\n" + "=" * 60)
    print("创建资产分类数据")
    print("=" * 60)
    
    # 一级分类定义
    level1_categories = [
        {'code': 'CAT_ELECTRONIC', 'name': '电子设备', 'description': '办公电子设备和数码产品'},
        {'code': 'CAT_OFFICE', 'name': '办公家具', 'description': '办公桌椅、柜子、沙发等家具'},
        {'code': 'CAT_VEHICLE', 'name': '交通运输设备', 'description': '公务车辆和交通设备'},
        {'code': 'CAT_NETWORK', 'name': '网络设备', 'description': '服务器、交换机、路由器等网络设备'},
        {'code': 'CAT_AUDIO', 'name': '音视频设备', 'description': '投影仪、音响、麦克风等'},
        {'code': 'CAT_SECURITY', 'name': '安全监控设备', 'description': '监控摄像头、门禁系统等'},
        {'code': 'CAT_TOOLS', 'name': '工具设备', 'description': '维修工具、检测仪器等'},
        {'code': 'CAT_SOFTWARE', 'name': '软件系统', 'description': '正版软件授权和系统许可证'},
        {'code': 'CAT consumable', 'name': '办公耗材', 'description': '打印耗材、纸张、文具等'},
        {'code': 'CAT_OTHER', 'name': '其他资产', 'description': '其他类型的固定资产'},
    ]
    
    # 二级分类定义（关联到一级分类）
    level2_categories = [
        # 电子设备 - CAT_ELECTRONIC
        {'code': 'CAT_PC', 'name': '计算机设备', 'description': '台式电脑、笔记本电脑、工作站', 'parent_code': 'CAT_ELECTRONIC'},
        {'code': 'CAT_TABLET', 'name': '平板设备', 'description': '平板电脑、掌上电脑', 'parent_code': 'CAT_ELECTRONIC'},
        {'code': 'CAT_PRINTER', 'name': '打印设备', 'description': '打印机、复印机、扫描仪', 'parent_code': 'CAT_ELECTRONIC'},
        {'code': 'CAT_DISPLAY', 'name': '显示设备', 'description': '显示器、电视、投影幕布', 'parent_code': 'CAT_ELECTRONIC'},
        {'code': 'CAT_PERIPHERAL', 'name': '外设配件', 'description': '键盘、鼠标、U盘、移动硬盘', 'parent_code': 'CAT_ELECTRONIC'},
        {'code': 'CAT_MOBILE', 'name': '移动设备', 'description': '手机、对讲机及其他移动设备', 'parent_code': 'CAT_ELECTRONIC'},
        
        # 办公家具 - CAT_OFFICE
        {'code': 'CAT_DESK', 'name': '桌类', 'description': '办公桌、会议桌、实验台', 'parent_code': 'CAT_OFFICE'},
        {'code': 'CAT_CHAIR', 'name': '椅类', 'description': '办公椅、会议椅、沙发椅', 'parent_code': 'CAT_OFFICE'},
        {'code': 'CAT_CABINET', 'name': '柜类', 'description': '文件柜、储物柜、更衣柜', 'parent_code': 'CAT_OFFICE'},
        {'code': 'CAT_SHELVES', 'name': '架类', 'description': '书架、货架、展示架', 'parent_code': 'CAT_OFFICE'},
        {'code': 'CAT_SOFA', 'name': '沙发茶几', 'description': '办公沙发、茶几、休闲椅', 'parent_code': 'CAT_OFFICE'},
        {'code': 'CAT_PARTITION', 'name': '屏风隔断', 'description': '屏风、隔断、办公隔间', 'parent_code': 'CAT_OFFICE'},
        
        # 交通运输设备 - CAT_VEHICLE
        {'code': 'CAT_CAR', 'name': '轿车', 'description': '商务轿车、轿车', 'parent_code': 'CAT_VEHICLE'},
        {'code': 'CAT_SUV', 'name': 'SUV越野车', 'description': '越野车、SUV车型', 'parent_code': 'CAT_VEHICLE'},
        {'code': 'CAT_MPV', 'name': '商务车', 'description': 'MPV商务车、面包车', 'parent_code': 'CAT_VEHICLE'},
        {'code': 'CAT_TRUCK', 'name': '货车', 'description': '货运车辆、货车', 'parent_code': 'CAT_VEHICLE'},
        {'code': 'CAT_MOTORCYCLE', 'name': '摩托车', 'description': '公务摩托车', 'parent_code': 'CAT_VEHICLE'},
        {'code': 'CAT_EBIKE', 'name': '电动自行车', 'description': '电动自行车、电动三轮车', 'parent_code': 'CAT_VEHICLE'},
        
        # 网络设备 - CAT_NETWORK
        {'code': 'CAT_SERVER', 'name': '服务器', 'description': '机架式服务器、塔式服务器', 'parent_code': 'CAT_NETWORK'},
        {'code': 'CAT_SWITCH', 'name': '网络交换机', 'description': '交换机、网络交换机', 'parent_code': 'CAT_NETWORK'},
        {'code': 'CAT_ROUTER', 'name': '路由器', 'description': '企业级路由器、无线路由器', 'parent_code': 'CAT_NETWORK'},
        {'code': 'CAT_WIFI', 'name': '无线设备', 'description': '无线AP、无线控制器', 'parent_code': 'CAT_NETWORK'},
        {'code': 'CAT_FIREWALL', 'name': '安全设备', 'description': '防火墙、入侵检测系统', 'parent_code': 'CAT_NETWORK'},
        {'code': 'CAT_STORAGE', 'name': '存储设备', 'description': 'NAS、磁盘阵列、存储服务器', 'parent_code': 'CAT_NETWORK'},
        
        # 音视频设备 - CAT_AUDIO
        {'code': 'CAT_PROJECTOR', 'name': '投影设备', 'description': '投影仪、投影机', 'parent_code': 'CAT_AUDIO'},
        {'code': 'CAT_SPEAKER', 'name': '音响设备', 'description': '功放、音箱、音响系统', 'parent_code': 'CAT_AUDIO'},
        {'code': 'CAT_MICROPHONE', 'name': '麦克风设备', 'description': '会议麦克风、无线麦克风', 'parent_code': 'CAT_AUDIO'},
        {'code': 'CAT_VIDEO', 'name': '视频会议设备', 'description': '视频会议终端、摄像头', 'parent_code': 'CAT_AUDIO'},
        {'code': 'CAT_TV', 'name': '电视设备', 'description': '液晶电视、智能电视', 'parent_code': 'CAT_AUDIO'},
        
        # 安全监控设备 - CAT_SECURITY
        {'code': 'CAT_CAMERA', 'name': '监控摄像头', 'description': '网络摄像头、监控摄像机', 'parent_code': 'CAT_SECURITY'},
        {'code': 'CAT_NVR', 'name': '录像存储', 'description': 'NVR硬盘录像机、DVR', 'parent_code': 'CAT_SECURITY'},
        {'code': 'CAT_ACCESS', 'name': '门禁系统', 'description': '门禁控制器、读卡器', 'parent_code': 'CAT_SECURITY'},
        {'code': 'CAT_ALARM', 'name': '报警设备', 'description': '报警主机、探测器', 'parent_code': 'CAT_SECURITY'},
        {'code': 'CAT_INTERCOM', 'name': '对讲设备', 'description': '可视对讲、门铃', 'parent_code': 'CAT_SECURITY'},
        
        # 工具设备 - CAT_TOOLS
        {'code': 'CAT_HANDTOOLS', 'name': '手动工具', 'description': '螺丝刀、扳手、钳子等', 'parent_code': 'CAT_TOOLS'},
        {'code': 'CAT_POWERTOOLS', 'name': '电动工具', 'description': '电钻、电锯、电动螺丝刀', 'parent_code': 'CAT_TOOLS'},
        {'code': 'CAT_MEASURE', 'name': '测量仪器', 'description': '万用表、示波器、测距仪', 'parent_code': 'CAT_TOOLS'},
        {'code': 'CAT_TEST', 'name': '检测设备', 'description': '网络测试仪、线缆测试仪', 'parent_code': 'CAT_TOOLS'},
        
        # 软件系统 - CAT_SOFTWARE
        {'code': 'CAT_OS', 'name': '操作系统', 'description': 'Windows、Linux等系统授权', 'parent_code': 'CAT_SOFTWARE'},
        {'code': 'CAT_OFFICE_SW', 'name': '办公软件', 'description': 'Office、WPS等办公软件', 'parent_code': 'CAT_SOFTWARE'},
        {'code': 'CAT_SECURITY_SW', 'name': '安全软件', 'description': '杀毒软件、防火墙软件', 'parent_code': 'CAT_SOFTWARE'},
        {'code': 'CAT_DATABASE', 'name': '数据库软件', 'description': 'MySQL、Oracle等数据库授权', 'parent_code': 'CAT_SOFTWARE'},
        {'code': 'CAT_CAD', 'name': '专业软件', 'description': 'CAD、PS、剪辑等专业软件', 'parent_code': 'CAT_SOFTWARE'},
        
        # 办公耗材 - CAT_CONSUMABLE
        {'code': 'CAT_INK', 'name': '打印耗材', 'description': '墨盒、碳粉、打印头', 'parent_code': 'CAT_CONSUMABLE'},
        {'code': 'CAT_PAPER', 'name': '纸张耗材', 'description': '打印纸、复印纸、标签纸', 'parent_code': 'CAT_CONSUMABLE'},
        {'code': 'CAT_STATIONERY', 'name': '文具用品', 'description': '笔、订书机、文件夹等', 'parent_code': 'CAT_CONSUMABLE'},
        {'code': 'CAT_CLEAN', 'name': '清洁用品', 'description': '清洁剂、擦拭布', 'parent_code': 'CAT_CONSUMABLE'},
    ]
    
    created_count = 0
    skip_count = 0
    
    # 创建一级分类
    level1_map = {}
    for cat_data in level1_categories:
        try:
            category, created = AssetCategory.objects.get_or_create(
                code=cat_data['code'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data['description'],
                    'parent': None,
                    'sort_order': created_count,
                    'is_active': True
                }
            )
            level1_map[cat_data['code']] = category
            if created:
                print(f"  创建一级分类: {category.code} - {category.name}")
                created_count += 1
            else:
                print(f"  跳过一级分类: {category.code} - {category.name} (已存在)")
                skip_count += 1
        except Exception as e:
            print(f"  创建一级分类失败 {cat_data['code']}: {e}")
    
    # 创建二级分类
    for cat_data in level2_categories:
        try:
            parent = level1_map.get(cat_data['parent_code'])
            if not parent:
                print(f"  跳过: {cat_data['code']} (父分类不存在)")
                continue
                
            category, created = AssetCategory.objects.get_or_create(
                code=cat_data['code'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data['description'],
                    'parent': parent,
                    'sort_order': created_count,
                    'is_active': True
                }
            )
            if created:
                print(f"  创建二级分类: {category.code} - {category.name}")
                created_count += 1
            else:
                print(f"  跳过二级分类: {category.code} - {category.name} (已存在)")
                skip_count += 1
        except Exception as e:
            print(f"  创建二级分类失败 {cat_data['code']}: {e}")
    
    print(f"\n资产分类创建完成! 新建 {created_count} 条, 跳过 {skip_count} 条")
    return AssetCategory.objects.filter(is_active=True)


def create_brands():
    """创建资产品牌数据"""
    print("\n" + "=" * 60)
    print("创建资产品牌数据")
    print("=" * 60)
    
    brands_data = [
        # 电脑/服务器品牌
        {'code': 'BRAND_DELL', 'name': '戴尔 (Dell)', 'description': '美国电脑品牌，服务器和台式机知名厂商'},
        {'code': 'BRAND_HP', 'name': '惠普 (HP)', 'description': '全球知名IT厂商，打印机和电脑制造商'},
        {'code': 'BRAND_LENOVO', 'name': '联想 (Lenovo)', 'description': '中国最大电脑制造商，ThinkPad品牌持有者'},
        {'code': 'BRAND_HUAWEI', 'name': '华为 (Huawei)', 'description': '中国科技企业，笔记本和服务器制造商'},
        {'code': 'BRAND_APPLE', 'name': '苹果 (Apple)', 'description': '美国科技公司，MacBook和iMac制造商'},
        {'code': 'BRAND_ASUS', 'name': '华硕 (ASUS)', 'description': '台湾电脑硬件制造商，主板和笔记本知名'},
        {'code': 'BRAND_ACER', 'name': '宏碁 (Acer)', 'description': '台湾电脑制造商，性价比产品为主'},
        {'code': 'BRAND_MSI', 'name': '微星 (MSI)', 'description': '台湾硬件制造商，游戏本和工作站知名'},
        
        # 网络设备品牌
        {'code': 'BRAND_CISCO', 'name': '思科 (Cisco)', 'description': '全球领先的网络设备供应商'},
        {'code': 'BRAND_H3C', 'name': '新华三 (H3C)', 'description': '中国网络设备知名品牌'},
        {'code': 'BRAND_RUIJIE', 'name': '锐捷 (Ruijie)', 'description': '中国网络设备制造商，企业网络解决方案'},
        {'code': 'BRAND_TP_LINK', 'name': 'TP-LINK', 'description': '中国网络设备品牌，路由器和交换机知名'},
        {'code': 'BRAND_MIKROTIK', 'name': 'MikroTik', 'description': '拉脱维亚网络设备品牌，RouterOS系统知名'},
        {'code': 'BRAND_UBIQUITI', 'name': 'Ubiquiti', 'description': '美国网络设备品牌，无线AP和交换机'},
        
        # 打印设备品牌
        {'code': 'BRAND_CANON', 'name': '佳能 (Canon)', 'description': '日本相机和办公设备制造商'},
        {'code': 'BRAND_BROTHER', 'name': '兄弟 (Brother)', 'description': '日本办公设备品牌，打印机和缝纫机'},
        {'code': 'BRAND_EPSON', 'name': '爱普生 (Epson)', 'description': '日本打印机和投影仪制造商'},
        {'code': 'BRAND_XEROX', 'name': '施乐 (Xerox)', 'description': '美国办公设备品牌，复印机发明者'},
        {'code': 'BRAND_KYOCERA', 'name': '京瓷 (Kyocera)', 'description': '日本办公设备制造商'},
        
        # 安防设备品牌
        {'code': 'BRAND_HIKVISION', 'name': '海康威视 (Hikvision)', 'description': '中国安防行业龙头企业'},
        {'code': 'BRAND_DAHUA', 'name': '大华 (Dahua)', 'description': '中国安防设备知名品牌'},
        {'code': 'BRAND_UNIVIEW', 'name': '宇视 (Uniview)', 'description': '中国视频监控设备制造商'},
        {'code': 'BRAND_TIANDY', 'name': '天地伟业 (Tiandy)', 'description': '中国安防设备品牌'},
        
        # 音视频设备品牌
        {'code': 'BRAND_SONY', 'name': '索尼 (Sony)', 'description': '日本电子娱乐公司，音视频设备知名'},
        {'code': 'BRAND_PANASONIC', 'name': '松下 (Panasonic)', 'description': '日本电器制造商，投影和音响设备'},
        {'code': 'BRAND_BOSE', 'name': '博士 (Bose)', 'description': '美国音响设备品牌，降噪耳机知名'},
        {'code': 'BRAND_JBL', 'name': 'JBL', 'description': '美国音响品牌，哈曼旗下'},
        {'code': 'BRAND_BENQ', 'name': '明基 (BenQ)', 'description': '台湾投影仪和显示器制造商'},
        {'code': 'BRAND_VIEWSONIC', 'name': '优派 (ViewSonic)', 'description': '美国显示器和投影仪品牌'},
        
        # 办公家具品牌
        {'code': 'BRAND_HERMANMILLER', 'name': '赫曼米勒 (Herman Miller)', 'description': '美国办公家具品牌，人体工学椅知名'},
        {'code': 'BRAND_STEELCASE', 'name': 'Steelcase', 'description': '美国办公家具制造商'},
        {'code': 'BRAND_VITRA', 'name': 'Vitra', 'description': '瑞士办公家具品牌'},
        {'code': 'BRAND_OKAMURA', 'name': '冈村 (Okamura)', 'description': '日本办公家具制造商'},
        {'code': 'BRAND_KOKUYO', 'name': '国誉 (Kokuyo)', 'description': '日本办公家具和文具品牌'},
        {'code': 'BRAND_LAMEX', 'name': '震旦 (Lamex)', 'description': '中国办公家具品牌'},
        {'code': 'BRAND_VICTOR', 'name': '冠美 (Victor)', 'description': '中国办公家具制造商'},
        {'code': 'BRAND_WEHAVE', 'name': '伟豪 (Wehave)', 'description': '中国办公家具品牌'},
        
        # 手机/移动设备品牌
        {'code': 'BRAND_XIAOMI', 'name': '小米 (Xiaomi)', 'description': '中国智能手机和电子设备品牌'},
        {'code': 'BRAND_OPPO', 'name': 'OPPO', 'description': '中国智能手机品牌'},
        {'code': 'BRAND_VIVO', 'name': 'vivo', 'description': '中国智能手机品牌'},
        {'code': 'BRAND_SAMSUNG', 'name': '三星 (Samsung)', 'description': '韩国电子巨头'},
        
        # 软件品牌
        {'code': 'BRAND_MICROSOFT', 'name': '微软 (Microsoft)', 'description': '美国软件巨头，Windows和Office'},
        {'code': 'BRAND_ADOBE', 'name': 'Adobe', 'description': '美国软件公司，Photoshop和PDF解决方案'},
        {'code': 'BRAND_ORACLE', 'name': '甲骨文 (Oracle)', 'description': '美国数据库软件公司'},
        {'code': 'BRAND_REDHAT', 'name': '红帽 (Red Hat)', 'description': '美国开源软件公司，Linux发行版'},
        
        # 车辆品牌
        {'code': 'BRAND_BENZ', 'name': '奔驰 (Mercedes-Benz)', 'description': '德国豪华汽车品牌'},
        {'code': 'BRAND_BMW', 'name': '宝马 (BMW)', 'description': '德国豪华汽车品牌'},
        {'code': 'BRAND_AUDI', 'name': '奥迪 (Audi)', 'description': '德国豪华汽车品牌'},
        {'code': 'BRAND_VOLKSWAGEN', 'name': '大众 (Volkswagen)', 'description': '德国汽车品牌'},
        {'code': 'BRAND_TOYOTA', 'name': '丰田 (Toyota)', 'description': '日本汽车品牌'},
        {'code': 'BRAND_FORD', 'name': '福特 (Ford)', 'description': '美国汽车品牌'},
        {'code': 'BRAND_BYD', 'name': '比亚迪 (BYD)', 'description': '中国新能源汽车品牌'},
        
        # 存储设备品牌
        {'code': 'BRAND_WD', 'name': '西部数据 (Western Digital)', 'description': '美国硬盘制造商'},
        {'code': 'BRAND_SEAGATE', 'name': '希捷 (Seagate)', 'description': '美国硬盘制造商'},
        {'code': 'BRAND_SAMSUNG_HDD', 'name': '三星存储 (Samsung)', 'description': '韩国存储设备品牌'},
        
        # 外设品牌
        {'code': 'BRAND_LOGITECH', 'name': '罗技 (Logitech)', 'description': '瑞士外设品牌，鼠标键盘知名'},
        {'code': 'BRAND_MICROSOFT_HW', 'name': '微软硬件 (Microsoft)', 'description': '微软硬件外设'},
        {'code': 'BRAND_RAZER', 'name': '雷蛇 (Razer)', 'description': '美国游戏外设品牌'},
        {'code': 'BRAND_A4TECH', 'name': '双飞燕 (A4Tech)', 'description': '中国外设品牌'},
    ]
    
    created_count = 0
    skip_count = 0
    
    for brand_data in brands_data:
        try:
            brand, created = AssetBrand.objects.get_or_create(
                code=brand_data['code'],
                defaults={
                    'name': brand_data['name'],
                    'description': brand_data['description'],
                    'is_active': True
                }
            )
            if created:
                print(f"  创建: {brand.code} - {brand.name}")
                created_count += 1
            else:
                print(f"  跳过: {brand.code} - {brand.name} (已存在)")
                skip_count += 1
        except Exception as e:
            print(f"  创建品牌失败 {brand_data['code']}: {e}")
    
    print(f"\n资产品牌创建完成! 新建 {created_count} 条, 跳过 {skip_count} 条")
    return AssetBrand.objects.filter(is_active=True)


def main():
    print("=" * 60)
    print("  资产分类与品牌测试数据创建脚本")
    print("  " + "=" * 60)
    
    categories = create_categories()
    brands = create_brands()
    
    print("\n" + "=" * 60)
    print("  数据统计")
    print("=" * 60)
    print(f"  资产分类: {categories.count()} 条")
    print(f"  资产品牌: {brands.count()} 条")
    
    # 分类统计
    level1_count = categories.filter(parent__isnull=True).count()
    level2_count = categories.filter(parent__isnull=False).count()
    print(f"    - 一级分类: {level1_count} 条")
    print(f"    - 二级分类: {level2_count} 条")
    
    print("=" * 60)
    print("  测试数据创建完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
