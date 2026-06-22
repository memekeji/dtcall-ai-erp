# -*- coding: utf-8 -*-
"""
为项目所有模块生成全面、合理、完整的测试数据
使用方式: python manage.py generate_test_data
"""

import random
import os
from datetime import datetime, timedelta, date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

User = get_user_model()


def now_ts():
    """返回当前时间戳"""
    return int(timezone.now().timestamp())


def random_ts(days_back=365):
    """返回随机过去时间戳"""
    delta = timedelta(seconds=random.randint(1, days_back * 86400))
    return int((timezone.now() - delta).timestamp())


def random_date(start_days_back=365, end_days_back=1):
    """返回随机日期"""
    delta = timedelta(days=random.randint(end_days_back, start_days_back))
    return (timezone.now() - delta).date()


def random_phone():
    """随机手机号"""
    return f"1{random.choice(['3','5','6','7','8','9'])}{''.join([str(random.randint(0,9)) for _ in range(9)])}"


class Command(BaseCommand):
    help = '为项目所有模块生成全面测试数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-count', type=int, default=30,
            help='生成用户数量(默认30)')
        parser.add_argument(
            '--clear', action='store_true',
            help='是否先清空所有数据'
        )

    # ========== 16. 审批流程模块 ==========
    def create_approval_module(self):
        self.stdout.write('\n[16/19] 创建审批流程模块数据...')
        from apps.approval.models import (
            ApprovalType, ApprovalFlow, ApprovalStep, ApprovalFlowEdge,
            Approval, ApprovalRecord, ApprovalTask,
        )
        from apps.user.models.department import Department as UserDepartment

        admin = self._get_user()

        # 审批类型
        type_data = [
            ('expense', '报销审批', 'layui-icon-rmb', '各类费用报销审批'),
            ('leave', '请假审批', 'layui-icon-log', '员工请假申请审批'),
            ('contract', '合同审批', 'layui-icon-file', '合同签署审批流程'),
            ('purchase', '采购审批', 'layui-icon-cart-simple', '采购申请审批'),
            ('travel', '出差审批', 'layui-icon-location', '出差申请审批'),
            ('overtime', '加班审批', 'layui-icon-time', '加班申请审批'),
        ]
        types = {}
        for code, name, icon, desc in type_data:
            obj, _ = ApprovalType.objects.get_or_create(
                code=code,
                defaults={'name': name, 'icon': icon, 'description': desc, 'sort_order': len(types), 'is_active': True}
            )
            types[code] = obj

        # 审批流程
        flow_data = [
            ('expense_flow', '标准报销审批流程', 'expense'),
            ('leave_flow', '请假审批流程', 'leave'),
            ('contract_flow', '合同审批流程', 'contract'),
            ('purchase_flow', '采购审批流程', 'purchase'),
            ('travel_flow', '出差审批流程', 'travel'),
            ('overtime_flow', '加班审批流程', 'overtime'),
        ]
        flows = {}
        for code, name, atype_code in flow_data:
            obj, _ = ApprovalFlow.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'approval_type': types.get(atype_code),
                    'is_active': True,
                    'form_fields': '[]',
                }
            )
            flows[code] = obj

        # 审批步骤（每个流程3-4个步骤）
        step_configs = {
            'expense_flow': [
                ('提交报销申请', 'department_head', 'approve', 1),
                ('财务审核', 'role', 'approve', 2),
                ('总经理审批(>=5000元)', 'condition', 'approve', 3),
                ('财务打款', 'execute', 'execute', 4),
            ],
            'leave_flow': [
                ('提交请假申请', 'department_head', 'approve', 1),
                ('HR审核', 'role', 'approve', 2),
                ('总经理审批(>=3天)', 'condition', 'approve', 3),
            ],
            'contract_flow': [
                ('提交合同', 'department_head', 'approve', 1),
                ('法务审核', 'specific_user', 'review', 2),
                ('财务审核', 'department', 'approve', 3),
                ('总经理审批', 'level', 'approve', 4),
            ],
            'purchase_flow': [
                ('提交采购申请', 'department_head', 'approve', 1),
                ('财务审核预算', 'department', 'approve', 2),
                ('采购确认', 'execute', 'execute', 3),
            ],
            'travel_flow': [
                ('提交出差申请', 'department_head', 'approve', 1),
                ('行政备案', 'notification', 'notify', 2),
            ],
            'overtime_flow': [
                ('提交加班申请', 'department_head', 'approve', 1),
                ('累计时长确认', 'condition', 'review', 2),
            ],
        }

        all_approvers = [u for u in self.USERS[:3]]

        for flow_code, steps_data in step_configs.items():
            flow = flows[flow_code]
            for step_name, step_type, action_type, step_order in steps_data:
                step, _ = ApprovalStep.objects.get_or_create(
                    flow=flow,
                    step_name=step_name,
                    step_order=step_order,
                    defaults={
                        'step_type': step_type,
                        'action_type': action_type,
                        'approver': random.choice(all_approvers) if step_type == 'specific_user' else None,
                        'approver_role': '财务主管' if step_type == 'role' else '',
                        'approver_department': '财务部' if step_type == 'department' else '',
                        'approver_level': '总经理' if step_type == 'level' else '',
                        'time_limit_hours': random.choice([24, 48, 72]),
                        'is_required': True,
                        'require_comment': True,
                        'config_json': '{}',
                    }
                )

        # 审批申请数据
        approval_titles = [
            '出差至北京参加行业峰会', '购买服务器设备申请', '2025年Q3差旅费报销',
            '年假申请(5天)', 'OA系统升级服务合同', '办公家具采购申请',
            '部门团建费用报销', '参加技术培训请假', '年度维护服务续约合同',
            '项目外包采购申请', '国庆节加班申请(3天)', '客户招待费报销',
        ]
        for i, title in enumerate(approval_titles):
            flow = random.choice(list(flows.values()))
            status = random.choice([0, 1, 2, 2, 2])
            app = Approval.objects.create(
                title=title,
                flow=flow,
                type_id=flow.approval_type_id if flow.approval_type_id else 1,
                applicant_id=random.choice(self.USERS).id,
                status=status,
                content=f'{title}的申请内容: 申请人因工作需要，申请{title.replace("申请", "").replace("审批", "")}...',
                reviewer=random.choice(self.USERS),
                current_step_order=1 if status in [0, 1] else 3,
            )

            # 审批记录
            record_actions = ['submit']
            if status >= 1:
                record_actions.append('approve')
            if status == 2:
                record_actions.append('approve')
            elif status == 3:
                record_actions.append('reject')
            for j, action in enumerate(record_actions):
                ApprovalRecord.objects.create(
                    approval=app,
                    step_order=j + 1,
                    step_name=f'第{j + 1}步',
                    action=action,
                    comment='同意' if action in ('approve', 'submit') else '不通过',
                    handler=random.choice(self.USERS),
                )

            # 审批任务
            for j in range(min(2, app.current_step_order)):
                ApprovalTask.objects.create(
                    approval=app,
                    step=flow.steps.first() if flow.steps.exists() else None,
                    handler=random.choice(self.USERS),
                    status='completed' if j == 0 else random.choice(['pending', 'completed', 'completed']),
                    result='通过',
                    comment='同意申请',
                    completed_at=timezone.now() - timedelta(hours=random.randint(1, 48)) if j == 0 else None,
                )

        self.stdout.write(f'  - 创建了 {len(types)} 个审批类型、{len(flows)} 个流程、{len(approval_titles)} 个审批申请')

    # ========== 17. AI智能模块 ==========
    def create_ai_module(self):
        self.stdout.write('\n[17/19] 创建AI智能模块数据...')
        try:
            from apps.ai.models import AIModelConfig, AIIntentRecognition, WorkflowTemplate
        except ImportError:
            self.stdout.write('  - AI模块模型未就绪，跳过')
            return

        admin = self._get_user()

        # AI模型配置
        model_data = [
            ('gpt-default', 'GPT-4o默认配置', 'openai', 'gpt-4o', 0.7, 4096),
            ('gpt-fast', 'GPT-4o-mini快速响应', 'openai', 'gpt-4o-mini', 0.5, 2048),
            ('claude-analysis', 'Claude分析模型', 'anthropic', 'claude-3-sonnet', 0.8, 8192),
            ('qwen-local', '通义千问本地推理', 'qwen', 'qwen-turbo', 0.7, 4096),
        ]
        models = {}
        for code, name, provider, model_name, temp, max_tokens in model_data:
            if hasattr(AIModelConfig, 'code'):
                obj, _ = AIModelConfig.objects.get_or_create(
                    code=code,
                    defaults={'name': name, 'provider': provider, 'model_name': model_name,
                              'temperature': temp, 'max_tokens': max_tokens, 'is_active': True}
                )
            else:
                obj, _ = AIModelConfig.objects.get_or_create(
                    name=name,
                    defaults={'provider': provider, 'model_name': model_name,
                              'temperature': temp, 'max_tokens': max_tokens, 'is_active': True}
                )
            models[code] = obj

        # 意图识别配置 (使用 intent_type 作为唯一标识)
        intent_data = [
            ('expense_review', '报销审核意图', '识别并处理费用报销相关意图', True),
            ('customer_intent', '客户意向识别', '识别客户意图和需求分类', True),
            ('contract_risk', '合同风险识别', '识别合同中的风险条款', True),
            ('sentiment_analysis', '情感分析', '分析文本中的情感倾向', True),
        ]
        for intent_type, name, desc, active in intent_data:
            AIIntentRecognition.objects.get_or_create(
                intent_type=intent_type,
                defaults={'description': desc, 'is_active': active}
            )

        # 工作流模板
        workflow_data = [
            ('expense_approval_wf', '报销审批工作流', '自动化报销审批流程，包含AI审核节点', True),
            ('contract_review_wf', '合同审查工作流', '智能合同审查和风险评估工作流', True),
            ('data_analysis_wf', '数据分析工作流', '自动生成数据分析和报告', False),
        ]
        for _, name, desc, active in workflow_data:
            WorkflowTemplate.objects.get_or_create(
                name=name,
                defaults={
                    'description': desc, 'is_public': active,
                    'category': 'other',
                    'workflow_data': {'nodes': [], 'edges': []},
                    'created_by': admin,
                }
            )

        self.stdout.write('  - 创建了AI模型配置、意图识别和工作流模板')

    # ========== 18. 蜘蛛数据模块 ==========
    def create_spider_module(self):
        self.stdout.write('\n[18/19] 创建蜘蛛数据模块...')
        try:
            from apps.spider.models import Company
        except ImportError:
            self.stdout.write('  - 蜘蛛模块模型未就绪，跳过')
            return

        company_data = [
            ('深圳市腾讯计算机系统有限公司', '马化腾', '650000000', '1998-11-11',
             '存续', '计算机软硬件技术开发、销售；信息咨询；经营进出口业务', '深圳市南山区粤海街道'),
            ('阿里巴巴（中国）有限公司', '蔡崇信', '1000000000', '1999-09-09',
             '存续', '电子商务、网络技术、信息技术服务', '浙江省杭州市余杭区'),
            ('华为技术有限公司', '任正非', '405000000', '1987-09-15',
             '存续', '通信设备制造、信息技术研发、服务', '深圳市龙岗区坂田街道'),
            ('北京字节跳动科技有限公司', '张一鸣', '300000000', '2012-03-09',
             '存续', '技术开发、技术推广、技术转让', '北京市海淀区知春路'),
            ('百度在线网络技术（北京）有限公司', '李彦宏', '200000000', '2000-01-03',
             '存续', '互联网信息服务、技术开发', '北京市海淀区上地十街'),
            ('京东集团股份有限公司', '刘强东', '500000000', '2004-01-01',
             '存续', '电子商务、物流配送、技术研发', '北京市亦庄经济技术开发区'),
        ]
        for name, legal_person, capital, date_str, status, scope, address in company_data:
            Company.objects.get_or_create(
                name=name,
                defaults={
                    'legal_person': legal_person,
                    'registered_capital': capital,
                    'establishment_date': date_str,
                    'registration_status': status,
                    'business_scope': scope,
                    'address': address,
                }
            )

        self.stdout.write(f'  - 创建了 {len(company_data)} 家企业信息')

    # ========== 19. 公共基础数据模块 ==========
    def create_common_module(self):
        self.stdout.write('\n[19/19] 创建公共基础数据...')
        try:
            from apps.common.models import IndustryCategory
        except ImportError:
            pass
        else:
            industries = [
                ('互联网/IT', 'it'), ('金融/保险', 'finance'),
                ('教育培训', 'education'), ('医疗健康', 'healthcare'),
                ('制造业', 'manufacturing'), ('房地产/建筑', 'real_estate'),
                ('贸易/零售', 'retail'), ('物流/运输', 'logistics'),
                ('能源/环保', 'energy'), ('文化/传媒', 'media'),
                ('政府/公共事业', 'government'), ('农林牧渔', 'agriculture'),
            ]
            for name, code in industries:
                IndustryCategory.objects.get_or_create(
                    code=code, defaults={'name': name, 'is_active': True}
                )
            self.stdout.write(f'  - 创建了 {len(industries)} 个行业分类')


    def handle(self, *args, **options):
        user_count = options['user_count']
        should_clear = options['clear']

        if should_clear:
            self.stdout.write(self.style.WARNING('警告：将清空所有现有数据...'))
            # 此处不自动清空，避免误操作
            self.stdout.write(self.style.ERROR('请手动清理数据库后再运行此命令'))
            return

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('开始为项目所有模块生成测试数据...'))
        self.stdout.write(self.style.SUCCESS(f'目标用户数: {user_count}'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # 逐模块执行，单个模块失败不影响其他模块
        module_methods = [
            ('1. 用户与组织架构', self.create_users_and_org, [user_count]),
            ('2. 企业信息', self.create_enterprise, []),
            ('3. 合同模块', self.create_contract_module, []),
            ('4. 客户模块', self.create_customer_module, []),
            ('5. 财务模块', self.create_finance_module, []),
            ('6. 项目模块', self.create_project_module, []),
            ('7. 定时任务模块', self.create_task_module, []),
            ('8. 生产模块', self.create_production_module, []),
            ('9. 库存模块', self.create_inventory_module, []),
            ('10. OA办公模块', self.create_oa_module, []),
            ('11. 系统管理模块', self.create_system_module, []),
            ('12. 知识库模块', self.create_disk_module, []),
            ('13. 消息通知模块', self.create_message_module, []),
            ('14. 个人中心模块', self.create_personal_module, []),
            ('15. 工作台模块', self.create_work_module, []),
            ('16. 审批流程模块', self.create_approval_module, []),
            ('17. AI模块', self.create_ai_module, []),
            ('18. 爬虫模块', self.create_spider_module, []),
            ('19. 通用模块', self.create_common_module, []),
        ]

        success_count = 0
        fail_count = 0
        for module_name, method, args in module_methods:
            try:
                with transaction.atomic():
                    method(*args)
                success_count += 1
            except Exception as e:
                fail_count += 1
                self.stdout.write(self.style.ERROR(f'  [ERR] {module_name} : {e}'))
                import traceback
                self.stdout.write(self.style.WARNING(traceback.format_exc()))

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS(f'测试数据生成完成！成功: {success_count}/{len(module_methods)}, 失败: {fail_count}'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

    # ========== 辅助方法 ==========
    def _get_user(self):
        """获取第一个用户作为默认用户"""
        if not hasattr(self, 'USERS') or not self.USERS:
            return User.objects.first()
        return self.USERS[0]

    def _random_name(self):
        """生成随机中文姓名"""
        surnames = ['张', '王', '李', '赵', '刘', '陈', '杨', '黄', '周', '吴', '徐', '孙', '马', '朱', '胡', '郭', '何', '高', '林', '罗',
                    '郑', '梁', '谢', '宋', '唐', '韩', '曹', '许', '邓', '冯', '彭', '曾', '肖', '田', '董', '潘', '袁', '于', '蒋', '蔡']
        male_names = ['伟', '强', '磊', '军', '涛', '明', '华', '建国', '文', '志强', '建军', '志伟', '鹏', '辉', '勇', '刚', '峰', '宇', '杰', '博',
                      '洋', '浩', '斌', '东', '宏', '超', '文华', '健', '宁', '志勇', '飞', '磊', '致远', '思远', '子轩', '浩然', '宇轩', '志明', '建华', '文博']
        female_names = ['芳', '敏', '静', '丽', '婷', '雪', '艳', '玲', '红', '娟', '秀兰', '秀英', '凤英', '桂英', '梅', '霞', '燕', '丽华', '海燕', '洁',
                        '颖', '小红', '雅文', '思雨', '紫萱', '雨桐', '一诺', '若溪', '沐晴', '心怡', '语嫣', '梦瑶', '诗涵', '悠然', '晓彤', '美琳', '梓萱', '欣怡', '静怡', '若兰']
        names = male_names + female_names
        return random.choice(surnames) + random.choice(names)

    # ========== 1. 用户与组织架构 ==========
    def create_users_and_org(self, user_count):
        self.stdout.write('\n[1/19] 创建用户与组织架构...')

        # 导入模型
        from apps.department.models import Department
        from apps.user.models.position import Position

        # 创建部门
        dept_names = [
            ('总经办', 0), ('技术研发部', 0), ('产品部', 0),
            ('市场部', 0), ('销售部', 0), ('客服部', 0),
            ('财务部', 0), ('人力资源部', 0), ('行政部', 0),
            ('采购部', 0), ('生产部', 0), ('质量部', 0),
            ('物流部', 0), ('信息部', 0), ('法务部', 0),
        ]
        # 二级部门
        sub_dept_names = [
            ('前端开发组', '技术研发部'), ('后端开发组', '技术研发部'), ('AI研发组', '技术研发部'),
            ('华东销售组', '销售部'), ('华南销售组', '销售部'), ('华北销售组', '销售部'),
            ('大客户销售组', '销售部'), ('电销组', '销售部'),
            ('会计组', '财务部'), ('出纳组', '财务部'),
        ]

        department_map = {}
        for name, pid_name in dept_names:
            dept, created = Department.objects.get_or_create(
                name=name,
                defaults={'pid': 0, 'sort': random.randint(1, 50), 'status': 1}
            )
            department_map[name] = dept

        for name, parent_name in sub_dept_names:
            parent = department_map.get(parent_name)
            Department.objects.get_or_create(
                name=name,
                defaults={'pid': parent.id if parent else 0, 'sort': random.randint(51, 100), 'status': 1}
            )

        all_departments = list(Department.objects.all())
        self.stdout.write(f'  - 创建了 {len(department_map) + len(sub_dept_names)} 个部门')

        # 创建职位
        position_names = ['CEO', 'CTO', '总监', '经理', '副经理', '主管', '高级工程师', '工程师', '助理工程师', '专员', '助理', '实习生']
        for i, pos_name in enumerate(position_names):
            Position.objects.get_or_create(
                title=pos_name,
                defaults={'did': 0, 'desc': f'公司{pos_name}岗位', 'sort': i + 1, 'status': 1}
            )
        all_positions = list(Position.objects.all())
        self.stdout.write(f'  - 创建了 {len(all_positions)} 个职位')

        # 创建用户
        last_names = ['张', '李', '王', '赵', '刘', '陈', '杨', '黄', '周', '吴',
                      '徐', '孙', '胡', '朱', '高', '林', '何', '郭', '马', '罗']
        first_names = ['伟', '芳', '娜', '秀珍', '敏', '静', '丽', '强', '磊', '军',
                       '洋', '勇', '艳', '杰', '娟', '涛', '明', '超', '秀兰', '霞',
                       '平', '刚', '桂秀', '文', '华', '飞', '玉兰', '桂花', '波', '斌']

        created_users = []
        for i in range(user_count):
            last_name = random.choice(last_names)
            if random.random() > 0.5:
                first_name = random.choice(first_names)
            else:
                first_name = ''.join(random.sample(first_names, random.choice([1, 2])))

            full_name = last_name + first_name
            username = f"user{i + 1:03d}"
            dept = random.choice(all_departments)
            pos = random.choice(all_positions)
            entry_ts = random_ts(days_back=1095)  # 3年内入职

            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'name': full_name,
                    'email': f'{username}@example.com',
                    'mobile': random_phone(),
                    'sex': random.choice([1, 2]),
                    'nickname': f'{full_name[:1]}{random.choice(["工","同","老"])}',
                    'did': dept.id,
                    'pid': 0,
                    'position_id': pos.id,
                    'position_name': pos.title,
                    'position_rank': random.randint(1, 8),
                    'type': '正式员工',
                    'is_staff': 1,
                    'job_number': f'EMP{1000 + i:04d}',
                    'entry_time': entry_ts,
                    'status': 1,
                    'thumb': random.choice([
                        '/static/images/avatar1.jpg',
                        '/static/images/avatar2.jpg',
                        '/static/images/avatar3.jpg',
                        '/static/images/avatar4.jpg',
                        '/static/images/avatar5.jpg',
                    ]),
                }
            )
            if created:
                user.set_password('test123456')
                user.save()
            created_users.append(user)

        self.stdout.write(f'  - 创建了 {len(created_users)} 个用户')
        self.USERS = created_users
        self.DEPTS = all_departments
        self.POSITIONS = all_positions

    # ========== 2. 企业信息 ==========
    def create_enterprise(self):
        self.stdout.write('\n[2/19] 创建企业信息...')
        from apps.enterprise.models import Enterprise

        enterprise_names = [
            '深圳市科创科技集团有限公司',
            '广州数智信息技术有限公司',
        ]
        for ent_name in enterprise_names:
            Enterprise.objects.get_or_create(
                title=ent_name,
                defaults={
                    'city': '深圳',
                    'bank': '中国工商银行深圳科技支行',
                    'bank_sn': f'622202{random.randint(1000000000, 9999999999)}',
                    'tax_num': f'91440300{random.randint(10000000, 99999999)}',
                    'phone': '0755-8600' + str(random.randint(1000, 9999)),
                    'address': '广东省深圳市南山区科技园高新大道' + str(random.randint(1, 200)) + '号',
                    'status': 1,
                    'create_time': random_ts(730),
                    'update_time': now_ts(),
                }
            )
        self.stdout.write('  - 创建了 2 个企业主体')

    # ========== 3. 合同模块 ==========
    def create_contract_module(self):
        self.stdout.write('\n[3/19] 创建合同模块数据...')
        from apps.contract.models import (
            ContractCategory, ProductCategory, ServiceCategory,
            Service, Supplier, PurchaseCategory, PurchaseItem,
            ContractCate, Contract, Product, ProductCate, Services
        )

        # 合同分类
        cate_names = ['销售合同', '采购合同', '服务合同', '租赁合同', '合作协议', '保密协议']
        contract_cates = []
        for name in cate_names:
            obj, _ = ContractCate.objects.get_or_create(title=name, defaults={'status': 1})
            contract_cates.append(obj)

        # 产品分类
        pc_names = ['软件产品', '硬件产品', '服务产品', '耗材配件']
        for name in pc_names:
            ProductCate.objects.get_or_create(title=name, defaults={'status': 1})
        product_cates = list(ProductCate.objects.all())

        # 产品
        products_data = [
            ('ERP企业管理系统', 'ERP-001'), ('CRM客户管理系统', 'CRM-001'),
            ('OA办公系统', 'OA-001'), ('MES生产执行系统', 'MES-001'),
            ('WMS仓储管理系统', 'WMS-001'), ('HRM人力资源系统', 'HRM-001'),
            ('服务器-Dell R750', 'HW-001'), ('交换机-Cisco 9200', 'HW-002'),
            ('云服务器ECS', 'SVC-001'), ('数据备份服务', 'SVC-002'),
        ]
        admin_user = self._get_user()
        for name, code in products_data:
            Product.objects.get_or_create(
                name=name, defaults={
                    'code': code,
                    'cate': random.choice(product_cates) if product_cates else None,
                    'unit': random.choice(['套', '台', '个', '年']),
                    'price': Decimal(str(random.randint(5000, 500000))),
                    'admin': admin_user,
                    'specs': random.choice(['标准版', '企业版', '专业版', 'V3.0']),
                }
            )

        # 合同分类（basedata）
        for name in ['销售合同', '采购合同', '服务合同', '合作协议']:
            ContractCategory.objects.get_or_create(name=name, defaults={'sort_order': 0, 'is_active': True})

        # 供应商
        suppliers = []
        supplier_names = ['华为技术有限公司', '阿里巴巴云计算', '腾讯云科技', '用友网络科技',
                          '金蝶软件', '浪潮集团', '戴尔中国', '深信服科技']
        for name in supplier_names:
            obj, _ = Supplier.objects.get_or_create(
                name=name, defaults={
                    'code': f'SUP-{name[:4].upper()}',
                    'contact_person': self._random_name(),
                    'contact_phone': random_phone(),
                    'address': f'深圳市南山区科技路{random.randint(1,500)}号',
                    'is_active': True,
                }
            )
            suppliers.append(obj)

        # 合同
        contracts_data = [
            ('智慧园区管理系统开发合同', 1, 350000),
            ('ERP系统实施服务合同', 2, 500000),
            ('OA办公自动化系统合同', 1, 200000),
            ('云服务器采购合同', 1, 120000),
            ('大数据分析平台合同', 1, 800000),
            ('网络安全加固服务合同', 2, 150000),
            ('数据中心托管服务合同', 2, 300000),
            ('全员培训服务合同', 2, 80000),
        ]
        sign_date = random_date(180)
        for i, (cname, types, cost) in enumerate(contracts_data):
            Contract.objects.get_or_create(
                name=cname, defaults={
                    'code': f'HT-{timezone.now().year}-{1001 + i:04d}',
                    'cate_id': contract_cates[i % len(contract_cates)].id if contract_cates else 0,
                    'types': types,
                    'customer': f'客户公司{chr(65+i)}',
                    'cost': Decimal(str(cost)),
                    'admin_id': admin_user.id,
                    'sign_time': int(sign_date.timestamp()) if hasattr(sign_date, 'timestamp') else 0,
                    'start_time': int(sign_date.timestamp()) if hasattr(sign_date, 'timestamp') else 0,
                    'end_time': random_ts(200),
                    'check_status': random.choice([0, 1, 2]),
                    'content': f'{cname}的详细合同内容......',
                    'did': admin_user.did,
                }
            )

        self.stdout.write('  - 创建了合同分类、产品、供应商和合同等数据')

    # ========== 4. 客户模块 ==========
    def create_customer_module(self):
        self.stdout.write('\n[4/19] 创建客户模块数据...')
        from apps.customer.models import (
            Customer, Contact, FollowRecord, CustomerOrder,
            CustomerContract, CustomerInvoice, CustomerGrade,
            CustomerSource, CustomerIntent, CustomerField,
            FollowField, OrderField, CallRecord
        )

        admin = self._get_user()

        # 客户等级
        grades = ['A级-战略客户', 'B级-重点客户', 'C级-普通客户', 'D级-潜在客户', 'E级-待开发']
        for i, name in enumerate(grades):
            CustomerGrade.objects.get_or_create(title=name, defaults={'sort': i + 1, 'status': 1})
        all_grades = list(CustomerGrade.objects.all())

        # 客户来源
        sources = ['搜索引擎', '电话营销', '展会活动', '老客户推荐', '社交媒体', '代理商渠道', '线下拜访']
        for i, name in enumerate(sources):
            CustomerSource.objects.get_or_create(title=name, defaults={'sort': i + 1, 'status': 1})
        all_sources = list(CustomerSource.objects.all())

        # 客户意向
        intents = ['高意向', '中意向', '低意向', '观望中', '可转化']
        for i, name in enumerate(intents):
            CustomerIntent.objects.get_or_create(name=name, defaults={'sort': i + 1, 'status': 1})
        all_intents = list(CustomerIntent.objects.all())

        # 客户跟进字段
        follow_fields_data = [
            ('跟进结果', 'follow_result', 'select', '成功,失败,待定', 1),
            ('客户反馈', 'feedback', 'textarea', '', 2),
        ]
        for name, fname, ftype, opts, sort in follow_fields_data:
            FollowField.objects.get_or_create(
                field_name=fname,
                defaults={
                    'name': name, 'field_type': ftype,
                    'options': opts, 'sort_order': sort, 'is_active': True, 'is_required': False
                }
            )

        # 订单字段
        order_fields_data = [
            ('交付方式', 'delivery_method', 'select', '快递,自取,电子交付', 1),
            ('付款方式', 'payment_method', 'select', '现结,月结,分期,预付', 2),
        ]
        for name, fname, ftype, opts, sort in order_fields_data:
            OrderField.objects.get_or_create(
                field_name=fname,
                defaults={
                    'name': name, 'field_type': ftype,
                    'options': opts, 'sort_order': sort, 'is_active': True, 'is_required': False
                }
            )

        # 客户自定义字段
        cust_fields = [('客户规模', 'company_scale', 'select', '小型,中型,大型,集团型')]
        for name, fname, ftype, opts in cust_fields:
            CustomerField.objects.get_or_create(
                field_name=fname,
                defaults={'name': name, 'field_type': ftype, 'options': opts, 'status': True}
            )

        # 客户
        industries = ['信息技术', '制造业', '金融', '教育', '医疗', '零售', '房地产', '物流', '能源', '建筑']
        cities = ['深圳', '广州', '上海', '北京', '杭州', '成都', '武汉', '南京', '西安', '重庆']

        for i in range(40):
            cust_name = f'{random.choice(["深圳市","广州市","上海市"])}' \
                       f'{random.choice(["创新","智联","华信","博达","天元","瑞丰"])}' \
                       f'{random.choice(["科技","信息技术","软件","数据"])}' \
                       f'{random.choice(["有限公司","股份有限公司"])}'
            follow_ts = random_ts(180)

            Customer.objects.get_or_create(
                name=cust_name,
                defaults={
                    'customer_source': random.choice(all_sources) if all_sources else None,
                    'grade_id': random.choice(all_grades).id if all_grades else 0,
                    'industry_id': 0,
                    'services_id': random.choice(all_intents).id if all_intents else 0,
                    'province': '广东省',
                    'city': random.choice(cities),
                    'address': f'{random.choice(["科技园","高新区","CBD","产业园"])}路{random.randint(1,500)}号',
                    'admin_id': admin.id,
                    'belong_uid': random.choice(self.USERS).id,
                    'belong_did': admin.did,
                    'follow_time': follow_ts,
                    'next_time': int((timezone.now() + timedelta(days=random.randint(1, 30))).timestamp()),
                    'content': f'{cust_name}主要业务介绍...',
                    'market': random.choice(industries),
                    'remark': f'重点跟进客户，决策链: {self._random_name()}',
                }
            )

        all_customers = list(Customer.objects.filter(delete_time=0))

        # 联系人
        for cust in all_customers[:20]:
            for _ in range(random.randint(1, 3)):
                Contact.objects.get_or_create(
                    customer=cust, contact_person=self._random_name(),
                    defaults={
                        'phone': random_phone(),
                        'position': random.choice(['总经理', '采购经理', '技术总监', 'IT经理']),
                        'is_primary': random.random() > 0.7,
                        'email': f'contact{random.randint(1,9999)}@example.com',
                    }
                )

        # 跟进记录
        for cust in all_customers[:25]:
            for _ in range(random.randint(1, 4)):
                ft = random.choice(['phone', 'visit', 'email', 'meeting', 'other'])
                FollowRecord.objects.create(
                    customer=cust,
                    follow_type=ft,
                    content=f'与客户沟通了{random.choice(["产品需求","项目进度","报价方案","合同条款"])}相关事宜。',
                    follow_user=random.choice(self.USERS),
                    next_follow_time=timezone.now() + timedelta(days=random.randint(1, 30)),
                    create_time=timezone.now() - timedelta(days=random.randint(1, 90)),
                )

        # 客户合同
        contract_status_choices = ['draft', 'pending', 'approved', 'signed', 'executing']
        for i, cust in enumerate(all_customers[:15]):
            sign_dt = random_date(365)
            contract_num = f'KH-HT-{timezone.now().year}-{1001 + sum(ord(c) for c in cust.name) + i * 7:04d}'
            CustomerContract.objects.get_or_create(
                contract_number=contract_num,
                defaults={
                    'customer': cust,
                    'name': f'{cust.name}项目合同',
                    'amount': Decimal(str(random.randint(50000, 800000))),
                    'sign_date': sign_dt,
                    'end_date': sign_dt + timedelta(days=random.randint(30, 365)),
                    'status': random.choice(contract_status_choices),
                    'contract_type': random.choice(['sales', 'service', 'maintenance']),
                    'create_user': admin,
                }
            )

        # 客户订单
        order_status_choices = ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'completed']
        for cust in all_customers[:12]:
            for _ in range(random.randint(1, 2)):
                CustomerOrder.objects.get_or_create(
                    customer=cust,
                    order_number=f'DD-{timezone.now().year}-{random.randint(20001,39999)}',
                    defaults={
                        'product_name': random.choice(['ERP系统', 'OA系统', 'CRM系统', '云服务器', '安全服务']),
                        'amount': Decimal(str(random.randint(10000, 300000))),
                        'order_date': random_date(180),
                        'status': random.choice(order_status_choices),
                        'finance_status': random.choice(['pending', 'synced']),
                        'create_user': admin,
                    }
                )

        # 客户发票
        for i, cust in enumerate(all_customers[:8]):
            inv_date = random_date(180)
            inv_no = f'FP-{timezone.now().year}-{10001 + sum(ord(c) for c in cust.name) + i * 3:04d}'
            CustomerInvoice.objects.get_or_create(
                invoice_number=inv_no,
                defaults={
                    'customer': cust,
                    'amount': Decimal(str(random.randint(10000, 200000))),
                    'tax_rate': Decimal('13.00'),
                    'tax_amount': Decimal(str(round(random.randint(10000, 200000) * 0.13, 2))),
                    'invoice_date': inv_date,
                    'invoice_type': random.choice(['ordinary', 'special', 'electronic']),
                    'status': random.choice(['draft', 'issued', 'sent']),
                    'create_user': admin,
                }
            )

        # 拨号记录
        for cust in all_customers[:10]:
            for _ in range(random.randint(1, 3)):
                CallRecord.objects.create(
                    phone=random_phone(),
                    customer_name=cust.name,
                    customer=cust,
                    duration=random.randint(30, 1200),
                    status=random.choice([0, 1, 1, 1, 2]),
                    call_count=random.randint(1, 5),
                    create_user=random.choice(self.USERS),
                )

        self.stdout.write(f'  - 创建了 {len(all_customers)} 个客户及相关数据')

    # ========== 5. 财务模块 ==========
    def create_finance_module(self):
        self.stdout.write('\n[5/19] 创建财务模块数据...')
        from apps.finance.models import (
            Expense, Income, Invoice, Payment, InvoiceRequest,
            TaxRecord, ChartOfAccount, FinanceAccount, FinanceBudget,
            AccountsReceivable, AccountsPayable, BankTransaction,
            FinancialReport, FinancialPeriodClose, LedgerVoucher, LedgerVoucherLine
        )
        import time

        admin_id = self._get_user().id
        now = int(time.time())
        last_year = now - 365 * 86400

        # 会计科目
        accounts_data = [
            ('1001', '库存现金', 'asset'), ('1002', '银行存款', 'asset'),
            ('1122', '应收账款', 'asset'), ('1403', '原材料', 'asset'),
            ('2001', '短期借款', 'liability'), ('2202', '应付账款', 'liability'),
            ('4001', '实收资本', 'equity'), ('4103', '本年利润', 'equity'),
            ('6001', '主营业务收入', 'income'), ('6601', '销售费用', 'expense'),
        ]
        for code, name, atype in accounts_data:
            ChartOfAccount.objects.get_or_create(
                code=code,
                defaults={
                    'name': name, 'account_type': atype,
                    'level': 1, 'is_leaf': True,
                    'balance_direction': 'debit' if atype in ['asset', 'cost', 'expense'] else 'credit',
                    'status': 'active', 'create_time': now,
                }
            )
        all_accounts = list(ChartOfAccount.objects.all())

        # 资金账户
        bank_names = ['中国工商银行深圳分行', '中国建设银行深圳分行', '招商银行深圳分行']
        for bank_name in bank_names:
            FinanceAccount.objects.get_or_create(
                name=bank_name,
                defaults={
                    'account_type': 'bank',
                    'bank_name': bank_name,
                    'account_no': f'6222{random.randint(10000000, 99999999)}',
                    'opening_balance': Decimal(str(random.randint(500000, 5000000))),
                    'current_balance': Decimal(str(random.randint(200000, 3000000))),
                    'status': 'active',
                    'create_time': now,
                }
            )
        fin_accounts = list(FinanceAccount.objects.all())

        # 报销 (混合新旧数据，确保本月有数据)
        expense_code_prefixes = ['BX', 'CL', 'CG']
        for i in range(20):
            # 前5条为本月数据，其余为过去1-180天
            if i < 5:
                expense_ts = now - random.randint(0, 28) * 86400
            else:
                expense_ts = now - random.randint(1, 180) * 86400
            Expense.objects.create(
                code=f'{random.choice(expense_code_prefixes)}-{timezone.now().year}-{1001 + i:04d}',
                admin_id=random.choice(self.USERS).id,
                did=random.choice(self.DEPTS).id,
                cost=Decimal(str(random.randint(500, 50000))),
                expense_time=expense_ts,
                check_status=random.choice([0, 1, 2, 2, 2]),
                pay_status=random.choice([0, 1]),
                create_time=expense_ts,
                remark=f'报销事项{i + 1}',
            )

        # 发票 (混合新旧数据)
        for i in range(15):
            if i < 5:
                invoice_ts = now - random.randint(0, 28) * 86400
            else:
                invoice_ts = now - random.randint(1, 200) * 86400
            Invoice.objects.create(
                code=f'FP-{timezone.now().year}-{20001 + i:04d}',
                customer_id=0,
                amount=Decimal(str(random.randint(10000, 500000))),
                admin_id=admin_id,
                open_status=random.choice([0, 1, 1]),
                types=1,
                invoice_type=random.choice([1, 2, 3]),
                invoice_title=f'客户公司{chr(65 + i)}',
                invoice_tax=f'914403{random.randint(10000000, 99999999):08d}',
                enter_status=random.choice([0, 1, 2]),
                check_status=2,
                create_time=invoice_ts,
            )

        # 回款 (混合新旧数据)
        for i in range(12):
            if i < 4:
                income_days = random.randint(0, 28)
            else:
                income_days = random.randint(30, 150)
            Income.objects.create(
                invoice_id=random.randint(1, 15),
                amount=Decimal(str(random.randint(5000, 200000))),
                income_date=timezone.now() - timedelta(days=income_days),
                create_time=now - income_days * 86400,
            )

        # 付款 (混合新旧数据)
        for i in range(10):
            if i < 3:
                pay_days = random.randint(0, 28)
            else:
                pay_days = random.randint(30, 120)
            Payment.objects.create(
                expense_id=random.randint(1, 20),
                amount=Decimal(str(random.randint(500, 30000))),
                payment_date=timezone.now() - timedelta(days=pay_days),
                create_time=now - pay_days * 86400,
            )

        # 税务记录
        tax_types = ['vat', 'income_tax', 'surtax', 'stamp']
        for i in range(8):
            TaxRecord.objects.create(
                period=f'{(timezone.now() - timedelta(days=30*(i+1))).strftime("%Y-%m")}',
                tax_type=random.choice(tax_types),
                taxable_amount=Decimal(str(random.randint(50000, 800000))),
                tax_rate=Decimal(str(random.choice([6, 9, 13, 25]))),
                tax_amount=Decimal(str(random.randint(3000, 100000))),
                status=random.choice(['declared', 'paid']),
                create_time=now,
            )

        # 应收
        for i in range(8):
            AccountsReceivable.objects.create(
                code=f'YS-{timezone.now().year}-{1001 + i:04d}',
                customer_id=0,
                amount=Decimal(str(random.randint(20000, 300000))),
                received_amount=Decimal(str(random.randint(0, 200000))),
                status=random.choice(['pending', 'partial', 'settled']),
                create_time=now,
            )

        # 应付
        for i in range(6):
            AccountsPayable.objects.create(
                code=f'YF-{timezone.now().year}-{1001 + i:04d}',
                supplier_id=0,
                amount=Decimal(str(random.randint(10000, 200000))),
                paid_amount=Decimal(str(random.randint(0, 150000))),
                status=random.choice(['pending', 'partial', 'settled']),
                create_time=now,
            )

        # 预算
        for i in range(5):
            FinanceBudget.objects.create(
                name=f'{timezone.now().year}年{random.choice(["Q1","Q2","Q3","Q4"])}部门预算',
                department_id=random.choice(self.DEPTS).id,
                period_type=random.choice(['quarter', 'year']),
                start_date=date(timezone.now().year, 1, 1),
                end_date=date(timezone.now().year, 12, 31),
                budget_amount=Decimal(str(random.randint(100000, 1000000))),
                used_amount=Decimal(str(random.randint(20000, 500000))),
                status='active',
                create_time=now,
            )

        # 银行流水 (混合新旧数据)
        for fa in fin_accounts:
            for idx in range(random.randint(3, 8)):
                if idx < 2:
                    tx_days = random.randint(0, 28)
                else:
                    tx_days = random.randint(1, 90)
                BankTransaction.objects.create(
                    account=fa,
                    transaction_date=timezone.now() - timedelta(days=tx_days),
                    direction=random.choice(['in', 'out']),
                    amount=Decimal(str(random.randint(1000, 50000))),
                    counterparty=f'交易方{random.randint(1,50)}',
                    transaction_no=f'TXN{random.randint(1000000, 9999999)}',
                    match_status=random.choice(['unmatched', 'matched']),
                    create_time=now,
                )

        # 财务报表
        for i in range(3):
            FinancialReport.objects.create(
                report_no=f'CWBB-{timezone.now().year}-{1001 + i:04d}',
                report_type=random.choice(['balance_sheet', 'income_statement', 'cash_flow']),
                period=f'{(timezone.now() - timedelta(days=90*(i+1))).strftime("%Y")}',
                total_assets=Decimal(str(random.randint(5000000, 50000000))),
                total_liabilities=Decimal(str(random.randint(1000000, 20000000))),
                revenue_amount=Decimal(str(random.randint(2000000, 10000000))),
                profit_amount=Decimal(str(random.randint(100000, 3000000))),
                status='generated',
                create_time=now,
            )

        # 总账凭证
        for i in range(15):
            vouch_date = date(timezone.now().year, random.randint(1, 6), random.randint(1, 28))
            voucher = LedgerVoucher.objects.create(
                voucher_no=f'PZ-{timezone.now().year}-{1001 + i:04d}',
                voucher_date=vouch_date,
                summary=f'第{i + 1}号凭证',
                debit_amount=Decimal(str(random.randint(10000, 200000))),
                credit_amount=Decimal(str(random.randint(10000, 200000))),
                status=random.choice(['draft', 'posted']),
                create_time=now,
            )
            # 凭证明细
            for _ in range(2):
                LedgerVoucherLine.objects.create(
                    voucher=voucher,
                    account=random.choice(all_accounts),
                    summary=f'摘要{random.randint(1,20)}',
                    debit_amount=Decimal(str(random.randint(1000, 50000))),
                    credit_amount=Decimal('0'),
                    create_time=now,
                )

        self.stdout.write('  - 创建了完整的财务模块数据（科目、账户、发票、报销、回款、凭证等）')

    # ========== 6. 项目模块 ==========
    def create_project_module(self):
        self.stdout.write('\n[6/19] 创建项目模块数据...')
        from apps.project.models import (
            Project, ProjectStep, Task, WorkHour,
            ProjectCategory, ProjectStage, WorkType,
            ProjectDocument, Comment
        )
        from django.contrib.contenttypes.models import ContentType

        # 项目分类
        cat_names = [('研发项目','rd_project','#2196F3'), ('实施项目','impl_project','#4CAF50'),
                     ('服务项目','svc_project','#FF9800'), ('内部项目','internal','#9C27B0')]
        for name, code, color in cat_names:
            ProjectCategory.objects.get_or_create(name=name, defaults={'code': code, 'color': color, 'sort_order': 0, 'is_active': True})
        all_cats = list(ProjectCategory.objects.all())

        # 项目阶段
        stage_names = ['需求分析', '方案设计', '开发实施', '测试验收', '上线交付', '维护支持']
        for i, name in enumerate(stage_names):
            ProjectStage.objects.get_or_create(
                name=name,
                defaults={'code': f'STAGE-{i+1}', 'sort_order': i + 1, 'is_active': True}
            )
        all_stages = list(ProjectStage.objects.all())

        # 工作类别
        work_types = ['需求分析', '设计', '编码开发', '测试', '文档', '培训', '技术支持', '项目管理']
        for i, name in enumerate(work_types):
            WorkType.objects.get_or_create(
                name=name,
                defaults={'code': f'WT-{i+1}', 'hourly_rate': random.randint(100, 500), 'sort_order': i + 1, 'is_active': True}
            )
        all_work_types = list(WorkType.objects.all())

        # 项目
        project_names = [
            '智慧园区管理平台项目', 'ERP系统升级改造项目',
            '大数据分析平台建设项目', '移动办公APP开发项目',
            '客户关系管理系统项目', '供应链管理系统项目',
            '企业门户网站改版项目', '网络安全体系建设项目',
        ]
        admin = self._get_user()
        for i, pname in enumerate(project_names):
            start_d = random_date(365)
            code = f'PROJ-{timezone.now().year}-{1001 + i:04d}'
            project, _ = Project.objects.get_or_create(
                code=code,
                defaults={
                    'name': pname,
                    'description': f'{pname}的详细描述...',
                    'category': random.choice(all_cats) if all_cats else None,
                    'manager': random.choice(self.USERS),
                    'start_date': start_d,
                    'end_date': start_d + timedelta(days=random.randint(60, 360)),
                    'budget': Decimal(str(random.randint(100000, 2000000))),
                    'actual_cost': Decimal(str(random.randint(10000, 1500000))),
                    'status': random.choice([1, 2, 2, 2, 3]),
                    'priority': random.choice([1, 2, 2, 3, 4]),
                    'progress': random.randint(0, 100),
                    'department': random.choice(self.DEPTS),
                    'creator': admin,
                }
            )
            # 项目阶段
            for s_idx, sname in enumerate(stage_names[:random.randint(2, 5)]):
                s_start = start_d + timedelta(days=s_idx * 30)
                ProjectStep.objects.create(
                    project=project,
                    name=sname,
                    manager=random.choice(self.USERS),
                    start_date=s_start,
                    end_date=s_start + timedelta(days=28),
                    sort=s_idx + 1,
                    is_current=(s_idx == 1),
                    progress=random.randint(0, 100),
                )

            # 项目成员
            project.members.add(*random.sample(self.USERS, min(4, len(self.USERS))))

            # 任务
            for t in range(random.randint(3, 8)):
                t_start = start_d + timedelta(days=t * 7)
                task = Task.objects.create(
                    title=f'{pname}-任务{t + 1}',
                    project=project,
                    assignee=random.choice(self.USERS),
                    start_date=t_start,
                    end_date=t_start + timedelta(days=random.randint(7, 30)),
                    estimated_hours=random.randint(8, 160),
                    actual_hours=random.randint(4, 140),
                    status=random.choice([1, 2, 2, 3]),
                    priority=random.choice([1, 2, 2, 3]),
                    progress=random.randint(0, 100),
                    creator=admin,
                )

                # 工时记录
                for _ in range(random.randint(1, 5)):
                    WorkHour.objects.create(
                        task=task,
                        user=random.choice(self.USERS),
                        work_date=random_date(90),
                        hours=Decimal(str(round(random.uniform(1, 8), 1))),
                        description=f'任务{t + 1}的工作记录',
                    )

            # 项目文档
            for _ in range(random.randint(1, 3)):
                ProjectDocument.objects.create(
                    project=project,
                    title=f'{pname}-{random.choice(["需求规格说明书","设计文档","测试报告","用户手册"])}',
                    content='文档内容...',
                    creator=random.choice(self.USERS),
                )

            # 评论
            project_ct = ContentType.objects.get_for_model(Project)
            for _ in range(random.randint(2, 5)):
                Comment.objects.create(
                    content_type=project_ct,
                    object_id=project.id,
                    user=random.choice(self.USERS),
                    content=random.choice([
                        '项目进展顺利，按计划推进中。',
                        '需要协调更多资源，时间较紧。',
                        '已完成的模块质量不错，继续保持。',
                        '下周需要和客户确认需求变更。',
                        '注意风险控制，特别是第三方接口对接。',
                    ]),
                )

        self.stdout.write(f'  - 创建了 {len(project_names)} 个项目及相关数据')

    # ========== 7. 定时任务模块 ==========
    def create_task_module(self):
        self.stdout.write('\n[7/19] 创建定时任务模块数据...')
        from apps.task.models import Task

        task_data = [
            ('数据备份任务', '每日凌晨2点执行数据库备份'),
            ('日志清理任务', '每周清理30天前的日志'),
            ('报表生成任务', '每月1号生成上月报表'),
            ('邮件提醒任务', '每天上午9点发送待办提醒'),
            ('数据同步任务', '每小时同步外部系统数据'),
            ('缓存刷新任务', '每30分钟刷新系统缓存'),
        ]
        for title, desc in task_data:
            Task.objects.get_or_create(
                title=title,
                defaults={
                    'description': desc,
                    'status': random.choice([0, 0, 1]),
                    'assignee': random.choice(self.USERS),
                }
            )
        self.stdout.write(f'  - 创建了 {len(task_data)} 个定时任务')

    # ========== 8. 生产模块 ==========
    def create_production_module(self):
        self.stdout.write('\n[8/19] 创建生产模块数据...')
        from apps.production.models import (
            ProductionProcedure, ProcedureSet, ProcedureSetItem,
            BOM, BOMItem, Equipment, ProductionPlan,
            ProductionTask as ProdTask, QualityCheck, SOP
        )
        from apps.contract.models import Product

        admin = self._get_user()

        # 基本工序
        procedure_names = ['下料', '焊接', '打磨', '喷漆', '组装', '调试', '质检', '包装']
        procedures = []
        for i, name in enumerate(procedure_names):
            obj, _ = ProductionProcedure.objects.get_or_create(
                name=name,
                defaults={
                    'code': f'PR-{i+1:03d}',
                    'standard_time': Decimal(str(round(random.uniform(0.5, 4), 1))),
                    'cost_per_hour': Decimal(str(random.randint(50, 200))),
                    'department': random.choice(self.DEPTS),
                    'sort': i + 1,
                    'creator': admin,
                }
            )
            procedures.append(obj)

        # 工序集
        for i in range(3):
            ps, created = ProcedureSet.objects.get_or_create(
                code=f'PS-{i+1:03d}',
                defaults={
                    'name': f'工序集{chr(65+i)}',
                    'description': f'标准工序集{i+1}',
                    'total_time': Decimal(str(round(random.uniform(8, 24), 1))),
                    'total_cost': Decimal(str(random.randint(1000, 5000))),
                    'creator': admin,
                }
            )
            for seq, proc in enumerate(procedures[:random.randint(3, 6)], 1):
                ProcedureSetItem.objects.get_or_create(
                    procedure_set=ps,
                    procedure=proc,
                    defaults={
                        'sequence': seq,
                        'estimated_time': Decimal(str(round(random.uniform(1, 4), 1))),
                    }
                )

        # 设备
        equip_names = ['数控切割机', '焊接机器人', '自动喷漆线', '组装工作台', '综合测试仪', '打包机']
        all_equipments = []
        for i, name in enumerate(equip_names):
            obj, _ = Equipment.objects.get_or_create(
                name=name,
                defaults={
                    'code': f'EQ-{i+1:03d}',
                    'model': f'MODEL-{random.randint(100,999)}',
                    'manufacturer': random.choice(['华为', '比亚迪', '大族激光', '新松机器人']),
                    'purchase_cost': Decimal(str(random.randint(50000, 500000))),
                    'department': random.choice(self.DEPTS),
                    'status': 1,
                    'creator': admin,
                }
            )
            all_equipments.append(obj)

        # BOM
        product = Product.objects.first()
        for i in range(3):
            bom, _ = BOM.objects.get_or_create(
                code=f'BOM-{i+1:03d}',
                defaults={
                    'name': f'BOM-{chr(65+i)}',
                    'product': product,
                    'description': f'物料清单{i+1}',
                    'creator': admin,
                }
            )
            for j in range(random.randint(3, 6)):
                BOMItem.objects.create(
                    bom=bom,
                    material_name=f'物料{chr(65+j)}',
                    material_code=f'MAT-{i+1:02d}{j+1:02d}',
                    unit=random.choice(['个','kg','m','套']),
                    quantity=Decimal(str(round(random.uniform(1, 20), 2))),
                    unit_cost=Decimal(str(random.randint(10, 500))),
                )

        # 生产计划
        for i in range(6):
            plan_start = random_date(180)
            plan_code = f'PLAN-{timezone.now().year}-{1001 + i:04d}'
            plan, _ = ProductionPlan.objects.get_or_create(
                code=plan_code,
                defaults={
                    'name': f'生产计划{i+1}',
                    'product': product,
                    'quantity': Decimal(str(random.randint(100, 5000))),
                    'unit': '台',
                    'plan_start_date': plan_start,
                    'plan_end_date': plan_start + timedelta(days=random.randint(30, 90)),
                    'status': random.choice([1, 2, 3, 4]),
                    'department': random.choice(self.DEPTS),
                    'manager': random.choice(self.USERS),
                    'creator': admin,
                }
            )
            # 生产任务
            for j in range(random.randint(1, 4)):
                proc = random.choice(procedures)
                task_quant = Decimal(str(random.randint(50, 1000)))
                comp_quant = task_quant if random.random() > 0.6 else Decimal(str(random.randint(0, int(task_quant))))
                task_code = f'TASK-{plan.code}-{j+1:02d}'
                task, _ = ProdTask.objects.get_or_create(
                    code=task_code,
                    defaults={
                        'plan': plan,
                        'name': f'{plan.name}-{proc.name}',
                        'procedure': proc,
                        'equipment': random.choice(all_equipments),
                        'quantity': task_quant,
                        'completed_quantity': comp_quant,
                        'qualified_quantity': comp_quant * Decimal('0.95') if comp_quant > 0 else Decimal('0'),
                        'plan_start_time': timezone.now() - timedelta(days=random.randint(1, 30)),
                        'plan_end_time': timezone.now() + timedelta(days=random.randint(1, 30)),
                        'status': random.choice([1, 2, 3]),
                        'assignee': random.choice(self.USERS),
                        'creator': admin,
                    }
                )
                # 质量检查
                if comp_quant > 0:
                    QualityCheck.objects.create(
                        task=task,
                        check_quantity=comp_quant,
                        qualified_quantity=comp_quant * Decimal('0.95'),
                        defective_quantity=comp_quant * Decimal('0.05'),
                        result=random.choice([1, 1, 1, 2]),
                        created_by=random.choice(self.USERS),
                    )

            # SOP
            for proc in random.sample(procedures, min(3, len(procedures))):
                SOP.objects.get_or_create(
                    name=f'{proc.name}SOP',
                    code=f'SOP-{proc.code}',
                    defaults={
                        'procedure': proc,
                        'content': f'{proc.name}的标准操作流程...',
                        'safety_requirements': '佩戴安全帽、护目镜',
                        'quality_standards': '合格率≥98%',
                        'creator': admin,
                    }
                )

        self.stdout.write('  - 创建了完整的生产模块数据（工序、设备、BOM、计划、任务等）')

    # ========== 9. 库存模块 ==========
    def create_inventory_module(self):
        self.stdout.write('\n[9/19] 创建库存模块数据...')
        from apps.inventory.models import (
            Warehouse, WarehouseLocation, InventoryCategory,
            InventoryItem, Inventory, StockTransaction,
            StockIn, StockInItem, StockOut, StockOutItem,
            InventoryAlert
        )

        admin = self._get_user()

        # 仓库
        wh_data = [
            ('主仓库', 'main', '深圳市南山区'),
            ('分仓库A', 'branch', '深圳市宝安区'),
            ('生产仓库', 'production', '深圳市龙岗区'),
        ]
        warehouses = []
        for name, wh_type, addr in wh_data:
            obj, _ = Warehouse.objects.get_or_create(
                name=name,
                defaults={
                    'code': f'WH-{name}',
                    'warehouse_type': wh_type,
                    'address': f'{addr}工业园{random.randint(1,20)}栋',
                    'manager': random.choice(self.USERS),
                    'phone': random_phone(),
                    'capacity': Decimal('10000'),
                    'used_capacity': Decimal(str(random.randint(1000, 8000))),
                    'status': 1,
                    'is_default': (wh_type == 'main'),
                }
            )
            warehouses.append(obj)

        # 库位
        for wh in warehouses:
            for area in ['A区', 'B区', 'C区']:
                loc_code = f'{wh.code}-{area}'
                loc, _ = WarehouseLocation.objects.get_or_create(
                    warehouse=wh,
                    code=loc_code,
                    defaults={
                        'name': area,
                        'location_type': 'area',
                        'capacity': Decimal('2000'),
                    }
                )
                for shelf in range(1, 4):
                    shelf_code = f'{loc.code}-SH{shelf}'
                    WarehouseLocation.objects.get_or_create(
                        warehouse=wh,
                        code=shelf_code,
                        defaults={
                            'parent': loc,
                            'name': f'{area}-货架{shelf}',
                            'location_type': 'shelf',
                        }
                    )

        # 库存类别
        cat_data = [
            ('原材料', 'material'), ('产成品', 'product'), ('半成品', 'semi'),
            ('包装物', 'pack'), ('消耗品', 'consumable'),
        ]
        all_icats = []
        for name, ctype in cat_data:
            obj, _ = InventoryCategory.objects.get_or_create(
                name=name,
                defaults={'code': f'CAT-{name}', 'category_type': ctype, 'status': 1}
            )
            all_icats.append(obj)

        # 库存物料
        mat_names = [
            ('钢板', 'kg'), ('螺栓', '个'), ('电机', '台'), ('传感器', '个'),
            ('控制器', '台'), ('显示屏', '个'), ('线缆', 'm'), ('密封圈', '个'),
            ('轴承', '个'), ('润滑油', 'L'), ('包装箱', '个'), ('标签纸', '张'),
        ]
        all_items = []
        for name, unit in mat_names:
            obj, _ = InventoryItem.objects.get_or_create(
                name=name,
                defaults={
                    'code': f'MAT-{name}',
                    'category': random.choice(all_icats),
                    'specification': f'{name}规格{random.randint(1,100)}',
                    'unit': unit,
                    'standard_cost': Decimal(str(random.randint(5, 500))),
                    'average_cost': Decimal(str(random.randint(5, 500))),
                    'min_stock': Decimal(str(random.randint(50, 500))),
                    'max_stock': Decimal(str(random.randint(1000, 10000))),
                    'reorder_point': Decimal(str(random.randint(100, 1000))),
                    'safety_stock': Decimal(str(random.randint(50, 500))),
                    'status': 1,
                }
            )
            all_items.append(obj)

        # 库存记录
        for item in all_items:
            wh = random.choice(warehouses)
            Inventory.objects.get_or_create(
                item=item,
                warehouse=wh,
                batch_number=f'BATCH-{timezone.now().strftime("%Y%m")}-{random.randint(1,10):02d}',
                defaults={
                    'quantity': Decimal(str(random.randint(100, 5000))),
                    'unit_cost': item.standard_cost,
                    'status': 'normal',
                }
            )

        # 库存交易记录
        for _ in range(30):
            item = random.choice(all_items)
            qty = Decimal(str(round(random.uniform(10, 200), 2)))
            StockTransaction.objects.create(
                transaction_type=random.choice(['stock_in', 'stock_out', 'adjustment']),
                transaction_code=f'STX-{random.randint(10000, 99999)}',
                item=item,
                warehouse=random.choice(warehouses),
                quantity=qty,
                unit_cost=item.standard_cost,
                total_cost=qty * item.standard_cost,
                before_quantity=Decimal(str(random.randint(100, 3000))),
                after_quantity=Decimal(str(random.randint(100, 3000))),
                operator=admin,
            )

        # 入库单
        for i in range(8):
            si_code = f'SI-{timezone.now().year}-{1001 + i:04d}'
            stock_in, _ = StockIn.objects.get_or_create(
                code=si_code,
                defaults={
                    'stock_in_type': random.choice(['purchase', 'production', 'other']),
                    'warehouse': random.choice(warehouses),
                    'status': random.choice([1, 2, 3]),
                    'checker': admin,
                    'stocker': admin,
                }
            )
            for _ in range(random.randint(1, 3)):
                item = random.choice(all_items)
                qty = Decimal(str(random.randint(50, 500)))
                StockInItem.objects.create(
                    stock_in=stock_in,
                    item=item,
                    quantity=qty,
                    unit_cost=item.standard_cost,
                    amount=qty * item.standard_cost,
                )

        # 出库单
        for i in range(6):
            so_code = f'SO-{timezone.now().year}-{1001 + i:04d}'
            stock_out, _ = StockOut.objects.get_or_create(
                code=so_code,
                defaults={
                    'stock_out_type': random.choice(['sale', 'production', 'other']),
                    'warehouse': random.choice(warehouses),
                    'status': random.choice([1, 2, 3]),
                    'checker': admin,
                    'stocker': admin,
                }
            )
            for _ in range(random.randint(1, 3)):
                item = random.choice(all_items)
                qty = Decimal(str(random.randint(10, 200)))
                StockOutItem.objects.create(
                    stock_out=stock_out,
                    item=item,
                    quantity=qty,
                    unit_cost=item.standard_cost,
                    amount=qty * item.standard_cost,
                )

        # 库存预警
        for item in random.sample(all_items, 5):
            InventoryAlert.objects.create(
                item=item,
                warehouse=random.choice(warehouses),
                alert_type=random.choice(['low_stock', 'over_stock', 'reorder']),
                current_quantity=Decimal(str(random.randint(0, 50))),
                threshold_value=item.reorder_point,
                message=f'{item.name}库存不足，请及时补货',
                status=random.choice([1, 1, 2]),
            )

        self.stdout.write(f'  - 创建了 {len(warehouses)} 个仓库、{len(all_items)} 种物料及入库出库数据')

    # ========== 10. OA办公模块 ==========
    def create_oa_module(self):
        self.stdout.write('\n[10/19] 创建OA办公模块数据...')
        from apps.oa.models import (
            MeetingRoom, MeetingRecord, OAMessage,
            ApprovalFlow, ApprovalStep, ApprovalRequest, ApprovalRecord,
            Schedule
        )
        from apps.user.models.department import Department as UserDepartment

        admin = self._get_user()
        # 获取用户部门模型中的部门列表（MeetingRecord使用user.Department）
        user_depts = list(UserDepartment.objects.filter(status=1)[:10])

        # 会议室
        room_names = [
            ('星辰厅', 20), ('朝阳厅', 15), ('创意厅', 10),
            ('协作厅', 8), ('VIP洽谈室', 6), ('培训室', 50),
        ]
        rooms = []
        for name, cap in room_names:
            obj, _ = MeetingRoom.objects.get_or_create(
                name=name,
                defaults={
                    'code': f'ROOM-{name}',
                    'location': f'{random.choice(["A座","B座"])}{random.randint(3,20)}层',
                    'capacity': cap,
                    'has_projector': random.choice([True, True, True, False]),
                    'has_whiteboard': True,
                    'has_wifi': True,
                    'has_phone': random.choice([True, False]),
                    'status': 'active',
                    'manager': admin,
                }
            )
            rooms.append(obj)

        # 会议记录
        meeting_titles = [
            '周例会', '项目进度评审会', '技术方案讨论会',
            '季度总结会', '新员工入职培训', '客户需求评审会',
            '安全生产会议', '部门工作会议',
        ]
        for i, title in enumerate(meeting_titles):
            start = timezone.now() - timedelta(days=random.randint(1, 60))
            room = random.choice(rooms)
            participants = random.sample(self.USERS, min(5, len(self.USERS)))
            meeting = MeetingRecord.objects.create(
                title=title,
                meeting_type=random.choice(['regular', 'project', 'training', 'strategic', 'emergency']),
                meeting_date=start,
                meeting_end_time=start + timedelta(minutes=random.choice([30, 60, 90, 120])),
                room=room,
                location=room.location,
                host=random.choice(self.USERS),
                recorder=random.choice(self.USERS),
                department=random.choice(user_depts) if user_depts else None,
                status=random.choice(['completed', 'completed', 'completed', 'in_progress', 'confirmed']),
                content=f'{title}的会议记录...',
                summary=f'{title}的纪要摘要',
            )
            meeting.participants.add(*participants)

        # OA消息
        msg_types = ['system', 'notice', 'personal']
        for i in range(15):
            msg = OAMessage.objects.create(
                title=random.choice([
                    '系统升级通知', '假期安排通知', '培训报名通知',
                    '制度更新提醒', '业绩通报', '活动通知',
                    '安全提醒', '福利发放通知',
                ]),
                content=f'消息内容{i + 1}...',
                message_type=random.choice(msg_types),
                sender=admin,
                receiver_type=random.choice(['user', 'department', 'all']),
                priority=random.choice([1, 2, 2, 2, 3]),
                send_time=timezone.now() - timedelta(days=random.randint(1, 30)),
            )

        # 审批流程
        flow_types = ['expense', 'leave', 'purchase', 'contract', 'other']
        flow_names = ['报销审批', '请假审批', '采购审批', '合同审批', '用章审批']
        all_flows = []
        for i, (ftype, fname) in enumerate(zip(flow_types, flow_names)):
            flow, _ = ApprovalFlow.objects.get_or_create(
                code=f'FLOW-{ftype}',
                defaults={
                    'name': fname,
                    'description': f'{fname}流程',
                    'flow_type': ftype,
                    'is_active': True,
                    'is_default': (i == 0),
                    'creator': admin,
                }
            )
            all_flows.append(flow)
            for j in range(2):
                step, _ = ApprovalStep.objects.get_or_create(
                    flow=flow,
                    step_order=j + 1,
                    defaults={
                        'name': f'{fname}-步骤{j + 1}',
                        'approver_type': random.choice(['user', 'department_leader', 'direct_supervisor']),
                        'is_required': True,
                        'timeout_hours': random.choice([24, 48, 72]),
                    }
                )
                step.approvers.add(random.choice(self.USERS))

        # 审批申请
        all_flows = list(ApprovalFlow.objects.all())
        for i in range(12):
            flow = random.choice(all_flows)
            req = ApprovalRequest.objects.create(
                title=f'{flow.name}申请{i + 1}',
                content=f'申请内容{i + 1}...',
                applicant=random.choice(self.USERS),
                department=random.choice(user_depts) if user_depts else None,
                flow=flow,
                status=random.choice(['pending', 'in_review', 'approved', 'approved', 'approved']),
            )
            # 审批记录
            for step in flow.steps.all()[:1]:
                ApprovalRecord.objects.create(
                    request=req,
                    step=step,
                    approver=random.choice(self.USERS),
                    result=random.choice(['approved', 'approved', 'approved', 'rejected']),
                    comment=random.choice(['同意', '无异议', '通过', '请补充说明']),
                )

        # 工作日程
        for i in range(20):
            start = timezone.now() - timedelta(days=random.randint(0, 30))
            Schedule.objects.create(
                title=random.choice([
                    '拜访客户', '技术方案编写', '项目验收', '产品培训',
                    '部门会议', '报表制作', '合同审核', '需求调研',
                ]),
                start_time=start,
                end_time=start + timedelta(hours=random.randint(1, 4)),
                labor_time=round(random.uniform(1, 4), 1),
                admin_id=random.choice(self.USERS).id,
                did=random.choice(self.DEPTS).id,
                content='工作内容描述...',
                create_time=int(start.timestamp()),
            )

        self.stdout.write(f'  - 创建了 {len(rooms)} 个会议室、{len(flow_names)} 个审批流程等OA数据')

    # ========== 11. 系统管理模块 ==========
    def create_system_module(self):
        self.stdout.write('\n[11/19] 创建系统管理模块数据...')
        from apps.system.models import (
            AssetCategory, AssetBrand, Asset, AssetRepair,
            Vehicle, VehicleMaintenance, VehicleFee, VehicleOil,
            Notice, Seal, SealApplication, Document, DocumentCategory,
            StorageConfiguration, ServiceConfiguration
        )

        admin = self._get_user()

        # 资产分类
        ac_names = [('IT设备', 'it'), ('办公家具', 'furniture'), ('车辆', 'vehicle'), ('其他设备', 'other')]
        for name, code in ac_names:
            AssetCategory.objects.get_or_create(name=name, defaults={'code': code, 'is_active': True})
        all_cats = list(AssetCategory.objects.all())

        # 资产品牌
        brands = ['联想', '戴尔', '惠普', '华为', '小米', '三星', '苹果']
        for name in brands:
            AssetBrand.objects.get_or_create(name=name, defaults={'code': name.upper(), 'is_active': True})
        all_brands = list(AssetBrand.objects.all())

        # 固定资产
        asset_names = [
            ('笔记本电脑', 'NB-'), ('台式电脑', 'DT-'), ('打印机', 'PR-'),
            ('投影仪', 'PJ-'), ('服务器', 'SR-'), ('交换机', 'SW-'),
        ]
        for name, prefix in asset_names:
            for i in range(2):
                Asset.objects.get_or_create(
                    asset_number=f'{prefix}{random.randint(10001, 99999)}',
                    defaults={
                        'name': f'{name}{i + 1}',
                        'category': random.choice(all_cats),
                        'brand': random.choice(all_brands),
                        'purchase_date': random_date(730),
                        'purchase_price': Decimal(str(random.randint(2000, 80000))),
                        'status': random.choice(['normal', 'normal', 'normal', 'repair']),
                        'responsible_person': random.choice(self.USERS),
                        'department': random.choice(self.DEPTS),
                    }
                )

        # 资产报修
        all_assets = list(Asset.objects.all())
        for _ in range(5):
            AssetRepair.objects.create(
                asset=random.choice(all_assets),
                reporter=random.choice(self.USERS),
                fault_description=f'设备故障{random.randint(1,10)}',
                status=random.choice(['pending', 'processing', 'completed']),
                repair_cost=Decimal(str(random.randint(100, 3000))),
            )

        # 车辆
        vehicle_data = [
            ('粤B12345', '丰田', '凯美瑞'), ('粤B67890', '比亚迪', '汉'),
            ('粤B24680', '大众', '帕萨特'),
        ]
        for plate, brand, model in vehicle_data:
            Vehicle.objects.get_or_create(
                license_plate=plate,
                defaults={
                    'brand': brand, 'model': model,
                    'color': random.choice(['黑色', '白色', '银色']),
                    'engine_number': f'ENG{random.randint(100000, 999999)}',
                    'frame_number': f'FRM{random.randint(100000, 999999)}',
                    'purchase_date': random_date(1095),
                    'purchase_price': Decimal(str(random.randint(100000, 300000))),
                    'driver': random.choice(self.USERS),
                    'status': 'normal',
                }
            )

        # 公告
        for i in range(8):
            pub_time = timezone.now() - timedelta(days=random.randint(1, 90))
            Notice.objects.create(
                title=random.choice([
                    '关于公司放假的通知', '年度体检安排通知',
                    '新系统上线公告', '员工培训计划通知',
                    '安全生产提醒', '年度总结大会通知',
                    '制度更新公告', '优秀员工表彰通知',
                ]),
                content=f'公告详细内容{i + 1}...',
                notice_type=random.choice(['company', 'system', 'urgent']),
                is_published=True,
                publish_time=pub_time,
                author=admin,
            )

        # 印章
        seal_names = ['公司公章', '合同专用章', '财务专用章', '法人章']
        seals = []
        for name in seal_names:
            obj, _ = Seal.objects.get_or_create(
                name=name,
                defaults={
                    'seal_type': name.rsplit('章', 1)[0] if '章' in name else 'other',
                    'keeper': random.choice(self.USERS),
                    'is_active': True,
                }
            )
            seals.append(obj)

        # 用章申请
        for i in range(6):
            SealApplication.objects.create(
                seal=random.choice(seals),
                applicant=random.choice(self.USERS),
                purpose=f'合同签订用章{i + 1}',
                document_title=f'用章文件{i + 1}',
                use_date=random_date(30),
                status=random.choice(['approved', 'used', 'pending']),
                approver=random.choice(self.USERS),
            )

        # 公文分类
        doc_cats = ['通知公告', '规章制度', '会议纪要', '请示报告', '合同文件']
        for name in doc_cats:
            DocumentCategory.objects.get_or_create(name=name, defaults={'code': name[:2].upper(), 'is_active': True})
        all_doc_cats = list(DocumentCategory.objects.all())

        # 公文
        for i in range(10):
            Document.objects.get_or_create(
                document_number=f'GW-{timezone.now().year}-{1001 + i:04d}',
                defaults={
                    'title': f'公文标题{i + 1}',
                    'category': random.choice(all_doc_cats),
                    'content': f'公文内容{i + 1}...',
                    'author': admin,
                    'department': random.choice(self.DEPTS),
                    'status': random.choice(['draft', 'published', 'approved', 'archived']),
                    'urgency': random.choice(['normal', 'normal', 'urgent']),
                    'security_level': random.choice(['public', 'internal']),
                }
            )

        # 存储配置
        StorageConfiguration.objects.get_or_create(
            name='本地默认存储',
            defaults={
                'storage_type': 'local',
                'is_default': True,
                'local_path': 'uploads/',
                'status': 'active',
                'creator': admin,
            }
        )

        self.stdout.write('  - 创建了系统管理模块数据（资产、车辆、公告、印章、公文等）')

    # ========== 12. 网盘模块 ==========
    def create_disk_module(self):
        self.stdout.write('\n[12/19] 创建网盘模块数据...')
        from apps.disk.models import DiskFolder, DiskFile

        admin = self._get_user()

        # 文件夹
        folder_data = [
            ('公司制度', None), ('项目文档', None), ('技术资料', None),
            ('培训材料', None), ('行政文件', None),
        ]
        folders = []
        for name, parent in folder_data:
            obj, _ = DiskFolder.objects.get_or_create(
                name=name, owner=admin,
                defaults={'parent': parent, 'is_public': True, 'department': random.choice(self.DEPTS)}
            )
            folders.append(obj)

        # 子文件夹
        for folder in folders[:3]:
            for sub in ['草稿', '已归档', '模板']:
                DiskFolder.objects.get_or_create(
                    name=sub, owner=admin, parent=folder,
                    defaults={'is_public': True}
                )

        # 文件
        file_names = [
            ('2024年度工作总结.docx', 'document', 102400),
            ('员工手册V3.0.docx', 'document', 256000),
            ('项目需求规格说明书.pdf', 'document', 512000),
            ('技术架构设计图.png', 'image', 204800),
            ('培训视频教程.mp4', 'video', 10485760),
            ('合同模板.zip', 'archive', 3072000),
            ('会议录音.mp3', 'audio', 5120000),
            ('数据报表.xlsx', 'document', 128000),
            ('安全生产规范.pdf', 'document', 768000),
            ('产品宣传册.pptx', 'document', 4096000),
        ]
        for name, ftype, size in file_names:
            DiskFile.objects.get_or_create(
                name=name,
                owner=admin,
                defaults={
                    'original_name': name,
                    'file_path': f'uploads/{name}',
                    'file_size': size,
                    'file_ext': os.path.splitext(name)[1],
                    'file_type': ftype,
                    'folder': random.choice(folders),
                    'is_public': True,
                    'department': random.choice(self.DEPTS),
                    'download_count': random.randint(0, 100),
                    'view_count': random.randint(0, 200),
                }
            )

        self.stdout.write(f'  - 创建了 {len(folders)} 个文件夹及文件')

    # ========== 13. 消息模块 ==========
    def create_message_module(self):
        self.stdout.write('\n[13/19] 创建消息模块数据...')
        from apps.message.models import Message, MessageCategory, MessageUserRelation, NotificationPreference

        # 消息分类
        cat_data = [
            ('announcement', '公告通知', 'announcement', 'layui-icon-notice', '公司公告和通知消息'),
            ('approval', '审批通知', 'approval', 'layui-icon-ok-circle', '待审批和审批结果通知'),
            ('task', '任务通知', 'task', 'layui-icon-task', '任务分配和完成通知'),
            ('system', '系统通知', 'system', 'layui-icon-set', '系统维护和升级通知'),
            ('comment', '评论回复通知', 'comment', 'layui-icon-dialogue', '评论和回复通知'),
        ]
        cats = {}
        for i, (code, name, mtype, icon, desc) in enumerate(cat_data):
            obj, _ = MessageCategory.objects.get_or_create(
                code=code,
                defaults={'name': name, 'type': mtype, 'icon': icon, 'description': desc, 'sort_order': i, 'is_active': True}
            )
            cats[code] = obj

        # 消息标题和内容模板
        msg_templates = [
            ('announcement', '关于2025年度绩效考核工作安排的通知',
             '各部门：\n根据公司年度工作安排，2025年度绩效考核工作将于下月开始，请各部门提前做好准备工作。\n\n具体安排如下：\n1. 各员工于10日前完成自评\n2. 各部门负责人于15日前完成初评\n3. 人力资源部于20日前完成复评\n4. 公司领导于25日前完成终评\n\n请各部门高度重视，认真组织落实。\n\n特此通知。'),
            ('announcement', '关于国庆节放假安排的通知',
             '全体员工：\n根据国家法定节假日安排，结合公司实际情况，现将2025年国庆节放假安排通知如下：\n\n放假时间：10月1日至10月7日，共7天\n上班时间：10月8日（星期三）正常上班\n调休安排：9月28日（周日）、10月11日（周六）上班\n\n请各部门安排好值班人员，确保假期期间公司正常运转。\n\n祝大家国庆快乐！'),
            ('announcement', '关于启用新版OA系统的通知',
             '各位同事：\n为进一步提高办公效率，公司定于2025年9月15日正式启用新版OA系统。\n\n新版系统主要更新内容：\n1. 优化审批流程，支持移动端审批\n2. 新增智能日程管理功能\n3. 增强文档协作能力\n4. 改进消息通知机制\n\n请各部门管理员做好数据迁移准备，如有疑问请联系IT部门。'),
            ('approval', '您有一条新的请假审批待处理',
             '李伟提交了请假申请，请假时间：2025年9月20日至9月22日，共计3天，请假类型：年假。请及时处理。'),
            ('approval', '您提交的报销申请已审批通过',
             '您于2025年9月10日提交的差旅费报销申请（编号：BX-2025-0910-001）已审批通过，报销金额：¥3,580.00，款项将在3个工作日内到账。'),
            ('approval', '加班申请已审批通过',
             '您提交的加班申请（日期：2025年9月14日，时长：4小时）已由部门负责人审批通过。'),
            ('task', '新任务分配：完成Q3市场分析报告',
             '您被分配了一个新任务：完成2025年第三季度市场分析报告。\n\n任务详情：\n- 截止时间：2025年9月30日\n- 优先级：高\n- 任务内容：分析Q3市场趋势、竞品动态、客户需求变化，输出分析报告。\n\n请合理安排时间，按时完成任务。'),
            ('task', '任务提醒：项目验收会议明天召开',
             '温馨提示：您参与的项目验收会议将于明天（2025年9月16日）上午10:00在3楼大会议室召开，请准时参加。'),
            ('system', '系统维护通知',
             '尊敬的用户：\n系统将于2025年9月20日（周六）凌晨2:00-6:00进行例行维护，届时系统将暂时无法访问。请提前安排好工作，避免在此期间使用系统。\n\n维护内容：\n- 数据库性能优化\n- 安全补丁更新\n- 系统功能升级\n\n给您带来的不便敬请谅解。'),
            ('system', '系统升级完成通知',
             '系统已于今日凌晨完成升级，主要更新内容：\n1. 新增AI智能助手功能\n2. 优化消息推送机制\n3. 提升系统响应速度\n\n如在使���过程中遇到任何问题，请联系IT部门。'),
            ('comment', '有人回复了您的评论',
             '张明在"2025年度工作规划"中回复了您的评论："同意这个方案，建议加上预算说明。"'),
            ('comment', '有人在项目中@了你',
             '王芳在"智慧园区升级项目"的评审意见中@了你："请李工帮忙审核技术方案部分。"'),
        ]

        messages = []
        for i, (cat_code, title, content) in enumerate(msg_templates):
            is_broadcast = cat_code in ('announcement', 'system')
            sender = random.choice(self.USERS)
            receiver = None if is_broadcast else self.USERS[(i + 1) % len(self.USERS)]
            msg, _ = Message.objects.get_or_create(
                title=title,
                user=receiver,
                defaults={
                    'category': cats[cat_code],
                    'sender': sender,
                    'content': content,
                    'priority': 2 if cat_code in ('announcement', 'system') else random.choice([1, 2, 3, 4]),
                    'is_broadcast': is_broadcast,
                    'target_users': '[]',
                    'target_departments': '[]' if not is_broadcast else str([d.id for d in self.DEPTS[:3]]),
                    'is_active': True,
                    'expire_time': timezone.now() + timedelta(days=random.randint(7, 90)),
                }
            )
            messages.append(msg)

        # 为每条消息创建用户关系记录
        for msg in messages:
            if msg.is_broadcast:
                # 广播消息：为前10个用户创建关系记录
                for user in self.USERS[:10]:
                    MessageUserRelation.objects.get_or_create(
                        message=msg, user=user,
                        defaults={
                            'is_read': random.choice([True, True, False]),
                            'is_starred': random.choice([False, False, True]),
                            'read_time': timezone.now() - timedelta(minutes=random.randint(1, 1440)) if random.choice([True, False]) else None,
                        }
                    )
            else:
                # 非广播消息：为接收者创建关系记录
                if msg.user:
                    MessageUserRelation.objects.get_or_create(
                        message=msg, user=msg.user,
                        defaults={
                            'is_read': random.choice([True, False]),
                            'is_starred': False,
                            'read_time': timezone.now() - timedelta(minutes=random.randint(1, 1440)) if random.choice([True, False]) else None,
                        }
                    )

        # 通知偏好设置（为前15个用户）
        for user in self.USERS[:15]:
            NotificationPreference.objects.get_or_create(
                user=user,
                defaults={
                    'enable_email': True,
                    'enable_browser': True,
                    'quiet_hours_start': None if random.choice([True, False]) else datetime.strptime('22:00', '%H:%M').time(),
                    'quiet_hours_end': None if random.choice([True, False]) else datetime.strptime('08:00', '%H:%M').time(),
                    'notify_announcement': True,
                    'notify_approval': True,
                    'notify_task': True,
                    'notify_comment': random.choice([True, False]),
                    'notify_system': True,
                }
            )

        self.stdout.write(f'  - 创建了 {len(cats)} 个消息分类、{len(messages)} 条消息及用户关系和通知偏好')

    # ========== 14. 个人模块 ==========
    def create_personal_module(self):
        self.stdout.write('\n[14/19] 创建个人模块数据...')
        from apps.personal.models import WorkRecord, WorkReport, PersonalNote, PersonalTask, PersonalContact, MeetingMinutes

        # 工作记录
        work_contents = [
            '完成客户需求文档编写', '参加项目周例会', '处理客户反馈问题',
            '编写技术方案初稿', '审核合同条款', '整理部门工作汇报',
            '参加技术培训', '修复系统Bug', '编写测试用例',
            '配合完成系统部署', '编写API接口文档', '参加产品需求评审',
        ]
        for i in range(20):
            wd = random_date(90, 1)
            start_h = random.randint(8, 16)
            dur = random.choice([1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0, 8.0])
            WorkRecord.objects.get_or_create(
                title=f'工作记录{i + 1}: {random.choice(work_contents)}',
                user=random.choice(self.USERS),
                work_date=wd,
                defaults={
                    'content': f'详细工作内容记录{i + 1}...',
                    'work_type': random.choice(['daily', 'project', 'meeting', 'training', 'other']),
                    'start_time': datetime.strptime(f'{start_h}:00', '%H:%M').time(),
                    'end_time': datetime.strptime(f'{int((start_h + dur) % 24 or 0)}:{random.choice(["00", "30"])}', '%H:%M').time(),
                    'duration': dur,
                    'progress': random.choice([25, 50, 75, 100]),
                    'difficulty': random.randint(1, 5),
                    'result': f'工作成果{i + 1}',
                    'problem': '' if random.choice([True, False]) else f'遇到问题{i + 1}',
                    'next_plan': f'下步计划{i + 1}',
                    'department': random.choice(self.DEPTS),
                }
            )

        # 工作汇报
        rpt_types = ['daily', 'weekly', 'monthly', 'project', 'special']
        for i in range(15):
            rpt_type = random.choice(rpt_types)
            rpt_date = random_date(90, 1)
            rpt_user = random.choice(self.USERS)
            WorkReport.objects.get_or_create(
                title=f'{dict(WorkReport.REPORT_TYPES).get(rpt_type, "汇报")} - {rpt_date}',
                user=rpt_user,
                report_date=rpt_date,
                report_type=rpt_type,
                defaults={
                    'summary': f'工作总结{i + 1}',
                    'completed_work': f'已完成工作内容{i + 1}',
                    'next_work': f'下期工作计划{i + 1}',
                    'problems': '无重大问题' if random.choice([True, False]) else '部分项目进度延迟',
                    'suggestions': '建议加强跨部门沟通',
                    'attachments': '[]',
                    'department': random.choice(self.DEPTS),
                    'is_submitted': random.choice([True, True, True, False]),
                    'submitted_at': timezone.now() - timedelta(days=random.randint(1, 30)) if random.choice([True, True, False]) else None,
                }
            )
            # 添加接收人
            report = WorkReport.objects.last()
            if report and report.is_submitted:
                recipients = random.sample(self.USERS, min(3, len(self.USERS)))
                report.recipient_users.add(*recipients)

        # 个人笔记
        note_titles = [
            '项目架构设计思路', '技术选型对比分析', '代码审查检查清单',
            '团队管理心得', '年度工作规划', '学习笔记-Python高级特性',
            '客户沟通技巧总结', '产品优化建议', '安全漏洞防范要点',
            '性能优化方案', '数据库调优记录', '部署运维手册',
        ]
        for i, title in enumerate(note_titles):
            PersonalNote.objects.get_or_create(
                title=title,
                user=random.choice(self.USERS),
                defaults={
                    'content': f'{title}的详细内容...',
                    'category': random.choice(['work', 'study', 'meeting', 'idea', 'other']),
                    'tags': random.choice(['技术', '管理', '产品', '安全', '学习', '笔记']),
                    'is_important': random.choice([True, False, False]),
                    'is_private': random.choice([True, True, False]),
                }
            )

        # 个人任务
        task_titles = [
            '完成Q3绩效评估', '准备项目中期汇报', '更新技术文档',
            '学习新框架', '整理代码库', '完成代码审查',
            '编写培训材料', '处理客户投诉', '备份重要数据',
            '优化数据库查询', '设计新功能原型', '编写单元测试',
            '准备演示材料', '更新项目计划', '分析竞品功能',
        ]
        for i, title in enumerate(task_titles):
            due = timezone.now() + timedelta(days=random.randint(-15, 30))
            status = 'completed' if due < timezone.now() else random.choice(['todo', 'in_progress', 'in_progress', 'in_progress', 'completed'])
            PersonalTask.objects.get_or_create(
                title=title,
                user=random.choice(self.USERS),
                defaults={
                    'description': f'{title}的详细描述...',
                    'priority': random.choice([1, 2, 3, 3, 4]),
                    'status': status,
                    'due_date': due,
                    'completed_at': timezone.now() - timedelta(days=random.randint(1, 15)) if status == 'completed' else None,
                    'progress': random.choice([0, 25, 50, 75, 100]) if status == 'completed' else random.choice([0, 25, 50, 75]),
                    'estimated_hours': random.choice([2.0, 4.0, 8.0, 16.0, 24.0, 40.0]),
                    'actual_hours': random.choice([1.5, 3.0, 7.5, 15.0, 22.0, 38.0]),
                }
            )

        # 个人通讯录
        contact_data = [
            ('陈总', '科技有限公司', '总经理', '13800001111'),
            ('黄经理', '创新软件有限公司', '技术总监', '13900002222'),
            ('周工', '互联网科技有限公司', '高级工程师', '13600003333'),
            ('刘老师', '技术培训中心', '培训讲师', '13500004444'),
            ('杨顾问', '管理咨询有限公司', '资深顾问', '13700005555'),
            ('吴经理', '投资集团有限公司', '投资经理', '13800006666'),
            ('孙律师', '律师事务所', '合伙人', '13900007777'),
            ('赵总监', '广告传媒有限公司', '市场总监', '13600008888'),
            ('马老师', '职业技术学院', '教授', '13500009999'),
            ('胡总', '建筑工程有限公司', '副总经理', '13700001110'),
        ]
        for name, company, pos, phone in contact_data:
            PersonalContact.objects.get_or_create(
                name=name,
                user=random.choice(self.USERS),
                defaults={
                    'company': company,
                    'position': pos,
                    'phone': phone[:4] + '****' + phone[-3:],
                    'mobile': phone,
                    'email': f'{name.replace("总", "").replace("经理", "").replace("工", "").replace("老师", "").replace("顾问", "").replace("律师", "").replace("总监", "").replace("教授", "")}{random.randint(100, 999)}@example.com',
                    'address': f'北京市{"朝阳" if random.choice([True, False]) else "海淀"}区某某路{random.randint(1, 999)}号',
                    'notes': '重要合作伙伴' if random.choice([True, False]) else '',
                    'tags': random.choice(['客户', '供应商', '合作伙伴', '同行', '朋友']),
                    'is_important': random.choice([True, False, False]),
                }
            )

        # 会议纪要
        meeting_titles = [
            '2025年Q3经营分析会', '产品规划研讨会', '技术方案评审会',
            '项目启动会', '安全生产专题会议', '市场拓展策略讨论会',
            '员工培训方案讨论', '信息化建设推进会',
        ]
        for i, title in enumerate(meeting_titles):
            MeetingMinutes.objects.get_or_create(
                title=title,
                user=random.choice(self.USERS),
                defaults={
                    'meeting_type': random.choice(['regular', 'emergency', 'project', 'training']),
                    'meeting_date': timezone.now() - timedelta(days=random.randint(1, 90)),
                    'location': random.choice(['3楼大会议室', '2楼小会议室', '线上会议', '4楼报告厅']),
                    'host': self._random_name(),
                    'recorder': random.choice(self.USERS),
                    'attendees': '、'.join([self._random_name() for _ in range(random.randint(5, 15))]),
                    'content': f'{title}的内容记录...',
                    'decisions': f'会议决议{i + 1}：1. 通过XXX方案；2. 确定下阶段工作重点',
                    'action_items': f'行动项：1. 各部门于{random.randint(10, 30)}日前提交计划；2. 技术部完成方案评估',
                    'attachments': '[]',
                    'is_public': random.choice([True, True, False]),
                }
            )

        self.stdout.write('  - 创建了个人模块数据（工作记录、汇报、笔记、任务、通讯录、会议纪要）')

    # ========== 15. 工作分类模块 ==========
    def create_work_module(self):
        self.stdout.write('\n[15/19] 创建工作分类模块数据...')
        from apps.work.models import WorkCate

        work_cates = [
            # (title, pid, sort)
            ('项目管理', 0, 1),
            ('日常工作', 0, 2),
            ('会议工作', 0, 3),
            ('技术支持', 0, 4),
            ('行政事务', 0, 5),
            ('需求分析', 1, 1),
            ('系统设计', 1, 2),
            ('编码开发', 1, 3),
            ('测试验收', 1, 4),
            ('部署上线', 1, 5),
            ('代码审查', 2, 1),
            ('文档编写', 2, 2),
            ('问题跟踪', 2, 3),
            ('周例会', 3, 1),
            ('评审会', 3, 2),
            ('培训会', 3, 3),
            ('运维支持', 4, 1),
            ('客户支持', 4, 2),
            ('安全审计', 4, 3),
            ('办公用品管理', 5, 1),
            ('考勤统计', 5, 2),
        ]
        for title, pid, sort in work_cates:
            WorkCate.objects.get_or_create(
                title=title, pid=pid,
                defaults={'sort': sort, 'status': 1}
            )

        self.stdout.write(f'  - 创建了 {len(work_cates)} 个工作分类')
