import os
import shutil
import tempfile

from django.conf import settings
from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.personal.models import MeetingMinutes
from apps.user.models import Admin


TEST_MIDDLEWARE = [
    middleware for middleware in settings.MIDDLEWARE
    if middleware not in {
        'apps.system.middleware.permission_middleware.PermissionMiddleware',
        'apps.system.middleware.database_setup_middleware.DatabaseSetupMiddleware',
    }
]


@override_settings(
    MIDDLEWARE=TEST_MIDDLEWARE,
    ONLYOFFICE_ENABLED=True,
    ONLYOFFICE_SERVER_URL='http://127.0.0.1:8082',
    ONLYOFFICE_PUBLIC_PATH='/office/',
    ONLYOFFICE_CALLBACK_BASE_URL='http://testserver',
    ONLYOFFICE_JWT_SECRET='',
)
class PersonalMeetingMinutesOnlyOfficeTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix='personal-onlyoffice-')
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        self.override_media = override_settings(MEDIA_ROOT=self.media_root)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)

        self.user = Admin.objects.create_user(
            username='minutes_user',
            password='secret123',
            email='minutes@example.com',
            name='会议纪要测试员',
        )
        self.client.force_login(self.user)
        self.minutes = MeetingMinutes.objects.create(
            title='周例会',
            meeting_date=timezone.now(),
            recorder=self.user,
            user=self.user,
            attendees='张三\n李四',
            decisions='1. 排期推进 - 决策内容：本周完成联调 - 执行对象：研发部 - 目标：周五前提交验收',
            is_public=False,
        )

    def test_minutes_preview_renders_onlyoffice_shell(self):
        response = self.client.get(reverse('personal:minutes_preview', args=[self.minutes.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('personal:minutes_preview_config', args=[self.minutes.id]))

    def test_minutes_preview_config_is_read_only(self):
        response = self.client.get(reverse('personal:minutes_preview_config', args=[self.minutes.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['editorConfig']['mode'], 'view')
        self.assertFalse(payload['document']['permissions']['edit'])

    def test_minutes_preview_document_stream_requires_valid_token(self):
        token = signing.dumps(
            {
                'minutes_id': self.minutes.id,
                'path': 'generated/meeting_minutes/{}/minutes_preview.docx'.format(self.minutes.id),
                'action': 'document',
                'updated_at': self.minutes.updated_at.isoformat() if self.minutes.updated_at else '',
            },
            salt='personal.minutes.onlyoffice.document',
        )

        response = self.client.get(
            reverse('personal:minutes_preview_document', args=[self.minutes.id]),
            {'token': token},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
