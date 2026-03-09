import os, json
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
import django

django.setup()

from captcha.models import CaptchaStore
from apps.user.models import Menu

BASE = 'http://127.0.0.1:8000'
USERNAME = 'admin'
PASSWORD = 'admin123'

session = requests.Session()
session.headers.update({'User-Agent': 'OpenClawMenuTest/1.0'})


def login():
    r = session.get(urljoin(BASE, '/user/login/'), timeout=15)
    soup = BeautifulSoup(r.text, 'html.parser')
    csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})
    captcha_key = soup.find('input', {'name': 'captcha_key'})
    captcha_obj = CaptchaStore.objects.get(hashkey=captcha_key.get('value'))
    payload = {
        'csrfmiddlewaretoken': csrf.get('value'),
        'username': USERNAME,
        'password': PASSWORD,
        'captcha': captcha_obj.response,
        'captcha_key': captcha_obj.hashkey,
    }
    resp = session.post(urljoin(BASE, '/user/login-submit/'), data=payload, headers={'Referer': urljoin(BASE, '/user/login/')}, timeout=15)
    return resp.json()


def normalize(u):
    if not u:
        return None
    u = u.strip()
    if u.startswith('javascript:') or u.startswith('#'):
        return None
    full = urljoin(BASE, u)
    p = urlparse(full)
    if p.netloc != urlparse(BASE).netloc:
        return None
    return p._replace(fragment='').geturl()


def main():
    login_result = login()
    result = {'login': login_result, 'menus': [], 'issues': []}
    if login_result.get('code') != 0:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    urls = []
    for m in Menu.objects.filter(status=1).select_related('module').order_by('sort', 'id'):
        if not m.src:
            continue
        full = normalize(m.src)
        if not full:
            continue
        urls.append((m.id, m.title, m.src, full, getattr(m.module, 'name', '')))
    seen = set()
    for menu_id, title, src, full, module_name in urls:
        if full in seen:
            continue
        seen.add(full)
        item = {'menu_id': menu_id, 'title': title, 'src': src, 'url': full, 'module': module_name}
        try:
            r = session.get(full, timeout=20, allow_redirects=True)
            item['status'] = r.status_code
            item['final_url'] = r.url
            item['content_type'] = r.headers.get('Content-Type', '')
            text = r.text[:4000]
            item['traceback'] = any(k in text for k in ['TemplateDoesNotExist', 'TemplateSyntaxError', 'Traceback (most recent call last)', 'OperationalError', 'ProgrammingError', 'NoReverseMatch'])
            item['login_redirect'] = '/user/login/' in r.url and '/user/login/' not in full
            if r.status_code >= 400 or item['traceback'] or item['login_redirect']:
                result['issues'].append(item | {'snippet': text[:800]})
        except Exception as e:
            item['status'] = 'ERR'
            item['error'] = str(e)
            result['issues'].append(item)
        result['menus'].append(item)
    summary = {
        'menu_urls_total': len(result['menus']),
        'ok_200': sum(1 for x in result['menus'] if x.get('status') == 200),
        'status_404': sum(1 for x in result['menus'] if x.get('status') == 404),
        'status_500': sum(1 for x in result['menus'] if x.get('status') == 500),
        'status_err': sum(1 for x in result['menus'] if x.get('status') == 'ERR'),
        'issues': len(result['issues'])
    }
    result['summary'] = summary
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
