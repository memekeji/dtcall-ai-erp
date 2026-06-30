"""
Management command: check for updates.
Usage: python manage.py check_update
"""
from django.core.management.base import BaseCommand
from apps.system.version_service import check_for_updates, get_current_version, get_current_commit


class Command(BaseCommand):
    help = 'Check if a newer version of the system is available'

    def handle(self, **options):
        info = check_for_updates()

        self.stdout.write(f"Current version: {info['current_version']} ({info['current_commit']})")
        self.stdout.write(f"Latest version:  {info['latest_version'] or 'N/A'}")

        if info['update_available']:
            self.stdout.write(self.style.WARNING(
                f"Update available: {info['current_version']} -> {info['latest_version']}"
            ))
            if info.get('changelog'):
                self.stdout.write("Changelog:")
                for line in info['changelog'][:20]:
                    self.stdout.write(f"  {line}")
        else:
            self.stdout.write(self.style.SUCCESS("System is up to date."))
