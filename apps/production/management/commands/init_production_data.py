from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
import random
from apps.production.models import (
    ProductionProcedure, ProcedureSet, ProcedureSetItem, BOM, BOMItem,
    Equipment, ProductionPlan, ProductionTask, QualityCheck, DataCollection,
    SOP, DataSource, DataMapping, ProductionDataPoint,
    DataCollectionTask, ProductionOrderChange, ProductionLineDayPlan,
)
from apps.department.models import Department
from apps.contract.models import Product
from apps.user.models import Admin

User = get_user_model()


class Command(BaseCommand):
    help = '初始化生产管理模块测试数据 - 基础数据模型'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scale',
            type=str,
            default='medium',
            choices=[
                'small',
                'medium',
                'large'],
            help='数据规模: small/medium/large')
        parser.add_argument('--clear', action='store_true', help='清除现有数据后重新生成')

    def handle(self, *args, **options):
        scale = options['scale']
        clear_existing = options['clear']

        scale_config = {
            'small': {
                'procedures': 5,
                'equipment': 5,
                'plans': 3,
                'tasks_per_plan': 3,
                'data_points': 50},
            'medium': {
                'procedures': 10,
                'equipment': 10,
                'plans': 10,
                'tasks_per_plan': 5,
                'data_points': 200},
            'large': {
                'procedures': 20,
                'equipment': 20,
                'plans': 30,
                'tasks_per_plan': 8,
                'data_points': 500}}
        config = scale_config[scale]

        self.stdout.write(self.style.SUCCESS(
            f'开始初始化生产管理测试数据 (规模: {scale})...'))

        if clear_existing:
            self.stdout.write(self.style.WARNING('清除现有生产数据...'))
            self._clear_all_data()

        now = timezone.now()
        self.today = now.date()

        admin_user = self._ensure_admin_user()
        departments = self._ensure_departments()
        products = self._ensure_products()

        procedures = self._create_procedures(
            departments, admin_user, config['procedures'])
        procedure_set = self._create_procedure_set(procedures, admin_user)

        boms = self._create_boms(products, admin_user)

        equipment = self._create_equipment(
            departments, admin_user, config['equipment'])

        self._create_sops(procedures, admin_user)

        data_sources = self._create_data_sources(admin_user)

        plans = self._create_production_plans(
            products, boms, procedure_set, departments, admin_user,
            config['plans'], config['tasks_per_plan'], procedures, equipment
        )

        self._create_quality_checks(plans, admin_user)

        self._create_data_collection(
            data_sources,
            equipment,
            plans,
            config['data_points'],
            admin_user)

        self._create_production_data_points(
            equipment, plans, procedures, config['data_points'], admin_user)

        self._create_data_collection_tasks(data_sources, admin_user)

        self._create_production_order_changes(plans, admin_user)

        self._create_production_line_day_plans(plans, departments, admin_user)

        self._print_summary()

    def _clear_all_data(self):
        models_to_delete = [
            ProductionLineDayPlan, ProductionOrderChange,
            DataCollectionTask, ProductionDataPoint,
            DataCollection, DataMapping, DataSource, QualityCheck,
            ProductionTask, ProductionPlan, BOMItem, BOM,
            ProcedureSetItem, ProcedureSet, SOP, Equipment, ProductionProcedure
        ]
        for model in models_to_delete:
            model.objects.all().delete()
            self.stdout.write(f'  已清空: {model._meta.verbose_name}')

    def _ensure_admin_user(self):
        admin_user, created = Admin.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('创建管理员用户: admin'))
        return admin_user

    def _ensure_departments(self):
        departments = {}
        dept_data = [
            ('生产部', '负责产品生产制造', 1),
            ('质量部', '负责质量检测', 1),
            ('仓储部', '负责物料仓储管理', 1),
            ('设备部', '负责设备维护管理', 1),
        ]
        for name, remark, status in dept_data:
            dept, created = Department.objects.get_or_create(
                name=name,
                defaults={'remark': remark, 'status': status}
            )
            departments[name] = dept
            if created:
                self.stdout.write(self.style.SUCCESS(f'创建部门: {name}'))
        return departments

    def _ensure_products(self):
        products = []
        product_data = [
            ('工业机器人', 'ROBOT001', 'UR-10型工业机器人', '台', 150000),
            ('自动化生产线', 'LINE001', '汽车零部件自动化生产线', '条', 500000),
            ('数控机床', 'CNC001', '五轴联动数控机床', '台', 280000),
            ('检测设备', 'QC001', '高精度视觉检测设备', '套', 85000),
            ('包装机械', 'PKG001', '自动包装流水线', '台', 65000),
            ('输送设备', 'CONV001', '皮带输送机', '台', 25000),
        ]
        for name, code, specs, unit, price in product_data:
            product, created = Product.objects.get_or_create(
                code=code, defaults={
                    'name': name, 'specs': specs, 'unit': unit, 'price': Decimal(price)})
            products.append(product)
            if created:
                self.stdout.write(self.style.SUCCESS(f'创建产品: {name}'))
        return products

    def _create_procedures(self, departments, admin_user, count):
        procedures = []
        procedure_names = [
            ('原料检验', '原料入库前的质量检验', 1.0, 60.0),
            ('原料预处理', '原料清洗、切割等预处理', 2.0, 50.0),
            ('加工成型', '主要加工成型工序', 4.0, 80.0),
            ('热处理', '产品热处理工艺', 3.0, 70.0),
            ('表面处理', '喷涂、电镀等表面处理', 2.5, 65.0),
            ('精密加工', '高精度零件加工', 5.0, 120.0),
            ('组装工序', '产品组装装配', 3.0, 75.0),
            ('功能测试', '产品功能测试检验', 1.5, 70.0),
            ('外观检验', '产品外观质量检验', 1.0, 55.0),
            ('包装入库', '产品包装和入库', 1.5, 40.0),
        ]
        dept_list = list(departments.values())

        for i in range(min(count, len(procedure_names))):
            name, desc, time, cost = procedure_names[i]
            procedure, created = ProductionProcedure.objects.get_or_create(
                code=f'PROC{str(i+1).zfill(3)}',
                defaults={
                    'name': name,
                    'description': desc,
                    'standard_time': Decimal(str(time)),
                    'cost_per_hour': Decimal(str(cost)),
                    'department': random.choice(dept_list),
                    'creator': admin_user,
                    'status': True,
                    'sort': i,
                }
            )
            procedures.append(procedure)
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'创建工序: {procedure.name}'))
        return procedures

    def _create_procedure_set(self, procedures, admin_user):
        if not procedures:
            return None
        procedure_set, created = ProcedureSet.objects.get_or_create(
            code='SET001',
            defaults={
                'name': '标准生产工序集',
                'description': '标准产品生产的完整工艺流程',
                'total_time': sum(p.standard_time for p in procedures),
                'total_cost': sum(p.standard_time * p.cost_per_hour for p in procedures),
                'creator': admin_user,
                'status': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(
                f'创建工序集: {procedure_set.name}'))
            for i, procedure in enumerate(procedures):
                ProcedureSetItem.objects.create(
                    procedure_set=procedure_set,
                    procedure=procedure,
                    sequence=i + 1,
                    estimated_time=procedure.standard_time,
                )
        return procedure_set

    def _create_boms(self, products, admin_user):
        boms = []
        for i, product in enumerate(products):
            materials = [
                ('钢材', 'MAT-STEEL-001', 'Q235B', 'kg', 8.5),
                ('铝材', 'MAT-ALUM-001', '6061-T6', 'kg', 25.0),
                ('铜材', 'MAT-COP-001', '纯铜', 'kg', 65.0),
                ('塑料粒', 'MAT-PLAS-001', 'ABS', 'kg', 12.0),
                ('电子元件', 'MAT-ELEC-001', '各类', '个', 5.0),
                ('螺丝配件', 'MAT-SCREW-001', 'M6/M8', '个', 0.5),
            ]
            bom, created = BOM.objects.get_or_create(
                code=f'BOM{str(i+1).zfill(3)}',
                defaults={
                    'name': f'{product.name}物料清单',
                    'product': product,
                    'version': f'{random.randint(1, 5)}.0',
                    'description': f'{product.name}的标准BOM配置',
                    'creator': admin_user,
                    'status': True,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'创建BOM: {bom.name}'))
                item_count = random.randint(4, min(6, len(materials)))
                selected_materials = random.sample(materials, item_count)
                for j, (mat_name, mat_code, spec, unit,
                        unit_cost) in enumerate(selected_materials):
                    quantity = Decimal(str(random.uniform(1, 50)))
                    total_cost = quantity * Decimal(str(unit_cost))
                    BOMItem.objects.create(
                        bom=bom,
                        material_name=mat_name,
                        material_code=mat_code,
                        specification=spec,
                        unit=unit,
                        quantity=quantity,
                        unit_cost=Decimal(str(unit_cost)),
                        total_cost=total_cost,
                        supplier=f'供应商{random.randint(1, 10)}',
                    )
            boms.append(bom)
        return boms

    def _create_equipment(self, departments, admin_user, count):
        equipment_list = []
        equipment_names = [
            ('数控车床', 'CNC-LATHE', '沈阳机床'),
            ('加工中心', 'MC-CENTER', 'DMG Mori'),
            ('铣床', 'MILLING', '哈量集团'),
            ('磨床', 'GRINDER', '无心磨床'),
            ('冲压机', 'PRESS', '济南二机'),
            ('焊接机器人', 'WELD-ROBOT', '发那科'),
            ('喷涂设备', 'SPRAY', '涂装设备'),
            ('检测仪器', 'QC-INSTR', '海克斯康'),
            ('输送线', 'CONV-LINE', '输送设备'),
            ('装配工作台', 'ASSY-WORK', '定制工装'),
            ('空压机', 'COMPRESSOR', '压缩机'),
            ('制冷设备', 'COOLING', '制冷机组'),
        ]
        statuses = [1, 1, 1, 2, 1, 1, 1, 1, 1, 2, 1, 1]
        dept_list = list(departments.values())

        for i in range(min(count, len(equipment_names))):
            name, model, manufacturer = equipment_names[i]
            purchase_date = self.today - \
                timedelta(days=random.randint(30, 730))
            last_maintenance = self.today - \
                timedelta(days=random.randint(5, 60))
            next_maintenance = last_maintenance + timedelta(days=30)
            equipment, created = Equipment.objects.get_or_create(
                code=f'EQ{str(i+1).zfill(3)}',
                defaults={
                    'name': name,
                    'model': model,
                    'manufacturer': manufacturer,
                    'purchase_date': purchase_date,
                    'purchase_cost': Decimal(random.randint(50000, 500000)),
                    'department': random.choice(dept_list),
                    'location': f'车间{i//4 + 1}区{random.randint(1, 5)}号线',
                    'status': statuses[i % len(statuses)],
                    'responsible_person': admin_user,
                    'maintenance_cycle': random.choice([15, 30, 45, 60, 90]),
                    'last_maintenance': last_maintenance,
                    'next_maintenance': next_maintenance,
                    'creator': admin_user,
                }
            )
            equipment_list.append(equipment)
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'创建设备: {equipment.name}'))
        return equipment_list

    def _create_sops(self, procedures, admin_user):
        sops = []
        sop_templates = [
            ('安全操作规程', '设备安全操作注意事项', '严格遵守安全操作规程，佩戴防护装备'),
            ('开机前检查', '设备启动前检查项目', '检查油位、气压、冷却水'),
            ('加工操作规程', '零件加工标准操作流程', '按照工艺卡要求操作'),
            ('质量检验标准', '产品质量检验标准', '按检验规范进行抽检'),
            ('异常处理流程', '生产异常处理步骤', '发现异常立即停机报告'),
            ('设备维护保养', '日常维护保养项目', '定期清洁、润滑、紧固'),
        ]
        for i, (name, quality_std, safety) in enumerate(sop_templates):
            procedure = procedures[i % len(procedures)] if procedures else None
            sop, created = SOP.objects.get_or_create(
                code=f'SOP{str(i+1).zfill(3)}',
                defaults={
                    'name': name,
                    'procedure': procedure,
                    'version': f'{random.randint(1, 3)}.0',
                    'content': f'{name}详细操作说明...',
                    'safety_requirements': safety,
                    'quality_standards': quality_std,
                    'tools_required': '通用工具、量具',
                    'status': True,
                    'creator': admin_user,
                }
            )
            sops.append(sop)
            if created:
                self.stdout.write(self.style.SUCCESS(f'创建SOP: {sop.name}'))
        return sops

    def _create_data_sources(self, admin_user):
        data_sources = []
        source_types = [
            ('API接口', 'api', 'https://api.sensor.com/v1/data'),
            ('IoT设备', 'iot', 'mqtt://iot.platform.com'),
            ('数据库', 'database', 'postgresql://localhost:5432/production'),
            ('Modbus协议', 'modbus', 'modbus://192.168.1.100:502'),
        ]
        for i, (name, source_type, endpoint) in enumerate(source_types):
            ds, created = DataSource.objects.get_or_create(
                code=f'DS{str(i+1).zfill(3)}',
                defaults={
                    'name': name,
                    'source_type': source_type,
                    'description': f'{name}数据采集配置',
                    'endpoint_url': endpoint,
                    'host': f'192.168.{random.randint(1, 10)}.{random.randint(1, 254)}',
                    'port': random.choice([80, 443, 502, 1883]),
                    'auth_type': random.choice(['none', 'basic', 'api_key', 'bearer']),
                    'collection_interval': random.choice([5, 10, 30, 60, 300]),
                    'is_active': random.choice([True, True, True, False]),
                    'creator': admin_user,
                }
            )
            data_sources.append(ds)
            if created:
                self.stdout.write(self.style.SUCCESS(f'创建数据源: {ds.name}'))

            if created and random.random() > 0.3:
                for j in range(random.randint(2, 5)):
                    DataMapping.objects.create(
                        data_source=ds,
                        name=f'字段{j+1}',
                        source_path=f'data.{["value", "temperature", "pressure", "humidity"][j % 4]}',
                        field_type=random.choice(
                            ['float', 'integer', 'string', 'boolean']),
                        transform_type='none',
                        is_required=random.choice([True, False]),
                        sort=j,
                    )
        return data_sources

    def _create_production_plans(
            self,
            products,
            boms,
            procedure_set,
            departments,
            admin_user,
            plans_count,
            tasks_per_plan,
            procedures,
            equipment):
        plans = []
        plan_names = [
            'Q1季度生产计划', 'Q2季度生产计划', 'Q3季度生产计划', 'Q4季度生产计划',
            '紧急补货计划', '新产品试产计划', '常规生产计划', '大客户订单计划',
            '备库生产计划', '促销活动备货计划', '技术改造计划', '产能扩充计划',
        ]
        statuses = [3, 3, 4, 4, 2, 2, 1, 1, 1, 2, 2, 3]
        priorities = [1, 2, 2, 2, 1, 1, 3, 3, 2, 2, 2, 3]

        for i in range(plans_count):
            plan_start = self.today - timedelta(days=random.randint(0, 180))
            plan_end = plan_start + timedelta(days=random.randint(14, 60))
            status = statuses[i % len(statuses)]
            priority = priorities[i % len(priorities)]

            plan, created = ProductionPlan.objects.get_or_create(
                code=f'PP{str(i+1).zfill(4)}',
                defaults={
                    'name': plan_names[i % len(plan_names)] if i < len(plan_names) else f'生产计划{i+1}',
                    'product': products[i % len(products)] if products else None,
                    'bom': boms[i % len(boms)] if boms else None,
                    'procedure_set': procedure_set,
                    'quantity': Decimal(random.randint(100, 5000)),
                    'unit': '个',
                    'plan_start_date': plan_start,
                    'plan_end_date': plan_end,
                    'actual_start_date': plan_start if status in [2, 3, 4] else None,
                    'actual_end_date': plan_end if status == 4 else None,
                    'status': status,
                    'priority': priority,
                    'department': departments.get('生产部'),
                    'manager': admin_user,
                    'creator': admin_user,
                    'auto_complete': random.choice([True, False]),
                    'complete_threshold': Decimal(random.choice([95, 98, 100])),
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f'创建生产计划: {plan.name}'))

                for j in range(tasks_per_plan):
                    if not procedures:
                        continue
                    procedure = procedures[j % len(procedures)]
                    equip = equipment[j %
                                      len(equipment)] if equipment else None
                    task_start_date = plan_start + timedelta(days=j * 2)
                    task_end_date = task_start_date + timedelta(days=2)
                    task_start = datetime.combine(
                        task_start_date, datetime.min.time())
                    task_end = datetime.combine(
                        task_end_date, datetime.min.time())
                    quantity = plan.quantity / tasks_per_plan
                    task_status = random.choice([3, 3, 3, 2, 2, 1, 6])
                    completed_qty = Decimal(0)
                    qualified_qty = Decimal(0)

                    if task_status == 3:
                        completed_qty = quantity * \
                            Decimal(random.uniform(0.9, 1.0))
                        qualified_qty = completed_qty * \
                            Decimal(random.uniform(0.95, 1.0))
                    elif task_status == 2:
                        completed_qty = quantity * \
                            Decimal(random.uniform(0.2, 0.8))

                    task, task_created = ProductionTask.objects.get_or_create(
                        code=f'TASK{str(i+1).zfill(4)}{str(j+1).zfill(2)}',
                        defaults={
                            'plan': plan,
                            'name': f'{plan.name} - 任务{j+1}',
                            'procedure': procedure,
                            'equipment': equip,
                            'quantity': quantity,
                            'completed_quantity': completed_qty,
                            'qualified_quantity': qualified_qty,
                            'defective_quantity': max(Decimal(0), completed_qty - qualified_qty),
                            'plan_start_time': task_start,
                            'plan_end_time': task_end,
                            'actual_start_time': task_start if task_status in [2, 3] else None,
                            'actual_end_time': task_end if task_status == 3 else None,
                            'status': task_status,
                            'assignee': admin_user,
                            'creator': admin_user,
                        }
                    )

            plans.append(plan)
        return plans

    def _create_quality_checks(self, plans, admin_user):
        for plan in plans:
            tasks = plan.tasks.filter(status=3)
            for task in tasks[:random.randint(1, 3)]:
                if random.random() > 0.3:
                    check, created = QualityCheck.objects.get_or_create(
                        task=task,
                        check_time=task.actual_end_time or timezone.now(),
                        defaults={
                            'checker': admin_user,
                            'check_quantity': task.completed_quantity,
                            'qualified_quantity': task.qualified_quantity,
                            'defective_quantity': task.defective_quantity,
                            'result': 1 if (task.qualified_quantity / max(task.completed_quantity, 1) >= Decimal('0.95')) else 2,
                            'defect_description': '轻微划痕' if random.random() < 0.2 else '',
                            'improvement_suggestion': '加强过程控制' if random.random() < 0.3 else '',
                        }
                    )
                    if created:
                        self.stdout.write(f'  创建质量检查记录')

    def _create_data_collection(
            self,
            data_sources,
            equipment,
            plans,
            count,
            admin_user):
        if not equipment:
            return
        created_count = 0
        for i in range(min(count, 30)):
            equipment_item = random.choice(equipment)
            task = None
            if plans:
                plan = random.choice(plans)
                task = plan.tasks.first()

            DataCollection.objects.create(
                task=task,
                equipment=equipment_item,
                parameter_name=random.choice(
                    ['温度', '压力', '转速', '电流', '电压', '流量', '液位']),
                parameter_value=Decimal(str(random.uniform(0, 100))),
                unit=random.choice(
                    ['℃', 'MPa', 'r/min', 'A', 'V', 'm³/h', 'mm']),
                standard_min=Decimal(str(random.uniform(10, 30))),
                standard_max=Decimal(str(random.uniform(70, 90))),
                is_normal=random.choice([True, True, True, False]),
                collect_time=timezone.now() - timedelta(minutes=random.randint(0, 1000)),
                collector=admin_user,
            )
            created_count += 1
        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(
                f'创建数据采集记录: {created_count}条'))

    def _create_production_data_points(
            self,
            equipment,
            plans,
            procedures,
            count,
            admin_user):
        if not equipment:
            return
        created_count = 0
        for i in range(count):
            equip = random.choice(equipment)
            task = None
            procedure = None
            if plans:
                plan = random.choice(plans)
                task = plan.tasks.first()
            if procedures:
                procedure = random.choice(procedures)

            timestamp = timezone.now() - timedelta(minutes=random.randint(0, 10000))
            ProductionDataPoint.objects.create(
                equipment=equip,
                metric_name=random.choice(
                    ['设备温度', '运行转速', '生产产量', '能耗', '故障次数', '维护次数']),
                metric_value=str(random.uniform(0, 100)),
                metric_unit=random.choice(
                    ['℃', 'r/min', '个', 'kWh', '次', '次']),
                timestamp=timestamp,
                collection_time=timestamp,
                quality=random.choice(
                    ['good', 'good', 'good', 'uncertain', 'bad']),
                confidence=random.uniform(0.8, 1.0),
                task=task,
                procedure=procedure,
                tags={'生产线': f'Line{random.randint(1, 5)}', '班组': f'A班'},
                metadata={'source': 'sensor', 'version': '1.0'},
            )
            created_count += 1
        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(f'创建生产数据点: {created_count}条'))

    def _create_data_collection_tasks(self, data_sources, admin_user):
        task_types = ['scheduled', 'scheduled', 'manual', 'continuous']
        for i in range(5):
            task_name = f'数据采集任务{i+1}'
            task, created = DataCollectionTask.objects.get_or_create(
                name=task_name,
                defaults={
                    'task_type': task_types[i % len(task_types)],
                    'cron_expression': f'*/{random.randint(1, 5)} * * * *',
                    'interval_seconds': random.choice([60, 300, 600, 1800]),
                    'max_retries': random.randint(1, 5),
                    'timeout_seconds': random.choice([30, 60, 120, 300]),
                    'status': random.choice(['pending', 'running', 'completed']),
                    'total_runs': random.randint(0, 100),
                    'success_runs': random.randint(0, 100),
                    'failed_runs': random.randint(0, 10),
                    'is_active': random.choice([True, True, False]),
                    'creator': admin_user,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'创建数据采集任务: {task.name}'))
                if data_sources:
                    task.data_sources.set(
                        random.sample(
                            data_sources, min(
                                2, len(data_sources))))

    def _create_production_order_changes(self, plans, admin_user):
        for plan in plans[:min(3, len(plans))]:
            old_qty = float(plan.quantity)
            new_qty = float(plan.quantity * Decimal('1.2'))
            change, created = ProductionOrderChange.objects.get_or_create(
                production_plan=plan,
                change_type=random.choice(['数量变更', '交期变更', '工艺变更', '物料变更']),
                defaults={
                    'change_reason': '客户需求调整，需要修改生产计划',
                    'old_value': {'quantity': old_qty, 'end_date': str(plan.plan_end_date)},
                    'new_value': {'quantity': new_qty, 'end_date': str(plan.plan_end_date + timedelta(days=5))},
                    'status': random.choice([1, 2, 3, 4]),
                    'creator': admin_user,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'创建生产订单变更: {plan.name}'))

    def _create_production_line_day_plans(
            self, plans, departments, admin_user):
        for i, plan in enumerate(plans[:min(5, len(plans))]):
            day_plan, created = ProductionLineDayPlan.objects.get_or_create(
                code=f'DP{str(i+1).zfill(4)}',
                defaults={
                    'name': f'{plan.name}-日计划',
                    'production_line': f'Line{random.randint(1, 5)}',
                    'plan_date': plan.plan_start_date + timedelta(days=random.randint(0, 10)),
                    'production_plan': plan,
                    'quantity': plan.quantity / random.randint(5, 10),
                    'completed_quantity': Decimal(0),
                    'status': random.choice([1, 2, 3, 4]),
                    'manager': admin_user,
                    'creator': admin_user,
                }
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'创建生产线日计划: {day_plan.code}'))

    def _print_summary(self):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('生产管理模块测试数据初始化完成！'))
        self.stdout.write(f'  - 基本工序: {ProductionProcedure.objects.count()} 个')
        self.stdout.write(f'  - 工序集: {ProcedureSet.objects.count()} 个')
        self.stdout.write(f'  - BOM清单: {BOM.objects.count()} 个')
        self.stdout.write(f'  - 设备数量: {Equipment.objects.count()} 台')
        self.stdout.write(f'  - SOP文档: {SOP.objects.count()} 份')
        self.stdout.write(f'  - 生产计划: {ProductionPlan.objects.count()} 个')
        self.stdout.write(f'  - 生产任务: {ProductionTask.objects.count()} 个')
        self.stdout.write(f'  - 质量检查: {QualityCheck.objects.count()} 条')
        self.stdout.write(f'  - 数据源: {DataSource.objects.count()} 个')
        self.stdout.write(f'  - 数据采集: {DataCollection.objects.count()} 条')
        self.stdout.write(
            f'  - 生产数据点: {ProductionDataPoint.objects.count()} 条')
        self.stdout.write(self.style.SUCCESS('=' * 60))
