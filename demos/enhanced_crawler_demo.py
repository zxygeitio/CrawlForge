"""
增强爬虫示例
展示异步爬取、代理池、速率限制、隐身浏览器等特性
"""

import asyncio
import re
from datetime import datetime
from src.advanced_crawler import AdvancedCrawler, CrawlerConfig, RequestMethod
from src.js_hook_tools import JSHookManager
from src.proxy_manager import ProxyPoolConfig


# ============== 示例1: 基础爬取 ==============

def basic_crawl_example():
    """基础爬取示例"""
    config = CrawlerConfig(
        name="basic_demo",
        timeout=30,
        download_delay=0.5,
        use_stealth_browser=False
    )

    crawler = AdvancedCrawler(config)

    def parse_notice(response) -> dict:
        """解析通知公告"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        return {
            "title": soup.find("title").text if soup.find("title") else "",
            "content": soup.get_text(strip=True)[:500],
        }

    result = crawler.crawl_page(
        url="https://httpbin.org/html",
        parser=parse_notice,
        use_method=RequestMethod.CURL_CFFI
    )

    print(f"Result: {result}")
    crawler.close()
    return result


# ============== 示例2: Playwright隐身爬取 ==============

def playwright_stealth_example():
    """Playwright隐身浏览器示例"""
    config = CrawlerConfig(
        name="stealth_demo",
        timeout=30,
        headless=True,
        use_stealth_browser=True
    )

    crawler = AdvancedCrawler(config)

    def parse_page(page) -> dict:
        """使用页面对象解析"""
        return {
            "title": page.title(),
            "url": page.url,
            "content": page.content()[:500],
        }

    # 使用Playwright并安装Hook
    browser = crawler.stealth_browser.launch()
    context = browser.new_context()
    page = context.new_page()

    # 安装Hook
    JSHookManager.install_hooks(page, ['network', 'crypto', 'fingerprint'])

    page.goto("https://httpbin.org/headers")
    result = page.evaluate("""() => {
        return {
            title: document.title,
            content: document.body.innerText
        };
    }""")

    context.close()
    browser.close()
    crawler.close()

    print(f"Result: {result}")
    return result


# ============== 示例3: 异步并发爬取 ==============

async def async_crawl_example():
    """异步并发爬取示例"""
    config = CrawlerConfig(
        name="async_demo",
        timeout=30,
        download_delay=0.1,
        rate_limit=20.0,
        enable_rate_limit=True
    )

    crawler = AdvancedCrawler(config)

    def parse_json(response) -> dict:
        """JSON解析"""
        return response.json() if response else None

    # URL列表
    urls = [
        f"https://httpbin.org/json",
        f"https://httpbin.org/uuid",
        f"https://httpbin.org/headers",
        f"https://httpbin.org/ip",
        f"https://httpbin.org/user-agent",
    ]

    # 并发爬取
    tasks = [
        crawler.async_crawl_page(url, parse_json, RequestMethod.ASYNC_CURL)
        for url in urls
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    crawler.close()

    for i, result in enumerate(results):
        print(f"URL {i}: {result}")

    return results


# ============== 示例4: 带代理池爬取 ==============

def proxy_pool_example():
    """代理池示例"""
    config = CrawlerConfig(
        name="proxy_demo",
        timeout=30,
        proxy_enabled=True,
        proxy_pool=[
            "127.0.0.1:7890",
            "127.0.0.1:8080",
        ]
    )

    crawler = AdvancedCrawler(config)

    # 添加更多代理
    crawler.proxy_pool.add_proxy("proxy1.example.com:8080", {"country": "us"})
    crawler.proxy_pool.add_proxy("proxy2.example.com:8080", {"country": "cn"})

    def parse_response(response) -> dict:
        return {"status": response.status_code, "content": response.text[:100]}

    result = crawler.crawl_page(
        url="https://httpbin.org/ip",
        parser=parse_response,
        use_method=RequestMethod.CURL_CFFI
    )

    # 上报结果
    if result:
        asyncio.get_event_loop().run_until_complete(
            crawler.proxy_pool.report_result("proxy1.example.com:8080", True, 0.5)
        )

    crawler.close()
    print(f"Result: {result}")
    return result


# ============== 示例5: 滑块验证码Hook示例 ==============

def slider_captcha_hook_example():
    """滑块验证码Hook示例"""
    config = CrawlerConfig(
        name="slider_demo",
        headless=True,
        use_stealth_browser=True
    )

    crawler = AdvancedCrawler(config)

    browser = crawler.stealth_browser.launch()
    context = browser.new_context()
    page = context.new_page()

    # 安装滑块Hook
    JSHookManager.install_captcha_hook(page)

    page.goto("https://www.geetest.com/demo/slide-float.html")
    page.wait_for_timeout(2000)

    # 检测滑块
    slider = page.evaluate("window.getSliderDistance();")
    print(f"Slider detected: {slider}")

    context.close()
    browser.close()
    crawler.close()


# ============== 主函数 ==============

if __name__ == "__main__":
    print("=" * 50)
    print("1. Basic Crawl Example")
    print("=" * 50)
    basic_crawl_example()

    print("\n" + "=" * 50)
    print("2. Playwright Stealth Example")
    print("=" * 50)
    playwright_stealth_example()

    print("\n" + "=" * 50)
    print("3. Async Crawl Example")
    print("=" * 50)
    asyncio.run(async_crawl_example())

    print("\n" + "=" * 50)
    print("4. Proxy Pool Example")
    print("=" * 50)
    proxy_pool_example()

    print("\n" + "=" * 50)
    print("5. Slider Captcha Hook Example")
    print("=" * 50)
    slider_captcha_hook_example()
