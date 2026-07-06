import os
import shutil
import tempfile
from io import StringIO
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core import signing
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.department.models import Department
from apps.disk.models import DiskFile, DiskFolder, DiskShare
from apps.disk.services import onlyoffice as onlyoffice_service
from apps.disk.views import get_preview_cache_key


@override_settings(
    ROOT_URLCONF='dtcall.urls',
    ONLYOFFICE_ENABLED=True,
    ONLYOFFICE_SERVER_URL='http://127.0.0.1:8082',
    ONLYOFFICE_PUBLIC_PATH='/office/',
    ONLYOFFICE_CALLBACK_BASE_URL='http://testserver',
    ONLYOFFICE_JWT_SECRET='',
)
class OnlyOfficeIntegrationTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix='onlyoffice-tests-')
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        self.override_media = override_settings(MEDIA_ROOT=self.media_root)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)

        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username='oo_owner',
            password='pw',
            status=1,
            is_superuser=True,
            name='Owner',
        )
        self.viewer = user_model.objects.create_user(
            username='oo_viewer',
            password='pw',
            status=1,
            is_superuser=True,
            name='Viewer',
        )
        self.department = Department.objects.create(
            name='研发部',
            code='RD-OO',
            status=1,
        )
        self.owner.did = self.department.id
        self.owner.save(update_fields=['did'])
        self.viewer.did = self.department.id
        self.viewer.save(update_fields=['did'])

    def _create_disk_file(self, owner=None, name='proposal.docx', content=b'initial-content'):
        owner = owner or self.owner
        relative_path = os.path.join('disk', str(owner.id), name)
        absolute_path = os.path.join(self.media_root, relative_path)
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        with open(absolute_path, 'wb') as handle:
            handle.write(content)

        return DiskFile.objects.create(
            name=name,
            original_name=name,
            file_path=relative_path,
            file_size=os.path.getsize(absolute_path),
            owner=owner,
            department=self.department,
        )

    def _create_folder(self, owner=None, name='shared-folder', parent=None, permission_level=1):
        owner = owner or self.owner
        return DiskFolder.objects.create(
            name=name,
            owner=owner,
            department=self.department,
            parent=parent,
            permission_level=permission_level,
        )

    def test_office_preview_returns_onlyoffice_payload(self):
        disk_file = self._create_disk_file()
        self.client.force_login(self.owner)

        response = self.client.get(reverse('disk:file_preview', args=[disk_file.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data']['type'], 'onlyoffice')
        self.assertIn('editor_url', payload['data'])

    def test_office_preview_ignores_legacy_cached_payload(self):
        disk_file = self._create_disk_file()
        cache.set(
            get_preview_cache_key(disk_file),
            {
                'type': 'office_enhanced',
                'name': disk_file.name,
                'preview_options': [],
            },
            timeout=3600,
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse('disk:file_preview', args=[disk_file.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data']['type'], 'onlyoffice')
        self.assertIn('editor_url', payload['data'])

    def test_onlyoffice_editor_config_requires_permission(self):
        disk_file = self._create_disk_file()
        self.client.force_login(self.viewer)

        response = self.client.get(reverse('disk:onlyoffice_config', args=[disk_file.id]))

        self.assertEqual(response.status_code, 403)

    def test_onlyoffice_editor_config_returns_owner_document_metadata(self):
        disk_file = self._create_disk_file()
        self.client.force_login(self.owner)

        response = self.client.get(reverse('disk:onlyoffice_config', args=[disk_file.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('document', payload)
        self.assertEqual(payload['document']['title'], disk_file.original_name)
        self.assertEqual(payload['editorConfig']['mode'], 'edit')

    def test_onlyoffice_editor_config_returns_view_mode_for_shared_user(self):
        disk_file = self._create_disk_file()
        disk_file.shared_users.add(self.viewer)
        self.client.force_login(self.viewer)

        response = self.client.get(reverse('disk:onlyoffice_config', args=[disk_file.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['editorConfig']['mode'], 'view')
        self.assertFalse(payload['document']['permissions']['edit'])

    def test_onlyoffice_editor_config_returns_edit_mode_for_rw_shared_user(self):
        disk_file = self._create_disk_file()
        disk_file.permission_level = 2
        disk_file.save(update_fields=['permission_level'])
        disk_file.shared_users.add(self.viewer)
        self.client.force_login(self.viewer)

        response = self.client.get(reverse('disk:onlyoffice_config', args=[disk_file.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['editorConfig']['mode'], 'edit')
        self.assertTrue(payload['document']['permissions']['edit'])

    def test_onlyoffice_editor_config_inherits_edit_mode_from_shared_folder(self):
        shared_folder = self._create_folder(permission_level=2)
        shared_folder.shared_users.add(self.viewer)
        disk_file = self._create_disk_file()
        disk_file.folder = shared_folder
        disk_file.save(update_fields=['folder'])
        self.client.force_login(self.viewer)

        response = self.client.get(reverse('disk:onlyoffice_config', args=[disk_file.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['editorConfig']['mode'], 'edit')
        self.assertTrue(payload['document']['permissions']['edit'])

    def test_share_preview_returns_onlyoffice_editor_url_with_share_code(self):
        disk_file = self._create_disk_file()
        share = DiskShare.objects.create(
            share_type='file',
            file=disk_file,
            share_code='OO-SHARE-1',
            creator=self.owner,
            allow_download=True,
            allow_preview=True,
        )

        response = self.client.get(reverse('disk:share_preview', args=[disk_file.id]), {
            'share_code': share.share_code,
        })

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data']['type'], 'onlyoffice')
        self.assertIn('share_code=' + share.share_code, payload['data']['editor_url'])

    def test_onlyoffice_callback_ignores_non_save_status(self):
        disk_file = self._create_disk_file()
        token = signing.dumps(
            {'file_id': disk_file.id, 'share_code': '', 'action': 'callback', 'can_edit': True},
            salt=onlyoffice_service.CALLBACK_TOKEN_SALT,
        )

        response = self.client.post(
            reverse('disk:onlyoffice_callback', args=[disk_file.id]) + '?token=' + token,
            data='{"status": 1, "key": "noop"}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'error': 0})

    @patch('apps.disk.services.onlyoffice.requests.get')
    def test_onlyoffice_callback_persists_saved_file(self, mock_get):
        disk_file = self._create_disk_file(content=b'old-version')
        token = signing.dumps(
            {'file_id': disk_file.id, 'share_code': '', 'action': 'callback', 'can_edit': True},
            salt=onlyoffice_service.CALLBACK_TOKEN_SALT,
        )
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b'new-version'
        mock_get.return_value = mock_response

        response = self.client.post(
            reverse('disk:onlyoffice_callback', args=[disk_file.id]) + '?token=' + token,
            data='{"status": 2, "key": "save-key", "url": "http://document-server/cache/result.docx", "users": ["u1"]}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'error': 0})

        file_path = os.path.join(self.media_root, disk_file.file_path)
        with open(file_path, 'rb') as handle:
            self.assertEqual(handle.read(), b'new-version')

    def test_onlyoffice_document_token_is_rejected_after_share_state_changes(self):
        disk_file = self._create_disk_file()
        share = DiskShare.objects.create(
            share_type='file',
            file=disk_file,
            share_code='OO-SHARE-2',
            creator=self.owner,
            allow_download=True,
            allow_preview=True,
        )

        config_response = self.client.get(
            reverse('disk:onlyoffice_config', args=[disk_file.id]),
            {'share_code': share.share_code},
        )

        self.assertEqual(config_response.status_code, 200)
        document_url = config_response.json()['document']['url']
        token = parse_qs(urlparse(document_url).query)['token'][0]

        share.allow_preview = False
        share.save(update_fields=['allow_preview', 'update_time'])

        response = self.client.get(
            reverse('disk:onlyoffice_document', args=[disk_file.id]),
            {'token': token},
        )

        self.assertEqual(response.status_code, 403)

    @patch('apps.disk.management.commands.check_onlyoffice.requests.get')
    def test_check_onlyoffice_command_passes_with_valid_settings(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        stdout = StringIO()
        call_command('check_onlyoffice', stdout=stdout)

        output = stdout.getvalue()
        self.assertIn('ONLYOFFICE integration check passed.', output)
        mock_get.assert_called_once()

    @override_settings(X_FRAME_OPTIONS='DENY')
    def test_check_onlyoffice_command_fails_when_frame_options_block_iframe(self):
        with self.assertRaises(CommandError):
            call_command('check_onlyoffice', '--skip-network', stdout=StringIO())

    @override_settings(ONLYOFFICE_CALLBACK_BASE_URL='')
    def test_check_onlyoffice_command_allows_empty_callback_base(self):
        stdout = StringIO()

        call_command('check_onlyoffice', '--skip-network', stdout=stdout)

        output = stdout.getvalue()
        self.assertIn('ONLYOFFICE integration check passed.', output)
        self.assertIn('ONLYOFFICE_CALLBACK_BASE_URL is empty', output)
