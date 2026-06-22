import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import re
import time
from apps.spider.models import Company
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class PublicDataAccessError(Exception):
    """公开数据源访问受限。"""


class TianyanchaSpider:
    COOKIE_CONFIG_KEY = 'spider_tianyancha_cookie'
    TOKEN_CONFIG_KEY = 'spider_tianyancha_auth_token'
    PROXY_ENABLED_CONFIG_KEY = 'spider_proxy_enabled'
    PROXY_URL_CONFIG_KEY = 'spider_proxy_url'
    def __init__(self):
        self.base_url = 'https://www.tianyancha.com/search'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://www.tianyancha.com/',
            'Connection': 'keep-alive',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._load_auth_config()
        self._load_proxy_config()

    def _load_auth_config(self):
        try:
            from apps.user.models import SystemConfiguration
            configs = SystemConfiguration.objects.filter(
                key__in=[self.COOKIE_CONFIG_KEY, self.TOKEN_CONFIG_KEY],
                is_active=True
            )
            config_map = {item.key: item.value.strip() for item in configs if item.value and item.value.strip()}
        except Exception as e:
            logger.warning(f'读取天眼查授权配置失败: {str(e)}')
            config_map = {}

        cookie = config_map.get(self.COOKIE_CONFIG_KEY)
        if cookie:
            self.session.headers['Cookie'] = cookie
        token = config_map.get(self.TOKEN_CONFIG_KEY)
        if token:
            self.session.headers['Authorization'] = token

    def _load_proxy_config(self):
        try:
            from apps.user.models import SystemConfiguration
            enabled = SystemConfiguration.objects.filter(
                key=self.PROXY_ENABLED_CONFIG_KEY,
                is_active=True
            ).values_list('value', flat=True).first()
            proxy_url = SystemConfiguration.objects.filter(
                key=self.PROXY_URL_CONFIG_KEY,
                is_active=True
            ).values_list('value', flat=True).first()
        except Exception as e:
            logger.warning(f'读取代理配置失败: {str(e)}')
            enabled = ''
            proxy_url = ''

        if str(enabled).lower() not in ['true', '1', 'yes', 'on']:
            return
        if not proxy_url:
            return
        proxy_url = proxy_url.strip()
        if not proxy_url:
            return
        self.session.proxies.update({
            'http': proxy_url,
            'https': proxy_url,
        })
        logger.info('天眼查爬虫已启用代理: %s', proxy_url)

    def search_companies(self, keyword, page=1, region='', industry=''):
        """搜索企业并返回结果列表"""
        params = {
            'key': self._build_search_keyword(keyword, region, industry),
            'page': page
        }
        try:
            response = self.session.get(
                self.base_url, params=params, timeout=10)
            response.raise_for_status()
            self._ensure_accessible_response(response)
            companies = self.parse_search_results(response.text)
            if not companies and self._is_blocked_page(response.text, response.url):
                raise PublicDataAccessError('公开数据源返回了访问限制页面，无法获取企业列表')
            return companies
        except PublicDataAccessError:
            raise
        except Exception as e:
            logger.error(f"搜索企业失败: {str(e)}")
            return []

    def parse_search_results(self, html):
        """解析搜索结果页面，提取企业信息和链接"""
        soup = BeautifulSoup(html, 'html.parser')
        company_list = []
        seen_names = set()
        selectors = [
            '.search-list-item',
            '.index_search-box__7YVh6',
            '.search-result-single',
            '[data-click-name="search_company"]'
        ]
        items = []
        for selector in selectors:
            items = soup.select(selector)
            if items:
                break
        if not items:
            items = [link.find_parent(['div', 'section', 'article']) for link in soup.select('a[href*="/company/"]')]

        for item in items:
            if not item:
                continue
            try:
                name_elem = self._first_element(item, ['a[href*="/company/"]', '.name', '.title', 'a'])
                if not name_elem:
                    continue

                company_name = name_elem.get_text(' ', strip=True).replace('查看更多', '').strip()
                company_url = urljoin('https://www.tianyancha.com', name_elem.get('href', ''))
                if not company_name or company_name in seen_names:
                    continue
                seen_names.add(company_name)

                text = item.get_text('\n', strip=True)
                company_list.append({
                    'name': company_name,
                    'legal_person': self._extract_by_labels(text, ['法定代表人', '法人代表', '负责人']),
                    'registered_capital': self._extract_by_labels(text, ['注册资本']),
                    'establishment_date': self._extract_by_labels(text, ['成立日期', '成立时间']),
                    'registration_status': self._extract_by_labels(text, ['经营状态', '登记状态', '状态']),
                    'phone': self._extract_phone(text),
                    'email': self._extract_email(text),
                    'tianyancha_url': company_url
                })
            except Exception as e:
                logger.error(f"解析企业信息失败: {str(e)}")
                continue

        return company_list

    def get_company_detail(self, url):
        """获取企业详情页信息"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            self._ensure_accessible_response(response)
            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text('\n', strip=True)

            return {
                'business_scope': self._extract_by_labels(page_text, ['经营范围']),
                'address': self._extract_by_labels(page_text, ['注册地址', '经营地址', '企业地址', '地址']),
                'phone': self._extract_phone(page_text),
                'email': self._extract_email(page_text)
            }
        except PublicDataAccessError:
            raise
        except Exception as e:
            logger.error(f"获取企业详情失败: {str(e)}")
            return {}

    def _first_element(self, root, selectors):
        for selector in selectors:
            element = root.select_one(selector)
            if element:
                return element
        return None

    def _ensure_accessible_response(self, response):
        if self._is_blocked_page(response.text, response.url):
            logger.warning('公开数据源访问受限: url=%s final_url=%s status=%s', response.request.url, response.url, response.status_code)
            raise PublicDataAccessError(
                '公开数据源要求登录或限制访问，请在系统配置中维护 spider_tianyancha_cookie 或 spider_tianyancha_auth_token 后重试'
            )

    def _is_blocked_page(self, html, final_url=''):
        final_url = final_url or ''
        if '/login' in final_url or '/security' in final_url:
            return True
        text = BeautifulSoup(html, 'html.parser').get_text('\n', strip=True)
        blocked_keywords = ['登录/注册', '账号登录', '扫码登录', '安全验证', '访问受限', '请完成验证']
        return any(keyword in text for keyword in blocked_keywords)

    def _build_search_keyword(self, keyword, region='', industry=''):
        parts = [keyword]
        for value in [region, industry]:
            if value:
                parts.extend([item.strip() for item in value.split(',') if item.strip() and not item.strip().isdigit()])
        return ' '.join(dict.fromkeys(parts))

    def _extract_phone(self, text):
        mobile_match = re.search(r'1[3-9]\d{9}', text)
        if mobile_match:
            return mobile_match.group(0)
        tel_match = re.search(r'(?:0\d{2,3}[- ]?)?\d{7,8}|400[- ]?\d{3}[- ]?\d{4}|800[- ]?\d{3}[- ]?\d{4}', text)
        return tel_match.group(0) if tel_match else ''

    def _extract_email(self, text):
        email_match = re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', text)
        return email_match.group(0) if email_match else ''

    def _parse_date(self, value):
        if not value:
            return None
        value = value.strip()
        for pattern in ['%Y-%m-%d', '%Y年%m月%d日', '%Y.%m.%d', '%Y/%m/%d']:
            try:
                return datetime.strptime(value[:10] if pattern == '%Y-%m-%d' else value, pattern).date()
            except ValueError:
                continue
        match = re.search(r'(\d{4})[-年./](\d{1,2})[-月./](\d{1,2})', value)
        if match:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date()
        return None

    def _company_model_data(self, company_data):
        return {
            'name': company_data.get('name', ''),
            'legal_person': company_data.get('legal_person', ''),
            'registered_capital': company_data.get('registered_capital', ''),
            'establishment_date': self._parse_date(company_data.get('establishment_date')),
            'registration_status': company_data.get('registration_status', ''),
            'business_scope': company_data.get('business_scope', ''),
            'address': company_data.get('address', ''),
            'tianyancha_url': company_data.get('tianyancha_url', ''),
        }

    def _extract_by_labels(self, text, labels):
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        for index, line in enumerate(lines):
            normalized = line.rstrip(':：')
            for label in labels:
                if normalized == label and index + 1 < len(lines):
                    return lines[index + 1].strip()
                if line.startswith(label):
                    value = line[len(label):].strip(' :：')
                    if value:
                        return value
        return ''

    def crawl_and_save(self, keyword, max_pages=1):
        """爬取企业数据并保存到数据库"""
        saved_count = 0
        for page in range(1, max_pages + 1):
            logger.info(f"爬取第{page}页数据，关键词: {keyword}")
            companies = self.search_companies(keyword, page=page)
            if not companies:
                break

            with transaction.atomic():
                for company_data in companies:
                    # 检查企业是否已存在
                    if Company.objects.filter(
                            name=company_data['name']).exists():
                        logger.info(f"企业已存在: {company_data['name']}")
                        continue

                    # 获取企业详情
                    if company_data['tianyancha_url']:
                        detail_data = self.get_company_detail(
                            company_data['tianyancha_url'])
                        company_data.update(detail_data)

                    # 保存企业信息
                    Company.objects.create(**self._company_model_data(company_data))
                    saved_count += 1
                    logger.info(f"保存企业成功: {company_data['name']}")

            # 避免请求过于频繁
            time.sleep(2)

        logger.info(f"爬取完成，共保存{saved_count}家企业数据")
        return saved_count
