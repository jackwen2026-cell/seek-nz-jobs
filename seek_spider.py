import asyncio
from playwright.async_api import async_playwright
from datetime import datetime

# ─────────────────────────────────────────────
# 1. 搜索类别（体力工作）
# ─────────────────────────────────────────────
SEARCH_URLS = [
    "https://www.seek.co.nz/labourer-jobs",
    "https://www.seek.co.nz/warehouse-jobs",
    "https://www.seek.co.nz/manufacturing-jobs",
    "https://www.seek.co.nz/general-hand-jobs",
    "https://www.seek.co.nz/construction-jobs",
    "https://www.seek.co.nz/trades-services-jobs",
]

# ─────────────────────────────────────────────
# 2. 签证/身份限制关键词
# ─────────────────────────────────────────────
VISA_BLACKLIST = [
    "nz citizen", "new zealand citizen",
    "nz resident", "new zealand resident",
    "permanent resident", "pr required", "pr holder",
    "right to work", "must have right to work",
    "must be eligible to work", "eligibility to work",
    "valid work visa", "valid visa", "work visa required",
    "valid nz work visa", "current work visa",
    "no visa sponsorship", "unable to sponsor", "cannot sponsor",
    "sponsorship not available", "not able to sponsor",
    "citizenship required", "residency required",
    "must have nz", "must hold nz", "must be nz",
    "legally entitled to work", "lawful right to work",
    "unrestricted right", "full working rights",
    "open work visa only",
]

# ─────────────────────────────────────────────
# 3. 排除职种关键词
# ─────────────────────────────────────────────
JOB_BLACKLIST = [
    "driver", "delivery driver", "courier", "truck driver",
    "forklift driver", "machine operator",
    "manager", "supervisor", "team leader",
    "engineer", "technician", "mechanic",
]

# ─────────────────────────────────────────────
# 4. 排除大城市
# ─────────────────────────────────────────────
BIG_CITIES = [
    "auckland", "central auckland", "east auckland",
    "west auckland", "north auckland", "south auckland",
    "manukau", "waitakere",
    "wellington", "lower hutt", "upper hutt", "porirua",
    "christchurch", "selwyn",
]


# ─────────────────────────────────────────────
# 核心爬虫
# ─────────────────────────────────────────────
async def scrape_seek():
    stats = {
        "total_scanned": 0,
        "visa_filtered": 0,
        "job_filtered": 0,
        "city_filtered": 0,
        "saved": 0,
    }
    job_list = []
    seen_links = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        for base_url in SEARCH_URLS:
            category = base_url.rstrip("/").split("/")[-1].replace("-jobs", "")
            print(f"\n📂 [{category}] scanning...")

            for page_num in range(1, 4):  # 搜索 3 页
                url = f"{base_url}?page={page_num}&sortmode=ListedDate"
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(1800)
                except Exception as e:
                    print(f"  ⚠ page {page_num} failed: {e}")
                    continue

                cards = await page.query_selector_all('article[data-automation="normalJob"]')
                stats["total_scanned"] += len(cards)
                print(f"  page {page_num}: {len(cards)} listings")

                for card in cards:
                    title_el = await card.query_selector('[data-automation="jobTitle"]')
                    loc_el   = await card.query_selector('[data-automation="jobLocation"]')
                    comp_el  = await card.query_selector('[data-automation="jobCompany"]')
                    if not title_el or not loc_el:
                        continue

                    title = (await title_el.inner_text()).strip()
                    loc   = (await loc_el.inner_text()).strip()
                    comp  = (await comp_el.inner_text()).strip() if comp_el else "—"
                    title_lower = title.lower()
                    loc_lower   = loc.lower()

                    # 过滤：职种
                    if any(kw in title_lower for kw in JOB_BLACKLIST):
                        stats["job_filtered"] += 1
                        continue

                    # 过滤：大城市
                    if any(city in loc_lower for city in BIG_CITIES):
                        stats["city_filtered"] += 1
                        continue

                    # 过滤：签证（标题层）
                    if any(kw in title_lower for kw in VISA_BLACKLIST):
                        stats["visa_filtered"] += 1
                        continue

                    # 去重
                    link_el = await card.query_selector("a")
                    if not link_el:
                        continue
                    href = await link_el.get_attribute("href")
                    if not href or href in seen_links:
                        continue
                    seen_links.add(href)

                    full_url = f"https://www.seek.co.nz{href}" if href.startswith("/") else href

                    # 过滤：签证（详情页全文）
                    try:
                        dp = await context.new_page()
                        await dp.goto(full_url, wait_until="domcontentloaded", timeout=15000)
                        await dp.wait_for_timeout(800)
                        body_text = (await dp.inner_text("body")).lower()
                        await dp.close()
                        if any(kw in body_text for kw in VISA_BLACKLIST):
                            stats["visa_filtered"] += 1
                            continue
                    except Exception:
                        pass

                    stats["saved"] += 1
                    job_list.append({
                        "title":    title,
                        "company":  comp,
                        "location": loc,
                        "category": category,
                        "url":      full_url,
                    })
                    print(f"  ✅ {title} | {loc}")

        await browser.close()

    stats["filtered_out"] = (
        stats["visa_filtered"] + stats["job_filtered"] + stats["city_filtered"]
    )
    return job_list, stats


# ─────────────────────────────────────────────
# 生成 index.html 报告
# ─────────────────────────────────────────────
def generate_html(job_list, stats, output_path="index.html"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    filter_rate = (
        f"{stats['filtered_out'] / stats['total_scanned'] * 100:.0f}%"
        if stats["total_scanned"] > 0 else "—"
    )

    if not job_list:
        rows_html = '<tr><td colspan="4" class="empty">⚠ No jobs found.</td></tr>'
    else:
        rows_html = ""
        for i, job in enumerate(job_list):
            cat = job["category"].replace("-", " ").title()
            rows_html += f"""
        <tr style="animation-delay:{i*0.03:.2f}s">
          <td class="td-title">
            <a href="{job['url']}" target="_blank">{job['title']}</a>
            <span class="badge">{cat}</span>
          </td>
          <td class="td-co">{job['company']}</td>
          <td class="td-loc">{job['location']}</td>
          <td class="td-btn">
            <a href="{job['url']}" target="_blank" class="btn">Apply ↗</a>
          </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SEEK NZ Jobs — {now}</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#f5f3ee;--sur:#fff;--ink:#1a1a18;--muted:#7a7870;--bdr:#e0ddd6;
      --grn:#1a6b4a;--grn-lt:#e8f3ee;--org:#c45c1a;
      --mono:'DM Mono',monospace;--sans:'DM Sans',sans-serif}}
body{{font-family:var(--sans);background:var(--bg);color:var(--ink);padding:48px 32px 96px}}
.topbar{{max-width:1080px;margin:0 auto 40px;display:flex;justify-content:space-between;
         align-items:flex-start;padding-bottom:28px;border-bottom:2px solid var(--ink);flex-wrap:wrap;gap:24px}}
.logo{{font-family:var(--mono);font-size:12px;color:var(--muted);letter-spacing:.06em;text-transform:uppercase;margin-bottom:8px}}
h1{{font-size:clamp(28px,4vw,44px);font-weight:700;letter-spacing:-.03em;line-height:1.05}}
h1 em{{font-style:normal;color:var(--grn)}}
.sub{{font-size:13px;color:var(--muted);margin-top:6px;font-weight:300}}
.run{{text-align:right;font-family:var(--mono);font-size:12px;color:var(--muted);line-height:1.9}}
.stats{{max-width:1080px;margin:0 auto 32px;display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.stat{{background:var(--sur);border:1px solid var(--bdr);padding:20px 22px}}
.stat-n{{font-family:var(--mono);font-size:38px;line-height:1}}
.stat-n.g{{color:var(--grn)}}.stat-n.o{{color:var(--org)}}
.stat-lbl{{font-size:10px;color:var(--muted);margin-top:8px;text-transform:uppercase;letter-spacing:.08em;font-weight:500}}
.stat-sub{{font-size:12px;color:var(--muted);margin-top:4px}}
.wrap{{max-width:1080px;margin:0 auto;background:var(--sur);border:1px solid var(--bdr);overflow-x:auto}}
.thead{{display:flex;justify-content:space-between;align-items:center;
        padding:14px 20px;border-bottom:1px solid var(--bdr);background:#fafaf8}}
.tlbl{{font-family:var(--mono);font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em}}
.cnt{{font-family:var(--mono);font-size:11px;background:var(--grn-lt);color:var(--grn);padding:4px 12px;border-radius:2px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
thead th{{text-align:left;font-size:10px;font-weight:500;text-transform:uppercase;
          letter-spacing:.1em;color:var(--muted);padding:12px 20px;
          border-bottom:1px solid var(--bdr);background:#fafaf8;font-family:var(--mono)}}
tr{{animation:ri .35s ease both;border-bottom:1px solid var(--bdr);transition:background .12s}}
tr:last-child{{border-bottom:none}}tr:hover{{background:#fafaf8}}
@keyframes ri{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:translateY(0)}}}}
td{{padding:14px 20px;vertical-align:middle}}
.td-title a{{color:var(--ink);text-decoration:none;font-weight:500;display:block}}
.td-title a:hover{{color:var(--grn);text-decoration:underline}}
.badge{{display:inline-block;margin-top:5px;font-size:10px;font-family:var(--mono);
        color:var(--muted);background:var(--bg);padding:2px 8px;border:1px solid var(--bdr)}}
.td-co,.td-loc{{color:var(--muted);font-size:13px;width:18%}}
.td-btn{{width:10%;text-align:right}}
.btn{{display:inline-block;font-family:var(--mono);font-size:11px;font-weight:500;
      color:var(--grn);border:1px solid var(--grn);padding:6px 14px;text-decoration:none;
      transition:all .15s;white-space:nowrap}}
.btn:hover{{background:var(--grn);color:#fff}}
.empty{{text-align:center;padding:60px;color:var(--muted)}}
.foot{{max-width:1080px;margin:20px auto 0;display:flex;gap:20px;flex-wrap:wrap;
       font-family:var(--mono);font-size:11px;color:var(--muted)}}
.foot b{{color:var(--org)}}
@media(max-width:700px){{
  .stats{{grid-template-columns:repeat(2,1fr)}}
  .td-co,.td-loc{{display:none}}
}}
</style>
</head>
<body>
<div class="topbar">
  <div>
    <div class="logo">// seek.co.nz · auto scan</div>
    <h1>NZ <em>Labour</em> Jobs</h1>
    <div class="sub">Labourer · Warehouse · Manufacturing · Construction · Trades · General Hand<br>
    Excludes big cities &amp; visa-required roles</div>
  </div>
  <div class="run">Updated {now}<br>3 pages × {len(SEARCH_URLS)} categories</div>
</div>
<div class="stats">
  <div class="stat"><div class="stat-n">{stats['total_scanned']}</div><div class="stat-lbl">Scanned</div><div class="stat-sub">total listings</div></div>
  <div class="stat"><div class="stat-n o">{stats['visa_filtered']}</div><div class="stat-lbl">Visa / Rights</div><div class="stat-sub">sponsorship needed</div></div>
  <div class="stat"><div class="stat-n o">{stats['city_filtered'] + stats['job_filtered']}</div><div class="stat-lbl">City / Role</div><div class="stat-sub">excluded</div></div>
  <div class="stat"><div class="stat-n g">{stats['saved']}</div><div class="stat-lbl">Qualified</div><div class="stat-sub">ready to apply</div></div>
</div>
<div class="wrap">
  <div class="thead">
    <span class="tlbl">Results</span>
    <span class="cnt">{stats['saved']} jobs</span>
  </div>
  <table>
    <thead><tr><th>Job Title</th><th>Company</th><th>Location</th><th></th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>
<div class="foot">
  <span>Visa removed: <b>{stats['visa_filtered']}</b></span>
  <span>Role removed: <b>{stats['job_filtered']}</b></span>
  <span>City removed: <b>{stats['city_filtered']}</b></span>
  <span>Filter rate: <b>{filter_rate}</b></span>
</div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✅ Saved → {output_path}")


async def main():
    print("🔍 SEEK NZ Scanner starting...\n")
    job_list, stats = await scrape_seek()
    print(f"\n{'─'*40}")
    print(f"  Scanned : {stats['total_scanned']}")
    print(f"  Visa ❌  : {stats['visa_filtered']}")
    print(f"  City ❌  : {stats['city_filtered']}")
    print(f"  Role ❌  : {stats['job_filtered']}")
    print(f"  ✅ Saved : {stats['saved']}")
    print(f"{'─'*40}\n")
    generate_html(job_list, stats, "index.html")


if __name__ == "__main__":
    asyncio.run(main())
