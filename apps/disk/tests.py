import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.department.models import Department
from apps.disk.models import DiskFile, DiskFolder, DiskShare


@override_settings(ROOT_URLCONF='dtcall.urls')
class DiskShareFlowTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix='disk-tests-')
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        self.override_media = override_settings(MEDIA_ROOT=self.media_root)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)

        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username='disk_owner',
            password='pw',
            status=1,
            is_superuser=True,
            name='Owner',
        )
        self.recipient = user_model.objects.create_user(
            username='disk_recipient',
            password='pw',
            status=1,
            is_superuser=True,
            name='Recipient',
        )
        self.department = Department.objects.create(
            name='研发部',
            code='RD',
            status=1,
        )
        self.owner.did = self.department.id
        self.owner.save(update_fields=['did'])
        self.recipient.did = self.department.id
        self.recipient.save(update_fields=['did'])

    def _create_disk_file(self, owner=None, name='shared-note.txt', content='shared content'):
        owner = owner or self.owner
        relative_path = os.path.join('disk', str(owner.id), name)
        absolute_path = os.path.join(self.media_root, relative_path)
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        with open(absolute_path, 'w', encoding='utf-8') as handle:
            handle.write(content)

        return DiskFile.objects.create(
            name=name,
            original_name=name,
            file_path=relative_path,
            file_size=os.path.getsize(absolute_path),
            owner=owner,
            department=self.department,
        )

    def _create_folder(self, owner=None, name='shared-folder', parent=None):
        owner = owner or self.owner
        return DiskFolder.objects.create(
            name=name,
            owner=owner,
            department=self.department,
            parent=parent,
        )

    def test_shared_user_can_preview_text_file_from_internal_share(self):
        disk_file = self._create_disk_file()
        disk_file.shared_users.add(self.recipient)
        self.client.force_login(self.recipient)

        response = self.client.get(reverse('disk:file_preview', args=[disk_file.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data']['type'], 'text')
        disk_file.refresh_from_db()
        self.assertEqual(disk_file.preview_count, 1)

    def test_shared_folder_children_keeps_inherited_access(self):
        parent_folder = self._create_folder(name='parent-folder')
        child_folder = self._create_folder(name='child-folder', parent=parent_folder)
        child_file = self._create_disk_file(name='child.txt')

        child_file.folder = parent_folder
        child_file.save(update_fields=['folder'])
        parent_folder.shared_users.add(self.recipient)

        self.client.force_login(self.recipient)

        response = self.client.get(reverse('disk:shared_children'), {
            'folder_id': parent_folder.id,
        })

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 0)
        self.assertEqual(
            [item['name'] for item in payload['data']['folders']],
            ['child-folder'],
        )
        self.assertEqual(
            [item['name'] for item in payload['data']['files']],
            ['child.txt'],
        )

    def test_shared_root_lists_real_accessible_items(self):
        shared_folder = self._create_folder(owner=self.owner, name='visible-folder')
        shared_file = self._create_disk_file(owner=self.owner, name='visible.txt')
        shared_file.folder = shared_folder
        shared_file.save(update_fields=['folder'])
        shared_folder.shared_users.add(self.recipient)
        shared_file.shared_users.add(self.recipient)

        hidden_folder = self._create_folder(owner=self.owner, name='hidden-folder')
        self._create_disk_file(owner=self.owner, name='hidden.txt')
        hidden_folder.refresh_from_db()

        self.client.force_login(self.recipient)

        response = self.client.get(reverse('disk:shared'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('shared_folders', response.context)
        self.assertIn('shared_files', response.context)
        folder_names = [item.name for item in response.context['shared_folders']]
        file_names = [item.name for item in response.context['shared_files']]
        self.assertIn('visible-folder', folder_names)
        self.assertIn('visible.txt', file_names)
        self.assertNotIn('hidden-folder', folder_names)
        self.assertNotIn('hidden.txt', file_names)

    def test_permission_manage_view_renders_department_labels(self):
        disk_file = self._create_disk_file()
        disk_file.shared_users.add(self.recipient)
        self.client.force_login(self.owner)

        response = self.client.get(reverse('disk:permission_manage'), {
            'type': 'file',
            'id': disk_file.id,
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('shared_user_count', response.context)
        self.assertEqual(response.context['shared_user_count'], 1)
        self.assertEqual(response.context['user_department_map'][self.recipient.id], '研发部')
        self.assertEqual(response['X-Disk-UI-Version'], 'modern-permission-v2')

    def test_permission_add_pages_use_local_static_assets(self):
        disk_file = self._create_disk_file()
        self.client.force_login(self.owner)

        user_response = self.client.get(reverse('disk:user_permission_add'), {
            'type': 'file',
            'id': disk_file.id,
        }, follow=True)
        dept_response = self.client.get(reverse('disk:dept_permission_add'), {
            'type': 'file',
            'id': disk_file.id,
        }, follow=True)
        manage_response = self.client.get(reverse('disk:permission_manage'), {
            'type': 'file',
            'id': disk_file.id,
        }, follow=True)

        self.assertEqual(user_response.status_code, 200)
        self.assertEqual(dept_response.status_code, 200)
        self.assertEqual(manage_response.status_code, 200)
        user_body = user_response.content.decode('utf-8')
        dept_body = dept_response.content.decode('utf-8')
        manage_body = manage_response.content.decode('utf-8')
        self.assertNotIn('code.jquery.com', user_body)
        self.assertNotIn('code.jquery.com', dept_body)
        self.assertNotIn('code.jquery.com', manage_body)
        self.assertIn('/static/js/jquery.min.js', user_body)
        self.assertIn('/static/js/jquery.min.js', dept_body)
        self.assertIn('/static/js/jquery.min.js', manage_body)
        self.assertEqual(user_response['X-Disk-UI-Version'], 'modern-permission-user-v2')
        self.assertEqual(dept_response['X-Disk-UI-Version'], 'modern-permission-dept-v2')
        self.assertEqual(manage_response['X-Disk-UI-Version'], 'modern-permission-v2')

    def test_shared_root_shows_real_source_details(self):
        disk_file = self._create_disk_file()
        disk_file.shared_users.add(self.recipient)
        self.client.force_login(self.recipient)

        response = self.client.get(reverse('disk:shared'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('用户共享', body)
        self.assertIn('来源用户：Owner', body)
        self.assertIn('方式：直接共享', body)

    def test_share_create_persists_copy_and_screenshot_permissions(self):
        disk_file = self._create_disk_file()
        self.client.force_login(self.owner)

        response = self.client.post(reverse('disk:share_create'), {
            'type': 'file',
            'id': str(disk_file.id),
            'password': '',
            'expire_days': '7',
            'allow_download': 'on',
            'allow_preview': 'on',
            'allow_copy': 'off',
            'allow_screenshot': 'off',
            'access_limit': '0',
            'download_limit': '0',
            'is_active': 'on',
        })

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 0)
        share = DiskShare.objects.get(id=payload['data']['share_id'])
        self.assertFalse(share.allow_copy)
        self.assertFalse(share.allow_screenshot)

    def test_external_share_action_records_copy_and_screenshot_events(self):
        disk_file = self._create_disk_file()
        share = DiskShare.objects.create(
            share_type='file',
            file=disk_file,
            share_code='COPYSHOT1',
            creator=self.owner,
            allow_download=True,
            allow_preview=True,
            allow_copy=False,
            allow_screenshot=False,
        )

        copy_response = self.client.post(reverse('disk:share_action'), {
            'share_code': share.share_code,
            'action': 'copy',
        })
        screenshot_response = self.client.post(reverse('disk:share_action'), {
            'share_code': share.share_code,
            'action': 'screenshot',
        })

        self.assertEqual(copy_response.status_code, 200)
        self.assertEqual(screenshot_response.status_code, 200)
        self.assertEqual(copy_response.json()['code'], 1)
        self.assertEqual(screenshot_response.json()['code'], 1)

        share.refresh_from_db()
        self.assertEqual(share.copy_blocked_count, 1)
        self.assertEqual(share.screenshot_blocked_count, 1)

    def test_legacy_permission_manage_path_redirects_to_current_route(self):
        disk_file = self._create_disk_file()
        self.client.force_login(self.owner)

        response = self.client.get('/disk/permission/manage/', {
            'type': 'file',
            'id': disk_file.id,
        })

        self.assertEqual(response.status_code, 302)
        self.assertIn('/disk/permission/?type=file&id=', response.url)

    def test_permission_pages_redirect_to_modern_cache_busting_query(self):
        disk_file = self._create_disk_file()
        self.client.force_login(self.owner)

        manage_response = self.client.get(reverse('disk:permission_manage'), {
            'type': 'file',
            'id': disk_file.id,
        })
        user_response = self.client.get(reverse('disk:user_permission_add'), {
            'type': 'file',
            'id': disk_file.id,
        })
        dept_response = self.client.get(reverse('disk:dept_permission_add'), {
            'type': 'file',
            'id': disk_file.id,
        })

        self.assertEqual(manage_response.status_code, 302)
        self.assertIn('_ui=modern', manage_response.url)
        self.assertEqual(user_response.status_code, 302)
        self.assertIn('_ui=modern', user_response.url)
        self.assertEqual(dept_response.status_code, 302)
        self.assertIn('_ui=modern', dept_response.url)
