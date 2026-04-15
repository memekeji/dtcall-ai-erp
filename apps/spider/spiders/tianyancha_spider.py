import requests
from bs4 import BeautifulSoup
import time
from apps.spider.models import Company
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


class TianyanchaSpider:
    def __init__(self):
        self.base_url = 'https://www.tianyancha.com/search'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Connection': 'keep-alive',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def search_companies(self, keyword, page=1):
        """搜索企业并返回结果列表"""
        try:
            params = {
                'key': keyword,
                'page': page
            }
            response = self.session.get(
                self.base_url, params=params, timeout=10)
            response.raise_for_status()
            return self.parse_search_results(response.text)
        except Exception as e:
            logger.error(f"搜索企业失败: {str(e)}")
            return []

    def parse_search_results(self, html):
        """解析搜索结果页面，提取企业信息和链接"""
        soup = BeautifulSoup(html, 'html.parser')
        company_list = []

        # 查找企业列表项 - 注意：实际选择器可能需要根据天眼查当前页面结构调整
        for item in soup.select('.search-list-item'):
            try:
                name_elem = item.select_one('.name')
                if not name_elem:
                    continue

                company_name = name_elem.get_text(strip=True)
                company_url = name_elem.get('href', '')
                if company_url and not company_url.startswith('http'):
                    company_url = f'https://www.tianyancha.com{company_url}'

                # 提取基本信息
                legal_person = item.select_one(
                    '.legal-person').get_text(strip=True) if item.select_one('.legal-person') else ''
                reg_capital = item.select_one(
                    '.reg-capital').get_text(strip=True) if item.select_one('.reg-capital') else ''
                est_date = item.select_one(
                    '.est-date').get_text(strip=True) if item.select_one('.est-date') else ''
                status = item.select_one('.status').get_text(
                    strip=True) if item.select_one('.status') else ''

                company_list.append({
                    'name': company_name,
                    'legal_person': legal_person,
                    'registered_capital': reg_capital,
                    'establishment_date': est_date,
                    'registration_status': status,
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
            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取详细信息 - 注意：实际选择器可能需要根据天眼查当前页面结构调整
            business_scope = soup.select_one(
                '.business-scope').get_text(strip=True) if soup.select_one('.business-scope') else ''
            address = soup.select_one('.address').get_text(
                strip=True) if soup.select_one('.address') else ''

            return {
                'business_scope': business_scope,
                'address': address
            }
        except Exception as e:
            logger.error(f"获取企业详情失败: {str(e)}")
            return {}

    def crawl_and_save(self, keyword, max_pages=1):
        """爬取企业数据并保存到数据库"""
        saved_count = 0
        for page in range(1, max_pages + 1):
            logger.info(f"爬取第{page}页数据，关键词: {keyword}")
            companies = self.search_companies(keyword, page)
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
                    Company.objects.create(**company_data)
                    saved_count += 1
                    logger.info(f"保存企业成功: {company_data['name']}")

            # 避免请求过于频繁
            time.sleep(2)

        logger.info(f"爬取完成，共保存{saved_count}家企业数据")
        return saved_count
