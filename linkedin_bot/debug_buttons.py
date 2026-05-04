from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv(".env")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(storage_state="playwright_state.json")
    page = context.new_page()

    url = "https://www.linkedin.com/jobs/search/?keywords=Full+Stack+Developer&location=Hungary&f_LF=f_AL"
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    for _ in range(3):
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(800)

    anchors = page.query_selector_all("a")
    job_links = []
    for a in anchors:
        href = a.get_attribute("href") or ""
        if "/jobs/view/" in href:
            clean = href.split("?")[0]
            if clean not in job_links:
                job_links.append(clean)

    print("Jobs found:", len(job_links))

    for jl in job_links[:3]:
        full_url = ("https://www.linkedin.com" + jl) if jl.startswith("/") else jl
        print("\n--- Job:", full_url)
        page.goto(full_url, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        buttons = page.query_selector_all("button")
        for b in buttons:
            txt = (b.inner_text() or "").strip()
            aria = (b.get_attribute("aria-label") or "").strip()
            if "apply" in txt.lower() or "apply" in aria.lower():
                print(f"  APPLY BUTTON -> text={txt!r}, aria={aria!r}")

    context.close()
    browser.close()
