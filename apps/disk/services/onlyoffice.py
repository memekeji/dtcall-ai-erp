import hashlib
from urllib.parse import urlencode, urljoin

import requests
from django.conf import settings
from django.core import signing
from django.urls import reverse

try:
    import jwt
except ImportError:  # pragma: no cover
    jwt = None


OFFICE_EXTENSIONS = {
    '.doc',
    '.docx',
    '.xls',
    '.xlsx',
    '.ppt',
    '.pptx',
}

DOCUMENT_TYPE_MAP = {
    '.doc': 'word',
    '.docx': 'word',
    '.xls': 'cell',
    '.xlsx': 'cell',
    '.ppt': 'slide',
    '.pptx': 'slide',
}

DOCUMENT_SIGNED_URL_TTL_SECONDS = 60 * 60
CALLBACK_SIGNED_URL_TTL_SECONDS = 60 * 60 * 24
DOCUMENT_TOKEN_SALT = 'disk.onlyoffice.document'
CALLBACK_TOKEN_SALT = 'disk.onlyoffice.callback'


def _normalize_extension(file_ext):
    ext = (file_ext or '').strip().lower()
    if not ext:
        return ''
    return ext if ext.startswith('.') else f'.{ext}'


def is_supported_extension(file_ext):
    return _normalize_extension(file_ext) in OFFICE_EXTENSIONS


def get_document_type(file_ext):
    return DOCUMENT_TYPE_MAP.get(_normalize_extension(file_ext), 'word')


def get_file_type(file_ext):
    return _normalize_extension(file_ext).lstrip('.')


def build_document_key(disk_file):
    update_timestamp = getattr(disk_file, 'update_time', None)
    update_marker = update_timestamp.isoformat() if update_timestamp else ''
    return build_document_key_from_values(
        disk_file.id,
        update_marker,
        disk_file.file_size,
        disk_file.original_name,
    )


def build_document_key_from_values(*values):
    raw = ':'.join('' if value is None else str(value) for value in values)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def get_share_version(share):
    if not share:
        return ''
    update_timestamp = getattr(share, 'update_time', None)
    return update_timestamp.isoformat() if update_timestamp else ''


def _absolute_url(request, path, base_url=''):
    if path.startswith('http://') or path.startswith('https://'):
        return path

    normalized_base = (base_url or '').strip()
    if normalized_base:
        return urljoin(normalized_base.rstrip('/') + '/', path.lstrip('/'))
    return request.build_absolute_uri(path)


def build_public_asset_url(request, asset_path):
    public_base = getattr(settings, 'ONLYOFFICE_PUBLIC_PATH', '') or getattr(
        settings, 'ONLYOFFICE_SERVER_URL', '')
    return _absolute_url(request, asset_path, base_url=public_base)


def build_editor_page_url(request, disk_file, share_code=''):
    path = reverse('disk:onlyoffice_editor', args=[disk_file.id])
    if share_code:
        path = f'{path}?{urlencode({"share_code": share_code})}'
    return request.build_absolute_uri(path)


def _sign_payload(payload, salt):
    return signing.dumps(payload, salt=salt)


def load_signed_payload(token, salt, max_age=None):
    ttl = max_age
    if ttl is None:
        ttl = (
            DOCUMENT_SIGNED_URL_TTL_SECONDS
            if salt == DOCUMENT_TOKEN_SALT
            else CALLBACK_SIGNED_URL_TTL_SECONDS
        )
    return signing.loads(token, salt=salt, max_age=ttl)


def build_document_url(request, disk_file, share_code='', share=None):
    path = reverse('disk:onlyoffice_document', args=[disk_file.id])
    token = _sign_payload(
        {
            'file_id': disk_file.id,
            'share_code': share_code,
            'share_version': get_share_version(share),
            'action': 'document',
        },
        salt=DOCUMENT_TOKEN_SALT,
    )
    query = urlencode({'token': token})
    base_url = getattr(settings, 'ONLYOFFICE_CALLBACK_BASE_URL', '')
    return _absolute_url(request, f'{path}?{query}', base_url=base_url)


def build_callback_url(request, disk_file, share_code='', can_edit=False):
    path = reverse('disk:onlyoffice_callback', args=[disk_file.id])
    token = _sign_payload(
        {
            'file_id': disk_file.id,
            'share_code': share_code,
            'action': 'callback',
            'can_edit': bool(can_edit),
        },
        salt=CALLBACK_TOKEN_SALT,
    )
    query = urlencode({'token': token})
    base_url = getattr(settings, 'ONLYOFFICE_CALLBACK_BASE_URL', '')
    return _absolute_url(request, f'{path}?{query}', base_url=base_url)


def build_editor_config(
    request,
    disk_file,
    *,
    user,
    can_edit,
    share_code='',
    share=None,
    allow_download=True,
    allow_copy=True,
):
    title = (disk_file.original_name or disk_file.name or 'document')[
        : settings.ONLYOFFICE_DOCUMENT_TITLE_MAX_LENGTH
    ]
    return build_editor_config_from_urls(
        title=title,
        file_ext=disk_file.file_ext,
        document_url=build_document_url(
            request,
            disk_file,
            share_code=share_code,
            share=share,
        ),
        document_key=build_document_key(disk_file),
        user=user,
        can_edit=can_edit,
        allow_download=allow_download,
        allow_copy=allow_copy,
        callback_url=build_callback_url(
            request, disk_file, share_code=share_code, can_edit=can_edit),
    )


def build_editor_config_from_urls(
    *,
    title,
    file_ext,
    document_url,
    document_key,
    user,
    can_edit,
    allow_download=True,
    allow_copy=True,
    callback_url='',
):
    normalized_title = (title or 'document')[
        : settings.ONLYOFFICE_DOCUMENT_TITLE_MAX_LENGTH
    ]
    config = {
        'documentType': get_document_type(file_ext),
        'type': 'desktop',
        'document': {
            'title': normalized_title,
            'url': document_url,
            'fileType': get_file_type(file_ext),
            'key': document_key,
            'permissions': {
                'edit': bool(can_edit),
                'download': bool(allow_download),
                'print': True,
                'copy': bool(allow_copy),
            },
        },
        'editorConfig': {
            'mode': 'edit' if can_edit else 'view',
            'user': {
                'id': str(getattr(user, 'id', 'anonymous')),
                'name': getattr(user, 'name', '') or getattr(user, 'username', '') or '访客',
            },
            'customization': {
                'autosave': bool(can_edit),
                'forcesave': bool(can_edit),
            },
        },
    }

    if callback_url:
        config['editorConfig']['callbackUrl'] = callback_url

    jwt_secret = getattr(settings, 'ONLYOFFICE_JWT_SECRET', '').strip()
    if jwt_secret and jwt is not None:
        config['token'] = jwt.encode(config, jwt_secret, algorithm='HS256')

    return config


def get_editor_api_script_url(request):
    return build_public_asset_url(
        request,
        'web-apps/apps/api/documents/api.js',
    )


def extract_callback_token(request, payload):
    token = payload.get('token')
    if token:
        return token

    configured_header = getattr(settings, 'ONLYOFFICE_JWT_HEADER', 'Authorization')
    header_names = [configured_header, 'Authorization']
    for header_name in header_names:
        meta_key = f'HTTP_{header_name.upper().replace("-", "_")}'
        value = request.META.get(meta_key, '').strip()
        if not value:
            continue
        if value.lower().startswith('bearer '):
            return value.split(' ', 1)[1].strip()
        return value
    return ''


def validate_callback_token(request, payload):
    jwt_secret = getattr(settings, 'ONLYOFFICE_JWT_SECRET', '').strip()
    if not jwt_secret:
        return True
    if jwt is None:
        return False

    token = extract_callback_token(request, payload)
    if not token:
        return False

    try:
        jwt.decode(token, jwt_secret, algorithms=['HS256', 'HS384', 'HS512'])
        return True
    except Exception:
        return False


def should_persist_status(status):
    return status in {2, 6}


def fetch_saved_document(url):
    response = requests.get(
        url,
        timeout=60,
        verify=getattr(settings, 'ONLYOFFICE_VERIFY_SSL', True),
    )
    response.raise_for_status()
    return response.content
