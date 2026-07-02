from django.core.management.base import BaseCommand
from apps.system.version_service import check_for_updates


class Command(BaseCommand):
    help = 'Check if a newer version is available from the official update center'

    def handle(self, **options):
        info = check_for_updates()

        self.stdout.write(f"Current version: {info['current_version']} ({info['current_commit']})")
        self.stdout.write(f"Latest version:  {info.get('latest_version') or 'N/A'}")
        self.stdout.write(f"Source:          {info.get('source', 'unknown')}")
        if info.get('channel'):
            self.stdout.write(f"Channel:         {info.get('channel')}")
        if info.get('platform'):
            self.stdout.write(f"Platform:        {info.get('platform')}")

        if info['update_available']:
            self.stdout.write(self.style.WARNING(
                f"Update available: {info['current_version']} -> {info['latest_version']}"
            ))
            if info.get('changelog'):
                self.stdout.write("Highlights:")
                for line in info['changelog'][:20]:
                    self.stdout.write(f"  {line}")
        else:
            self.stdout.write(self.style.SUCCESS("System is up to date."))
