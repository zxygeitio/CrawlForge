"""
mingblog.site 爬虫
"""

import requests
import json


def crawl_mingblog():
    """爬取 mingblog.site 文章列表"""
    url = "https://mingblog.site/index.php/wp-json/wp/v2/posts"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    print("[*] 获取文章列表...")

    all_posts = []
    page = 1

    while True:
        params = {"per_page": 100, "page": page}
        resp = requests.get(url, headers=headers, params=params, timeout=10)

        if resp.status_code != 200 or not resp.json():
            break

        posts = resp.json()
        all_posts.extend(posts)
        print(f"[*] 第 {page} 页: 获取 {len(posts)} 篇")
        page += 1

        if len(posts) < 100:
            break

    return all_posts


def main():
    print("[*] mingblog.site 爬虫开始...\n")

    try:
        posts = crawl_mingblog()
        print(f"\n[*] 共获取 {len(posts)} 篇文章")

        # 提取关键信息
        articles = []
        for p in posts:
            articles.append({
                "id": p["id"],
                "title": p["title"]["rendered"],
                "date": p["date"],
                "link": p["link"],
                "excerpt": p["excerpt"]["rendered"][:100] + "..." if p["excerpt"]["rendered"] else ""
            })

        # 保存完整JSON
        with open("demos/mingblog_results.json", "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)

        print("\n[*] 文章列表:")
        for a in articles:
            # 去除HTML标签
            title = a["title"].replace("<", "<").replace(">", ">").replace("&#8217;", "'").replace("&amp;", "&")
            title = ''.join(c for c in title if ord(c) < 128 or c in "中文")
            print(f"  {a['date'][:10]} | {title}")

        print(f"\n[*] 结果已保存到 demos/mingblog_results.json")

    except Exception as e:
        print(f"[!] 错误: {e}")


if __name__ == "__main__":
    main()