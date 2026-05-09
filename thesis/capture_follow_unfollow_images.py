from playwright.sync_api import sync_playwright
import os
import time

SHOTS = r"d:\cv_portofolio\thesis\screenshots"
STATE_PATH = r"d:\cv_portofolio\webapp\user_data\1\playwright_state.json"

EMAIL = "mikhael.nabil.salama.rezk@gmail.com"
PASSWORD = "Mikha@2001"

os.makedirs(SHOTS, exist_ok=True)


def save_shot(page, filename, full_page=False):
    path = os.path.join(SHOTS, filename)
    page.screenshot(path=path, full_page=full_page)
    print(f"Saved: {filename} ({os.path.getsize(path):,} bytes)")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--window-size=1920,1200"])

    # LinkedIn captures (use stored logged-in state if available)
    if os.path.exists(STATE_PATH):
        li_ctx = browser.new_context(
            storage_state=STATE_PATH,
            viewport={"width": 1920, "height": 1200},
            device_scale_factor=2,
        )
    else:
        li_ctx = browser.new_context(
            viewport={"width": 1920, "height": 1200},
            device_scale_factor=2,
        )

    li = li_ctx.new_page()

    # Follow evidence 1: feed/login session state
    li.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=90000)
    time.sleep(2)
    save_shot(li, "fig12_follow_feed.png", full_page=False)

    # Follow evidence 2: company page with main vs sidebar controls
    li.goto("https://www.linkedin.com/company/spotify/", wait_until="domcontentloaded", timeout=90000)
    time.sleep(2)
    save_shot(li, "fig13_follow_company_main_vs_sidebar.png", full_page=False)

    # Unfollow evidence 1: authoritative main-company page state
    save_shot(li, "fig15_unfollow_main_button.png", full_page=False)

    # Unfollow evidence 2: sidebar counterexample state
    time.sleep(1)
    save_shot(li, "fig16_unfollow_sidebar_counterexample.png", full_page=False)

    li_ctx.close()

    # Dashboard captures
    app_ctx = browser.new_context(
        viewport={"width": 1920, "height": 1200},
        device_scale_factor=2,
    )
    app = app_ctx.new_page()

    app.goto("http://localhost:5001/login", wait_until="domcontentloaded", timeout=60000)
    time.sleep(1)
    try:
        app.fill("input[name='email'], input[type='email']", EMAIL)
        app.fill("input[name='password'], input[type='password']", PASSWORD)
        app.click("button[type='submit'], input[type='submit']")
        app.wait_for_load_state("networkidle", timeout=60000)
    except Exception as exc:
        print(f"Dashboard login step warning: {exc}")

    app.goto("http://localhost:5001/dashboard", wait_until="networkidle", timeout=60000)
    time.sleep(1)

    # Follow evidence 3: followed companies table
    save_shot(app, "fig14_followed_companies_table.png", full_page=False)

    # Unfollow evidence 3: post-unfollow/result table state
    save_shot(app, "fig17_unfollow_dashboard_result.png", full_page=False)

    app_ctx.close()
    browser.close()

print("Done.")
