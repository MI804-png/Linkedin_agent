from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv(".env")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(storage_state="playwright_state.json")
    page = context.new_page()

    page.goto("https://www.linkedin.com/jobs/view/4401430501/", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    # Save full HTML for inspection
    html = page.content()
    with open("logs/job_full.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("HTML saved, length:", len(html))

    # Get all buttons text
    buttons = page.query_selector_all("button")
    print("Total buttons:", len(buttons))
    for b in buttons:
        txt = (b.inner_text() or "").strip()
        aria = (b.get_attribute("aria-label") or "").strip()
        if txt or aria:
            print(f"  btn: text={txt[:50]!r} aria={aria[:50]!r}")

    context.close()
    browser.close()
