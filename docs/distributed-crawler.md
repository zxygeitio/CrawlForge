# 分布式爬虫与存储架构

## 1. 分布式爬虫架构

### 1.1 分层设计

```
┌─────────────────────────────────────────────────────────┐
│                      调度层 (Scheduler)                   │
│  - URL去重 (Redis Set)                                   │
│  - 任务分发 (Celery/RabbitMQ)                            │
│  - 优先级队列 (Priority Queue)                            │
└─────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Worker Node 1 │  │   Worker Node 2 │  │   Worker Node N │
│   - Crawler     │  │   - Crawler     │  │   - Crawler     │
│   - Processor   │  │   - Processor   │  │   - Processor   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────┐
│                      存储层 (Storage)                     │
│  - MongoDB (爬虫数据)                                    │
│  - Redis (缓存/队列)                                     │
│  - S3/OSS (文件/图片)                                   │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Scrapy-Redis 方案

```python
# settings.py
BOT_NAME = "my_project"

# Redis配置
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

# Scrapy-Redis配置
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
SCHEDULER = "scrapy_redis.scheduler.Scheduler"
SCHEDULER_PERSIST = True  # 持久化队列

# 爬虫配置
CONCURRENT_REQUESTS = 16
DOWNLOAD_DELAY = 0.5
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 10

# MongoDBPipeline配置
MONGODB_HOST = "localhost"
MONGODB_PORT = 27017
MONGODB_DB = "crawler"
```

```python
# pipelines.py
import pymongo

class MongoPipeline:
    def __init__(self, mongo_uri, mongo_db):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri = crawler.settings.get('MONGODB_URI'),
            mongo_db = crawler.settings.get('MONGODB_DB')
        )

    def open_spider(self, spider):
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]

    def close_spider(self, spider):
        self.client.close()

    def process_item(self, item, spider):
        # URL去重
        if self.db[spider.name].find_one({"url": item["url"]}):
            return item

        self.db[spider.name].insert_one(dict(item))
        return item
```

### 1.3 Celery 方案

```python
# tasks.py
from celery import Celery
from pymongo import MongoClient
import requests

app = Celery('crawler', broker='redis://localhost:6379/0')

def get_db():
    return MongoClient('mongodb://localhost:27017')['crawler']

@app.task(bind=True, max_retries=3)
def crawl_page(self, url):
    """单个页面抓取任务"""
    try:
        resp = requests.get(url, timeout=10)

        if resp.status_code == 429:
            # 被限流,等待后重试
            raise self.retry(countdown=60)

        if resp.status_code == 200:
            data = parse_page(resp.text)

            # 存储到MongoDB
            db = get_db()
            db.pages.update_one(
                {"url": url},
                {"$set": data},
                upsert=True
            )

            return {"status": "success", "url": url}

        return {"status": "error", "code": resp.status_code}

    except requests.RequestException as e:
        # 网络错误,重试
        raise self.retry(exc=e, countdown=30)

@app.task
def crawl_site(root_url):
    """整站爬取任务"""
    urls = extract_urls(root_url)  # 获取所有URL

    # 批量分发任务
    for url in urls:
        crawl_page.delay(url)

@app.task
def crawl_incremental():
    """增量爬取 - 只爬取新URL"""
    db = get_db()
    new_urls = check_new_urls(db)  # 对比sitemap等

    for url in new_urls:
        crawl_page.delay(url)
```

## 2. 代理池管理

```python
import redis
import random
import time
from typing import Optional

class ProxyPool:
    """基于Redis的代理池,实现代理评分机制"""

    def __init__(self, redis_url: str):
        self.db = redis.from_url(redis_url)
        self.pool_key = "proxy:pool"
        self.fail_key = "proxy:failures"

    def add_proxy(self, proxy: str, score: int = 100):
        """添加代理到池中"""
        self.db.zadd(self.pool_key, {proxy: score})

    def get_proxy(self) -> Optional[str]:
        """获取可用代理 (分数>60)"""
        candidates = self.db.zrangebyscore(
            self.pool_key, 60, 100
        )
        if candidates:
            return random.choice(candidates)
        return None

    def report_success(self, proxy: str):
        """代理可用,增加分数"""
        self.db.zincrby(self.pool_key, 5, proxy)
        # 确保分数不超过100
        score = self.db.zscore(self.pool_key, proxy)
        if score > 100:
            self.db.zadd(self.pool_key, {proxy: 100})

    def report_failure(self, proxy: str):
        """代理失败,减少分数"""
        self.db.zincrby(self.pool_key, -10, proxy)

    def get_stats(self) -> dict:
        """获取代理池统计"""
        all_proxies = self.db.zrange(self.pool_key, 0, -1, withscores=True)
        return {
            "total": len(all_proxies),
            "available": len([p for p, s in all_proxies if s > 60]),
            "scores": {p: int(s) for p, s in all_proxies}
        }

# 使用示例
pool = ProxyPool("redis://localhost:6379/0")

def fetch_with_proxy(url: str) -> requests.Response:
    proxy = pool.get_proxy()

    if not proxy:
        # 无代理,直接请求
        return requests.get(url)

    try:
        resp = requests.get(url, proxies={
            "http": proxy,
            "https": proxy
        }, timeout=10)

        if resp.status_code == 200:
            pool.report_success(proxy)
            return resp
        else:
            pool.report_failure(proxy)
            return resp

    except requests.RequestException:
        pool.report_failure(proxy)
        raise
```

## 3. 增量爬取与断点恢复

```python
import hashlib
from datetime import datetime
from pymongo import MongoClient

class IncrementalCrawler:
    """增量爬虫,支持断点恢复"""

    def __init__(self, db_name: str):
        self.db = MongoClient()[db_name]
        self.crawled_urls = set(
            d["url"] for d in self.db.crawled.find({}, {"url": 1})
        )
        self.pending_urls = []

    def is_crawled(self, url: str) -> bool:
        return url in self.crawled_urls

    def mark_crawled(self, url: str, data: dict = None):
        """标记URL已爬取"""
        self.crawled_urls.add(url)
        record = {
            "url": url,
            "crawled_at": datetime.utcnow(),
            "hash": hashlib.md5(url.encode()).hexdigest()
        }
        if data:
            record["data"] = data

        self.db.crawled.update_one(
            {"url": url},
            {"$set": record},
            upsert=True
        )

    def add_pending(self, urls: list):
        """添加待爬URL"""
        new_urls = [u for u in urls if not self.is_crawled(u)]
        self.db.pending.insert_many([
            {"url": u, "added_at": datetime.utcnow()}
            for u in new_urls
        ])

    def get_next(self, batch_size: int = 10) -> list:
        """获取下一批待爬URL"""
        cursor = self.db.pending.find().limit(batch_size)
        return [doc["url"] for doc in cursor]

    def remove_pending(self, url: str):
        """从待爬队列移除"""
        self.db.pending.delete_one({"url": url})

    def save_checkpoint(self, state: dict):
        """保存检查点"""
        self.db.checkpoints.update_one(
            {"_id": "current"},
            {"$set": {**state, "updated_at": datetime.utcnow()}},
            upsert=True
        )

    def load_checkpoint(self) -> dict:
        """加载检查点"""
        return self.db.checkpoints.find_one({"_id": "current"}) or {}
```

## 4. 数据存储方案

### 4.1 MongoDB Schema

```javascript
// houses collection
{
    "_id": ObjectId,
    "url": "https://sh.lianjia.com/ershoufang/123.html",
    "title": "万科品质小区...",
    "price": "598万",
    "unit_price": "56,640元/平",
    "area": "105.58平米",
    "layout": "3室2厅",
    "floor": "中楼层(共11层)",
    "year": "2000年",
    "direction": "南 北",
    "decoration": "简装",
    "location": {
        "district": "闵行",
        "板块": "七宝",
        "xiaoqu": "万科优诗美地"
    },
    "tags": ["VR房源", "房本满五年"],
    "crawled_at": ISODate("2026-04-02"),
    "updated_at": ISODate("2026-04-02")
}

// 索引
db.houses.createIndex({"url": 1}, {unique: true})
db.houses.createIndex({"price": 1})
db.houses.createIndex({"location.district": 1})
db.houses.createIndex({"crawled_at": 1})
```

### 4.2 数据导出格式

```python
# 导出为不同格式
import pandas as pd

def export_data(format: str):
    df = pd.DataFrame(list(db.houses.find()))

    if format == "csv":
        df.to_csv("data.csv", index=False)
    elif format == "parquet":
        df.to_parquet("data.parquet")
    elif format == "json":
        df.to_json("data.json", orient="records", force_ascii=False)
    elif format == "excel":
        df.to_excel("data.xlsx")
```

## 5. 监控与报警

```python
from prometheus_client import Counter, Histogram, Gauge
import redis

# Prometheus指标
crawl_requests = Counter(
    'crawler_requests_total',
    'Total crawl requests',
    ['status', 'source']
)

crawl_duration = Histogram(
    'crawler_request_duration_seconds',
    'Crawl request duration',
    ['source']
)

proxy_pool_size = Gauge(
    'proxy_pool_size',
    'Current proxy pool size',
    ['status']  # available, unavailable, total
)

# 报警规则示例 (Prometheus AlertManager)
alert_rules = """
groups:
- name: crawler
  rules:
  - alert: HighErrorRate
    expr: rate(crawler_requests_total{status="error"}[5m]) > 0.1
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate in crawler"

  - alert: ProxyPoolExhausted
    expr: proxy_pool_size{status="available"} < 5
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "Proxy pool running low"
"""
```

---

*Last Updated: 2026-04-02*
