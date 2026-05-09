"""Capture webapp screenshots for thesis document."""
import os, time
os.makedirs('d:/cv_portofolio/thesis/screenshots', exist_ok=True)
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=['--no-sandbox'])
    ctx = b.new_context(viewport={'width': 1280, 'height': 800})
    page = ctx.new_page()

    base = 'http://localhost:5001'

    # --- Login page ---
    page.goto(f'{base}/login')
    page.wait_for_load_state('networkidle')
    page.screenshot(path='d:/cv_portofolio/thesis/screenshots/fig_login.png', full_page=False)
    print('fig_login saved')

    # --- Register page ---
    page.goto(f'{base}/register')
    page.wait_for_load_state('networkidle')
    page.screenshot(path='d:/cv_portofolio/thesis/screenshots/fig_register.png', full_page=False)
    print('fig_register saved')

    # --- Authenticate ---
    page.goto(f'{base}/login')
    page.fill('input[type=email]', 'mikhael@autoapply.com')
    page.fill('input[type=password]', 'Thesis2026!')
    page.click('button[type=submit]')
    page.wait_for_url(f'{base}/**', timeout=8000)
    time.sleep(1)

    # --- Dashboard ---
    page.goto(f'{base}/dashboard')
    page.wait_for_load_state('networkidle')
    page.screenshot(path='d:/cv_portofolio/thesis/screenshots/fig_dashboard.png', full_page=True)
    print('fig_dashboard saved')

    # --- Profile page (top) ---
    page.goto(f'{base}/profile')
    page.wait_for_load_state('networkidle')
    page.screenshot(path='d:/cv_portofolio/thesis/screenshots/fig_profile_top.png', full_page=False)
    print('fig_profile_top saved')

    # --- Profile page (full) ---
    page.screenshot(path='d:/cv_portofolio/thesis/screenshots/fig_profile_full.png', full_page=True)
    print('fig_profile_full saved')

    # --- History page ---
    hist_url = f'{base}/history'
    page.goto(hist_url)
    page.wait_for_load_state('networkidle')
    page.screenshot(path='d:/cv_portofolio/thesis/screenshots/fig_history.png', full_page=True)
    print('fig_history saved')

    # --- Watch/Config page ---
    for path_try in ['/watch', '/config', '/settings', '/watch_config']:
        try:
            page.goto(f'{base}{path_try}')
            page.wait_for_load_state('networkidle')
            page.screenshot(
                path=f'd:/cv_portofolio/thesis/screenshots/fig_watch_config.png',
                full_page=True
            )
            print(f'fig_watch_config saved from {path_try}')
            break
        except Exception as e:
            print(f'  {path_try} failed: {e}')

    b.close()
print('All screenshots done')
