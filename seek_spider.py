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
        
        # Pure English channels for NZ blue-collar jobs with AEWV
        search_urls = [
            "https://www.seek.co.nz/labourer-aewv-jobs?sortmode=ListedDate",
            "https://www.seek.co.nz/packer-aewv-jobs?sortmode=ListedDate",
            "https://www.seek.co.nz/warehouse-aewv-jobs?sortmode=ListedDate",
            "https://www.seek.co.nz/cleaner-aewv-jobs?sortmode=ListedDate",
            "https://www.seek.co.nz/general-hand-aewv-jobs?sortmode=ListedDate"
        ]
        
        job_list = []
        seen_links = set()

        for url in search_urls:
            print(f"Scanning: {url}")
            try:
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

                    text_to_check = (title + teaser).lower()
                    if "aewv" in text_to_check or "sponsorship" in text_to_check or "accredited" in text_to_check:
                        job_list.append({
                            "Category": "Blue Collar / AEWV",
                            "Job Title": title,
                            "Employer": company,
                            "Location": location,
                            "Listed Date": date_text,
                            "Action": f'<a href="{link}" target="_blank" style="color: #007A87; font-weight: bold; text-decoration: none;">Apply Now ↗</a>'
                        })
                        seen_links.add(link)
                except:
                    continue
                    
        await browser.close()
        return job_list

def generate_html(jobs):
    if not jobs:
        jobs = [{"Category": "-", "Job Title": "No new jobs found matching AEWV keywords today. Please refresh later.", "Employer": "-", "Location": "-", "Listed Date": "-", "Action": "-"}]
        
    df = pd.DataFrame(jobs)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NZ AEWV Job Monitor (Blue Collar)</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 15px; background-color: #f8fafc; color: #1e293b; }}
            .container {{ max-width: 1100px; margin: 0 auto; background: white; padding: 24px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
            h2 {{ color: #0f172a; margin-top: 0; font-size: 24px; border-left: 5px solid #007A87; padding-left: 10px; }}
            .time {{ font-size: 13px; color: #64748b; margin-bottom: 20px; background: #f1f5f9; padding: 8px 12px; border-radius: 6px; display: inline-block; }}
            .tip {{ background: #e0f2fe; border-left: 4px solid #0284c7; padding: 12px; font-size: 14px; margin-bottom: 20px; border-radius: 4px; line-height: 1.5; color: #0369a1; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ padding: 14px; text-align: left; border-bottom: 1px solid #e2e8f0; font-size: 15px; }}
            th {{ background-color: #007A87; color: white; font-weight: 600; letter-spacing: 0.5px; }}
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
            <h2>New Zealand AEWV Job Monitor (Labour / Packing / Logistics)</h2>
            <div class="time">🕒 Last updated (NZT/AU Local): {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
            <div class="tip">
                📌 <b>Job Hunting Tip:</b> This dashboard monitors SEEK NZ for roles explicitly mentioning <b>AEWV, Visa Sponsorship, or Accredited Employer</b>. Roles update automatically twice a day.
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
