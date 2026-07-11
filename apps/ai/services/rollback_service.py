from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Any

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.ai.models import AIOperation, AIOperationChangeSet, AIOperationRollback


def inverse_change_type(change_type: str) -> str:
    mapping = {
        'create': 'delete',
        'update': 'restore',
        'delete': 'recreate',
    }
    return mapping.get(change_type, 'restore')


@dataclass(slots=True)
class RollbackStep:
    sequence: int
    app_label: str
    model_name: str
    object_pk: str
    forward_change_type: str
    rollback_change_type: str
    before_snapshot: dict[str, Any] | None
    after_snapshot: dict[str, Any] | None


def build_rollback_plan(change_sets):
    return sorted(change_sets, key=lambda item: getattr(item, 'sequence', 0), reverse=True)


class AIOperationRollbackService:
    def rollback_operation(self, operation_id, user):
        operation = AIOperation.objects.get(id=operation_id, user=user)
        rollback_record = AIOperationRollback.objects.create(
            operation=operation,
            requested_by=user,
            status='pending',
        )

        try:
            with transaction.atomic():
                plan = build_rollback_plan(self._get_change_sets(operation))
                result_items = []
                for change_set in plan:
                    result_items.append(self._apply_change_set(change_set))

                operation.status = 'rolled_back'
                operation.rollback_status = 'completed'
                operation.rolled_back_at = timezone.now()
                operation.save(update_fields=['status', 'rollback_status', 'rolled_back_at', 'updated_at'])

                rollback_record.status = 'completed'
                rollback_record.result_summary = {'items': result_items}
                rollback_record.completed_at = timezone.now()
                rollback_record.save(update_fields=['status', 'result_summary', 'completed_at'])

            return {'success': True, 'operation_id': operation.id, 'rollback_record_id': rollback_record.id}
        except Exception as exc:
            rollback_record.status = 'failed'
            rollback_record.error_message = str(exc)
            rollback_record.completed_at = timezone.now()
            rollback_record.save(update_fields=['status', 'error_message', 'completed_at'])
            return {'success': False, 'message': str(exc), 'operation_id': operation.id}

    def _get_change_sets(self, operation):
        change_sets = getattr(operation, 'change_sets', None)
        if change_sets is not None and hasattr(change_sets, 'all'):
            return list(change_sets.all())
        return list(AIOperationChangeSet.objects.filter(operation=operation).order_by('sequence'))

    def _apply_change_set(self, change_set):
        model = apps.get_model(change_set.app_label, change_set.model_name)
        if not model:
            raise LookupError(f'Model not found: {change_set.app_label}.{change_set.model_name}')

        if change_set.app_label == 'disk' and change_set.change_type == 'delete':
            return self._restore_deleted_disk_object(model, change_set)

        if change_set.change_type == 'update':
            obj = model.objects.get(pk=change_set.object_pk)
            for field, value in (change_set.before_snapshot or {}).items():
                setattr(obj, field, value)
            obj.save()
            return {'object_pk': change_set.object_pk, 'rolled_back': 'update'}

        if change_set.change_type == 'create':
            obj = model.objects.get(pk=change_set.object_pk)
            if hasattr(obj, 'hard_delete'):
                obj.hard_delete()
            elif hasattr(obj, 'delete'):
                obj.delete()
            else:
                raise AttributeError(f'Object {change_set.object_pk} does not support delete()')
            return {'object_pk': change_set.object_pk, 'rolled_back': 'create'}

        if change_set.change_type == 'delete':
            try:
                obj = model.objects.get(pk=change_set.object_pk)
            except Exception:
                obj = self._recreate_deleted_object(model, change_set)
            else:
                for field, value in (change_set.before_snapshot or {}).items():
                    setattr(obj, field, value)
                if hasattr(obj, 'save'):
                    obj.save()
                return {'object_pk': change_set.object_pk, 'rolled_back': 'delete'}

            return {'object_pk': change_set.object_pk, 'rolled_back': 'delete'}

        raise NotImplementedError(f'Rollback for {change_set.change_type} is not implemented yet')

    def _restore_deleted_disk_object(self, model, change_set):
        metadata = change_set.rollback_metadata or {}
        model_name = str(getattr(change_set, 'model_name', '') or getattr(model, '__name__', ''))
        if metadata.get('permanent'):
            backup_path = metadata.get('backup_file_path') or metadata.get('backup_folder_path')
            if backup_path and os.path.exists(backup_path):
                target_path = self._restore_disk_backup_path(change_set, metadata)
                if target_path and os.path.isfile(backup_path):
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copy2(backup_path, target_path)
            if model_name == 'DiskFolder' and metadata.get('tree_snapshot'):
                self._restore_disk_folder_tree(metadata['tree_snapshot'])
        return self._recreate_deleted_object(model, change_set)

    def _restore_disk_backup_path(self, change_set, metadata):
        before_snapshot = change_set.before_snapshot or {}
        file_path = before_snapshot.get('file_path')
        if file_path:
            return os.path.join(settings.MEDIA_ROOT, file_path)

        object_pk = change_set.object_pk
        if metadata.get('backup_file_path') and object_pk:
            filename = os.path.basename(metadata['backup_file_path'])
            return os.path.join(settings.MEDIA_ROOT, 'disk', str(object_pk), filename)
        return None

    def _restore_disk_folder_tree(self, tree_snapshot):
        folder_snapshot = tree_snapshot.get('folder') or {}
        folder_model = apps.get_model('disk', folder_snapshot.get('model_name', 'DiskFolder'))
        folder = self._create_or_restore_disk_object(folder_model, folder_snapshot)

        for file_snapshot in tree_snapshot.get('files', []):
            file_model = apps.get_model('disk', file_snapshot.get('model_name', 'DiskFile'))
            self._create_or_restore_disk_object(file_model, file_snapshot)
            backup_path = file_snapshot.get('backup_file_path')
            file_path = file_snapshot.get('file_path')
            if backup_path and file_path and os.path.exists(backup_path):
                target_path = os.path.join(settings.MEDIA_ROOT, file_path)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(backup_path, target_path)

        for child_snapshot in tree_snapshot.get('children', []):
            self._restore_disk_folder_tree(child_snapshot)

        return folder

    def _create_or_restore_disk_object(self, model, snapshot):
        object_pk = snapshot.get('id') or snapshot.get('pk')
        lookup = {'pk': object_pk} if object_pk is not None else {}
        try:
            obj = model.objects.get(**lookup) if lookup else None
        except Exception:
            obj = None

        if obj is None:
            create_kwargs = dict(snapshot)
            create_kwargs.pop('model_name', None)
            create_kwargs.pop('backup_file_path', None)
            create_kwargs.pop('delete_time', None)
            create_kwargs.pop('file_path', None)
            if 'folder_id' in create_kwargs and 'folder' not in create_kwargs:
                create_kwargs['folder_id'] = create_kwargs['folder_id']
            if hasattr(model.objects, 'create'):
                created = model.objects.create(**create_kwargs)
                self._restore_disk_object_file_payload(created, snapshot)
                return created
            raise AttributeError(f'Model {model.__name__} does not support recreation')

        for field, value in snapshot.items():
            if field in {'model_name', 'backup_file_path'}:
                continue
            setattr(obj, field, value)
        if hasattr(obj, 'save'):
            obj.save()
        self._restore_disk_object_file_payload(obj, snapshot)
        return obj

    def _restore_disk_object_file_payload(self, obj, snapshot):
        file_path = snapshot.get('file_path')
        backup_path = snapshot.get('backup_file_path')
        if not file_path or not backup_path or not os.path.exists(backup_path):
            return
        target_path = os.path.join(settings.MEDIA_ROOT, file_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.copy2(backup_path, target_path)

    def _recreate_deleted_object(self, model, change_set):
        snapshot = dict(change_set.before_snapshot or {})
        object_pk = change_set.object_pk
        if object_pk and object_pk.isdigit():
            snapshot.setdefault('id', int(object_pk))
        elif 'pk' in snapshot and 'id' not in snapshot:
            snapshot['id'] = snapshot['pk']
        snapshot.pop('pk', None)
        create_kwargs = dict(snapshot)
        if hasattr(model.objects, 'create'):
            try:
                return model.objects.create(**create_kwargs)
            except Exception:
                create_kwargs.pop('id', None)
                return model.objects.create(**create_kwargs)
        raise AttributeError(f'Model {getattr(model, "__name__", "unknown")} does not support recreation')


rollback_service = AIOperationRollbackService()
