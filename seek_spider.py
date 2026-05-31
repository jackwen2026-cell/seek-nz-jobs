import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import random

# 1. 扫描范围：蓝领核心类目
SEARCH_URLS = [
    "https://www.seek.co.nz/labourer-jobs?sortmode=ListedDate",
    "https://www.seek.co.nz/warehouse-jobs?sortmode=ListedDate",
    "https://www.seek.co.nz/manufacturing-jobs?sortmode=ListedDate",
    "https://www.seek.co.nz/general-hand-jobs?sortmode=ListedDate"
]

# 2. 终极过滤器：同时包含（排雷 + 司机过滤 + 地区限制）
BLACKLIST_KEYWORDS = [
    "driver", "delivery", "courier", "truck", "driving", "transport", # 司机排雷
    "legal right", "right to work", "nz citizen", "nz resident", "pr holder", # 身份排雷
    "no visa sponsorship", "cannot sponsor" # 签证排雷
]

# 核心搜索策略：只看偏远地区（不在这些大城市里的岗位才有机会）
TARGET_LOCATIONS = ["auckland", "wellington", "christchurch"]

async def scrape_seek():
    stats = {"total_scanned": 0, "filtered_out": 0, "saved": 0}
    job_list = []
    seen_links = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for url in SEARCH_URLS:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            
            cards = await page.query_selector_all('article[data-automation="normalJob"]')
            
            for card in cards:
                stats["total_scanned"] += 1
                
                # 获取信息
                title = await (await card.query_selector('[data-automation="jobTitle"]')).inner_text()
                loc = await (await card.query_selector('[data-automation="jobLocation"]')).inner_text()
                
                # A. 司机排雷 + 身份排雷
                if any(kw in title.lower() for kw in BLACKLIST_KEYWORDS):
                    stats["filtered_out"] += 1
                    continue
                
                # B. 偏远地区优先：如果工作地点不在大城市，视为更有潜力的冷门岗
                # 这里我们反过来：如果岗位在奥克兰/惠灵顿，它会被标记为“竞争高”，我们过滤掉
                if any(city in loc.lower() for city in TARGET_LOCATIONS):
                    stats["filtered_out"] += 1
                    continue
                
                # 存活下来的：偏远地区 + 无身份歧视 + 非司机
                stats["saved"] += 1
                link = await (await card.query_selector("a")).get_attribute("href")
                job_list.append({
                    "Job Title": title,
                    "Location": loc,
                    "Action": f'<a href="https://www.seek.co.nz{link}" target="_blank">View Role ↗</a>'
                })
        await browser.close()
        return job_list, stats

# ... (generate_html 保持不变)
