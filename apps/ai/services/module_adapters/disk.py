from __future__ import annotations

import hashlib
import os
import shutil

from django.conf import settings
from django.utils import timezone

from apps.disk.models import DiskFile, DiskFolder, DiskShare
from apps.ai.services.permission_guard import AIPermissionGuard
from apps.ai.services.module_adapters.base import AIBaseModuleAdapter


class DiskModuleAdapter(AIBaseModuleAdapter):
    resource = 'disk'
    permission_guard = AIPermissionGuard()
    SHARE_ALLOWED_FIELDS = {
        'permission_type',
        'allow_download',
        'allow_preview',
        'allow_copy',
        'allow_screenshot',
        'access_limit',
        'download_limit',
        'is_active',
        'expire_time',
        'password',
    }
    PERMISSION_ALLOWED_FIELDS = {
        'is_public',
        'permission_level',
        'shared_users',
        'shared_departments',
        'shared_user_ids',
        'shared_department_ids',
        'add_shared_user_ids',
        'remove_shared_user_ids',
        'add_shared_department_ids',
        'remove_shared_department_ids',
    }

    def validate(self, action):
        model = self._resolve_model_name(action)
        if model not in {'file', 'folder', 'share', 'permission'}:
            return {
                'success': False,
                'message': '网盘操作缺少目标模型标识',
            }

        if action.operation == 'update' and model == 'file':
            invalid_fields = sorted(set(action.changes.keys()) - {'name', 'folder_id'})
            if invalid_fields:
                return {
                    'success': False,
                    'message': f'网盘文件更新包含不允许的字段: {", ".join(invalid_fields)}',
                }
        if action.operation == 'update' and model == 'folder':
            invalid_fields = sorted(set(action.changes.keys()) - {'name', 'parent_id'})
            if invalid_fields:
                return {
                    'success': False,
                    'message': f'网盘文件夹更新包含不允许的字段: {", ".join(invalid_fields)}',
                }
        if model == 'share':
            invalid_fields = sorted(set(action.changes.keys()) - self.SHARE_ALLOWED_FIELDS)
            if invalid_fields:
                return {
                    'success': False,
                    'message': f'网盘分享更新包含不允许的字段: {", ".join(invalid_fields)}',
                }
            if self._resolve_share_type(action) not in {'file', 'folder'}:
                return {
                    'success': False,
                    'message': '网盘分享缺少有效的分享类型',
                }
        if model == 'permission':
            invalid_fields = sorted(set(action.changes.keys()) - self.PERMISSION_ALLOWED_FIELDS)
            if invalid_fields:
                return {
                    'success': False,
                    'message': f'网盘权限更新包含不允许的字段: {", ".join(invalid_fields)}',
                }
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        model = self._resolve_model_name(action)
        if model == 'share':
            if action.operation == 'create':
                item = self._get_share_item_for_action(action, user)
                return self._build_preview_for_share_create(action, item, user)
            share = self._get_share_for_action(action, user)
            return self._build_preview_for_share(action, share)
        if model == 'permission':
            target = self._get_permission_target_for_action(action, user)
            return self._build_preview_for_permission(action, target)
        if model == 'file':
            file_obj = self._get_file_for_action(
                action.object_ids[0],
                user,
                deleted=action.operation == 'restore',
            )
            return self._build_preview_for_file(action, file_obj)

        folder = self._get_folder_for_action(
            action.object_ids[0],
            user,
            deleted=action.operation == 'restore',
        )
        return self._build_preview_for_folder(action, folder)

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        model = self._resolve_model_name(action)
        if model == 'share':
            return self._execute_share(action, user, preview)
        if model == 'permission':
            return self._execute_permission(action, user, preview)
        if model == 'file':
            file_obj = self._get_file_for_action(
                action.object_ids[0],
                user,
                deleted=action.operation == 'restore',
            )
            return self._execute_file(action, file_obj, preview)

        folder = self._get_folder_for_action(
            action.object_ids[0],
            user,
            deleted=action.operation == 'restore',
        )
        return self._execute_folder(action, folder, preview)

    def _build_preview_for_share(self, action, share):
        before_snapshot = self._snapshot_instance(share, fields=self._share_snapshot_fields())
        after_snapshot = dict(before_snapshot)
        if action.operation == 'delete':
            after_snapshot['delete_time'] = 'NOW'
            change_type = 'delete'
            changed_fields = ['delete_time']
        elif action.operation == 'restore':
            after_snapshot['is_active'] = True
            change_type = 'update'
            changed_fields = ['is_active']
        else:
            normalized_changes = self._normalize_share_changes(action.changes)
            after_snapshot.update(normalized_changes)
            change_type = 'update'
            changed_fields = sorted(normalized_changes.keys())
        return {
            'success': True,
            'change_set': [
                {
                    'app_label': 'disk',
                    'model_name': 'DiskShare',
                    'object_pk': str(getattr(share, 'id', action.object_ids[0])),
                    'change_type': change_type,
                    'before_snapshot': before_snapshot,
                    'after_snapshot': after_snapshot,
                    'changed_fields': changed_fields,
                }
            ],
        }

    def _build_preview_for_share_create(self, action, item, user):
        share_type = self._resolve_share_type(action)
        after_snapshot = {
            'share_type': share_type,
            'creator_id': getattr(user, 'id', None),
            'share_code': 'NEW',
            'password': action.changes.get('password', ''),
            'permission_type': action.changes.get('permission_type', 'download'),
            'allow_download': action.changes.get('allow_download', True),
            'allow_preview': action.changes.get('allow_preview', True),
            'allow_copy': action.changes.get('allow_copy', True),
            'allow_screenshot': action.changes.get('allow_screenshot', True),
            'access_limit': action.changes.get('access_limit', 0),
            'download_limit': action.changes.get('download_limit', 0),
            'is_active': action.changes.get('is_active', True),
            'expire_time': action.changes.get('expire_time'),
        }
        if share_type == 'file':
            after_snapshot['file_id'] = getattr(item, 'id', action.object_ids[0])
            after_snapshot['folder_id'] = None
        else:
            after_snapshot['folder_id'] = getattr(item, 'id', action.object_ids[0])
            after_snapshot['file_id'] = None
        return {
            'success': True,
            'change_set': [
                {
                    'app_label': 'disk',
                    'model_name': 'DiskShare',
                    'object_pk': f'new-{self._resolve_share_type(action)}-{getattr(item, "id", action.object_ids[0])}',
                    'change_type': 'create',
                    'before_snapshot': None,
                    'after_snapshot': after_snapshot,
                    'changed_fields': sorted(k for k in after_snapshot.keys() if k not in {'share_code'}),
                }
            ],
        }

    def _build_preview_for_permission(self, action, target):
        before_snapshot = self._permission_snapshot(target)
        after_snapshot = self._apply_permission_preview(before_snapshot, action.changes)
        changed_fields = sorted(set(action.changes.keys()) | self._permission_relation_change_fields(action.changes))
        return {
            'success': True,
            'change_set': [
                {
                    'app_label': 'disk',
                    'model_name': 'DiskPermission',
                    'object_pk': str(getattr(target, 'id', action.object_ids[0])),
                    'change_type': 'update',
                    'before_snapshot': before_snapshot,
                    'after_snapshot': after_snapshot,
                    'changed_fields': changed_fields,
                    'rollback_metadata': {
                        'relation_snapshots': {
                            'shared_users': before_snapshot.get('shared_user_ids', []),
                            'shared_departments': before_snapshot.get('shared_department_ids', []),
                        }
                    },
                }
            ],
        }

    def _build_preview_for_file(self, action, file_obj):
        before_snapshot = self._snapshot_instance(file_obj, fields=[
            'name',
            'file_path',
            'folder_id',
            'delete_time',
            'is_public',
            'is_starred',
        ])
        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot['delete_time'] = 'NOW'
            change_type = 'delete'
            changed_fields = ['delete_time']
        elif action.operation == 'restore':
            after_snapshot = dict(before_snapshot)
            after_snapshot['delete_time'] = None
            change_type = 'update'
            changed_fields = ['delete_time']
        else:
            after_snapshot = dict(before_snapshot)
            after_snapshot.update(action.changes)
            change_type = 'update'
            changed_fields = sorted(action.changes.keys())
        return {
            'success': True,
            'change_set': [
                {
                    'app_label': 'disk',
                    'model_name': 'DiskFile',
                    'object_pk': str(getattr(file_obj, 'id', action.object_ids[0])),
                    'change_type': change_type,
                    'before_snapshot': before_snapshot,
                    'after_snapshot': after_snapshot,
                    'changed_fields': changed_fields,
                }
            ],
        }

    def _build_preview_for_folder(self, action, folder):
        before_snapshot = self._snapshot_instance(folder, fields=[
            'name',
            'parent_id',
            'delete_time',
            'is_public',
            'permission_level',
        ])
        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot['delete_time'] = 'NOW'
            change_type = 'delete'
            changed_fields = ['delete_time']
        elif action.operation == 'restore':
            after_snapshot = dict(before_snapshot)
            after_snapshot['delete_time'] = None
            change_type = 'update'
            changed_fields = ['delete_time']
        else:
            after_snapshot = dict(before_snapshot)
            after_snapshot.update(action.changes)
            change_type = 'update'
            changed_fields = sorted(action.changes.keys())
        return {
            'success': True,
            'change_set': [
                {
                    'app_label': 'disk',
                    'model_name': 'DiskFolder',
                    'object_pk': str(getattr(folder, 'id', action.object_ids[0])),
                    'change_type': change_type,
                    'before_snapshot': before_snapshot,
                    'after_snapshot': after_snapshot,
                    'changed_fields': changed_fields,
                }
            ],
        }

    def _execute_file(self, action, file_obj, preview):
        if action.operation == 'delete':
            if action.changes.get('permanent'):
                backup_path = self._backup_deleted_file(file_obj)
                if hasattr(file_obj, 'delete'):
                    file_obj.delete()
                change_set = self._attach_rollback_metadata(
                    preview['change_set'],
                    {'permanent': True, 'backup_file_path': backup_path},
                )
                return {'success': True, 'message': 'deleted', 'change_set': change_set}

            if hasattr(file_obj, 'delete_time'):
                file_obj.delete_time = timezone.now()
            if hasattr(file_obj, 'save'):
                file_obj.save(
                    update_fields=['delete_time', 'update_time']
                    if self._supports_update_time(file_obj)
                    else None
                )
            change_set = self._attach_rollback_metadata(
                preview['change_set'],
                {'permanent': False},
            )
            return {'success': True, 'message': 'deleted', 'change_set': change_set}

        if action.operation == 'restore':
            file_obj.delete_time = None
            if hasattr(file_obj, 'save'):
                file_obj.save(
                    update_fields=['delete_time', 'update_time']
                    if self._supports_update_time(file_obj)
                    else None
                )
            return {'success': True, 'message': 'restored', 'change_set': preview['change_set']}

        for field, value in action.changes.items():
            if field == 'folder_id':
                setattr(file_obj, 'folder_id', value)
            else:
                setattr(file_obj, field, value)
        if hasattr(file_obj, 'save'):
            file_obj.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _execute_folder(self, action, folder, preview):
        if action.operation == 'delete':
            if action.changes.get('permanent'):
                backup_path = self._backup_deleted_folder(folder)
                if hasattr(folder, 'delete'):
                    folder.delete()
                change_set = self._attach_rollback_metadata(
                    preview['change_set'],
                    {'permanent': True, 'backup_folder_path': backup_path},
                )
                return {'success': True, 'message': 'deleted', 'change_set': change_set}

            folder.delete_time = timezone.now()
            if hasattr(folder, 'save'):
                folder.save(
                    update_fields=['delete_time', 'update_time']
                    if self._supports_update_time(folder)
                    else None
                )
            change_set = self._attach_rollback_metadata(
                preview['change_set'],
                {'permanent': False},
            )
            return {'success': True, 'message': 'deleted', 'change_set': change_set}

        if action.operation == 'restore':
            folder.delete_time = None
            if hasattr(folder, 'save'):
                folder.save(
                    update_fields=['delete_time', 'update_time']
                    if self._supports_update_time(folder)
                    else None
                )
            return {'success': True, 'message': 'restored', 'change_set': preview['change_set']}

        for field, value in action.changes.items():
            if field == 'parent_id':
                setattr(folder, 'parent_id', value)
            else:
                setattr(folder, field, value)
        if hasattr(folder, 'save'):
            folder.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _execute_share(self, action, user, preview):
        share_type = self._resolve_share_type(action)
        if action.operation == 'create':
            share = self._create_share(action, user, share_type)
            change_set = self._build_share_change_set(share, action, 'create')
            return {'success': True, 'message': 'created', 'change_set': [change_set]}

        share = self._get_share_for_action(action, user)
        if action.operation == 'delete':
            change_set = self._build_share_change_set(share, action, 'delete')
            if hasattr(share, 'delete'):
                share.delete()
            return {'success': True, 'message': 'deleted', 'change_set': [change_set]}

        if action.operation == 'restore':
            share.is_active = True
            if hasattr(share, 'save'):
                share.save(update_fields=['is_active', 'update_time'] if self._supports_update_time(share) else ['is_active'])
            return {'success': True, 'message': 'restored', 'change_set': preview['change_set']}

        self._apply_share_updates(share, action.changes)
        if hasattr(share, 'save'):
            share.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _execute_permission(self, action, user, preview):
        target = self._get_permission_target_for_action(action, user)
        before_snapshot = self._permission_snapshot(target)
        relation_snapshot = {
            'shared_users': before_snapshot.get('shared_user_ids', []),
            'shared_departments': before_snapshot.get('shared_department_ids', []),
        }
        self._apply_permission_updates(target, action.changes)
        if hasattr(target, 'save'):
            target.save()
        change_set = self._build_permission_change_set(target, before_snapshot, action, relation_snapshot)
        return {'success': True, 'message': 'updated', 'change_set': [change_set]}

    def _check_permission(self, action, user):
        model = self._resolve_model_name(action)
        permission_target = self._resolve_permission_target_type(action)
        permission_map = {
            ('file', 'update'): 'disk.change_disk_file',
            ('file', 'delete'): 'disk.delete_disk_file',
            ('file', 'restore'): 'disk.change_disk_file',
            ('file', 'create'): 'disk.add_disk_file',
            ('folder', 'update'): 'disk.change_disk_folder',
            ('folder', 'delete'): 'disk.delete_disk_folder',
            ('folder', 'restore'): 'disk.change_disk_folder',
            ('folder', 'create'): 'disk.add_disk_folder',
            ('share', 'create'): 'disk.add_share',
            ('share', 'update'): 'disk.change_share',
            ('share', 'delete'): 'disk.delete_share',
            ('share', 'restore'): 'disk.change_share',
            ('permission', 'update'): f'disk.change_disk_{permission_target}',
        }
        permission_code = permission_map.get((model, action.operation))
        if not permission_code:
            return {'allowed': False, 'message': '未配置网盘操作权限'}
        result = self.permission_guard.check_action_permission(user, action, permission_code)
        return {'allowed': result.allowed, 'message': '权限不足' if not result.allowed else 'allowed'}

    def _resolve_model_name(self, action):
        context = action.context or {}
        model = context.get('model') or context.get('model_name')
        if model:
            return str(model).lower()
        return 'file'

    def _resolve_share_type(self, action):
        context = action.context or {}
        share_type = context.get('share_type') or action.changes.get('share_type')
        if share_type in {'file', 'folder'}:
            return share_type
        return 'file'

    def _resolve_permission_target_type(self, action):
        context = action.context or {}
        item_type = context.get('item_type') or context.get('target_type') or context.get('share_type')
        if item_type in {'file', 'folder'}:
            return item_type
        return 'folder'

    def _share_snapshot_fields(self):
        return [
            'id',
            'share_type',
            'file_id',
            'folder_id',
            'share_code',
            'password',
            'creator_id',
            'expire_time',
            'permission_type',
            'allow_download',
            'allow_preview',
            'allow_copy',
            'allow_screenshot',
            'access_limit',
            'access_count',
            'download_limit',
            'download_count',
            'copy_count',
            'copy_blocked_count',
            'screenshot_count',
            'screenshot_blocked_count',
            'visitor_ips',
            'is_active',
            'create_time',
            'update_time',
        ]

    def _normalize_share_changes(self, changes):
        normalized = dict(changes)
        normalized.pop('share_type', None)
        return normalized

    def _permission_snapshot(self, target):
        snapshot = self._snapshot_instance(target, fields=[
            'id',
            'name',
            'is_public',
            'permission_level',
        ])
        snapshot['shared_user_ids'] = self._get_relation_ids(target, 'shared_users')
        snapshot['shared_department_ids'] = self._get_relation_ids(target, 'shared_departments')
        return snapshot

    def _apply_permission_preview(self, before_snapshot, changes):
        after_snapshot = dict(before_snapshot)
        after_snapshot.update({k: v for k, v in changes.items() if k in {'is_public', 'permission_level'}})
        user_ids = list(before_snapshot.get('shared_user_ids', []))
        dept_ids = list(before_snapshot.get('shared_department_ids', []))
        if 'shared_user_ids' in changes:
            user_ids = list(dict.fromkeys(changes.get('shared_user_ids') or []))
        if 'shared_department_ids' in changes:
            dept_ids = list(dict.fromkeys(changes.get('shared_department_ids') or []))
        if 'shared_users' in changes:
            user_ids = list(dict.fromkeys(changes.get('shared_users') or []))
        if 'shared_departments' in changes:
            dept_ids = list(dict.fromkeys(changes.get('shared_departments') or []))
        for user_id in changes.get('add_shared_user_ids', []) or []:
            if user_id not in user_ids:
                user_ids.append(user_id)
        for user_id in changes.get('remove_shared_user_ids', []) or []:
            if user_id in user_ids:
                user_ids.remove(user_id)
        for dept_id in changes.get('add_shared_department_ids', []) or []:
            if dept_id not in dept_ids:
                dept_ids.append(dept_id)
        for dept_id in changes.get('remove_shared_department_ids', []) or []:
            if dept_id in dept_ids:
                dept_ids.remove(dept_id)
        after_snapshot['shared_user_ids'] = sorted(user_ids)
        after_snapshot['shared_department_ids'] = sorted(dept_ids)
        return after_snapshot

    def _permission_relation_change_fields(self, changes):
        fields = set()
        if any(key in changes for key in ('shared_users', 'shared_user_ids', 'add_shared_user_ids', 'remove_shared_user_ids')):
            fields.add('shared_users')
        if any(key in changes for key in ('shared_departments', 'shared_department_ids', 'add_shared_department_ids', 'remove_shared_department_ids')):
            fields.add('shared_departments')
        return fields

    def _build_permission_change_set(self, target, before_snapshot, action, relation_snapshot):
        after_snapshot = self._permission_snapshot(target)
        return {
            'app_label': 'disk',
            'model_name': 'DiskPermission',
            'object_pk': str(getattr(target, 'id', action.object_ids[0])),
            'change_type': 'update',
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': sorted(set(action.changes.keys()) | self._permission_relation_change_fields(action.changes)),
            'rollback_metadata': {
                'relation_snapshots': relation_snapshot,
            },
        }

    def _create_share(self, action, user, share_type):
        from apps.disk.models import DiskShare

        item = self._get_share_item_for_action(action, user)
        share = DiskShare(
            share_type=share_type,
            share_code=self._generate_share_code(),
            creator=user,
        )
        if share_type == 'file':
            share.file = item
        else:
            share.folder = item
        self._apply_share_updates(share, action.changes, creating=True)
        if not getattr(share, 'password', '') and action.changes.get('password'):
            share.password = hashlib.sha256(str(action.changes.get('password')).encode()).hexdigest()
        if hasattr(share, 'save'):
            share.save()
        return share

    def _apply_share_updates(self, share, changes, creating=False):
        normalized = self._normalize_share_changes(changes)
        password = normalized.pop('password', None) if 'password' in normalized else None
        for field, value in normalized.items():
            if hasattr(share, field):
                setattr(share, field, value)
        if password is not None:
            setattr(share, 'password', hashlib.sha256(str(password).encode()).hexdigest() if password else '')

    def _build_share_change_set(self, share, action, change_type):
        before_snapshot = getattr(share, '_ai_before_snapshot', None)
        if before_snapshot is None and change_type != 'create':
            before_snapshot = self._snapshot_instance(share, fields=self._share_snapshot_fields())
        after_snapshot = dict(before_snapshot) if before_snapshot is not None else {}
        if change_type == 'delete':
            after_snapshot['deleted'] = True
            changed_fields = ['id']
        elif change_type == 'create':
            after_snapshot = self._snapshot_instance(share, fields=self._share_snapshot_fields())
            changed_fields = sorted(after_snapshot.keys())
        else:
            normalized_changes = self._normalize_share_changes(action.changes)
            after_snapshot.update(normalized_changes)
            changed_fields = sorted(normalized_changes.keys())
        return {
            'app_label': 'disk',
            'model_name': 'DiskShare',
            'object_pk': str(getattr(share, 'id', action.object_ids[0])),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields,
        }

    def _build_share_create_change_set(self, share, action):
        after_snapshot = self._snapshot_instance(share, fields=self._share_snapshot_fields())
        return {
            'app_label': 'disk',
            'model_name': 'DiskShare',
            'object_pk': str(getattr(share, 'id', action.object_ids[0])),
            'change_type': 'create',
            'before_snapshot': None,
            'after_snapshot': after_snapshot,
            'changed_fields': sorted(after_snapshot.keys()),
        }

    def _build_permission_change_set(self, target, before_snapshot, action, relation_snapshot):
        after_snapshot = self._permission_snapshot(target)
        return {
            'app_label': 'disk',
            'model_name': 'DiskPermission',
            'object_pk': str(getattr(target, 'id', action.object_ids[0])),
            'change_type': 'update',
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': sorted(set(action.changes.keys()) | self._permission_relation_change_fields(action.changes)),
            'rollback_metadata': {
                'relation_snapshots': relation_snapshot,
            },
        }

    def _apply_permission_updates(self, target, changes):
        if 'is_public' in changes:
            setattr(target, 'is_public', bool(changes.get('is_public')))
        if 'permission_level' in changes and hasattr(target, 'permission_level'):
            setattr(target, 'permission_level', changes.get('permission_level'))
        self._sync_many_to_many(target, 'shared_users', changes, 'shared_user_ids', 'add_shared_user_ids', 'remove_shared_user_ids')
        self._sync_many_to_many(target, 'shared_departments', changes, 'shared_department_ids', 'add_shared_department_ids', 'remove_shared_department_ids')

    def _sync_many_to_many(self, target, field_name, changes, replace_key, add_key, remove_key):
        manager = getattr(target, field_name, None)
        if manager is None:
            return
        if replace_key in changes:
            self._set_relation_by_ids(manager, list(changes.get(replace_key) or []))
            return
        if field_name == 'shared_users' and 'shared_users' in changes:
            self._set_relation_by_ids(manager, list(changes.get('shared_users') or []))
        if field_name == 'shared_departments' and 'shared_departments' in changes:
            self._set_relation_by_ids(manager, list(changes.get('shared_departments') or []))
        for object_id in list(changes.get(add_key) or []):
            self._add_relation_by_id(manager, object_id)
        for object_id in list(changes.get(remove_key) or []):
            self._remove_relation_by_id(manager, object_id)

    def _set_relation_by_ids(self, manager, ids):
        if hasattr(manager, 'set'):
            manager.set(self._resolve_related_objects(manager, ids))

    def _add_relation_by_id(self, manager, object_id):
        if hasattr(manager, 'add'):
            manager.add(*self._resolve_related_objects(manager, [object_id]))

    def _remove_relation_by_id(self, manager, object_id):
        if hasattr(manager, 'remove'):
            manager.remove(*self._resolve_related_objects(manager, [object_id]))

    def _resolve_related_objects(self, manager, ids):
        model = getattr(manager, 'model', None)
        if model is None:
            return ids
        return list(model.objects.filter(id__in=list(ids)))

    def _supports_update_time(self, instance):
        return hasattr(instance, 'update_time')

    def _snapshot_instance(self, instance, fields=None):
        if fields is None:
            fields = [key for key in vars(instance).keys() if not key.startswith('_') and not callable(getattr(instance, key))]
        snapshot = {}
        for field in fields:
            snapshot[field] = getattr(instance, field, None)
        return snapshot

    def _get_file_for_action(self, file_id, user, deleted=False):
        from apps.disk.models import DiskFile

        lookup = {'id': file_id, 'owner': user}
        lookup['delete_time__isnull'] = not deleted
        return DiskFile.objects.get(**lookup)

    def _get_folder_for_action(self, folder_id, user, deleted=False):
        from apps.disk.models import DiskFolder

        lookup = {'id': folder_id, 'owner': user}
        lookup['delete_time__isnull'] = not deleted
        return DiskFolder.objects.get(**lookup)

    def _get_share_item_for_action(self, action, user, deleted=False):
        share_type = self._resolve_share_type(action)
        item_id = action.object_ids[0]
        if share_type == 'folder':
            return self._get_folder_for_action(item_id, user, deleted=deleted)
        return self._get_file_for_action(item_id, user, deleted=deleted)

    def _get_share_for_action(self, action, user):
        from apps.disk.models import DiskShare

        return DiskShare.objects.get(id=action.object_ids[0], creator=user)

    def _get_permission_target_for_action(self, action, user, deleted=False):
        model = self._resolve_model_name(action)
        if model == 'permission':
            context = action.context or {}
            item_type = context.get('item_type') or context.get('model') or 'folder'
        else:
            item_type = 'folder'
        item_id = action.object_ids[0]
        if item_type == 'file':
            return self._get_file_for_action(item_id, user, deleted=deleted)
        return self._get_folder_for_action(item_id, user, deleted=deleted)

    def _get_relation_ids(self, instance, field_name):
        manager = getattr(instance, field_name, None)
        if manager is None:
            return []
        if hasattr(manager, 'values_list'):
            try:
                return list(manager.values_list('id', flat=True))
            except Exception:
                pass
        if hasattr(manager, 'all'):
            try:
                return [getattr(item, 'id', item) for item in manager.all()]
            except Exception:
                pass
        if callable(manager):
            try:
                return [getattr(item, 'id', item) for item in manager()]
            except Exception:
                pass
        return []

    def _generate_share_code(self):
        from apps.disk.models import DiskShare

        while True:
            code = hashlib.md5(os.urandom(16)).hexdigest()[:8].upper()
            if not DiskShare.objects.filter(share_code=code).exists():
                return code

    def _attach_rollback_metadata(self, change_sets, metadata):
        enriched = []
        for item in change_sets:
            merged = dict(item)
            rollback_metadata = dict(merged.get('rollback_metadata') or {})
            rollback_metadata.update(metadata)
            merged['rollback_metadata'] = rollback_metadata
            enriched.append(merged)
        return enriched

    def _backup_deleted_file(self, file_obj):
        source_path = os.path.join(settings.MEDIA_ROOT, file_obj.file_path)
        backup_dir = os.path.join(settings.MEDIA_ROOT, 'ai_backups', 'disk', 'file', str(getattr(file_obj, 'id', '0')))
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, os.path.basename(file_obj.file_path))
        if os.path.exists(source_path):
            shutil.copy2(source_path, backup_path)
            os.remove(source_path)
        return backup_path

    def _backup_deleted_folder(self, folder):
        backup_dir = os.path.join(settings.MEDIA_ROOT, 'ai_backups', 'disk', 'folder', str(getattr(folder, 'id', '0')))
        os.makedirs(backup_dir, exist_ok=True)
        return backup_dir
