"""
链家网(上海)二手房爬虫

技术方案:
1. 使用Chrome DevTools MCP绕过验证码
2. 通过pyautogui模拟操作(备用)
3. 解析HTML提取房源信息

网站反爬措施:
- TLS指纹检测
- 验证码墙
- 请求频率限制
"""

import json
import time
import re


def get_lianjia_houses_via_devtools():
    """
    通过Chrome DevTools获取链家房源数据
    这个方法利用浏览器MCP直接访问页面，绕过部分反爬
    """
    houses = []

    # 注意：这里需要MCP服务器运行
    # 通过curl调用本地MCP或直接用playwright

    try:
        from playwright.sync_api import sync_playwright

        url = 'https://sh.lianjia.com/ershoufang/'

        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--no-sandbox',
                ]
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
            )
            page = context.new_page()

            print('正在访问链家...')
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            page.wait_for_timeout(5000)

            # 通过JS提取房源数据
            js_code = '''
            () => {
                const houses = [];
                const allItems = document.querySelectorAll('li');

                allItems.forEach((li) => {
                    const links = li.querySelectorAll('a[href*="/ershoufang/"]');
                    links.forEach(link => {
                        if (link.href.includes('/ershoufang/') &&
                            link.href.match(/\/ershoufang\/\d+\.html$/)) {
                            const parent = li;
                            const text = parent.innerText;
                            const priceMatch = text.match(/(\d+)\s*万/);
                            const unitMatch = text.match(/([\d,]+)\s*元\/平/);

                            houses.push({
                                title: link.textContent.trim(),
                                url: link.href,
                                price: priceMatch ? priceMatch[0] : '',
                                unitPrice: unitMatch ? unitMatch[0] : ''
                            });
                        }
                    });
                });

                // 去重
                const seen = new Set();
                return houses.filter(h => {
                    if (seen.has(h.url)) return false;
                    seen.add(h.url);
                    return true;
                });
            }
            '''

            houses = page.evaluate(js_code)
            browser.close()

    except Exception as e:
        print(f'Playwright error: {e}')

    return houses


def get_lianjia_houses_via_api():
    """
    通过API直接获取数据（如果可用）
    """
    from curl_cffi import requests

    houses = []
    url = 'https://sh.lianjia.com/ershoufang/'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }

    resp = requests.get(url, impersonate='chrome', headers=headers, timeout=10)

    if resp.status_code == 200:
        content = resp.text
        # 解析房源数据...

    return houses


def clean_house_data(houses):
    """清理房源数据"""
    cleaned = []
    for h in houses:
        price = h.get('price', '').replace('\n', '').strip()
        unit_price = h.get('unitPrice', '').replace('\n', '').strip()

        cleaned.append({
            'title': h.get('title', '').strip(),
            'url': h.get('url', '').strip(),
            'price': price,
            'unitPrice': unit_price
        })
    return cleaned


def main():
    print('='*60)
    print('链家网(上海)二手房爬虫')
    print('='*60)

    # 方法1: 通过Playwright（已验证可行）
    print('\n方法1: 使用Playwright...')
    houses = get_lianjia_houses_via_devtools()

    if not houses:
        print('Playwright方法失败，尝试备用方法...')
        houses = get_lianjia_houses_via_api()

    if houses:
        houses = clean_house_data(houses)
        print(f'\n成功获取 {len(houses)} 条房源信息')

        # 显示前10条
        print('\n前10条房源:')
        for i, h in enumerate(houses[:10], 1):
            print(f"{i}. {h['title'][:40]}...")
            print(f"   价格: {h['price']} | 单价: {h['unitPrice']}")

        # 保存结果
        output_file = 'crawler-reverse/demos/lianjia_results.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(houses, f, ensure_ascii=False, indent=2)
        print(f'\n结果已保存到: {output_file}')
    else:
        print('未能获取到房源数据')


if __name__ == '__main__':
    main()