import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import random

# 1. 核心搜索分类
SEARCH_URLS = [
    "https://www.seek.co.nz/labourer-jobs",
    "https://www.seek.co.nz/warehouse-jobs",
    "https://www.seek.co.nz/manufacturing-jobs",
    "https://www.seek.co.nz/general-hand-jobs"
]

# 2. 终极过滤词库（Visa + 司机 + 身份）
BLACKLIST = [
    # 身份限制
    "nz citizen", "nz resident", "right to work", "valid visa", "citizenship", "pr holder",
    # 司机/运输限制
    "driver", "delivery", "courier", "truck", "transport", "driving", "forklift" 
]

# 3. 大城市过滤（这里填入你要排除的城市）
BIG_CITIES = ["auckland", "wellington", "christchurch", "central auckland"]

async def scrape_seek():
    stats = {"total_scanned": 0, "filtered_out": 0, "saved": 0}
    job_list = []
    seen_links = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for base_url in SEARCH_URLS:
            # 自动翻 3 页
            for page_num in range(1, 4):
                url = f"{base_url}?page={page_num}&sortmode=ListedDate"
                try:
                    await page.goto(url, wait_until="domcontentloaded")
                    await page.wait_for_timeout(2000)
                except: continue
                
                cards = await page.query_selector_all('article[data-automation="normalJob"]')
                stats["total_scanned"] += len(cards)
                
                for card in cards:
                    title_el = await card.query_selector('[data-automation="jobTitle"]')
                    loc_el = await card.query_selector('[data-automation="jobLocation"]')
                    if not title_el or not loc_el: continue
                    
                    title = await title_el.inner_text()
                    loc = await loc_el.inner_text()
                    
                    # === 核心过滤器 ===
                    # 1. 标题检查 (Visa/司机/身份)
                    if any(bad_word in title.lower() for bad_word in BLACKLIST):
                        stats["filtered_out"] += 1
                        continue
                    
                    # 2. 地区检查 (剔除大城市)
                    if any(city in loc.lower() for city in BIG_CITIES):
                        stats["filtered_out"] += 1
                        continue
                    
                    # === 如果通过以上所有关卡 ===
                    link = await (await card.query_selector("a")).get_attribute("href")
                    if link in seen_links: continue
                    seen_links.add(link)
                    
                    stats["saved"] += 1
                    job_list.append({
                        "Job Title": title,
                        "Location": loc,
                        "Action": f'<a href="https://www.seek.co.nz{link}" target="_blank">View ↗</a>'
                    })
        await browser.close()
        return job_list, stats

# ... (之后的 generate_html 函数代码保持你之前的样子即可)
