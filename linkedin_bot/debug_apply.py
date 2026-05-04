from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os

load_dotenv(".env")

APPLY_URL = "https://www.linkedin.com/jobs/view/4407350660/apply/?openSDUIApplyFlow=true&trackingId=QER2TrHMT5KV5Xe28qXz0A%3D%3D"
JOB_URL   = "https://www.linkedin.com/jobs/view/4407350660/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(storage_state="playwright_state.json")
    page = context.new_page()

    # --- 1. Check the job page for the apply element ---
    print("=== JOB PAGE ===")
    page.goto(JOB_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    print("URL after load:", page.url)

    for sel in [
        "a[aria-label*='Easy Apply']",
        "a[href*='openSDUIApplyFlow']",
        "a:has-text('Easy Apply')",
        "button:has-text('Easy Apply')",
        "button[aria-label*='Easy Apply']",
    ]:
        el = page.query_selector(sel)
        if el:
            print(f"FOUND {sel}: text={el.inner_text().strip()!r} href={el.get_attribute('href')!r}")
        else:
            print(f"miss  {sel}")

    # --- 2. Navigate directly to the Easy Apply flow URL ---
    print("\n=== APPLY FLOW PAGE ===")
    page.goto(APPLY_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    print("URL after load:", page.url)

    # All inputs/selects/textareas
    for el in page.query_selector_all("input, select, textarea, button"):
        tag = el.evaluate("e => e.tagName").lower()
        typ = el.get_attribute("type") or ""
        lbl = el.get_attribute("aria-label") or ""
        ph  = el.get_attribute("placeholder") or ""
        txt = ""
        if tag == "button":
            try: txt = el.inner_text().strip()
            except: pass
        print(f"  <{tag} type={typ!r}> aria={lbl!r} placeholder={ph!r} text={txt!r}")

    # Save HTML for deep inspection
    with open("logs/apply_flow.html", "w", encoding="utf-8") as f:
        f.write(page.content())
    print("\nApply flow HTML saved to logs/apply_flow.html")

    context.close()
    browser.close()
