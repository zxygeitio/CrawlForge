# CrawlForge

[![Stars](https://img.shields.io/github/stars/zxygeitio/CrawlForge?style=social)](https://github.com/zxygeitio/CrawlForge/stargazers)
[![Forks](https://img.shields.io/github/forks/zxygeitio/CrawlForge?style=social)](https://github.com/zxygeitio/CrawlForge/network/members)
[![License](https://img.shields.io/github/license/zxygeitio/CrawlForge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Last Commit](https://img.shields.io/github/last-commit/zxygeitio/CrawlForge/main)](https://github.com/zxygeitio/CrawlForge/commits)

**A powerful, stealthy crawler framework with anti-detection capabilities.**

CrawlForge is a production-ready Python web scraping framework built for challenging websites that employ advanced anti-bot measures. It combines TLS fingerprint bypass, stealth browser automation, and human behavior simulation to extract data reliably.

[English](README.md) | [中文](README_CN.md)

---

## Features

| Feature | Description |
|---------|-------------|
| **TLS/JA3/ JA4 Fingerprint Bypass** | Uses `curl_cffi` + TLS fingerprint analyzer |
| **Stealth Browser Automation** | Playwright with 20+ anti-detection hooks |
| **Human Behavior Simulation** | Mouse, touch, keyboard, scroll patterns |
| **Proxy Pool Manager** | Built-in proxy rotation with health scoring |
| **Adaptive Rate Limiting** | Token bucket + sliding window, auto-adjusts |
| **Captcha Solving** | Protocol-based slider + image captcha solver |
| **Chrome DevTools MCP** | Control Chrome remotely via MCP protocol |
| **Distributed Tasks** | Redis-based async task queue for scaling |
| **Monitor & Alert** | Real-time metrics with webhook notifications |
| **JS Hook Tools** | 15+ hook categories: crypto, wasm, sw, ws, etc |
| **AI Page Analyzer** | Structure analysis, captcha detection |
| **TLS Fingerprint Analyzer** | JA3/JA4 calculator and target fingerprinting |

---

## Quick Start

### Installation

```bash
git clone https://github.com/zxygeitio/CrawlForge.git
cd CrawlForge
pip install -r requirements.txt
playwright install chromium
```

### Basic Usage

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

### Async Concurrent Scraping

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

### CLI Mode

```bash
# Crawl a page
python -m src.cli crawl https://example.com -m curl -o result.json

# Show config
python -m src.cli config --show

# Interactive shell
python -m src.cli shell
```

---

## Request Methods

| Method | Use Case | Features |
|--------|---------|----------|
| `RequestMethod.REQUESTS` | Simple pages | Fast, lightweight |
| `RequestMethod.CURL_CFFI` | TLS-bypassed | JA3 fingerprint imitation |
| `RequestMethod.PLAYWRIGHT` | JS-rendered | Full browser execution |
| `RequestMethod.ASYNC_CURL` | High concurrency | Async aiohttp |

---

## Architecture

```
CrawlForge/
├── src/
│   ├── __init__.py            # 50+ exports
│   ├── advanced_crawler.py    # Core crawler
│   ├── stealth_browser.py     # 20+ anti-detection hooks
│   ├── humanizer.py           # Mouse/touch/keyboard/scroll
│   ├── proxy_manager.py       # Proxy pool with scoring
│   ├── rate_limiter.py        # Adaptive rate limiting
│   ├── captcha_solver.py      # Protocol + browser captcha
│   ├── config_manager.py      # YAML config loader
│   ├── data_processor.py      # Data extraction & cleaning
│   ├── monitor.py             # Metrics & alerts
│   ├── distributed_tasks.py    # Redis task queue
│   ├── js_hook_tools.py       # 15+ hook categories
│   ├── tls_fingerprint.py     # JA3/JA4 analyzer
│   ├── page_analyzer.py       # AI page structure analyzer
│   └── cli.py                 # CLI entry
├── tests/                     # 82 passing tests
├── demos/                     # Usage examples
└── docs/                      # Research docs
```

---

## Configuration

Create `config.yaml`:

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

## Docker Deployment

```bash
docker-compose up -d
```

---

## Use Cases

- **Web Scraping** — E-commerce, news, social platforms
- **Security Testing** — Test your site's bot protection
- **SEO Monitoring** — Track rankings and search results
- **Price Intelligence** — Monitor competitor pricing
- **Data Research** — Collect datasets for ML/AI training

---

## Contributing

Issues and PRs are welcome! Please read the documentation before contributing.

---

## License

MIT License
