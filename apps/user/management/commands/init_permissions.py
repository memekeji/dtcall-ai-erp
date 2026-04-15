"""
权限初始化命令
根据权限管理详细设计文档创建系统权限节点
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from apps.user.config.permission_nodes import PERMISSION_NODES


class Command(BaseCommand):
    help = '根据权限管理详细设计文档初始化系统权限节点'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制重新创建所有权限（删除现有权限）',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='预览模式，不实际创建权限',
        )

    def handle(self, *args, **options):
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('=== 预览模式，不会实际创建任何权限 ===\n'))
            self._preview_permissions()
        elif options['force']:
            self.stdout.write(self.style.WARNING(
                '=== 警告：强制模式将删除现有权限并重新创建 ==='))
            confirm = input('\n确认继续？(yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('操作已取消'))
                return
            with transaction.atomic():
                self._clear_permissions()
                self._create_permissions()
        else:
            self._create_permissions()

    def _clear_permissions(self):
        """清除现有权限"""
        self.stdout.write('正在清除现有权限...')
        deleted_count = 0
        for perm in Permission.objects.filter(
                codename__in=self._get_all_permission_codenames()):
            perm.delete()
            deleted_count += 1
        self.stdout.write(self.style.SUCCESS(f'已清除 {deleted_count} 个自定义权限'))

    def _get_all_permission_codenames(self):
        """获取所有需要清除的权限codename列表"""
        codenames = []
        for module_name, module_config in PERMISSION_NODES.items():
            if 'permissions' in module_config:
                for perm_config in module_config['permissions']:
                    codename = perm_config.get('codename')
                    if codename:
                        codenames.append(codename)
            if 'children' in module_config:
                for child_key, child_config in module_config['children'].items(
                ):
                    codenames.append(f'view_{child_key}')
                    if 'permissions' in child_config:
                        for perm_config in child_config['permissions']:
                            codename = perm_config.get('codename')
                            if codename:
                                codenames.append(codename)
                    if 'children' in child_config:
                        for sub_key, sub_config in child_config['children'].items(
                        ):
                            codenames.append(f'view_{sub_key}')
                            if 'permissions' in sub_config:
                                for perm_config in sub_config['permissions']:
                                    codename = perm_config.get('codename')
                                    if codename:
                                        codenames.append(codename)
        return codenames

    def _create_permissions(self):
        """创建权限"""
        self.stdout.write('\n开始创建权限节点...')
        total_created = 0
        total_existed = 0

        content_type, _ = ContentType.objects.get_or_create(
            app_label='user',
            model='permission'
        )

        for module_name, module_config in PERMISSION_NODES.items():
            self.stdout.write(f'\n处理模块: {module_name}')
            module_created, module_existed = self._create_module_permissions(
                module_name, module_config, content_type
            )
            total_created += module_created
            total_existed += module_existed

        self.stdout.write(self.style.SUCCESS(f'\n权限创建完成！'))
        self.stdout.write(f'  新建: {total_created} 个')
        self.stdout.write(f'  已存在: {total_existed} 个')

    def _create_module_permissions(
            self, module_name, module_config, content_type):
        """创建单个模块的权限"""
        created = 0
        existed = 0

        if 'permissions' in module_config:
            for perm_config in module_config['permissions']:
                perm_created, perm_existed = self._create_permission(
                    module_name, perm_config, content_type
                )
                created += perm_created
                existed += perm_existed

        if 'children' in module_config:
            for child_key, child_config in module_config['children'].items():
                child_created, child_existed = self._create_child_permissions(
                    module_name, child_key, child_config, content_type
                )
                created += child_created
                existed += child_existed

        return created, existed

    def _create_child_permissions(
            self, module_name, child_key, child_config, content_type):
        """创建子菜单权限"""
        created = 0
        existed = 0

        child_name = child_config.get('name', child_key)

        child_perm_code = f'view_{child_key}'
        child_perm_name = f'查看{child_name}'
        is_new, is_existed = self._get_or_create_permission(
            child_perm_code, child_perm_name, content_type
        )
        if is_new:
            created += 1
        if is_existed:
            existed += 1

        if 'permissions' in child_config:
            for perm_config in child_config['permissions']:
                action_perm_code = perm_config.get(
                    'codename', f'change_{child_key}')
                action_perm_name = perm_config.get('name', child_name)
                is_new, is_existed = self._get_or_create_permission(
                    action_perm_code, action_perm_name, content_type
                )
                if is_new:
                    created += 1
                if is_existed:
                    existed += 1

        if 'children' in child_config:
            for sub_key, sub_config in child_config['children'].items():
                sub_created, sub_existed = self._create_sub_permissions(
                    module_name, child_name, sub_key, sub_config, content_type
                )
                created += sub_created
                existed += sub_existed

        return created, existed

    def _create_sub_permissions(
            self, module_name, parent_name, sub_key, sub_config, content_type):
        """创建三级子菜单权限"""
        created = 0
        existed = 0

        sub_name = sub_config.get('name', sub_key)

        sub_perm_code = f'view_{sub_key}'
        sub_perm_name = f'查看{sub_name}'
        is_new, is_existed = self._get_or_create_permission(
            sub_perm_code, sub_perm_name, content_type
        )
        if is_new:
            created += 1
        if is_existed:
            existed += 1

        if 'permissions' in sub_config:
            for perm_config in sub_config['permissions']:
                action_perm_code = perm_config.get(
                    'codename', f'change_{sub_key}')
                action_perm_name = perm_config.get('name', sub_name)
                is_new, is_existed = self._get_or_create_permission(
                    action_perm_code, action_perm_name, content_type
                )
                if is_new:
                    created += 1
                if is_existed:
                    existed += 1

        return created, existed

    def _create_permission(self, module_name, perm_config, content_type):
        """创建独立权限"""
        perm_code = perm_config.get('codename', f'view_{module_name}')
        perm_name = perm_config.get('name', module_name)
        is_new, is_existed = self._get_or_create_permission(
            perm_code, perm_name, content_type
        )
        return (1, 0) if is_new else (0, 1)

    def _get_or_create_permission(self, codename, name, content_type):
        """获取或创建权限"""
        try:
            perm, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={'name': name}
            )
            if created:
                return True, False
            return False, True
        except Exception as e:
            self.stdout.write(self.style.WARNING(
                f'  权限创建跳过 ({codename}): {str(e)}'))
            return False, False

    def _preview_permissions(self):
        """预览权限创建计划"""
        self.stdout.write('=== 权限创建预览 ===\n')

        for module_key, module_config in PERMISSION_NODES.items():
            module_name = module_config.get('name', module_key)
            self.stdout.write(f'\n【{module_name}】')
            perm_count = 0

            if 'permissions' in module_config:
                perm_count += len(module_config['permissions'])

            if 'children' in module_config:
                for child_key, child_config in module_config['children'].items(
                ):
                    child_name = child_config.get('name', child_key)
                    perm_count += 1
                    if 'permissions' in child_config:
                        perm_count += len(child_config['permissions'])
                    if 'children' in child_config:
                        for sub_key, sub_config in child_config['children'].items(
                        ):
                            perm_count += 1
                            if 'permissions' in sub_config:
                                perm_count += len(sub_config['permissions'])

            self.stdout.write(f'  权限数量: {perm_count}')

            if 'permissions' in module_config:
                for perm_config in module_config['permissions']:
                    self.stdout.write(f'    - {perm_config["name"]}')

            if 'children' in module_config:
                for child_key, child_config in module_config['children'].items(
                ):
                    child_name = child_config.get('name', child_key)
                    self.stdout.write(f'    - 查看: {child_name}')
                    if 'permissions' in child_config:
                        for perm_config in child_config['permissions']:
                            self.stdout.write(f'      + {perm_config["name"]}')
                    if 'children' in child_config:
                        for sub_key, sub_config in child_config['children'].items(
                        ):
                            sub_name = sub_config.get('name', sub_key)
                            self.stdout.write(f'        * 查看: {sub_name}')
                            if 'permissions' in sub_config:
                                for perm_config in sub_config['permissions']:
                                    self.stdout.write(
                                        f'          - {perm_config["name"]}')

        total_perms = 0
        for module_key, module_config in PERMISSION_NODES.items():
            if 'permissions' in module_config:
                total_perms += len(module_config['permissions'])
            if 'children' in module_config:
                for child_key, child_config in module_config['children'].items(
                ):
                    total_perms += 1
                    if 'permissions' in child_config:
                        total_perms += len(child_config['permissions'])
                    if 'children' in child_config:
                        for sub_key, sub_config in child_config['children'].items(
                        ):
                            total_perms += 1
                            if 'permissions' in sub_config:
                                total_perms += len(sub_config['permissions'])

        self.stdout.write(f'\n总计约 {total_perms} 个权限节点')
