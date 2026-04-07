"""
Boss直聘 (zhipin.com) 爬虫

功能:
- 爬取城市职位列表页
- 提取职位名称、薪资、公司名、详情链接
- 支持增量爬取（去重）
- 支持多页爬取

依赖: curl_cffi (TLS impersonation 绕过反爬)
"""

import sys
sys.path.insert(0, "src")

from bs4 import BeautifulSoup
from advanced_crawler import AdvancedCrawler, CrawlerConfig, RequestMethod


class ZhipinCrawler:
    """Boss直聘爬虫"""

    BASE_URL = "https://www.zhipin.com"
    CITIES = {
        "chengdu": "成都",
        "beijing": "北京",
        "shanghai": "上海",
        "shenzhen": "深圳",
        "guangzhou": "广州",
        "hangzhou": "杭州",
        "wuhan": "武汉",
        "nanjing": "南京",
        "xian": "西安",
        "chongqing": "重庆",
    }

    def __init__(self, city: str = "chengdu"):
        self.city = city
        self.city_name = self.CITIES.get(city, city)
        self.config = CrawlerConfig(
            name=f"zhipin_{city}",
            timeout=30,
            enable_rate_limit=False,  # Boss直聘对频率不敏感，先快速验证
            download_delay=1.0,
        )
        self.crawler = AdvancedCrawler(self.config)
        self.seen_urls = set()

    def parse_job_list_page(self, content: str) -> list:
        """
        解析职位列表页，返回职位信息列表
        """
        soup = BeautifulSoup(content, "html.parser")
        jobs = []

        # 查找所有职位卡片 (在 li 标签内)
        job_cards = soup.find_all("a", class_="job-info")

        for card in job_cards:
            try:
                href = card.get("href", "")

                # 跳过非详情链接
                if not href or not href.startswith("/job_detail/"):
                    continue

                # 提取职位名称
                name_el = card.find("p", class_="name")
                name = name_el.get_text(strip=True) if name_el else ""

                # 提取薪资
                salary_el = card.find("p", class_="salary")
                salary = salary_el.get_text(strip=True) if salary_el else ""

                # 提取职位描述标签 (地点、经验、学历等)
                job_text_el = card.find("p", class_="job-text")
                job_tags = []
                if job_text_el:
                    tags = job_text_el.find_all("span")
                    job_tags = [t.get_text(strip=True) for t in tags if t.get_text(strip=True)]

                # 找公司信息 (在同级 sub-li-bottom div 里的 user-info)
                parent_div = card.find_parent("div", class_="sub-li")
                company_name = ""
                company_url = ""
                company_type = ""
                company_level = ""

                if parent_div:
                    bottom_div = parent_div.find("div", class_="sub-li-bottom")
                    if bottom_div:
                        user_info = bottom_div.find("a", class_="user-info")
                        if user_info:
                            company_url = user_info.get("href", "")
                            if company_url and not company_url.startswith("http"):
                                company_url = f"{self.BASE_URL}{company_url}"

                            name_span = user_info.find("span", class_="name")
                            company_name = name_span.get_text(strip=True) if name_span else ""

                            info_p = user_info.find("p", class_="sub-li-bottom-commany-info")
                            if info_p:
                                spans = info_p.find_all("span")
                                for span in spans:
                                    text = span.get_text(strip=True)
                                    if text and text not in ["", "|"]:
                                        if not company_type:
                                            company_type = text
                                        elif not company_level:
                                            company_level = text

                job_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

                # 去重
                if job_url in self.seen_urls:
                    continue
                self.seen_urls.add(job_url)

                jobs.append({
                    "name": name,
                    "url": job_url,
                    "company": company_name,
                    "company_url": company_url,
                    "company_type": company_type,
                    "company_level": company_level,
                    "salary": salary,
                    "city": self.city_name,
                    "tags": job_tags,
                })

            except Exception as e:
                continue

        return jobs

    def crawl_list_page(self, page: int = 1) -> list:
        """
        爬取单页列表
        """
        if page == 1:
            url = f"{self.BASE_URL}/{self.city}/"
        else:
            url = f"{self.BASE_URL}/{self.city}/?page={page}"

        print(f"[Zhipin] Crawling: {url}")

        result = self.crawler.request(
            "GET",
            url,
            use_method=RequestMethod.CURL_CFFI
        )

        if not result:
            print(f"[Zhipin] Failed to fetch {url}")
            return []

        content = result.text
        print(f"[Zhipin] Got {len(content)} bytes")

        jobs = self.parse_job_list_page(content)
        print(f"[Zhipin] Extracted {len(jobs)} jobs")
        return jobs

    def crawl(self, pages: int = 3) -> list:
        """
        爬取多页
        """
        all_jobs = []

        for page in range(1, pages + 1):
            print(f"\n{'='*60}")
            print(f"[Zhipin] Page {page}/{pages}")
            print(f"{'='*60}")

            jobs = self.crawl_list_page(page)
            all_jobs.extend(jobs)

            if len(jobs) == 0:
                print(f"[WARN] No jobs extracted from page {page}")
                # 不停止，继续尝试其他页

            # 保存中间结果
            self.save_jobs(all_jobs, f"zhipin_{self.city}_page{page}.json")

            # 翻页间隔
            if page < pages and jobs:
                import time
                time.sleep(2)

        self.crawler.close()
        return all_jobs

    def save_jobs(self, jobs: list, filename: str):
        """保存到 JSON"""
        import json

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        print(f"[Zhipin] Saved {len(jobs)} jobs to {filename}")

    def print_summary(self, jobs: list):
        """打印摘要"""
        print(f"\n{'='*60}")
        print(f"[Zhipin] Summary")
        print(f"{'='*60}")
        print(f"City: {self.city_name}")
        print(f"Total jobs: {len(jobs)}")
        print(f"Unique jobs: {len(self.seen_urls)}")

        if jobs:
            print(f"\nFirst 5 jobs:")
            for i, job in enumerate(jobs[:5]):
                print(f"  {i+1}. {job['name']} | {job['company']} | {job['url']}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Boss直聘爬虫")
    parser.add_argument("--city", "-c", default="chengdu",
                        choices=list(ZhipinCrawler.CITIES.keys()),
                        help="城市代码")
    parser.add_argument("--pages", "-p", type=int, default=3,
                        help="爬取页数")
    args = parser.parse_args()

    crawler = ZhipinCrawler(city=args.city)
    jobs = crawler.crawl(pages=args.pages)
    crawler.print_summary(jobs)

    return jobs


if __name__ == "__main__":
    main()
