from django.core.management.base import BaseCommand

from apps.system.version_service import perform_offline_import


class Command(BaseCommand):
    help = "Import a DTCall offline ZIP release package and activate it"

    def add_arguments(self, parser):
        parser.add_argument("zip_path", type=str, help="Absolute path to the offline ZIP package")

    def handle(self, *args, **options):
        zip_path = options["zip_path"]
        self.stdout.write(f"Importing release package: {zip_path}")
        result = perform_offline_import(zip_path)
        if result.get("success"):
            self.stdout.write(self.style.SUCCESS(f"Offline import successful: {result.get('new_version')}"))
            self.stdout.write(f"  Release dir: {result.get('release_dir')}")
            self.stdout.write(f"  Backup: {result.get('backup_file')}")
            if result.get("imported_images"):
                self.stdout.write(f"  Images: {', '.join(result.get('imported_images'))}")
        else:
            self.stderr.write(self.style.ERROR(f"Offline import failed: {result.get('error', 'Unknown error')}"))
