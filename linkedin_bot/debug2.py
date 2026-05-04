from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv(".env")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(storage_state="playwright_state.json")
    page = context.new_page()

    job_url = "https://www.linkedin.com/jobs/view/4401430501/"
    page.goto(job_url, wait_until="networkidle")
    page.wait_for_timeout(5000)

    print("URL:", page.url)

    # Try all the new selectors
    selectors = [
        "a[aria-label*='Easy Apply']",
        "a:has-text('Easy Apply')",
        "a[href*='openSDUIApplyFlow']",
        "button:has-text('Easy Apply')",
        "button[aria-label*='Easy Apply']",
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                print(f"FOUND: {sel!r} -> text={el.inner_text().strip()!r}, href={el.get_attribute('href')!r}")
            else:
                print(f"Not found: {sel!r}")
        except Exception as ex:
            print(f"Error {sel!r}: {ex}")

    # Also print any element containing "Easy Apply" text
    all_a = page.query_selector_all("a")
    for a in all_a:
        try:
            txt = a.inner_text().strip()
            aria = a.get_attribute("aria-label") or ""
            if "apply" in txt.lower() or "apply" in aria.lower():
                print(f"  ANCHOR: text={txt!r}, aria={aria!r}, href={a.get_attribute('href')!r}")
        except:
            pass

    context.close()
    browser.close()
