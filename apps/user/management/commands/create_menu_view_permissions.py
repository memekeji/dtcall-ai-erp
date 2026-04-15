"""
为所有菜单创建查看权限
"""
from django.core.management.base import BaseCommand
from apps.user.models.menu import Menu


class Command(BaseCommand):
    help = '为所有菜单创建查看权限'

    def handle(self, *args, **options):
        menus = Menu.objects.all()
        total = menus.count()
        created = 0
        skipped = 0

        self.stdout.write(f'开始处理 {total} 个菜单...')

        for menu in menus:
            if menu.view_permission:
                skipped += 1
                self.stdout.write(f'跳过: {menu.title} (已有查看权限)')
            else:
                permission = menu.create_view_permission()
                if permission:
                    created += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'成功: {menu.title} - 权限ID: {permission.id}'))
                else:
                    self.stdout.write(self.style.ERROR(f'失败: {menu.title}'))

        self.stdout.write(self.style.SUCCESS(
            f'\n完成! 总计: {total}, 创建: {created}, 跳过: {skipped}'
        ))
