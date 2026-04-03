# CrawlForge

**一款强大的隐身爬虫框架，具备反检测能力。**

CrawlForge 是一个生产级 Python 网络爬虫框架，专为应对高级反爬虫措施而设计。它结合了 TLS 指纹绕过、隐身浏览器自动化和人类行为模拟，确保数据提取的可靠性。

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **TLS/JA3 指纹绕过** | 使用 `curl_cffi` 模拟真实浏览器 TLS 签名 |
| **隐身浏览器** | 基于 Playwright，移除自动化特征 |
| **人类行为模拟** | 鼠标轨迹、随机延迟、滚动模式 |
| **代理池管理** | 内置代理轮换与健康评分 |
| **自适应速率限制** | Token Bucket + 滑动窗口，自动适应服务器响应 |
| **验证码识别** | 支持滑块、图片、极验验证码 |
| **Chrome DevTools MCP** | 通过 MCP 协议远程控制 Chrome |
| **分布式任务** | 基于 Redis 的异步任务队列 |
| **监控告警** | 实时指标与 Webhook 通知 |
| **JS Hook 工具箱** | 拦截 XHR/Fetch、CryptoJS、存储操作 |

---

## 快速开始

### 安装

```bash
git clone https://github.com/zxygeitio/CrawlForge.git
cd CrawlForge
pip install -r requirements.txt
playwright install chromium
```

### 基础使用

```python
from src.advanced_crawler import AdvancedCrawler, CrawlerConfig, RequestMethod

config = CrawlerConfig(
    name="my_crawler",
    timeout=30,
    download_delay=1.0,
    use_stealth_browser=True
)

crawler = AdvancedCrawler(config)

def parser(response):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    return {
        "title": soup.find("title").text,
        "content": soup.get_text(strip=True)[:500]
    }

result = crawler.crawl_page(
    url="https://example.com",
    parser=parser,
    use_method=RequestMethod.CURL_CFFI
)

crawler.close()
```

### 异步并发爬取

```python
import asyncio
from src.advanced_crawler import AdvancedCrawler, CrawlerConfig, RequestMethod

async def main():
    config = CrawlerConfig(name="async_demo", rate_limit=20.0)
    crawler = AdvancedCrawler(config)

    urls = [f"https://example.com/page/{i}" for i in range(10)]

    tasks = [
        crawler.async_crawl_page(url, parser, RequestMethod.ASYNC_CURL)
        for url in urls
    ]

    results = await asyncio.gather(*tasks)
    crawler.close()
    return results

asyncio.run(main())
```

### CLI 模式

```bash
# 爬取页面
python -m src.cli crawl https://example.com -m curl -o result.json

# 显示配置
python -m src.cli config --show

# 交互式 Shell
python -m src.cli shell
```

---

## 请求方法

| 方法 | 适用场景 | 特点 |
|------|---------|------|
| `RequestMethod.REQUESTS` | 简单页面 | 轻量快速 |
| `RequestMethod.CURL_CFFI` | TLS 绕过 | JA3 指纹模拟 |
| `RequestMethod.PLAYWRIGHT` | JS 渲染 | 完整浏览器执行 |
| `RequestMethod.ASYNC_CURL` | 高并发 | 异步 aiohttp |

---

## 目录结构

```
CrawlForge/
├── src/
│   ├── __init__.py            # 43 个导出
│   ├── advanced_crawler.py    # 核心爬虫类
│   ├── stealth_browser.py     # Playwright 隐身封装
│   ├── humanizer.py           # 人类行为模拟
│   ├── proxy_manager.py       # 代理池管理
│   ├── rate_limiter.py        # 自适应速率限制
│   ├── captcha_solver.py      # 验证码识别
│   ├── config_manager.py      # YAML 配置加载
│   ├── data_processor.py      # 数据提取与清洗
│   ├── monitor.py             # 监控与告警
│   ├── distributed_tasks.py    # Redis 分布式任务
│   ├── js_hook_tools.py       # JS 拦截工具
│   └── cli.py                 # CLI 入口
├── tests/                     # 82 个测试
├── demos/                     # 示例代码
└── docs/                      # 研究文档
```

---

## 配置

创建 `config.yaml`:

```yaml
crawler:
  timeout: 30
  retry_times: 3
  delay_range: [1, 3]

proxy:
  enabled: true
  pool_size: 10
  min_score: 60

rate_limit:
  requests_per_minute: 60
  burst_size: 10

stealth:
  humanize_mouse: true
  random_scroll: true
  block_ads: true
```

---

## Docker 部署

```bash
docker-compose up -d
```

---

## 使用场景

- **网页爬取** — 电商、新闻、社交平台
- **安全测试** — 测试站点抗爬虫能力
- **SEO 监控** — 追踪排名和搜索结果
- **价格情报** — 监控竞品价格
- **数据研究** — 为 ML/AI 收集训练数据集

---

## 贡献

欢迎提交 Issue 和 PR！

---

## 许可

MIT License
