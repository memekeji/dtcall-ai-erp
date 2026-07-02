from django.core.management.base import BaseCommand
from apps.system.version_service import perform_update, check_for_updates


class Command(BaseCommand):
    help = 'Update the system from the official update center'

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
            help='Deprecated; backup is handled inside updater flow',
        )

    def handle(self, **options):
        info = check_for_updates()
        target = options['target'] or info.get('latest_version')
        if not target:
            self.stderr.write(self.style.ERROR('No target version available from the official update center.'))
            return

        self.stdout.write(f'Updating to {target} from official update center...')
        result = perform_update(target_version=target)

        if result['success']:
            self.stdout.write(self.style.SUCCESS(
                f"Update successful: {result['previous_version']} -> {result['new_version']}"
            ))
            self.stdout.write(f"  Release dir: {result.get('release_dir')}")
            self.stdout.write(f"  Backup: {result.get('backup_file')}")
        else:
            self.stderr.write(self.style.ERROR(f"Update failed: {result.get('error', 'Unknown error')}"))
            if result.get('stage'):
                self.stderr.write(f"  Failed at stage: {result['stage']}")
