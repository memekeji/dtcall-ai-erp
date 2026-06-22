"""
权限初始化命令
根据权限管理详细设计文档创建系统权限节点
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from apps.user.config.permission_nodes import (
    PERMISSION_NODES,
    get_permission_metadata,
)
from apps.user.models.permission import GroupExtension


PERMISSION_CONTENT_TYPE = {
    'app_label': 'user',
    'model': 'permission',
}

DEFAULT_ADMIN_ROLE = {
    'name': '管理员',
    'description': '系统默认管理员角色，拥有全部菜单与按钮操作权限。',
}


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
                self._create_default_admin_role()
        else:
            with transaction.atomic():
                self._create_permissions()
                self._create_default_admin_role()

    def _clear_permissions(self):
        """清除现有的自定义权限"""
        self.stdout.write('\n清除现有自定义权限...')
        content_type = self._get_permission_content_type()
        deleted_count, _ = Permission.objects.filter(
            content_type=content_type
        ).delete()
        self.stdout.write(
            self.style.SUCCESS(f'已删除 {deleted_count} 个自定义权限'))

    def _get_permission_content_type(self):
        return ContentType.objects.get_or_create(**PERMISSION_CONTENT_TYPE)[0]

    def _flatten_permissions(self):
        permissions = []

        def collect_permissions(
                node_key,
                node_data,
                module_key,
                module_name,
                parent_names=None):
            parent_names = parent_names or []
            current_names = parent_names + [node_data['name']]

            for permission in node_data.get('permissions', []):
                metadata = get_permission_metadata(
                    permission['codename'], permission['name'])
                permissions.append({
                    **permission,
                    **metadata,
                    'module_key': module_key,
                    'module_name': module_name,
                    'page_key': node_key,
                    'page_name': node_data['name'],
                    'page_path': ' / '.join(current_names),
                })

            for child_key, child_data in node_data.get('children', {}).items():
                collect_permissions(
                    child_key,
                    child_data,
                    module_key,
                    module_name,
                    current_names,
                )

        for module_key, module_data in PERMISSION_NODES.items():
            collect_permissions(
                module_key,
                module_data,
                module_key,
                module_data['name'],
                [],
            )

        return permissions

    def _create_permissions(self):
        """创建权限"""
        content_type = self._get_permission_content_type()
        permissions = self._flatten_permissions()
        created_count = 0
        updated_count = 0

        self.stdout.write('\n开始初始化权限节点...\n')

        for permission_data in permissions:
            permission, created = Permission.objects.update_or_create(
                codename=permission_data['codename'],
                content_type=content_type,
                defaults={'name': permission_data['name']},
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[新增] 权限: {permission_data['page_path']} - "
                        f"{permission.name} ({permission.codename})"))
            else:
                updated_count += 1
                self.stdout.write(
                    f"[更新] 权限: {permission_data['page_path']} - "
                    f"{permission.name} ({permission.codename})")

        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS(
            f'权限初始化完成！创建 {created_count} 个，更新 {updated_count} 个'))
        self.stdout.write(f'总权限数: {created_count + updated_count}')
        return Permission.objects.filter(
            content_type=content_type,
            codename__in=[item['codename'] for item in permissions],
        )

    def _create_default_admin_role(self):
        permissions = self._get_configured_permission_queryset()
        group, created = Group.objects.get_or_create(
            name=DEFAULT_ADMIN_ROLE['name'])
        group.permissions.set(permissions)
        extension, _ = GroupExtension.objects.get_or_create(group=group)
        extension.description = DEFAULT_ADMIN_ROLE['description']
        extension.status = True
        extension.save(update_fields=['description', 'status', 'updated_at'])
        action_text = '创建' if created else '更新'
        self.stdout.write(self.style.SUCCESS(
            f"{action_text}默认管理员角色: {group.name}，已授予 {permissions.count()} 个权限"))

    def _get_configured_permission_queryset(self):
        content_type = self._get_permission_content_type()
        permissions = self._flatten_permissions()
        return Permission.objects.filter(
            content_type=content_type,
            codename__in=[item['codename'] for item in permissions],
        )

    def _preview_permissions(self):
        self.stdout.write('=== 权限创建预览 ===\n')
        permissions = self._flatten_permissions()
        module_summary = {}

        for permission in permissions:
            module_summary.setdefault(permission['module_name'], 0)
            module_summary[permission['module_name']] += 1
            self.stdout.write(
                f"- {permission['page_path']} / {permission['category']} / "
                f"{permission['name']} ({permission['codename']})")

        self.stdout.write('\n=== 模块汇总 ===')
        for module_name, count in module_summary.items():
            self.stdout.write(f'{module_name}: {count} 个权限')
        self.stdout.write(f'\n总计 {len(permissions)} 个权限节点')
