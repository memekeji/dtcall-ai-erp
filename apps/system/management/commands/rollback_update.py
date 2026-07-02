"""
Management command: rollback the last update.
Usage: python manage.py rollback_update
"""
from django.core.management.base import BaseCommand
from apps.system.version_service import get_rollback_info, perform_rollback


class Command(BaseCommand):
    help = 'Rollback to the previous version before the last update'

    def handle(self, **options):
        rb = get_rollback_info()
        if not rb:
            self.stderr.write(self.style.ERROR('No rollback state found. Nothing to rollback.'))
            return

        previous_commit = rb.get('previous_commit') or 'unknown'
        self.stdout.write(f"Rolling back from version {rb.get('target_version', 'unknown')} "
                          f"to {rb['previous_version']} ({previous_commit})")
        self.stdout.write('Confirm? [y/N] ', ending='')
        answer = input().strip().lower()
        if answer != 'y':
            self.stdout.write('Rollback cancelled.')
            return

        result = perform_rollback()
        if result['success']:
            restored_commit = result.get('restored_commit') or 'unknown'
            self.stdout.write(self.style.SUCCESS(
                f"Rollback successful. Restored to {result['restored_version']} ({restored_commit})"
            ))
        else:
            self.stderr.write(self.style.ERROR(f"Rollback failed: {result.get('error', 'Unknown error')}"))
