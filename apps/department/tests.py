from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.department.models import Department


class DepartmentFormTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username='department-admin',
            password='pw',
            status=1,
            is_superuser=True,
            is_staff=True,
            name='部门管理员',
        )
        self.client.force_login(self.user)

    def test_create_department_auto_generates_top_level_code(self):
        response = self.client.post(
            reverse('department_add'),
            {
                'name': '运营中心',
                'pid': '0',
                'sort': '10',
                'status': '1',
                'leader_ids': '',
                'phone': '',
                'remark': '',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)

        department = Department.objects.get(name='运营中心')
        self.assertEqual(department.code, 'D001')

    def test_create_department_auto_generates_child_code(self):
        parent = Department.objects.create(name='研发中心', code='D009', status=1)
        Department.objects.create(name='后端组', code='D009001', pid=parent.id, status=1)

        response = self.client.post(
            reverse('department_add'),
            {
                'name': '前端组',
                'pid': str(parent.id),
                'sort': '20',
                'status': '1',
                'leader_ids': '',
                'phone': '',
                'remark': '',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)

        department = Department.objects.get(name='前端组')
        self.assertEqual(department.code, 'D009002')

    def test_department_form_renders_auto_generated_code_and_single_submit_entry(self):
        response = self.client.get(reverse('department_add'))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('dept-compact-head', body)
        self.assertNotIn('dept-hero', body)
        self.assertIn('id="departmentCodeField"', body)
        self.assertIn('id="departmentCodeInlinePreview"', body)
        self.assertIn('data-auto-generate="true"', body)
        self.assertIn('readonly', body)
        self.assertIn('id="departmentSubmitBtn"', body)
        self.assertIn('type="button"', body)

    def test_department_list_uses_single_screen_workspace_layout(self):
        response = self.client.get(reverse('department_list'))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('function syncWorkspaceHeight()', body)
        self.assertIn('overflow-y: hidden;', body)
        self.assertIn('department-sidebar', body)

    def test_department_list_renders_compact_toolbar_and_viewport_table_layout(self):
        response = self.client.get(reverse('department_list'))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('department-toolbar', body)
        self.assertIn('departmentScopeLabel', body)
        self.assertIn('人事管理', body)
        self.assertIn('department-title-scope', body)
        self.assertNotIn('右侧抽屉操作', body)
        self.assertIn('department-table-shell', body)
        self.assertIn('function getTableHeight()', body)
        self.assertIn('limit: 10', body)

    def test_department_list_renders_direct_row_actions(self):
        response = self.client.get(reverse('department_list'))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('lay-event="detail"', body)
        self.assertIn('lay-event="edit"', body)
        self.assertIn('lay-event="role_management"', body)
        self.assertIn('lay-event="delete"', body)
        self.assertIn('lay-event="disable"', body)
        self.assertIn('lay-event="enable"', body)
        self.assertNotIn('lay-event="more"', body)
        self.assertNotIn('function openActionMenu(', body)
        self.assertIn("/user/department/' + data.id + '/roles/", body)
        self.assertNotIn("/system/permission/department/' + data.id + '/roles/", body)
        self.assertIn("Number(d.status) === 1", body)
        self.assertNotIn("String(d.is_active) === '1'", body)

    def test_department_list_renders_csrf_token_for_ajax_actions(self):
        response = self.client.get(reverse('department_list'))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('csrfmiddlewaretoken', body)
        self.assertIn('function getCsrfToken()', body)

    def test_department_detail_endpoint_renders_department_content(self):
        department = Department.objects.create(name='客服部', code='D020', status=1, is_active=True)

        response = self.client.get(reverse('department_detail', kwargs={'pk': department.id}))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('部门详情', body)
        self.assertIn('客服部', body)

    def test_department_change_status_endpoint_updates_status_and_is_active(self):
        department = Department.objects.create(name='财务一部', code='D021', status=1, is_active=True)

        response = self.client.post(
            reverse('department_change_status', kwargs={'department_id': department.id}),
            {'status': '0'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)

        department.refresh_from_db()
        self.assertEqual(department.status, 0)
        self.assertFalse(department.is_active)
