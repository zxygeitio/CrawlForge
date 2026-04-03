"""
豆瓣电影排行榜爬虫
目标: https://movie.douban.com/chart
"""

import asyncio
import re
from typing import TypedDict
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup


class Movie(TypedDict):
    """电影数据结构"""
    rank: int
    title: str
    title_foreign: str
    rating: str
    vote_count: str
    description: str
    url: str
    poster: str


@dataclass
class CrawlResult:
    """爬取结果"""
    section: str
    movies: list[Movie]


class DoubanChartCrawler:
    """豆瓣电影排行榜爬虫"""

    BASE_URL = "https://movie.douban.com/chart"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://movie.douban.com/",
    }

    def __init__(self):
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            headers=self.HEADERS,
            timeout=30.0,
            follow_redirects=True
        )
        return self

    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()

    async def fetch_page(self) -> str:
        """获取页面HTML"""
        response = await self.client.get(self.BASE_URL)
        response.raise_for_status()
        return response.text

    def parse_new_movies(self, soup: BeautifulSoup) -> list[Movie]:
        """解析豆瓣新片榜"""
        movies: list[Movie] = []

        # 新片榜：div.indent > table > tr.item
        indent_div = soup.find("div", class_="indent")
        if not indent_div:
            return movies

        for rank, tr in enumerate(indent_div.find_all("tr", class_="item"), 1):
            # 海报图片
            img_tag = tr.find("a", class_="nbg")
            poster = ""
            title = ""
            url = ""
            if img_tag:
                poster = img_tag.find("img").get("src", "") if img_tag.find("img") else ""
                url = img_tag.get("href", "")

            # 标题区域
            pl2_div = tr.find("div", class_="pl2")
            if pl2_div:
                title_link = pl2_div.find("a")
                if title_link:
                    title = title_link.get_text(strip=True).split("/")[0].strip()

            # 详细信息（导演、演员等）
            desc_p = pl2_div.find("p") if pl2_div else None
            description = desc_p.get_text(strip=True) if desc_p else ""

            # 评分
            rating_span = tr.find("span", class_="rating_nums")
            rating = rating_span.get_text(strip=True) if rating_span else ""

            # 评价人数
            pl_span = tr.find("span", class_="pl")
            vote_text = ""
            if pl_span:
                match = re.search(r"\((\d+)", pl_span.get_text())
                if match:
                    vote_text = match.group(1)

            if title:
                movies.append(Movie(
                    rank=rank,
                    title=title,
                    title_foreign="",
                    rating=rating,
                    vote_count=vote_text,
                    description=description,
                    url=url,
                    poster=poster
                ))

        return movies

    def parse_weekly_hot(self, soup: BeautifulSoup) -> list[Movie]:
        """解析一周口碑榜"""
        movies: list[Movie] = []

        # 一周口碑榜：ul#listCont2 > li.clearfix
        ul = soup.find("ul", id="listCont2")
        if not ul:
            return movies

        for rank, li in enumerate(ul.find_all("li", class_="clearfix"), 1):
            name_div = li.find("div", class_="name")
            a = name_div.find("a") if name_div else None
            title = a.get_text(strip=True) if a else ""
            url = a.get("href", "") if a else ""

            # 排名变化（上/下/不变）
            change_span = li.find("span")
            change_text = ""
            if change_span:
                up_div = change_span.find("div", class_="up")
                down_div = change_span.find("div", class_="down")
                stay_div = change_span.find("div", class_="stay")
                if up_div:
                    change_text = f"+{up_div.get_text(strip=True)}"
                elif down_div:
                    change_text = f"-{down_div.get_text(strip=True)}"
                elif stay_div:
                    change_text = stay_div.get_text(strip=True)

            if title:
                movies.append(Movie(
                    rank=rank,
                    title=title,
                    title_foreign="",
                    rating="",
                    vote_count=change_text,
                    description="",
                    url=url,
                    poster=""
                ))

        return movies

    def parse_us_box(self, soup: BeautifulSoup) -> list[Movie]:
        """解析北美票房榜"""
        movies: list[Movie] = []

        # 北美票房榜：ul#listCont1 > li.clearfix
        ul = soup.find("ul", id="listCont1")
        if not ul:
            return movies

        for rank, li in enumerate(ul.find_all("li", class_="clearfix"), 1):
            box_div = li.find("div", class_="box_chart")
            a = box_div.find("a") if box_div else None
            title = a.get_text(strip=True) if a else ""
            url = a.get("href", "") if a else ""

            # 票房数据
            box_span = li.find("span", class_="box_chart_num")
            box_office = box_span.get_text(strip=True) if box_span else ""

            if title:
                movies.append(Movie(
                    rank=rank,
                    title=title,
                    title_foreign="",
                    rating="",
                    vote_count=box_office,
                    description="",
                    url=url,
                    poster=""
                ))

        return movies

    async def crawl(self) -> list[CrawlResult]:
        """执行爬取"""
        html = await self.fetch_page()
        soup = BeautifulSoup(html, "html.parser")

        results = [
            CrawlResult(section="豆瓣新片榜", movies=self.parse_new_movies(soup)),
            CrawlResult(section="一周口碑榜", movies=self.parse_weekly_hot(soup)),
            CrawlResult(section="北美票房榜", movies=self.parse_us_box(soup)),
        ]

        return results


def print_results(results: list[CrawlResult]):
    """格式化打印结果"""
    for result in results:
        print(f"\n{'='*60}")
        print(f"[{result.section}]")
        print('='*60)

        if not result.movies:
            print("  (no data)")
            continue

        for movie in result.movies:
            print(f"\n  {movie['rank']:2d}. {movie['title']}")
            if movie['rating']:
                print(f"      Rating: {movie['rating']} ({movie['vote_count']} votes)")
            elif movie['vote_count']:
                print(f"      Data: {movie['vote_count']}")
            if movie['description']:
                desc_preview = movie['description'][:80] + "..." if len(movie['description']) > 80 else movie['description']
                print(f"      Info: {desc_preview}")


async def main():
    """主入口"""
    print("[*] Fetching Douban movie charts...")
    print()

    async with DoubanChartCrawler() as crawler:
        results = await crawler.crawl()
        print_results(results)

    total = sum(len(r.movies) for r in results)
    print(f"\n[*] Done! Total {total} movies fetched")


if __name__ == "__main__":
    asyncio.run(main())
