"""
命令行入口
支持 crawl, scrape, config 等命令
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from src.advanced_crawler import AdvancedCrawler, CrawlerConfig, RequestMethod
from src.config_manager import ConfigManager, create_default_config
from src.logger import setup_logger, get_logger
from src.js_hook_tools import JSHookManager


def create_parser() -> argparse.ArgumentParser:
    """创建命令行解析器"""
    parser = argparse.ArgumentParser(
        prog="crawler",
        description="爬虫逆向框架 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s crawl https://example.com                    # 爬取单个页面
  %(prog)s crawl https://example.com --method playwright  # 使用Playwright
  %(prog)s config --create-default                     # 创建默认配置
  %(prog)s config --show                               # 显示当前配置
  %(prog)s shell                                        # 交互式Shell
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # crawl 命令
    crawl_parser = subparsers.add_parser("crawl", help="爬取页面")
    crawl_parser.add_argument("url", help="目标URL")
    crawl_parser.add_argument("-m", "--method", choices=["requests", "curl", "playwright", "async_curl"],
                              default="curl", help="请求方法")
    crawl_parser.add_argument("-o", "--output", help="输出文件路径")
    crawl_parser.add_argument("-c", "--config", help="配置文件路径")
    crawl_parser.add_argument("--parser", default="json", choices=["json", "html", "text"],
                              help="解析方式")
    crawl_parser.add_argument("--hooks", nargs="+",
                              choices=["network", "crypto", "storage", "fingerprint", "antidebug", "slider"],
                              help="安装的Hook")

    # config 命令
    config_parser = subparsers.add_parser("config", help="配置管理")
    config_parser.add_argument("--create-default", action="store_true",
                               help="创建默认配置文件")
    config_parser.add_argument("--show", action="store_true",
                               help="显示当前配置")
    config_parser.add_argument("-o", "--output", default="config.yaml",
                               help="输出路径")
    config_parser.add_argument("-c", "--config", help="配置文件路径")

    # shell 命令
    subparsers.add_parser("shell", help="交互式Python Shell")

    # version
    parser.add_argument("--version", action="version", version="%(prog)s 2.0.0")

    return parser


def crawl_url(
    url: str,
    method: str = "curl",
    output: Optional[str] = None,
    config_path: Optional[str] = None,
    parser_mode: str = "json",
    hooks: Optional[list] = None,
):
    """爬取单个URL"""
    # 加载配置
    if config_path:
        manager = ConfigManager()
        config = manager.load_from_yaml(config_path)
    else:
        config = CrawlerConfig()

    # 设置日志
    setup_logger(log_level=config.log_level, log_dir="logs")

    # 创建爬虫
    crawler = AdvancedCrawler(config)
    logger = get_logger()

    # 选择请求方法
    method_map = {
        "requests": RequestMethod.REQUESTS,
        "curl": RequestMethod.CURL_CFFI,
        "playwright": RequestMethod.PLAYWRIGHT,
        "async_curl": RequestMethod.ASYNC_CURL,
    }
    use_method = method_map.get(method, RequestMethod.CURL_CFFI)

    # 定义解析函数
    def html_parser(response) -> dict:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        return {
            "title": soup.find("title").text if soup.find("title") else "",
            "content": soup.get_text(strip=True)[:1000],
            "status_code": response.status_code,
        }

    def json_parser(response) -> dict:
        try:
            return {"data": response.json(), "status_code": response.status_code}
        except json.JSONDecodeError:
            return html_parser(response)

    def text_parser(response) -> dict:
        return {"content": response.text[:1000], "status_code": response.status_code}

    parser_map = {
        "html": html_parser,
        "json": json_parser,
        "text": text_parser,
    }
    parser = parser_map.get(parser_mode, json_parser)

    # 执行爬取
    logger.info(f"开始爬取: {url} (method={method})")
    result = crawler.crawl_page(url, parser, use_method)

    # 输出结果
    if result:
        logger.success(f"爬取成功")
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"结果已保存: {output}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        logger.error("爬取失败")
        sys.exit(1)

    crawler.close()


def show_config(config_path: Optional[str] = None):
    """显示配置"""
    if config_path:
        manager = ConfigManager()
        config = manager.load_from_yaml(config_path)
        print(json.dumps(vars(config), indent=2, ensure_ascii=False))
    else:
        config = CrawlerConfig()
        print(json.dumps(vars(config), indent=2, ensure_ascii=False))


def create_config(output: str = "config.yaml"):
    """创建默认配置"""
    path = create_default_config(output)
    print(f"默认配置已创建: {path}")


def interactive_shell():
    """交互式Shell"""
    import code
    from src import (
        AdvancedCrawler, CrawlerConfig, RequestMethod,
        ProxyPoolManager, ProxyPoolConfig,
        TokenBucket, MultiLimiter,
        StealthBrowser, StealthConfig,
        JSHookManager,
    )

    banner = """
    爬虫逆向框架 v2.0 - 交互式Shell
    可用对象:
      - AdvancedCrawler, CrawlerConfig, RequestMethod
      - ProxyPoolManager, ProxyPoolConfig
      - TokenBucket, MultiLimiter
      - StealthBrowser, StealthConfig
      - JSHookManager
    """

    variables = globals().copy()
    variables.update(locals())

    code.InteractiveConsole(variables).interact(banner)


def main():
    """主入口"""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "crawl":
        crawl_url(
            url=args.url,
            method=args.method,
            output=args.output,
            config_path=args.config,
            parser_mode=args.parser,
            hooks=args.hooks,
        )
    elif args.command == "config":
        if args.create_default:
            create_config(args.output)
        elif args.show:
            show_config(args.config)
    elif args.command == "shell":
        interactive_shell()


if __name__ == "__main__":
    main()
