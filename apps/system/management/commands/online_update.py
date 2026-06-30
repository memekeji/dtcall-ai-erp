"""
Management command: perform online update.
Usage: python manage.py online_update [--target VERSION] [--no-backup]
"""
from django.core.management.base import BaseCommand
from apps.system.version_service import backup_database, perform_update, get_latest_tag


class Command(BaseCommand):
    help = 'Update the system to the latest (or specified) version'

    def add_arguments(self, parser):
        parser.add_argument(
            '--target',
            type=str,
            default=None,
            help='Target version tag to update to (default: latest)',
        )
        parser.add_argument(
            '--no-backup',
            action='store_true',
            default=False,
            help='Skip database backup before update',
        )

    def handle(self, **options):
        target = options['target'] or get_latest_tag()
        if not target:
            self.stderr.write(self.style.ERROR('No target version available. Run check_update first.'))
            return

        # Step 1: Backup
        if not options['no_backup']:
            self.stdout.write('Step 1/3: Backing up database...')
            result = backup_database()
            if result['success']:
                self.stdout.write(self.style.SUCCESS(f"Backup created: {result['file']}"))
            else:
                self.stderr.write(self.style.ERROR(f"Backup failed: {result['error']}"))
                self.stderr.write('Use --no-backup to skip backup step.')
                return

        # Step 2: Update
        self.stdout.write(f'Step 2/3: Updating to {target}...')
        result = perform_update(target_version=target)

        if result['success']:
            self.stdout.write(self.style.SUCCESS(
                f"Update successful: {result['previous_version']} -> {result['new_version']}"
            ))
            self.stdout.write(f"  Commit: {result['new_commit']}")
        else:
            self.stderr.write(self.style.ERROR(f"Update failed: {result.get('error', 'Unknown error')}"))
            if result.get('stage'):
                self.stderr.write(f"  Failed at stage: {result['stage']}")
