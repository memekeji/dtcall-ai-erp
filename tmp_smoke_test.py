import os, re, json, time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
import django

django.setup()
from captcha.models import CaptchaStore

BASE = 'http://127.0.0.1:8000'
USERNAME = 'admin'
PASSWORD = 'admin123'

session = requests.Session()
session.headers.update({'User-Agent': 'OpenClawSmokeTest/1.0'})


def solve_login():
    r = session.get(urljoin(BASE, '/user/login/'), timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})
    captcha_key = soup.find('input', {'name': 'captcha_key'})
    if not csrf or not captcha_key:
        raise RuntimeError('login page missing csrf or captcha_key')
    captcha_obj = CaptchaStore.objects.get(hashkey=captcha_key.get('value'))
    payload = {
        'csrfmiddlewaretoken': csrf.get('value'),
        'username': USERNAME,
        'password': PASSWORD,
        'captcha': captcha_obj.response,
        'captcha_key': captcha_obj.hashkey,
    }
    headers = {'Referer': urljoin(BASE, '/user/login/')}
    resp = session.post(urljoin(BASE, '/user/login-submit/'), data=payload, headers=headers, timeout=15)
    return r, resp


def normalize(url):
    if not url:
        return None
    if url.startswith('javascript:') or url.startswith('mailto:') or url.startswith('tel:') or url.startswith('#'):
        return None
    full = urljoin(BASE, url)
    p = urlparse(full)
    if p.scheme not in ('http', 'https'):
        return None
    if p.netloc != urlparse(BASE).netloc:
        return None
    if any(x in p.path for x in ['/logout', '/delete', '/del/', '/download/', '/export', '/approve/', '/reject/', '/submit/', '/cancel/', '/restore/', '/toggle/', '/action/', '/stock/', '/check/', '/publish/', '/revoke/']):
        return None
    return p._replace(fragment='').geturl()


def extract_links(html, current_url):
    soup = BeautifulSoup(html, 'html.parser')
    links = set()
    assets = set()
    for tag in soup.find_all(['a', 'link', 'script', 'img', 'iframe', 'form']):
        attr = 'href' if tag.name in ('a', 'link') else 'src' if tag.name in ('script', 'img', 'iframe') else 'action'
        val = tag.get(attr)
        if not val:
            continue
        full = normalize(val)
        if not full:
            continue
        if tag.name in ('link', 'script', 'img'):
            assets.add(full)
        else:
            links.add(full)
    text = soup.get_text('\n', strip=True)
    title = soup.title.string.strip() if soup.title and soup.title.string else ''
    return links, assets, title, text


def is_html(resp):
    return 'text/html' in resp.headers.get('Content-Type', '')


def check_asset(url):
    try:
        r = session.get(url, timeout=15, allow_redirects=True)
        return {'url': url, 'status': r.status_code, 'type': r.headers.get('Content-Type', '')}
    except Exception as e:
        return {'url': url, 'status': 'ERR', 'error': str(e)}


def main():
    login_page, login_resp = solve_login()
    result = {
        'login_page_status': login_page.status_code,
        'login_submit_status': login_resp.status_code,
        'login_submit_text': login_resp.text[:500],
        'pages': [],
        'issues': [],
        'assets': [],
    }
    try:
        login_json = login_resp.json()
    except Exception:
        login_json = None
    result['login_json'] = login_json
    if not login_json or login_json.get('code') != 0:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    queue = [urljoin(BASE, login_json['data'].get('redirect_url', '/home/main/'))]
    queue += [
        urljoin(BASE, '/home/dashboard/'),
        urljoin(BASE, '/user/employee/'),
        urljoin(BASE, '/customer/'),
        urljoin(BASE, '/finance/'),
        urljoin(BASE, '/contract/sales/'),
        urljoin(BASE, '/project/'),
        urljoin(BASE, '/task/'),
        urljoin(BASE, '/production/'),
        urljoin(BASE, '/approval/my/'),
        urljoin(BASE, '/disk/'),
        urljoin(BASE, '/system/config/'),
        urljoin(BASE, '/personal/'),
        urljoin(BASE, '/ai/chat/'),
        urljoin(BASE, '/inventory/'),
    ]
    seen = set()
    asset_seen = set()
    max_pages = 220

    while queue and len(seen) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        page = {'url': url}
        try:
            r = session.get(url, timeout=20, allow_redirects=True)
            page['status'] = r.status_code
            page['final_url'] = r.url
            page['content_type'] = r.headers.get('Content-Type', '')
            page['len'] = len(r.text)
            page['redirected_to_login'] = '/user/login/' in r.url and '/user/login/' not in url
            if is_html(r):
                links, assets, title, text = extract_links(r.text, r.url)
                page['title'] = title
                page['possible_traceback'] = any(k in text for k in ['Traceback (most recent call last)', 'Internal Server Error', 'NoReverseMatch', 'TemplateDoesNotExist', 'OperationalError', 'ProgrammingError'])
                page['possible_mojibake'] = '�' in r.text[:50000]
                if page['status'] >= 400 or page['redirected_to_login'] or page['possible_traceback']:
                    result['issues'].append({
                        'type': 'page',
                        'url': url,
                        'status': r.status_code,
                        'final_url': r.url,
                        'title': title,
                        'traceback': page['possible_traceback'],
                        'snippet': text[:600]
                    })
                for l in sorted(links):
                    if l not in seen and l not in queue:
                        queue.append(l)
                for a in sorted(assets):
                    if a not in asset_seen and len(asset_seen) < 200:
                        asset_seen.add(a)
            else:
                if page['status'] >= 400:
                    result['issues'].append({'type': 'non-html', 'url': url, 'status': r.status_code, 'final_url': r.url})
        except Exception as e:
            page['status'] = 'ERR'
            page['error'] = str(e)
            result['issues'].append({'type': 'exception', 'url': url, 'error': str(e)})
        result['pages'].append(page)

    for a in sorted(asset_seen):
        asset_result = check_asset(a)
        result['assets'].append(asset_result)
        if asset_result.get('status') not in (200, 304):
            result['issues'].append({'type': 'asset', **asset_result})

    summary = {
        'total_pages': len(result['pages']),
        'html_pages': sum(1 for p in result['pages'] if 'text/html' in p.get('content_type', '')),
        'status_200': sum(1 for p in result['pages'] if p.get('status') == 200),
        'status_302': sum(1 for p in result['pages'] if p.get('status') == 302),
        'status_403': sum(1 for p in result['pages'] if p.get('status') == 403),
        'status_404': sum(1 for p in result['pages'] if p.get('status') == 404),
        'status_500': sum(1 for p in result['pages'] if p.get('status') == 500),
        'status_err': sum(1 for p in result['pages'] if p.get('status') == 'ERR'),
        'issues': len(result['issues']),
        'assets_checked': len(result['assets']),
    }
    result['summary'] = summary
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
