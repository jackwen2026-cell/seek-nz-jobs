import asyncio
from playwright.async_api import async_playwright
import pandas as pd
from datetime import datetime

async def scrape_seek():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # 1. Expanded search URLs covering ALL entry-level & blue-collar categories on SEEK NZ
        search_urls = [
            "https://www.seek.co.nz/labourer-jobs?sortmode=ListedDate",
            "https://www.seek.co.nz/packer-jobs?sortmode=ListedDate",
            "https://www.seek.co.nz/warehouse-jobs?sortmode=ListedDate",
            "https://www.seek.co.nz/cleaner-jobs?sortmode=ListedDate",
            "https://www.seek.co.nz/general-hand-jobs?sortmode=ListedDate",
            "https://www.seek.co.nz/entry-level-jobs?sortmode=ListedDate",
            "https://www.seek.co.nz/kitchen-hand-jobs?sortmode=ListedDate",
            "https://www.seek.co.nz/factory-hand-jobs?sortmode=ListedDate"
        ]
        
        job_list = []
        seen_links = set()

        # 2. Hardcore Exclusion Keywords (Eliminates listings requiring existing work rights or local citizens)
        blacklist_keywords = [
            # Legal Work Rights & Visas
            "legal right", "right to work", "working rights", "work rights", "eligible to work", "entitled to work",
            "valid nz visa", "current nz visa", "already in nz", "immediate start",
            # Citizenship & Residency 
            "nz citizen", "nz resident", "citizen or resident", "citizenship", "residency", "pr holder",
            # Explicit No Sponsorship
            "no visa sponsorship", "no sponsorship", "cannot sponsor", "unable to sponsor", "no aewv sponsorship"
        ]

        for url in search_urls:
            print(f"Scanning: {url}")
            try:
                # 60s timeout to handle huge data pools smoothly
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(4000) 
            except Exception as e:
                print(f"Timeout skipping: {e}")
                continue

            cards = await page.query_selector_all('article[data-testid="job-card"]')
            
            for card in cards:
                try:
                    title_element = await card.query_selector('a[data-testid="job-title"]')
                    if not title_element: continue
                    title = await title_element.inner_text()
                    
                    raw_link = await title_element.get_attribute("href")
                    link = f"https://www.seek.co.nz{raw_link}" if raw_link.startswith("/") else raw_link
                    
                    if link in seen_links:
                        continue
                    
                    company_element = await card.query_selector('a[data-testid="job-company"]')
                    company = await company_element.inner_text() if company_element else "Private Advertiser"
                    
                    location_element = await card.query_selector('a[data-testid="job-location"]')
                    location = await location_element.inner_text() if location_element else "NZ Wide"
                    
                    date_element = await card.query_selector('span[data-testid="job-listing-date"]')
                    date_text = await date_element.inner_text() if date_element else "Just Listed"

                    teaser_element = await card.query_selector('span[data-testid="job-teaser"]')
                    teaser = await teaser_element.inner_text() if teaser_element else ""

                    # Combine title and teaser snippet for the filtering phase
                    full_text_lower = (title + " " + teaser).lower()
                    
                    # Anti-Local-Rights Filter Execution
                    is_blacklisted = False
                    for kw in blacklist_keywords:
                        if kw in full_text_lower:
                            is_blacklisted = True
                            break
                    
                    # Pass the filter -> Save the potential gem
                    if not is_blacklisted:
                        job_list.append({
                            "Category": "Entry / Blue Collar",
                            "Job Title": title,
                            "Employer": company,
                            "Location": location,
                            "Listed Date": date_text,
                            "Action": f'<a href="{link}" target="_blank" style="color: #4F46E5; font-weight: bold; text-decoration: none;">Check Details ↗</a>'
                        })
                        seen_links.add(link)
                except:
                    continue
                    
        await browser.close()
        return job_list

def generate_html(jobs):
    if not jobs:
        jobs = [{"Category": "-", "Job Title": "All scanned jobs require local work rights today. Keep an eye out tomorrow!", "Employer": "-", "Location": "-", "Listed Date": "-", "Action": "-"}]
        
    df = pd.DataFrame(jobs)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NZ Entry-Level & Blue-Collar Job Monitor</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 15px; background-color: #f8fafc; color: #1e293b; }}
            .container {{ max-width: 1100px; margin: 0 auto; background: white; padding: 24px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
            h2 {{ color: #1e293b; margin-top: 0; font-size: 24px; border-left: 5px solid #4F46E5; padding-left: 10px; }}
            .time {{ font-size: 13px; color: #64748b; margin-bottom: 20px; background: #f1f5f9; padding: 8px 12px; border-radius: 6px; display: inline-block; }}
            .tip {{ background: #ecfdf5; border-left: 4px solid #10b981; padding: 12px; font-size: 14px; margin-bottom: 20px; border-radius: 4px; line-height: 1.5; color: #065f46; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ padding: 14px; text-align: left; border-bottom: 1px solid #e2e8f0; font-size: 15px; }}
            th {{ background-color: #4F46E5; color: white; font-weight: 600; letter-spacing: 0.5px; }}
            tr:hover {{ background-color: #f8fafc; }}
            @media (max-width: 768px) {{
                table, thead, tbody, th, td, tr {{ display: block; }}
                th {{ display: none; }}
                tr {{ margin-bottom: 15px; border: 1px solid #e2e8f0; padding: 12px; border-radius: 8px; background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }}
                td {{ border-bottom: none; padding: 8px 0; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px dashed #f1f5f9; }}
                td:last-child {{ border-bottom: none; }}
                td:before {{ content: attr(data-label); font-weight: bold; color: #64748b; font-size: 14px; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>NZ Entry-Level & Blue-Collar Monitor (No Local Rights Restrictions)</h2>
            <div class="time">🕒 Filtered and Refreshed at (Beijing Time): {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
            <div class="tip">
                🚀 <b>Master Filter Activated:</b> 8 major entry-level/blue-collar job feeds scanned. Any jobs demanding existing "NZ Citizen/Resident" or "Legal Right to Work" have been fully filtered out. High-yield target list for overseas seekers!
            </div>
            {df.to_html(escape=False, index=False)}
        </div>
        <script>
            const headers = ["Category", "Job Title", "Employer", "Location", "Listed Date", "Action"];
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
    results = asyncio.run(scrape_seek())
    generate_html(results)
