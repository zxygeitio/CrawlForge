"""
SpiderBuf C09 爬虫 - 简单直接方案
让Selenium打开页面，等待JS执行完毕，直接从DOM读取数据
"""

import json
import time
from typing import Optional, List

import httpx
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class SpiderBufC09Crawler:
    """SpiderBuf C09 爬虫 - 直接从DOM读取"""

    BASE_URL = "https://spiderbuf.cn"
    TARGET_PATH = "/web-scraping-practice/scraper-practice-c09"

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

        # 隐藏自动化属性
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """
        })

    def crawl(self) -> List[dict]:
        """爬取数据"""
        if not self.driver:
            self._init_driver()

        print("[*] 访问目标页面...")
        self.driver.get(f"{self.BASE_URL}{self.TARGET_PATH}")

        print("[*] 等待数据加载...")
        # 等待最多30秒，让页面JS执行完毕
        try:
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#items table tbody tr"))
            )
        except:
            pass

        # 再等一下确保数据加载完成
        time.sleep(3)

        # 检查是否有数据 - items区域可能没有h2
        items_div = self.driver.find_element(By.ID, "items")
        items_html = items_div.get_attribute("innerHTML")
        print(f"[*] Items区域HTML: {items_html[:200]}")

        if "请使用浏览器访问" in items_html:
            print("[!] 页面检测到自动化工具")
            return []

        # 从DOM读取表格数据
        rows = self.driver.find_elements(By.CSS_SELECTOR, "#items table tbody tr")

        if not rows:
            print("[!] 表格为空")
            return []

        print(f"[*] 找到 {len(rows)} 行数据")

        data = []
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 7:
                data.append({
                    "index": cells[0].text.strip(),
                    "keyword": cells[1].text.strip(),
                    "cpc": cells[2].text.strip(),
                    "monthly": cells[3].text.strip(),
                    "competition": cells[4].text.strip(),
                    "industry": cells[5].text.strip(),
                    "source": cells[6].text.strip()
                })

        return data

    def calculate_cpc_average(self, data: List[dict]) -> float:
        """计算CPC平均值"""
        cpc_values = []
        for item in data:
            try:
                cpc_str = item["cpc"].replace("$", "").strip()
                cpc_values.append(float(cpc_str))
            except:
                pass

        if not cpc_values:
            return 0.0

        avg = sum(cpc_values) / len(cpc_values)
        # 四舍五入至两位小数
        avg = round(avg, 2)
        # 忽略末尾的0
        if avg == int(avg):
            return int(avg)
        return avg

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None


def main():
    print("[*] SpiderBuf C09 爬虫开始...")

    crawler = SpiderBufC09Crawler()

    try:
        # 爬取数据
        data = crawler.crawl()

        if data:
            print(f"\n[*] 成功获取 {len(data)} 条数据")

            # 显示前几条
            print("\n[*] 数据预览:")
            for item in data[:5]:
                print(f"    {item['index']:>3}. {item['keyword'][:25]:25s} | CPC: {item['cpc']:>8s}")

            # 计算CPC平均值
            avg_cpc = crawler.calculate_cpc_average(data)
            print(f"\n[*] CPC平均值: {avg_cpc}")

            # 保存
            with open("demos/spiderbuf_c09_results.json", "w", encoding="utf-8") as f:
                json.dump({
                    "cpc_average": avg_cpc,
                    "count": len(data),
                    "data": data
                }, f, ensure_ascii=False, indent=2)

            print("[*] 结果已保存")
        else:
            print("[!] 未能获取数据")

    finally:
        crawler.close()


if __name__ == "__main__":
    main()
