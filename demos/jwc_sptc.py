"""
jwc.sptc.edu.cn 爬虫
"""

import json
import time
from typing import Optional, List

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class JWCSpiderCrawler:
    """jwc.sptc.edu.cn 爬虫"""

    BASE_URL = "https://jwc.sptc.edu.cn"

    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None

    def _init_driver(self):
        """初始化Chrome"""
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--lang=zh-CN")
        options.add_experimental_option("prefs", {
            "intl.accept_languages": "zh-CN,zh"
        })
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Chrome(options=options)

        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """
        })

    def crawl_tzgg(self) -> List[dict]:
        """爬取通知公告"""
        if not self.driver:
            self._init_driver()

        print("[*] 访问通知公告页面...")
        self.driver.get(f"{self.BASE_URL}/tzgg")

        print("[*] 等待数据加载...")
        time.sleep(10)

        # 检查页面状态
        print(f"[*] 页面标题: {self.driver.title}")
        print(f"[*] URL: {self.driver.current_url}")

        # 获取页面源码
        page_source = self.driver.page_source
        print(f"[*] 页面源码长度: {len(page_source)}")

        if "网络爬虫" in page_source or "400" in page_source:
            print("[!] 页面被反爬拦截")
            return []

        # 尝试提取通知列表
        notices = []
        try:
            # 等待列表加载
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr, .list-item, .notice-item"))
            )

            # 提取通知
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr, .list-item, .notice-item, .article")
            print(f"[*] 找到 {len(rows)} 条记录")

            for row in rows:
                title = row.text.strip()
                if title:
                    notices.append({"title": title})

        except Exception as e:
            print(f"[!] 提取失败: {e}")

        return notices

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None


def main():
    print("[*] jwc.sptc.edu.cn 爬虫开始...")

    crawler = JWCSpiderCrawler()

    try:
        notices = crawler.crawl_tzgg()

        if notices:
            print(f"\n[*] 成功获取 {len(notices)} 条通知")
            for i, n in enumerate(notices[:10], 1):
                print(f"    {i}. {n.get('title', '')[:50]}")
        else:
            print("[!] 未能获取数据")

    finally:
        crawler.close()


if __name__ == "__main__":
    main()