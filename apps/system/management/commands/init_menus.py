#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Django管理命令：初始化菜单数据
用于创建系统默认的菜单配置
使用方法: python manage.py init_menus
"""
from django.core.management.base import BaseCommand
from apps.user.models import Menu


class Command(BaseCommand):
    help = '初始化系统菜单数据'

    def handle(self, *args, **options):
        # 检查是否已有菜单数据
        if Menu.objects.exists():
            self.stdout.write(self.style.WARNING('数据库中已存在菜单数据，跳过初始化'))
            return 0

        try:
            # 创建顶级菜单
            top_menus = [
                {
                    'title': '首页',
                    'src': '/home/dashboard/',
                    'icon': 'layui-icon-home',
                    'sort': 1,
                    'status': 1
                },
                {
                    'title': '人事管理',
                    'src': 'javascript:;',
                    'icon': 'layui-icon-user',
                    'sort': 2,
                    'status': 1
                },
                {
                    'title': '客户管理',
                    'src': 'javascript:;',
                    'icon': 'layui-icon-group',
                    'sort': 3,
                    'status': 1
                },
                {
                    'title': '项目管理',
                    'src': 'javascript:;',
                    'icon': 'layui-icon-template',
                    'sort': 4,
                    'status': 1
                },
                {
                    'title': '生产管理',
                    'src': 'javascript:;',
                    'icon': 'layui-icon-template',
                    'sort': 5,
                    'status': 1
                },
                {
                    'title': '系统管理',
                    'src': 'javascript:;',
                    'icon': 'layui-icon-set',
                    'sort': 6,
                    'status': 1
                }
            ]

            # 创建子菜单
            sub_menus = [
                # 人事管理子菜单
                {
                    'title': '员工管理',
                    'src': '/adm/employee_management/',
                    'icon': 'layui-icon-user',
                    'sort': 1,
                    'status': 1,
                    'parent_title': '人事管理'
                },
                {
                    'title': '角色管理',
                    'src': '/system/permission/role/',  # 修正为正确的URL路径
                    'icon': 'layui-icon-auz',
                    'sort': 2,
                    'status': 1,
                    'parent_title': '人事管理'
                },
                {
                    'title': '部门管理',
                    'src': '/adm/department/',
                    'icon': 'layui-icon-component',
                    'sort': 3,
                    'status': 1,
                    'parent_title': '人事管理'
                },
                {
                    'title': '职位管理',
                    'src': '/adm/position/',
                    'icon': 'layui-icon-username',
                    'sort': 4,
                    'status': 1,
                    'parent_title': '人事管理'
                },
                # 生产管理子菜单
                {
                    'title': '基础信息',
                    'src': '/production/baseinfo/',
                    'icon': 'layui-icon-console',
                    'sort': 1,
                    'status': 1,
                    'parent_title': '生产管理'
                },
                {
                    'title': '工艺路线',
                    'src': '/production/process/',
                    'icon': 'layui-icon-map',
                    'sort': 2,
                    'status': 1,
                    'parent_title': '生产管理'
                },
                {
                    'title': '生产计划',
                    'src': '/production/task/plan/',
                    'icon': 'layui-icon-calendar',
                    'sort': 3,
                    'status': 1,
                    'parent_title': '生产管理'
                },
                {
                    'title': '生产任务',
                    'src': '/production/task/execution/',
                    'icon': 'layui-icon-play',
                    'sort': 4,
                    'status': 1,
                    'parent_title': '生产管理'
                },
                {
                    'title': '质量管理',
                    'src': '/production/quality/',
                    'icon': 'layui-icon-survey',
                    'sort': 5,
                    'status': 1,
                    'parent_title': '生产管理'
                },
                {
                    'title': '设备监控',
                    'src': '/production/monitor/',
                    'icon': 'layui-icon-refresh',
                    'sort': 6,
                    'status': 1,
                    'parent_title': '生产管理'
                },
                {
                    'title': '数据采集',
                    'src': '/production/data/',
                    'icon': 'layui-icon-data',
                    'sort': 7,
                    'status': 1,
                    'parent_title': '生产管理'
                },
                {
                    'title': '性能分析',
                    'src': '/production/analysis/',
                    'icon': 'layui-icon-chart',
                    'sort': 8,
                    'status': 1,
                    'parent_title': '生产管理'
                }
            ]

            # 创建菜单数据
            created_count = 0

            # 创建顶级菜单
            top_menu_objects = {}
            for menu_data in top_menus:
                menu = Menu.objects.create(
                    title=menu_data['title'],
                    src=menu_data['src'],
                    icon=menu_data['icon'],
                    sort=menu_data['sort'],
                    status=menu_data['status']
                )
                top_menu_objects[menu_data['title']] = menu
                created_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f'创建顶级菜单: {menu_data["title"]}'))

            # 创建子菜单
            for menu_data in sub_menus:
                parent_menu = top_menu_objects.get(menu_data['parent_title'])
                if parent_menu:
                    menu = Menu.objects.create(
                        title=menu_data['title'],
                        src=menu_data['src'],
                        icon=menu_data['icon'],
                        pid=parent_menu,
                        sort=menu_data['sort'],
                        status=menu_data['status']
                    )
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'创建子菜单: {menu_data["parent_title"]} -> {menu_data["title"]}'))

            self.stdout.write(self.style.SUCCESS(
                f'菜单数据初始化完成！共创建 {created_count} 个菜单项'))
            return 0

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'初始化菜单数据时出错: {str(e)}'))
            import traceback
            traceback.print_exc()
            return 1
