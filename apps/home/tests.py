import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.home.views import quick_menus
from apps.user.models import Menu, SystemModule


class UserQuickMenuViewTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.module = SystemModule.objects.create(
            name='测试模块',
            code='quick-menu-test',
            is_active=True,
        )

    def create_user(self, username='quick_menu_user', is_superuser=False):
        return self.user_model.objects.create_user(
            username=username,
            password='test-pass-123',
            is_superuser=is_superuser,
            is_staff=True,
        )

    def create_menu(self, title, src, sort=1, status=1, module=None):
        return Menu.objects.create(
            title=title,
            src=src,
            sort=sort,
            status=status,
            module=module or self.module,
        )

    def test_menu_usage_endpoint_creates_and_increments_preference(self):
        user = self.create_user(username='usage_user', is_superuser=True)
        menu = self.create_menu('员工管理', '/user/employee/')
        self.client.force_login(user)

        response = self.client.post(
            reverse('home:menu_usage'),
            data=json.dumps({'menu_id': menu.id}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            user.menu_preferences.get(menu=menu).use_count,
            1,
        )

        response = self.client.post(
            reverse('home:menu_usage'),
            data=json.dumps({'menu_id': menu.id}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        preference = user.menu_preferences.get(menu=menu)
        self.assertEqual(preference.use_count, 2)
        self.assertIsNotNone(preference.last_used_at)

    def test_pin_endpoint_toggles_pin_status(self):
        user = self.create_user(username='pin_user', is_superuser=True)
        menu = self.create_menu('消息中心', '/message/conversations/page/')
        self.client.force_login(user)

        response = self.client.post(
            reverse('home:quick_menu_pin'),
            data=json.dumps({'menu_id': menu.id, 'is_pinned': True}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        preference = user.menu_preferences.get(menu=menu)
        self.assertTrue(preference.is_pinned)

        response = self.client.post(
            reverse('home:quick_menu_pin'),
            data=json.dumps({'menu_id': menu.id, 'is_pinned': False}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        preference.refresh_from_db()
        self.assertFalse(preference.is_pinned)

    def test_quick_menu_endpoint_groups_pinned_and_frequent_without_duplicates(self):
        user = self.create_user(username='group_user', is_superuser=True)
        pinned_menu = self.create_menu('员工管理', '/user/employee/', sort=1)
        frequent_menu = self.create_menu('消息中心', '/message/conversations/page/', sort=2)
        another_menu = self.create_menu('工作台', '/home/main/', sort=3)
        self.client.force_login(user)

        pinned_preference = user.menu_preferences.create(
            menu=pinned_menu,
            use_count=12,
            is_pinned=True,
            last_used_at=timezone.now(),
        )
        user.menu_preferences.create(
            menu=frequent_menu,
            use_count=9,
            last_used_at=timezone.now() - timedelta(minutes=5),
        )
        user.menu_preferences.create(
            menu=another_menu,
            use_count=3,
            last_used_at=timezone.now() - timedelta(minutes=10),
        )

        response = self.client.get(reverse('home:quick_menus'))

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode())
        pinned_ids = [item['id'] for item in payload['pinned_menus']]
        frequent_ids = [item['id'] for item in payload['frequent_menus']]

        self.assertEqual(pinned_ids, [pinned_menu.id])
        self.assertNotIn(pinned_menu.id, frequent_ids)
        self.assertEqual(frequent_ids, [frequent_menu.id, another_menu.id])
        self.assertEqual(payload['pinned_menus'][0]['use_count'], pinned_preference.use_count)

    def test_quick_menu_endpoint_filters_out_inaccessible_and_disabled_menus(self):
        user = self.create_user(username='filter_user', is_superuser=False)
        accessible_menu = self.create_menu('员工管理', '/user/employee/', sort=1)
        inaccessible_menu = self.create_menu('消息中心', '/message/conversations/page/', sort=2)
        disabled_menu = self.create_menu('停用菜单', '/home/main/', sort=3, status=0)
        inactive_module = SystemModule.objects.create(
            name='停用模块',
            code='inactive-quick-menu-test',
            is_active=False,
        )
        inactive_menu = self.create_menu(
            '停用模块菜单',
            '/home/dashboard/',
            sort=4,
            module=inactive_module,
        )
        user.user_permissions.add(Permission.objects.get(codename='view_employee'))

        user.menu_preferences.create(menu=accessible_menu, use_count=5, last_used_at=timezone.now())
        user.menu_preferences.create(menu=inaccessible_menu, use_count=7, last_used_at=timezone.now())
        user.menu_preferences.create(menu=disabled_menu, use_count=9, last_used_at=timezone.now())
        user.menu_preferences.create(menu=inactive_menu, use_count=11, last_used_at=timezone.now())

        request = RequestFactory().get(reverse('home:quick_menus'))
        request.user = user
        response = quick_menus(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode())
        returned_ids = {
            item['id']
            for item in payload['pinned_menus'] + payload['frequent_menus']
        }

        self.assertEqual(returned_ids, {accessible_menu.id})

    def test_main_page_uses_flow_layout_for_quick_menu_header(self):
        user = self.create_user(username='layout_user', is_superuser=True)
        self.client.force_login(user)

        response = self.client.get(reverse('home:main'))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('justify-content: flex-start;', content)
        self.assertIn('position: relative;', content)
        self.assertIn('padding: 0 24px 0 20px;', content)
        self.assertIn('position: static;', content)
        self.assertIn('margin-left: auto;', content)
