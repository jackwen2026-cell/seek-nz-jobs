import asyncio
from playwright.async_api import async_playwright
import pandas as pd
from datetime import datetime
import random

# ================= 配置区 =================
# 蓝领与基础工作扫描渠道
SEARCH_URLS = [
    "https://www.seek.co.nz/labourer-jobs?sortmode=ListedDate",
    "https://www.seek.co.nz/packer-jobs?sortmode=ListedDate",
    "https://www.seek.co.nz/warehouse-jobs?sortmode=ListedDate",
    "https://www.seek.co.nz/cleaner-jobs?sortmode=ListedDate",
    "https://www.seek.co.nz/general-hand-jobs?sortmode=ListedDate"
]

# 严格排雷词库（包含任何一个都会被无情剔除）
BLACKLIST = [
    "legal right", "right to work", "working rights", "work rights", "eligible to work", "entitled to work",
    "nz citizen", "nz resident", "citizen or resident", "citizenship", "residency", "pr holder",
    "no visa sponsorship", "no sponsorship", "cannot sponsor", "unable to sponsor", "valid visa", "already in nz"
]
# ==========================================

async def scrape_seek():
    # 统计数据
    stats = {"total_scanned": 0, "filtered_out": 0, "saved": 0}
    job_list = []
    seen_links = set()

    async with async_playwright() as p:
        # 1. 启动浏览器时加入反爬虫伪装参数
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled", # 禁用自动化标记
                "--disable-infobars",
                "--window-size=1920,1080"
            ]
        )
        
        # 2. 伪装真实的设备环境指纹
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-NZ",
            timezone_id="Pacific/Auckland"
        )
        page = await context.new_page()
        
        # 隐藏 webdriver 属性 (反爬核心)
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for url in SEARCH_URLS:
            print(f"[*] 正在扫描: {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # 随机停留 3 到 6 秒，模仿人类阅读
                await page.wait_for_timeout(random.randint(3000, 6000)) 
            except Exception as e:
                print(f"[!] 访问超时: {url} | 错误: {e}")
                continue

            # 获取所有职位卡片 (兼容两种常见的 SEEK 页面结构)
            cards = await page.query_selector_all('article[data-testid="job-card"]')
            if not cards:
                cards = await page.query_selector_all('article') # 备用选择器
                
            stats["total_scanned"] += len(cards)
            
            for card in cards:
                try:
                    title_el = await card.query_selector('a[data-testid="job-title"]')
                    if not title_el: continue
                    title = await title_el.inner_text()
                    
                    raw_link = await title_el.get_attribute("href")
                    link = f"https://www.seek.co.nz{raw_link}" if raw_link.startswith("/") else raw_link
                    
                    if link in seen_links:
                        continue
                    seen_links.add(link)
                    
                    company_el = await card.query_selector('a[data-testid="job-company"]')
                    company = await company_el.inner_text() if company_el else "Private Advertiser"
                    
                    location_el = await card.query_selector('a[data-testid="job-location"]')
                    location = await location_el.inner_text() if location_el else "NZ Wide"
                    
                    date_el = await card.query_selector('span[data-testid="job-listing-date"]')
                    date_text = await date_el.inner_text() if date_el else "Recent"

                    teaser_el = await card.query_selector('span[data-testid="job-teaser"]')
                    teaser = await teaser_el.inner_text() if teaser_el else ""

                    # 将标题和摘要合并，转为小写进行排雷
                    full_text = (title + " " + teaser).lower()
                    
                    # 排雷逻辑
                    is_blacklisted = any(kw in full_text for kw in BLACKLIST)
                    
                    if is_blacklisted:
                        stats["filtered_out"] += 1
                        continue
                        
                    # 存活下来的岗位
                    stats["saved"] += 1
                    job_list.append({
                        "Job Title": title,
                        "Employer": company,
                        "Location": location,
                        "Listed Date": date_text,
                        "Action": f'<a href="{link}" target="_blank" style="color: #ffffff; background-color: #4F46E5; padding: 6px 12px; border-radius: 4px; font-weight: bold; text-decoration: none; display: inline-block; text-align: center;">View Role ↗</a>'
                    })
                except Exception as e:
                    print(f"[!] 解析卡片出错: {e}")
                    continue
                    
        await browser.close()
        return job_list, stats

def generate_html(jobs, stats):
    # 处理空数据的情况
    if not jobs:
        jobs = [{"Job Title": "No matching jobs found today.", "Employer": "-", "Location": "-", "Listed Date": "-", "Action": "-"}]
        
    df = pd.DataFrame(jobs)
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NZ Blue-Collar Job Radar</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background-color: #f1f5f9; color: #1e293b; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); }}
            h2 {{ color: #0f172a; margin-top: 0; font-size: 28px; border-bottom: 2px solid #e2e8f0; padding-bottom: 15px; }}
            
            /* 数据看板样式 */
            .dashboard {{ display: flex; gap: 20px; margin-bottom: 25px; flex-wrap: wrap; }}
            .stat-card {{ flex: 1; min-width: 200px; padding: 20px; border-radius: 8px; text-align: center; font-weight: bold; }}
            .stat-scanned {{ background-color: #f8fafc; border: 1px solid #e2e8f0; color: #475569; }}
            .stat-filtered {{ background-color: #fef2f2; border: 1px solid #fecaca; color: #dc2626; }}
            .stat-saved {{ background-color: #f0fdf4; border: 1px solid #bbf7d0; color: #16a34a; }}
            .stat-num {{ font-size: 32px; display: block; margin-top: 10px; }}
            
            .time-banner {{ font-size: 14px; color: #64748b; margin-bottom: 20px; }}
            
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ padding: 16px; text-align: left; border-bottom: 1px solid #f1f5f9; font-size: 15px; }}
            th {{ background-color: #f8fafc; color: #475569; font-weight: 600; text-transform: uppercase; font-size: 13px; letter-spacing: 0.5px; }}
            tr:hover {{ background-color: #f8fafc; }}
            
            @media (max-width: 768px) {{
                table, thead, tbody, th, td, tr {{ display: block; }}
                th {{ display: none; }}
                tr {{ margin-bottom: 15px; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }}
                td {{ border-bottom: none; padding: 10px 0; display: flex; flex-direction: column; gap: 5px; }}
                td:last-child {{ margin-top: 10px; border-top: 1px dashed #e2e8f0; padding-top: 15px; }}
                td:before {{ content: attr(data-label); font-size: 12px; font-weight: 700; color: #94a3b8; text-transform: uppercase; }}
                .dashboard {{ flex-direction: column; gap: 10px; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🇳🇿 New Zealand Pro Job Radar</h2>
            <div class="time-banner">🕒 Data synced securely at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
            
            <div class="dashboard">
                <div class="stat-card stat-scanned">
                    Jobs Scanned
                    <span class="stat-num">{stats['total_scanned']}</span>
                </div>
                <div class="stat-card stat-filtered">
                    Local-Only Jobs Removed
                    <span class="stat-num">{stats['filtered_out']}</span>
                </div>
                <div class="stat-card stat-saved">
                    Overseas-Friendly Potential
                    <span class="stat-num">{stats['saved']}</span>
                </div>
            </div>

            {df.to_html(escape=False, index=False)}
        </div>
        <script>
            const headers = ["Job Title", "Employer", "Location", "Listed Date", "Action"];
            document.querySelectorAll('tbody tr').forEach(tr => {{
                tr.querySelectorAll('td').forEach((td, i) => {{
                    td.setAttribute('data-label', headers[i]);
                }});
            }});
        </script>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    jobs, stats = asyncio.run(scrape_seek())
    generate_html(jobs, stats)
