from urllib.parse import urljoin, urlparse

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Validate ONLYOFFICE integration settings and optional service reachability.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-network',
            action='store_true',
            help='Skip the remote health check against the ONLYOFFICE service.',
        )
        parser.add_argument(
            '--server-url',
            default='',
            help='Override ONLYOFFICE_SERVER_URL for the health check.',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=5,
            help='Health check timeout in seconds.',
        )

    def handle(self, *args, **options):
        issues = []
        warnings = []

        enabled = bool(getattr(settings, 'ONLYOFFICE_ENABLED', False))
        public_path = (getattr(settings, 'ONLYOFFICE_PUBLIC_PATH', '') or '').strip() or '/office/'
        callback_base_url = (getattr(settings, 'ONLYOFFICE_CALLBACK_BASE_URL', '') or '').strip()
        jwt_secret = (getattr(settings, 'ONLYOFFICE_JWT_SECRET', '') or '').strip()
        frame_options = (getattr(settings, 'X_FRAME_OPTIONS', '') or '').strip().upper()

        self.stdout.write('ONLYOFFICE integration check')
        self.stdout.write(f'  enabled: {enabled}')
        self.stdout.write(f'  public path: {public_path}')
        self.stdout.write(f'  callback base: {callback_base_url or "(empty)"}')

        if not enabled:
            warnings.append('ONLYOFFICE_ENABLED is False; Office files will not open in the embedded editor.')

        if not public_path.startswith('/') or not public_path.endswith('/'):
            issues.append('ONLYOFFICE_PUBLIC_PATH must start and end with "/". Example: /office/')

        if frame_options != 'SAMEORIGIN':
            issues.append('X_FRAME_OPTIONS must be SAMEORIGIN so the embedded editor iframe can load.')

        if not callback_base_url:
            warnings.append(
                'ONLYOFFICE_CALLBACK_BASE_URL is empty; runtime will use the current request host. '
                'Ensure the ONLYOFFICE service can resolve and reach that same-domain address.'
            )
        elif not self._is_absolute_http_url(callback_base_url):
            issues.append('ONLYOFFICE_CALLBACK_BASE_URL must be an absolute http(s) URL.')

        if not jwt_secret:
            warnings.append('ONLYOFFICE_JWT_SECRET is empty; production deployment should configure a shared secret.')

        if not options['skip_network']:
            server_url = (options['server_url'] or getattr(settings, 'ONLYOFFICE_SERVER_URL', '') or '').strip()
            if not server_url:
                warnings.append('Skipping health check because ONLYOFFICE_SERVER_URL is empty.')
            elif not self._is_absolute_http_url(server_url):
                issues.append('ONLYOFFICE_SERVER_URL must be an absolute http(s) URL for network verification.')
            else:
                health_url = urljoin(server_url.rstrip('/') + '/', 'healthcheck')
                self.stdout.write(f'  health check: {health_url}')
                try:
                    response = requests.get(
                        health_url,
                        timeout=max(1, options['timeout']),
                        verify=getattr(settings, 'ONLYOFFICE_VERIFY_SSL', True),
                    )
                    response.raise_for_status()
                except requests.RequestException as exc:
                    issues.append(f'ONLYOFFICE health check failed: {exc}')
                else:
                    self.stdout.write(self.style.SUCCESS(f'  health status: {response.status_code}'))

        for warning in warnings:
            self.stdout.write(self.style.WARNING(f'WARNING: {warning}'))

        if issues:
            for issue in issues:
                self.stderr.write(self.style.ERROR(f'ERROR: {issue}'))
            raise CommandError(f'ONLYOFFICE integration check failed with {len(issues)} issue(s).')

        self.stdout.write(self.style.SUCCESS('ONLYOFFICE integration check passed.'))

    @staticmethod
    def _is_absolute_http_url(value):
        parsed = urlparse(value)
        return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)
