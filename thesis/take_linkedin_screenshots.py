"""
Capture LinkedIn Easy Apply workflow screenshots for thesis.
Logs in, navigates to jobs, opens Easy Apply modal and screenshots each step.
Does NOT submit — closes the modal at the review step.
Also captures: notifications, job search, job with Applied status.
"""
from playwright.sync_api import sync_playwright
import os, time

SHOTS = r'd:\cv_portofolio\thesis\screenshots'
os.makedirs(SHOTS, exist_ok=True)

EMAIL    = 'mikhael.nabil.salama.rezk@gmail.com'
PASSWORD = 'Mikha@2001'

# A known Easy Apply job URL — Full Stack Developer in Hungary
SEARCH_URL = 'https://www.linkedin.com/jobs/search/?keywords=Full%20Stack%20Developer&location=Hungary&f_AL=true&f_TPR=r604800'

def shot(page, filename, full_page=False):
    path = os.path.join(SHOTS, filename)
    page.screenshot(path=path, full_page=full_page)
    size = os.path.getsize(path)
    print(f'  Saved: {filename}  ({size:,} bytes)')

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--window-size=1280,900', '--start-maximized'],
    )
    ctx = browser.new_context(
        viewport={'width': 1280, 'height': 900},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        locale='en-US',
    )
    page = ctx.new_page()

    # ── Login ─────────────────────────────────────────────────────────────────
    print('Logging in to LinkedIn...')
    page.goto('https://www.linkedin.com/login', wait_until='networkidle')
    time.sleep(1)
    page.fill('#username', EMAIL)
    page.fill('#password', PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')
    time.sleep(3)
    print(f'  URL after login: {page.url}')

    # ── fig_li_notifications — notifications page ─────────────────────────────
    print('\n[1/6] Notifications page...')
    page.goto('https://www.linkedin.com/notifications/', wait_until='networkidle')
    time.sleep(2)
    shot(page, 'fig_li_notifications.png', full_page=False)

    # ── fig_li_jobs_search — job search results with Easy Apply filter ─────────
    print('\n[2/6] Job search page...')
    page.goto(SEARCH_URL, wait_until='networkidle')
    time.sleep(3)
    shot(page, 'fig_li_jobs_search.png', full_page=False)

    # ── Find an Easy Apply job and open it ────────────────────────────────────
    print('\n[3/6] Finding a job to click...')
    try:
        # Click the first job in the list
        job_card = page.locator('.job-card-container, .jobs-search-results__list-item').first
        job_card.click()
        time.sleep(2)
        shot(page, 'fig_li_job_view.png', full_page=False)
        print('  fig_li_job_view saved')
    except Exception as e:
        print(f'  Could not click job card: {e}')
        shot(page, 'fig_li_job_view.png', full_page=False)

    # ── Open Easy Apply modal ─────────────────────────────────────────────────
    print('\n[4/6] Opening Easy Apply modal...')
    try:
        easy_apply_btn = page.locator('.jobs-apply-button, button:has-text("Easy Apply")').first
        easy_apply_btn.wait_for(timeout=5000)
        easy_apply_btn.click()
        time.sleep(2)

        # Step 1 — Contact Info (0%)
        shot(page, 'fig_li_apply_step1_contact.png', full_page=False)
        print('  Step 1 (Contact Info) saved')

        # Click Next to reach Resume step
        next_btn = page.locator('button:has-text("Next"), button[aria-label="Continue to next step"]').first
        if next_btn.is_visible():
            next_btn.click()
            time.sleep(1.5)
            shot(page, 'fig_li_apply_step2_resume.png', full_page=False)
            print('  Step 2 (Resume) saved')

            # Click Next again for additional questions or review
            next_btn2 = page.locator('button:has-text("Next"), button[aria-label="Continue to next step"]').first
            if next_btn2.is_visible():
                next_btn2.click()
                time.sleep(1.5)
                shot(page, 'fig_li_apply_step3_questions.png', full_page=False)
                print('  Step 3 (Questions/Review) saved')

                # Try one more next for review page
                next_btn3 = page.locator('button:has-text("Next"), button:has-text("Review"), button[aria-label="Continue to next step"]').first
                if next_btn3.is_visible():
                    next_btn3.click()
                    time.sleep(1.5)
                    shot(page, 'fig_li_apply_step4_review.png', full_page=False)
                    print('  Step 4 (Review) saved')

        # CLOSE without submitting
        close_btn = page.locator('button[aria-label="Dismiss"], button.artdeco-modal__dismiss').first
        if close_btn.is_visible():
            close_btn.click()
            time.sleep(1)
            # Confirm discard if dialog appears
            try:
                discard = page.locator('button:has-text("Discard")').first
                if discard.is_visible(timeout=2000):
                    discard.click()
            except:
                pass
        print('  Modal closed (NOT submitted)')

    except Exception as e:
        print(f'  Easy Apply modal error: {e}')

    # ── fig_li_applied — find a job already marked Applied ────────────────────
    print('\n[5/6] Finding Applied job confirmation...')
    try:
        page.goto('https://www.linkedin.com/my-items/saved-jobs/?cardType=APPLIED', wait_until='networkidle')
        time.sleep(2)
        shot(page, 'fig_li_applied_jobs.png', full_page=False)
        print('  fig_li_applied_jobs saved')
    except Exception as e:
        print(f'  Applied jobs page error: {e}')

    # ── fig_li_application_viewed — notification of application viewed ────────
    print('\n[6/6] Application viewed notification...')
    try:
        page.goto('https://www.linkedin.com/notifications/?filter=jobs', wait_until='networkidle')
        time.sleep(2)
        shot(page, 'fig_li_app_viewed.png', full_page=False)
        print('  fig_li_app_viewed saved')
    except Exception as e:
        print(f'  Notification page error: {e}')

    browser.close()

print('\n=== LinkedIn screenshots done! ===')
for f in sorted(os.listdir(SHOTS)):
    if 'li_' in f:
        size = os.path.getsize(os.path.join(SHOTS, f))
        print(f'  {f}: {size:,} bytes')
