"""
SpiderBuf C11 爬虫 - MacBook M4 价格抓取
目标: M4芯片的所有内存规格、所有币种的MacBook价格总和
"""

import json
import time
from typing import Optional, List

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class SpiderBufC11Crawler:
    """SpiderBuf C11 爬虫"""

    BASE_URL = "https://spiderbuf.cn"
    TARGET_PATH = "/web-scraping-practice/scraper-practice-js-reverse-c11"

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
        options.add_argument("--lang=zh-CN,zh;q=0.9,en;q=0.8")
        options.add_argument("--user-data-dir=C:/tmp/chrome-data")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--ignore-certificate-errors")
        options.add_experimental_option("prefs", {
            "intl.accept_languages": "zh-CN,zh",
            "profile.default_content_setting_values": {
                "notifications": 2,
                "popups": 2
            }
        })
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Chrome(options=options)

        # 隐藏自动化属性 - 更强力的方式
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
                window.chrome = { runtime: {} };
            """
        })

        # 修改window.navigator.webdriver为false
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def crawl(self) -> List[dict]:
        """爬取数据"""
        if not self.driver:
            self._init_driver()

        print("[*] 访问目标页面...")
        self.driver.get(f"{self.BASE_URL}{self.TARGET_PATH}")

        print("[*] 等待数据加载...")
        time.sleep(8)  # 等待JS执行

        # 检查页面内容
        page_source = self.driver.page_source
        if "网络爬虫" in page_source or "识别为网络爬虫" in page_source:
            print("[!] 页面检测到爬虫")
            # 打印页面部分内容用于调试
            print(f"[*] 页面标题: {self.driver.title}")
            return []

        # 获取所有表格行
        rows = self.driver.find_elements(By.CSS_SELECTOR, "#items table tbody tr")

        if not rows:
            print("[!] 表格为空或未找到")
            return []

        print(f"[*] 找到 {len(rows)} 行数据")

        data = []
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 7:
                item = {
                    "no": cells[0].text.strip(),
                    "model": cells[1].text.strip(),
                    "screen": cells[2].text.strip(),
                    "chip": cells[3].text.strip(),
                    "memory": cells[4].text.strip(),
                    "storage": cells[5].text.strip(),
                    "price": cells[6].text.strip(),
                    "currency": cells[7].text.strip() if len(cells) > 7 else "USD"
                }
                data.append(item)
                print(f"    {item['no']:>2}. {item['model']} | {item['chip']} | {item['memory']} | {item['price']} {item['currency']}")

        return data

    def calculate_m4_total(self, data: List[dict]) -> float:
        """计算M4芯片MacBook价格总和（所有内存规格、所有币种）"""
        total = 0.0
        m4_count = 0

        for item in data:
            chip = item.get("chip", "")
            if "M4" in chip.upper():
                try:
                    price_str = item.get("price", "0").replace(",", "").strip()
                    price = float(price_str)
                    total += price
                    m4_count += 1
                    print(f"    [M4] {item['model']} - {price}")
                except ValueError:
                    pass

        print(f"\n[*] 共找到 {m4_count} 款 M4 MacBook")
        return round(total, 2)

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None


def main():
    print("[*] SpiderBuf C11 爬虫开始...")
    print("[*] 目标: M4芯片的所有内存规格、所有币种的MacBook价格总和\n")

    crawler = SpiderBufC11Crawler()

    try:
        data = crawler.crawl()

        if data:
            print(f"\n[*] 成功获取 {len(data)} 条数据")

            # 筛选M4芯片并计算总和
            total = crawler.calculate_m4_total(data)
            print(f"\n[*] M4 MacBook 价格总和: {total}")

            # 保存
            with open("demos/spiderbuf_c11_results.json", "w", encoding="utf-8") as f:
                json.dump({
                    "total": total,
                    "data": data
                }, f, ensure_ascii=False, indent=2)

            print("[*] 结果已保存到 demos/spiderbuf_c11_results.json")
        else:
            print("[!] 未能获取数据")

    finally:
        crawler.close()


if __name__ == "__main__":
    main()