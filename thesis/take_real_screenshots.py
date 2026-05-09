"""
Take REAL screenshots of the live AutoApply webapp at http://localhost:5001
Saves into thesis/screenshots/ overwriting the PIL mockups.
"""
from playwright.sync_api import sync_playwright
import os, time

SHOTS = r'd:\cv_portofolio\thesis\screenshots'
os.makedirs(SHOTS, exist_ok=True)
STATE_PATH = r'd:\cv_portofolio\webapp\user_data\1\playwright_state.json'

EMAIL    = 'mikhael.nabil.salama.rezk@gmail.com'
PASSWORD = 'Mikha@2001'

def shot(page, filename, full_page=True):
    path = os.path.join(SHOTS, filename)
    page.screenshot(path=path, full_page=full_page)
    size = os.path.getsize(path)
    print(f'Saved: {filename}  ({size:,} bytes)')

def scroll_to(page, selector_text):
    """Scroll the first element whose text includes selector_text into view."""
    page.evaluate(f"""
        const all = [...document.querySelectorAll('h1,h2,h3,h4,h5,.card-header,.section-title')];
        const el = all.find(e => e.textContent.includes({repr(selector_text)}));
        if (el) el.scrollIntoView({{block: 'start', behavior: 'instant'}});
    """)
    time.sleep(0.6)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--window-size=1920,1200'])
    ctx = browser.new_context(viewport={'width': 1920, 'height': 1200}, device_scale_factor=2)
    page = ctx.new_page()

    # ── fig01_login ───────────────────────────────────────────────────────────
    page.goto('http://localhost:5001/login', wait_until='networkidle')
    shot(page, 'fig01_login.png', full_page=True)

    # ── fig02_register ────────────────────────────────────────────────────────
    page.goto('http://localhost:5001/register', wait_until='networkidle')
    shot(page, 'fig02_register.png', full_page=True)

    # ── Log in with real credentials ──────────────────────────────────────────
    page.goto('http://localhost:5001/login', wait_until='networkidle')
    page.fill('input[name="email"], input[type="email"]', EMAIL)
    page.fill('input[name="password"], input[type="password"]', PASSWORD)
    page.click('button[type="submit"], input[type="submit"]')
    page.wait_for_load_state('networkidle')
    time.sleep(1.5)
    print(f'After login URL: {page.url}')

    # ── fig03_profile — full page scroll ──────────────────────────────────────
    page.goto('http://localhost:5001/profile', wait_until='networkidle')
    time.sleep(1)
    # scroll to bottom to ensure all fields rendered, then full_page captures all
    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(0.5)
    page.evaluate("window.scrollTo(0, 0);")
    time.sleep(0.3)
    shot(page, 'fig03_profile.png', full_page=True)

    # Also split: top half and bottom half via pixel crop
    from PIL import Image
    img = Image.open(os.path.join(SHOTS, 'fig03_profile.png'))
    W, H = img.size
    mid = H // 2
    img.crop((0, 0, W, mid)).save(os.path.join(SHOTS, 'fig03a_profile_top.png'), compress_level=0)
    img.crop((0, mid, W, H)).save(os.path.join(SHOTS, 'fig03b_profile_bottom.png'), compress_level=0)
    print(f'Saved: fig03a_profile_top.png  ({W}x{mid})')
    print(f'Saved: fig03b_profile_bottom.png  ({W}x{H-mid})')

    # ── Dashboard — load once ─────────────────────────────────────────────────
    page.goto('http://localhost:5001/dashboard', wait_until='networkidle')
    time.sleep(2)

    # fig04_dashboard — full dashboard page
    page.evaluate("window.scrollTo(0, 0);")
    time.sleep(0.4)
    shot(page, 'fig04_dashboard.png', full_page=True)

    # Split dashboard top (stats + buttons) and bottom (history table)
    img = Image.open(os.path.join(SHOTS, 'fig04_dashboard.png'))
    W, H = img.size
    # top ~40% of page
    top_h = min(950, H)
    img.crop((0, 0, W, top_h)).save(os.path.join(SHOTS, 'fig04a_dashboard_top.png'), compress_level=0)
    # bottom section — history/runs
    img.crop((0, top_h, W, H)).save(os.path.join(SHOTS, 'fig04b_dashboard_bottom.png'), compress_level=0)
    print(f'Saved: fig04a_dashboard_top.png')
    print(f'Saved: fig04b_dashboard_bottom.png')

    # Follow table validation image (used in thesis follow/unfollow procedure)
    page.goto('http://localhost:5001/dashboard', wait_until='networkidle')
    time.sleep(1)
    scroll_to(page, 'Followed Companies')
    shot(page, 'fig14_followed_companies_table.png', full_page=False)

    # fig05 — Applied Jobs / History section — scroll to it
    scroll_to(page, 'Applied')
    shot(page, 'fig05_history.png', full_page=False)

    # fig06 — Chrome Extension / Watch config section
    scroll_to(page, 'Chrome Extension')
    shot(page, 'fig06_watch_config.png', full_page=False)
    # if that didn't work try other headings
    if os.path.getsize(os.path.join(SHOTS, 'fig06_watch_config.png')) < 30000:
        scroll_to(page, 'External Watch')
        shot(page, 'fig06_watch_config.png', full_page=False)
    if os.path.getsize(os.path.join(SHOTS, 'fig06_watch_config.png')) < 30000:
        scroll_to(page, 'Download')
        shot(page, 'fig06_watch_config.png', full_page=False)

    # ── fig_run_now — click "Run Now" and capture the running state ───────────
    page.goto('http://localhost:5001/dashboard', wait_until='networkidle')
    time.sleep(1.5)
    page.evaluate("window.scrollTo(0, 0);")
    time.sleep(0.3)
    # Find and click Run Now button
    try:
        btn = page.locator('button:has-text("Run Now"), a:has-text("Run Now")').first
        btn.click()
        time.sleep(3)  # let the run start and UI update
        shot(page, 'fig_run_now.png', full_page=False)
        print('Saved: fig_run_now.png')
    except Exception as e:
        print(f'Run Now button not found: {e}')

    # ── fig_run_watch — reload dashboard, click "Run and Watch" ──────────────
    page.goto('http://localhost:5001/dashboard', wait_until='networkidle')
    time.sleep(1.5)
    page.evaluate("window.scrollTo(0, 0);")
    time.sleep(0.3)
    try:
        btn = page.locator('button:has-text("Run and Watch"), a:has-text("Run and Watch"), button:has-text("Watch"), a:has-text("Watch")').first
        btn.click()
        time.sleep(3)
        shot(page, 'fig_run_watch.png', full_page=False)
        print('Saved: fig_run_watch.png')
    except Exception as e:
        print(f'Run and Watch button not found: {e}')

    # ── Optional LinkedIn follow/unfollow evidence screenshots ─────────────
    try:
        if os.path.exists(STATE_PATH):
            li_ctx = browser.new_context(
                storage_state=STATE_PATH,
                viewport={'width': 1920, 'height': 1200},
                device_scale_factor=2,
            )
            li = li_ctx.new_page()
            li.goto('https://www.linkedin.com/feed/', wait_until='domcontentloaded', timeout=60000)
            time.sleep(2)
            shot(li, 'fig12_follow_feed.png', full_page=False)

            li.goto('https://www.linkedin.com/company/uber-com/', wait_until='domcontentloaded', timeout=60000)
            time.sleep(2)
            shot(li, 'fig13_follow_company_main_vs_sidebar.png', full_page=False)

            # Same company-page evidence used for unfollow-state discussion.
            shot(li, 'fig15_unfollow_main_button.png', full_page=False)
            li_ctx.close()
        else:
            print(f'LinkedIn state not found: {STATE_PATH} (skipping fig12/13/15)')
    except Exception as e:
        print(f'LinkedIn screenshot block failed: {e}')

    browser.close()

    print('\n=== All screenshots done! ===')
    for f in sorted(os.listdir(SHOTS)):
        size = os.path.getsize(os.path.join(SHOTS, f))
        print(f'  {f}: {size:,} bytes')
