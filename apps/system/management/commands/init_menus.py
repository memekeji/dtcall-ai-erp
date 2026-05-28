#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from apps.system.menu_sync import sync_menus_from_config


class Command(BaseCommand):
    help = '从系统菜单配置同步初始化菜单数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-extra',
            action='store_true',
            help='保留数据库中不在配置文件内的菜单',
        )

    def handle(self, *args, **options):
        result = sync_menus_from_config(delete_extra=not options['keep_extra'])
        if result['errors']:
            self.stdout.write(self.style.ERROR('菜单同步失败，请检查服务端日志'))
            for error in result['errors']:
                self.stdout.write(self.style.ERROR(
                    f"ID:{error['id']} {error['title']} - {error['message']}"
                ))
            return 1

        self.stdout.write(self.style.SUCCESS(
            '菜单同步完成：'
            f"新增 {result['created']} 个，"
            f"更新 {result['updated']} 个，"
            f"删除 {result['deleted']} 个，"
            f"禁用额外菜单 {result['disabled_extra']} 个，"
            f"父级关联调整 {result['parent_updated']} 个，"
            f"配置总数 {result['total']} 个"
        ))
        return 0
