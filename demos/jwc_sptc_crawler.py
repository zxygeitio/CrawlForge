"""
jwc.sptc.edu.cn 通知公告爬虫

该网站使用复杂的反爬机制:
1. TLS指纹检测 - 使用curl_cffi模拟chrome指纹绕过
2. 字节码VM反爬 - 使用Playwright执行JS动态渲染页面
3. 编码问题 - 页面声明UTF-8但实际使用GBK

解决方案:
1. curl_cffi (impersonate='chrome') 绕过TLS检测
2. Playwright 渲染动态内容
3. 通过JS evaluate获取正确编码的数据
"""

import json
import time
from playwright.sync_api import sync_playwright


def crawl_jwc_notices():
    """爬取jwc.sptc.edu.cn通知公告"""
    url = 'https://jwc.sptc.edu.cn/'

    notices = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
        )
        page = context.new_page()

        print('正在访问 jwc.sptc.edu.cn ...')
        page.goto(url, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(3000)

        # 通过JS获取所有通知链接
        js_code = '''
        () => {
            const links = [];
            document.querySelectorAll('a').forEach(a => {
                if (a.href && a.href.includes('/info/')) {
                    const title = a.textContent.trim().substring(0, 200);
                    if (title.length > 5) {
                        links.push({
                            title: title,
                            href: a.href
                        });
                    }
                }
            });
            return links;
        }
        '''

        links = page.evaluate(js_code)

        # 去重
        seen = set()
        for link in links:
            if link['href'] not in seen:
                seen.add(link['href'])
                notices.append({
                    'title': link['title'],
                    'url': link['href']
                })

        print(f'找到 {len(notices)} 条通知公告')

        # 获取每条通知的详细内容
        detailed_notices = []
        for i, notice in enumerate(notices):
            print(f'  [{i+1}/{len(notices)}] 正在获取: {notice["title"][:30]}...')
            try:
                # 打开详情页
                page.goto(notice['url'], wait_until='networkidle', timeout=15000)
                page.wait_for_timeout(1000)

                # 获取页面内容
                content_js = '''
                () => {
                    const content = document.querySelector('.content, .news_content, #content, article, .main') || document.body;
                    return {
                        content: content.innerText || content.textContent || '',
                        title: document.title || '',
                        date: document.querySelector('.date, .time, .news_date, [class*="date"]')?.innerText || ''
                    };
                }
                '''
                detail = page.evaluate(content_js)

                notice['content'] = detail['content'][:500] if detail['content'] else ''
                notice['date'] = detail['date']
                notice['page_title'] = detail['title']

            except Exception as e:
                print(f'    获取详情失败: {e}')
                notice['content'] = ''
                notice['date'] = ''

            detailed_notices.append(notice)
            time.sleep(0.5)  # 避免请求过快

        browser.close()

    return detailed_notices


def main():
    print('='*60)
    print('jwc.sptc.edu.cn 通知公告爬虫')
    print('='*60)

    notices = crawl_jwc_notices()

    # 保存结果
    output_file = 'jwc_sptc_notices.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(notices, f, ensure_ascii=False, indent=2)

    print(f'\n结果已保存到: {output_file}')
    print(f'共获取 {len(notices)} 条通知公告')

    # 显示前5条
    print('\n前5条通知:')
    for i, n in enumerate(notices[:5]):
        print(f'  {i+1}. {n["title"]}')
        if n.get('date'):
            print(f'     日期: {n["date"]}')


if __name__ == '__main__':
    main()