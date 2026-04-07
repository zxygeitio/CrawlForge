"""
Boss直聘 (zhipin.com) 爬取测试

结论：
- CURL_CFFI: 成功，495KB，108个职位，反爬被 TLS impersonation 绕过
- PLAYWRIGHT: 失败，被检测后重定向到 about:blank（navigator.webdriver=true）
"""

import sys
sys.path.insert(0, "src")

from advanced_crawler import AdvancedCrawler, CrawlerConfig, RequestMethod


def test_zhipin():
    config = CrawlerConfig(
        name="zhipin_test",
        timeout=30,
    )

    crawler = AdvancedCrawler(config)
    url = "https://www.zhipin.com/chengdu/"

    print("=" * 60)
    print("Testing: CURL_CFFI (TLS impersonation)")
    print("=" * 60)

    result = crawler.request("GET", url, use_method=RequestMethod.CURL_CFFI)
    crawler.close()

    if result:
        content = result.text
        print(f"Status: {result.status_code}")
        print(f"Content length: {len(content)}")

        # 检查反爬
        anti_bot = any(k in content for k in ["访问受限", "请稍后", "安全验证", "blocked", "禁止访问"])
        if anti_bot:
            print("[WARN] Possible anti-bot check detected")
        else:
            print("[OK] Content appears clean")

        # 职位数量
        job_count = content.count("class=\"job-info\"")
        print(f"Job listings found: {job_count}")

        # 保存
        with open("zhipin_content.html", "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Saved to zhipin_content.html")
    else:
        print("[FAIL] Request returned None")

    print("\nDone")


if __name__ == "__main__":
    test_zhipin()
