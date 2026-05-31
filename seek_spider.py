import asyncio
from playwright.async_api import async_playwright
import pandas as pd
from datetime import datetime
import random

# 定义更宽泛的搜索 URL
SEARCH_URLS = [
    "https://www.seek.co.nz/labourer-jobs",
    "https://www.seek.co.nz/packer-jobs",
    "https://www.seek.co.nz/warehouse-jobs"
]

# 排雷关键词库
BLACKLIST = ["citizen", "resident", "work rights", "valid visa", "nz only"]

async def scrape_seek():
    stats = {"total_scanned": 0, "filtered_out": 0, "saved": 0}
    jobs = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        for url in SEARCH_URLS:
            await page.goto(url, wait_until="networkidle") # 确保所有 JS 加载完毕
            await page.wait_for_timeout(5000) # 强制给动态内容留出 5 秒加载时间
            
            # 使用更底层的选择器定位所有文章节点
            cards = await page.query_selector_all('article')
            stats["total_scanned"] += len(cards)
            
            for card in cards:
                try:
                    # 尝试从 h3 标签中获取标题
                    title_el = await card.query_selector('h3')
                    if not title_el: continue
                    title = await title_el.inner_text()
                    
                    # 获取详情链接
                    link_el = await card.query_selector('a')
                    link = await link_el.get_attribute('href')
                    full_link = f"https://www.seek.co.nz{link}" if link.startswith('/') else link
                    
                    # 简单过滤本地人要求
                    if any(kw in title.lower() for kw in BLACKLIST):
                        stats["filtered_out"] += 1
                        continue
                    
                    stats["saved"] += 1
                    jobs.append({"Job": title, "Link": full_link})
                except:
                    continue
        await browser.close()
    return jobs, stats

# ... (generate_html 部分保持不变)
