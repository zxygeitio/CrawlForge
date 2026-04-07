"""分析 zhipin CURL_CFFI 返回内容"""
import sys
sys.path.insert(0, "src")

from advanced_crawler import AdvancedCrawler, CrawlerConfig, RequestMethod

config = CrawlerConfig(name="zhipin_test", timeout=30)
crawler = AdvancedCrawler(config)

result = crawler.request("GET", "https://www.zhipin.com/chengdu/", use_method=RequestMethod.CURL_CFFI)
crawler.close()

if result:
    content = result.text
    print(f"Total length: {len(content)}")

    # 检查反爬关键词
    keywords = ["验证", "访问受限", "请稍后", "安全验证", "频繁", "禁止访问", "blocked"]
    for kw in keywords:
        if kw in content:
            idx = content.index(kw)
            print(f"Found '{kw}' at {idx}: ...{content[max(0,idx-50):idx+50]}...")

    # 检查职位相关内容
    job_keywords = ["job-card", "job-info", "job-title", "job-name", "boss", "薪资", "招聘", "职位"]
    for kw in job_keywords:
        if kw in content:
            idx = content.index(kw)
            print(f"Found job keyword '{kw}' at {idx}: ...{content[max(0,idx-30):idx+60]}...")

    # 保存完整内容供分析
    with open("zhipin_content.html", "w", encoding="utf-8") as f:
        f.write(content)
    print("Saved to zhipin_content.html")
