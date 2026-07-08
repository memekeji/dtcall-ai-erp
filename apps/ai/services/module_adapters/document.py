from __future__ import annotations

from datetime import datetime
from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class DocumentModuleAdapter(AIBaseModuleAdapter):
    resource = 'document'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'title', 'document_number', 'category_id', 'content'}
    allowed_fields = {
        'title',
        'document_number',
        'category_id',
        'content',
        'summary',
        'department_id',
        'status',
        'urgency',
        'security_level',
        'current_reviewer_id',
        'review_deadline',
        'publish_time',
        'effective_time',
        'expire_time',
        'attachments',
    }

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete', 'submit', 'approve', 'reject', 'publish'}:
            return {'success': False, 'message': f'暂不支持公文操作: {action.operation}'}

        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'公文创建缺少必填字段: {", ".join(missing)}'}
            invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
            if invalid:
                return {'success': False, 'message': f'公文创建包含不允许的字段: {", ".join(invalid)}'}
            return {'success': True}

        if not action.object_ids:
            return {'success': False, 'message': '公文操作缺少目标记录'}

        if action.operation in {'delete', 'submit', 'approve', 'reject', 'publish'}:
            return {'success': True}

        invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid:
            return {'success': False, 'message': f'公文更新包含不允许的字段: {", ".join(invalid)}'}
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {})
            if not normalized['success']:
                return normalized
            after_snapshot = self._build_create_snapshot(normalized['payload'], user)
            return {'success': True, 'change_set': [self._build_change_set('NEW', None, after_snapshot, 'create')]}

        document = self._get_document_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_document(document)

        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot['status'] = 'archived'
            return {
                'success': True,
                'change_set': [
                    self._build_change_set(
                        getattr(document, 'id', action.object_ids[0]),
                        before_snapshot,
                        after_snapshot,
                        'delete',
                        ['status'],
                    )
                ],
            }

        if action.operation == 'submit':
            after_snapshot = dict(before_snapshot)
            after_snapshot['status'] = 'submitted'
            return {'success': True, 'change_set': [self._build_change_set(getattr(document, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', ['status'])]}

        if action.operation == 'approve':
            after_snapshot = dict(before_snapshot)
            after_snapshot['status'] = 'approved'
            return {'success': True, 'change_set': [self._build_change_set(getattr(document, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', ['status'])]}

        if action.operation == 'reject':
            after_snapshot = dict(before_snapshot)
            after_snapshot['status'] = 'rejected'
            return {'success': True, 'change_set': [self._build_change_set(getattr(document, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', ['status'])]}

        if action.operation == 'publish':
            after_snapshot = dict(before_snapshot)
            after_snapshot['status'] = 'published'
            if not after_snapshot.get('publish_time'):
                after_snapshot['publish_time'] = 'NOW'
            return {'success': True, 'change_set': [self._build_change_set(getattr(document, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', ['status', 'publish_time'])]}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._snapshot_dict(normalized['payload']))
        return {
            'success': True,
            'change_set': [
                self._build_change_set(
                    getattr(document, 'id', action.object_ids[0]),
                    before_snapshot,
                    after_snapshot,
                    'update',
                    sorted(normalized['payload'].keys()),
                )
            ],
        }

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.system.models import Document

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {})
            payload = self._build_create_payload(normalized['payload'], user)
            document = Document.objects.create(**payload)
            return {
                'success': True,
                'message': 'created',
                'change_set': [self._build_change_set(document.id, None, self._snapshot_document(document), 'create')],
            }

        document = self._get_document_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            document.status = 'archived'
            document.save()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        if action.operation == 'submit':
            document.status = 'submitted'
            document.save()
            return {'success': True, 'message': 'submitted', 'change_set': preview['change_set']}

        if action.operation == 'approve':
            document.status = 'approved'
            document.save()
            return {'success': True, 'message': 'approved', 'change_set': preview['change_set']}

        if action.operation == 'reject':
            document.status = 'rejected'
            document.save()
            return {'success': True, 'message': 'rejected', 'change_set': preview['change_set']}

        if action.operation == 'publish':
            document.status = 'published'
            if not getattr(document, 'publish_time', None):
                document.publish_time = timezone.now()
            document.save()
            return {'success': True, 'message': 'published', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        for field, value in normalized['payload'].items():
            setattr(document, field, value)
        document.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'system.add_document',
            'update': 'system.change_document',
            'delete': 'system.delete_document',
            'submit': 'system.change_document',
            'approve': 'system.change_document_approve',
            'reject': 'system.change_document_approve',
            'publish': 'system.change_document_publish',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作公文' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'category_id', 'department_id', 'current_reviewer_id'}:
                    payload[field] = int(value) if value not in (None, '') else None
                elif field in {'review_deadline', 'publish_time', 'effective_time', 'expire_time'}:
                    payload[field] = self._parse_datetime(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError):
            return {'success': False, 'message': '公文字段格式无效，请检查分类、部门和时间信息'}
        return {'success': True, 'payload': payload}

    def _parse_datetime(self, value):
        if value in (None, ''):
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        raise ValueError('invalid datetime')

    def _build_create_payload(self, payload, user):
        return {
            'title': payload.get('title', ''),
            'document_number': payload.get('document_number', ''),
            'category_id': payload.get('category_id'),
            'content': payload.get('content', ''),
            'summary': payload.get('summary', ''),
            'author_id': getattr(user, 'id', None),
            'department_id': payload.get('department_id'),
            'status': payload.get('status', 'draft') or 'draft',
            'urgency': payload.get('urgency', 'normal') or 'normal',
            'security_level': payload.get('security_level', 'internal') or 'internal',
            'current_reviewer_id': payload.get('current_reviewer_id'),
            'review_deadline': payload.get('review_deadline'),
            'publish_time': payload.get('publish_time'),
            'effective_time': payload.get('effective_time'),
            'expire_time': payload.get('expire_time'),
            'attachments': payload.get('attachments', ''),
        }

    def _build_create_snapshot(self, payload, user):
        return self._snapshot_dict(self._build_create_payload(payload, user))

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'system',
            'model_name': 'Document',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or {}).keys()),
        }

    def _snapshot_document(self, document):
        return self._snapshot_dict({
            'id': getattr(document, 'id', None),
            'title': getattr(document, 'title', ''),
            'document_number': getattr(document, 'document_number', ''),
            'category_id': getattr(document, 'category_id', None),
            'content': getattr(document, 'content', ''),
            'summary': getattr(document, 'summary', ''),
            'author_id': getattr(document, 'author_id', None),
            'department_id': getattr(document, 'department_id', None),
            'status': getattr(document, 'status', 'draft'),
            'urgency': getattr(document, 'urgency', 'normal'),
            'security_level': getattr(document, 'security_level', 'internal'),
            'current_reviewer_id': getattr(document, 'current_reviewer_id', None),
            'review_deadline': getattr(document, 'review_deadline', None),
            'publish_time': getattr(document, 'publish_time', None),
            'effective_time': getattr(document, 'effective_time', None),
            'expire_time': getattr(document, 'expire_time', None),
            'attachments': getattr(document, 'attachments', ''),
        })

    def _snapshot_dict(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if isinstance(value, datetime):
                snapshot[field] = value.isoformat()
            else:
                snapshot[field] = value
        return snapshot

    def _get_document_for_action(self, document_id, user):
        from apps.system.models import Document

        return Document.objects.get(id=document_id)
