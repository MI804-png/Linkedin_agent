"""
bot_runner.py – runs the LinkedIn bot for a specific user.
Each user gets their own data directory with their own playwright state,
applied-jobs log, run history, and CV file.
"""
from __future__ import annotations

import sys
import os
import io
import json
import time
import threading
import importlib
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

# Add the linkedin_bot directory to path so we can import bot & config
BOT_DIR = Path(__file__).resolve().parent.parent / "linkedin_bot"
sys.path.insert(0, str(BOT_DIR))

from config import (
    CandidateProfile, BotSettings, RuntimeConfig, RuntimePaths
)
from bot import LinkedInAutoApplyBot


def _run_direct_external_campaign_fallback(config: RuntimeConfig, stop_flag: threading.Event) -> dict[str, object]:
    """
    Apply to jobs on external non-LinkedIn boards with AI-style page detection.
    Handles Greenhouse, Lever, Ashby, simple open forms, and mailto email apply.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    from urllib.parse import urlparse
    import datetime as _dt
    import re as _re

    keyword = ((config.profile.current_job_title or "").strip()
               or (config.settings.keywords or ["Software Developer"])[0])
    kw       = quote_plus(keyword)
    kw_slug  = keyword.lower().replace(" ", "-")

    # ── profile ───────────────────────────────────────────────────────────────
    full_name    = config.profile.full_name
    first_name   = full_name.split()[0] if full_name else ""
    last_name    = " ".join(full_name.split()[1:]) if full_name else ""
    email        = config.profile.email
    phone        = config.profile.phone
    location     = config.profile.location
    linkedin_url = config.profile.linkedin_url
    github_url   = config.profile.github_url
    cv_path      = str(config.paths.cv_path)
    cover_letter = (
        f"Dear Hiring Team,\n\n"
        f"I am {full_name}, a {keyword} with {config.profile.total_experience_years} years of experience. "
        f"I am excited to apply for this position. I am proficient in full-stack development, "
        f"have strong problem-solving skills, and am passionate about building impactful software.\n\n"
        f"LinkedIn: {linkedin_url}\nGitHub: {github_url}\n\n"
        f"Thank you for your consideration.\n\nBest regards,\n{full_name}"
    )

    # ── applied log ───────────────────────────────────────────────────────────
    applied_log_path = config.paths.applied_log
    try:
        applied_set: set[str] = set(
            json.loads(applied_log_path.read_text(encoding="utf-8")).keys()
            if applied_log_path.exists() else []
        )
    except Exception:
        applied_set = set()

    def _save_applied(job_url: str, source: str, method: str) -> None:
        try:
            existing: dict = {}
            if applied_log_path.exists():
                existing = json.loads(applied_log_path.read_text(encoding="utf-8"))
            existing[job_url] = {
                "applied_at": _dt.datetime.utcnow().isoformat() + "Z",
                "source": source,
                "via": method,
            }
            applied_log_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            applied_set.add(job_url)
        except Exception:
            pass

    # ── site search configs ───────────────────────────────────────────────────
    sites = [
        {
            "name": "WeWorkRemotely",
            "url": f"https://weworkremotely.com/remote-jobs/search?term={kw}",
            "job_sel": "article.job-listing a.listing-link, ul.jobs li a.listing-link, section.jobs article a",
            # Only keep actual job pages; filter out company profiles, RSS, ad trackers
            "url_must_contain": "/remote-jobs/",
            "url_must_not_contain": [".rss", "/company/", "/listing_ads/", "/categories/"],
            "max": 10,
        },
        {
            "name": "RemoteOK",
            # Use tag-based search; kw_slug e.g. "software-developer" → valid ROK tag page
            "url": f"https://remoteok.com/remote-{kw_slug}-jobs",
            "fallback_url": f"https://remoteok.com/?tags={kw_slug}",
            "job_sel": "tr.job a.preventLink[href*='/remote-jobs'], td.company h2 a, .job a[href*='/remote-jobs']",
            "url_must_contain": "/remote-jobs/",
            "url_must_not_contain": ["/company", "/blog", "/tag/", "/sign-up"],
            "max": 10,
        },
        {
            "name": "EuropeRemoteJobs",
            "url": f"https://europeremotejobs.com/remote-jobs/?s={kw}",
            "job_sel": "h2.job-title a, .job-title a, article.job a.job-link, .job_listing-clickbox",
            "url_must_contain": None,
            "url_must_not_contain": ["/category/", "/tag/", "/page/"],
            "max": 10,
        },
        {
            "name": "Jobicy",
            "url": f"https://jobicy.com/jobs/?s={kw}",
            "job_sel": "article.job-card a.listing-title, h2 a.job-link, .job-listing a, a[href*='/job/']",
            "url_must_contain": None,
            "url_must_not_contain": ["/company", "/tag/", "/feed"],
            "max": 10,
        },
    ]

    stats: dict[str, int] = {"scanned": 0, "submitted": 0, "skipped": 0, "failures": 0, "errors": 0}

    # ── totally unautomatable ATS (require full account login) ────────────────
    HARD_SKIP = [
        "workday.com", "myworkdayjobs.com", "taleo.net", "successfactors",
        "icims.com", "paylocity.com", "paycom.com", "oracle.com/hcm",
        "sap.com", "peoplesoft", "kronos.net",
    ]

    # ── ATS with automatable public forms ────────────────────────────────────
    GREENHOUSE_PAT = _re.compile(r"boards\.greenhouse\.io|grnh\.se")
    LEVER_PAT      = _re.compile(r"jobs\.lever\.co")
    ASHBY_PAT      = _re.compile(r"jobs\.ashbyhq\.com")
    SMARTR_PAT     = _re.compile(r"jobs\.smartrecruiters\.com")
    BAMBOO_PAT     = _re.compile(r"[a-z0-9-]+\.bamboohr\.com")
    RECRUITEE_PAT  = _re.compile(r"[a-z0-9-]+\.recruitee\.com")
    JOBVITE_PAT    = _re.compile(r"jobs\.jobvite\.com")
    LINKEDIN_PAT   = _re.compile(r"linkedin\.com")

    # ATS domains used for scoring apply-button hrefs
    ATS_DOMAINS = [
        "greenhouse.io", "lever.co", "ashbyhq.com", "bamboohr.com",
        "recruitee.com", "smartrecruiters.com", "jobvite.com",
        "workable.com", "breezy.hr", "teamtailor.com", "workday.com",
        "myworkdayjobs.com", "icims.com", "taleo.net", "apply.",
    ]

    def _find_best_apply_element(page):
        """
        Score every visible <a> and <button> on the page and return the
        highest-scoring element that looks like an Apply button/link.
        Returns (element, abs_href) or (None, None).
        """
        candidates = []
        try:
            for el in page.query_selector_all("a, button"):
                try:
                    if not el.is_visible():
                        continue
                    text = (el.inner_text() or "").strip().lower()
                    href = (el.get_attribute("href") or "").lower()
                    abs_href = _resolve_abs(href, page.url) if href else ""
                    score = 0
                    # Strong text matches
                    if text in ("apply now", "apply for this job", "apply for this position"):
                        score += 12
                    elif text == "apply":
                        score += 10
                    elif text.startswith("apply"):
                        score += 7
                    elif "apply" in text:
                        score += 4
                    # Href boosts
                    if "/apply" in abs_href:
                        score += 5
                    if any(d in abs_href for d in ATS_DOMAINS):
                        score += 8
                    # Penalise nav/social links
                    if any(bad in abs_href for bad in ["twitter", "facebook", "linkedin.com",
                                                        "mailto:", "javascript:", "#"]):
                        score -= 10
                    if score > 0:
                        candidates.append((score, el, abs_href))
                except Exception:
                    pass
        except Exception:
            pass
        if not candidates:
            return None, None
        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0]
        return best[1], best[2]  # element, abs_href

    def _fill_field(page_or_frame, sel: str, value: str) -> bool:
        """Try to find and fill a single field. Returns True if filled."""
        try:
            el = page_or_frame.query_selector(sel)
            if el and el.is_visible() and el.is_enabled():
                el.scroll_into_view_if_needed()
                el.click()
                el.fill(value)
                return True
        except Exception:
            pass
        return False

    def _fill_textarea(page_or_frame, sel: str, value: str) -> bool:
        try:
            el = page_or_frame.query_selector(sel)
            if el and el.is_visible() and el.is_enabled():
                el.scroll_into_view_if_needed()
                el.click()
                el.fill(value)
                return True
        except Exception:
            pass
        return False

    def _upload_cv(page_or_frame) -> bool:
        if not os.path.exists(cv_path):
            return False
        for sel in ["input[type='file'][name*='resume' i]", "input[type='file'][name*='cv' i]",
                    "input[type='file'][id*='resume' i]", "input[type='file'][id*='cv' i]",
                    "input[type='file']"]:
            try:
                el = page_or_frame.query_selector(sel)
                if el:
                    el.set_input_files(cv_path)
                    return True
            except Exception:
                pass
        return False

    def _click_submit(page_or_frame) -> bool:
        for sel in [
            "button[type='submit']", "input[type='submit']",
            "button:has-text('Submit Application')", "button:has-text('Submit')",
            "button:has-text('Apply Now')", "button:has-text('Apply')",
            "button:has-text('Send Application')", "button:has-text('Send')",
        ]:
            try:
                btn = page_or_frame.query_selector(sel)
                if btn and btn.is_visible() and btn.is_enabled():
                    btn.scroll_into_view_if_needed()
                    btn.click()
                    return True
            except Exception:
                pass
        return False

    def _handle_yes_no_selects(page_or_frame) -> None:
        """Auto-answer visible Yes/No select dropdowns."""
        try:
            selects = page_or_frame.query_selector_all("select")
            for sel_el in selects:
                try:
                    opts = sel_el.query_selector_all("option")
                    values = [o.get_attribute("value") or "" for o in opts]
                    # Pick 'Yes' or 'No' sensibly
                    for v in values:
                        vl = v.lower()
                        if vl in ("yes", "true", "1"):
                            sel_el.select_option(v)
                            break
                        if vl in ("no", "false", "0"):
                            sel_el.select_option(v)
                            break
                except Exception:
                    pass
        except Exception:
            pass

    def _detect_page_type(page) -> str:
        """
        Detect the page's intent by inspecting URL, DOM text, headings, and inputs.
        Returns one of:
          greenhouse | lever | ashby | smartrecruiters | bamboo | recruitee | jobvite
          simple_form | login_required | blocked_ats | linkedin
          search_page | job_listing | bad_redirect | unknown
        """
        url = page.url.lower()

        # ── Hard-skip domains ────────────────────────────────────────────────
        if LINKEDIN_PAT.search(url):
            return "linkedin"
        if any(d in url for d in HARD_SKIP):
            return "blocked_ats"

        # ── Cloudflare challenge ─────────────────────────────────────────────
        if _is_cloudflare_challenge(page):
            return "cloudflare"

        # ── RemoteOK sign-up wall ────────────────────────────────────────────
        if "remoteok.com/sign-up" in url or "remoteok.com/signup" in url:
            return "remoteok_signup"

        # ── Known ATS by URL ─────────────────────────────────────────────────
        if GREENHOUSE_PAT.search(url):
            return "greenhouse"
        if LEVER_PAT.search(url):
            return "lever"
        if ASHBY_PAT.search(url):
            return "ashby"
        if SMARTR_PAT.search(url):
            return "smartrecruiters"
        if BAMBOO_PAT.search(url):
            return "bamboo"
        if RECRUITEE_PAT.search(url):
            return "recruitee"
        if JOBVITE_PAT.search(url):
            return "jobvite"

        # ── DOM-based detection ───────────────────────────────────────────────
        try:
            # Grab visible page text for intent analysis (title + headings + buttons)
            page_title = (page.title() or "").lower()
            visible_text = ""
            try:
                # Collect text from key elements quickly
                for sel in ["h1", "h2", "button", "a.btn", ".submit-btn",
                            "input[type='submit']", "label"]:
                    els = page.query_selector_all(sel)
                    for el in els[:10]:
                        try:
                            t = (el.inner_text() or "").strip().lower()
                            if t:
                                visible_text += " " + t
                        except Exception:
                            pass
            except Exception:
                pass

            combined = page_title + " " + visible_text

            # ── Login / Sign-in wall ─────────────────────────────────────────
            login_signals = ["sign in", "log in", "login", "sign up", "create account",
                             "register", "forgot password", "remember me"]
            has_password_field = bool(page.query_selector("input[type='password']"))
            has_login_text = any(s in combined for s in login_signals)
            # Only flag as login_required if password field OR strong login text
            # without any obvious application form fields
            has_email_field = bool(page.query_selector("input[type='email'], input[name*='email' i]"))
            has_name_field  = bool(page.query_selector("input[name*='name' i], input[name*='first' i]"))
            if has_password_field and not (has_name_field and has_email_field):
                return "login_required"
            if has_login_text and has_password_field:
                return "login_required"

            # ── Search / Find-jobs page ──────────────────────────────────────
            search_signals = ["search jobs", "find jobs", "job search", "browse jobs",
                              "explore jobs", "search remote", "find remote", "job board",
                              "all jobs", "view all jobs"]
            has_search_input = bool(page.query_selector(
                "input[name*='search' i], input[placeholder*='search' i], "
                "input[placeholder*='find' i], input[placeholder*='keyword' i]"
            ))
            if any(s in combined for s in search_signals) and has_search_input:
                return "search_page"

            # ── Bad redirect / homepage / unrelated ─────────────────────────
            bad_signals = ["page not found", "404", "error", "something went wrong",
                           "oops", "not available", "no longer available",
                           "position has been filled", "job has been closed",
                           "this job is no longer"]
            if any(s in combined for s in bad_signals):
                return "bad_redirect"

            # ── Job listing page (has Apply button but we're not on apply form) ──
            job_listing_signals = ["about the role", "about this role", "about the job",
                                   "responsibilities", "requirements", "qualifications",
                                   "who you are", "what you'll do", "what we offer"]
            is_job_listing = any(s in combined for s in job_listing_signals)
            # Use smart scorer to detect any Apply button on the page
            _apply_el, _apply_href = _find_best_apply_element(page)
            has_apply_btn = _apply_el is not None
            if is_job_listing and has_apply_btn and not (has_name_field and has_email_field):
                return "job_listing"

            # ── Application form (has name+email fields) ─────────────────────
            if has_name_field and has_email_field:
                return "simple_form"

            # ── Has a visible Apply button → job listing, click through ──────
            if has_apply_btn:
                return "job_listing"

            # ── Has any form at all ──────────────────────────────────────────
            if page.query_selector("form"):
                return "simple_form"

        except Exception:
            pass

        return "unknown"

    def _try_apply_greenhouse(page) -> bool:
        """Handle boards.greenhouse.io application form."""
        try:
            page.wait_for_selector("form#application_form, form.application-form, form",
                                   timeout=8000)
        except Exception:
            return False
        f = 0
        f += _fill_field(page, "#first_name, input[name*='first' i]", first_name)
        f += _fill_field(page, "#last_name, input[name*='last' i]", last_name)
        f += _fill_field(page, "#email, input[type='email']", email)
        f += _fill_field(page, "#phone, input[type='tel']", phone)
        f += _fill_field(page, "input[name*='location' i], input[id*='location' i]", location)
        f += _fill_field(page, "input[name*='linkedin' i], input[id*='linkedin' i]", linkedin_url)
        f += _fill_field(page, "input[name*='github' i], input[id*='github' i], "
                               "input[name*='website' i], input[id*='website' i]", github_url)
        f += _fill_textarea(page, "textarea[name*='cover' i], textarea[id*='cover' i], "
                                  "textarea[name*='message' i], textarea[id*='message' i]",
                            cover_letter)
        _upload_cv(page)
        _handle_yes_no_selects(page)
        page.wait_for_timeout(800)
        if f < 1:
            return False
        clicked = _click_submit(page)
        if clicked:
            page.wait_for_timeout(3000)
        return clicked

    def _try_apply_lever(page) -> bool:
        """Handle jobs.lever.co application form."""
        try:
            page.wait_for_selector("form.application-form, form[action*='lever'], form",
                                   timeout=8000)
        except Exception:
            return False
        f = 0
        f += _fill_field(page, "input[name='name'], input[placeholder*='full name' i]", full_name)
        f += _fill_field(page, "input[name='email'], input[type='email']", email)
        f += _fill_field(page, "input[name='phone'], input[type='tel']", phone)
        f += _fill_field(page, "input[name*='location' i], input[placeholder*='location' i]", location)
        f += _fill_field(page, "input[name='urls[LinkedIn]'], input[placeholder*='linkedin' i]", linkedin_url)
        f += _fill_field(page, "input[name='urls[GitHub]'], input[placeholder*='github' i]", github_url)
        f += _fill_textarea(page, "textarea[name*='comments' i], textarea[name='comments'], "
                                  "textarea[placeholder*='cover' i]", cover_letter)
        _upload_cv(page)
        _handle_yes_no_selects(page)
        page.wait_for_timeout(800)
        if f < 1:
            return False
        clicked = _click_submit(page)
        if clicked:
            page.wait_for_timeout(3000)
        return clicked

    def _try_apply_ashby(page) -> bool:
        """Handle jobs.ashbyhq.com application form."""
        try:
            page.wait_for_selector("form, [data-qa='application-form']", timeout=8000)
        except Exception:
            return False
        f = 0
        f += _fill_field(page, "input[name*='firstName' i], input[placeholder*='first' i]", first_name)
        f += _fill_field(page, "input[name*='lastName' i], input[placeholder*='last' i]", last_name)
        f += _fill_field(page, "input[type='email']", email)
        f += _fill_field(page, "input[type='tel'], input[name*='phone' i]", phone)
        f += _fill_field(page, "input[name*='linkedIn' i], input[placeholder*='linkedin' i]", linkedin_url)
        f += _fill_textarea(page, "textarea[name*='coverLetter' i], textarea[placeholder*='cover' i]",
                            cover_letter)
        _upload_cv(page)
        _handle_yes_no_selects(page)
        page.wait_for_timeout(800)
        if f < 1:
            return False
        clicked = _click_submit(page)
        if clicked:
            page.wait_for_timeout(3000)
        return clicked

    def _try_apply_recruitee(page) -> bool:
        """Handle *.recruitee.com application form."""
        try:
            page.wait_for_selector("form, .application-form", timeout=8000)
        except Exception:
            return False
        f = 0
        f += _fill_field(page, "input[name='name'], input[name*='full' i]", full_name)
        f += _fill_field(page, "input[name*='first' i]", first_name)
        f += _fill_field(page, "input[name*='last' i]", last_name)
        f += _fill_field(page, "input[type='email']", email)
        f += _fill_field(page, "input[type='tel']", phone)
        f += _fill_field(page, "input[name*='location' i], input[name*='city' i]", location)
        f += _fill_textarea(page, "textarea[name*='cover' i], textarea[name*='message' i]", cover_letter)
        _upload_cv(page)
        _handle_yes_no_selects(page)
        page.wait_for_timeout(800)
        if f < 1:
            return False
        clicked = _click_submit(page)
        if clicked:
            page.wait_for_timeout(3000)
        return clicked

    def _try_apply_generic(page) -> bool:
        """
        Generic form filler for any site.
        Detects visible inputs by name/id/placeholder patterns, fills them,
        uploads CV, answers selects, then submits.
        """
        try:
            page.wait_for_selector("form, input[type='email']", timeout=6000)
        except Exception:
            return False

        # Check for iframe-hosted forms (e.g. embedded ATS)
        frames_tried = [page]
        try:
            for frame in page.frames:
                if frame != page.main_frame and frame.url not in ("", "about:blank"):
                    frames_tried.append(frame)
        except Exception:
            pass

        best_filled = 0
        best_frame = None
        for frame in frames_tried:
            f = 0
            try:
                f += _fill_field(frame, "input[name*='first' i][type!='hidden'], "
                                        "input[id*='first' i][type!='hidden'], "
                                        "input[placeholder*='first name' i]", first_name)
                f += _fill_field(frame, "input[name*='last' i][type!='hidden'], "
                                        "input[id*='last' i][type!='hidden'], "
                                        "input[placeholder*='last name' i]", last_name)
                f += _fill_field(frame, "input[name='name'][type!='hidden'], "
                                        "input[name*='full' i][type!='hidden'], "
                                        "input[placeholder*='full name' i]", full_name)
                f += _fill_field(frame, "input[type='email'], input[name*='email' i][type!='hidden']", email)
                f += _fill_field(frame, "input[type='tel'], input[name*='phone' i][type!='hidden']", phone)
                f += _fill_field(frame, "input[name*='location' i][type!='hidden'], "
                                        "input[placeholder*='location' i], input[placeholder*='city' i]", location)
                f += _fill_field(frame, "input[name*='linkedin' i][type!='hidden'], "
                                        "input[placeholder*='linkedin' i]", linkedin_url)
                f += _fill_field(frame, "input[name*='github' i], input[placeholder*='github' i], "
                                        "input[name*='website' i], input[placeholder*='website' i]", github_url)
                f += _fill_textarea(frame,
                                    "textarea[name*='cover' i], textarea[id*='cover' i], "
                                    "textarea[placeholder*='cover' i], textarea[name*='message' i], "
                                    "textarea[placeholder*='message' i], textarea[name*='letter' i]",
                                    cover_letter)
                _upload_cv(frame)
                _handle_yes_no_selects(frame)
            except Exception:
                pass
            if f > best_filled:
                best_filled = f
                best_frame = frame

        if best_filled < 1:
            return False

        frame = best_frame or page
        page.wait_for_timeout(800)
        clicked = _click_submit(frame)
        if clicked:
            page.wait_for_timeout(3000)
        return clicked

    def _try_apply_page(page) -> tuple[bool, str]:
        """
        Detect page type and apply.  Returns (submitted, method_used).

        page_type flow:
          linkedin / blocked_ats / login_required  → skip
          search_page / bad_redirect               → skip
          job_listing    → click the Apply button, re-detect, then apply
          greenhouse / lever / ashby               → ATS-specific handler
          recruitee / bamboo / smartrecruiters
            / jobvite / simple_form / unknown      → generic handler
        """
        page_type = _detect_page_type(page)

        # ── Skip states ───────────────────────────────────────────────────────
        if page_type in ("linkedin", "blocked_ats", "login_required",
                         "search_page", "bad_redirect"):
            return False, page_type

        # ── Cloudflare challenge: wait for auto-pass ──────────────────────────
        if page_type == "cloudflare":
            passed = _wait_through_cloudflare(page)
            if not passed:
                return False, "cloudflare_blocked"
            page_type = _detect_page_type(page)
            if page_type in ("linkedin", "blocked_ats", "login_required",
                             "search_page", "bad_redirect", "cloudflare"):
                return False, f"cloudflare→{page_type}"

        # ── Job listing page: we need to click Apply first ────────────────────
        if page_type == "job_listing":
            el, abs_href = _find_best_apply_element(page)
            if el is None:
                return False, "job_listing_no_apply_btn"
            try:
                if abs_href and abs_href != page.url:
                    # Navigate directly — avoids target=_blank new tab issues
                    page.goto(abs_href, wait_until="domcontentloaded", timeout=18000)
                    page.wait_for_timeout(2000)
                else:
                    # No href or same-page anchor — click and watch for popup
                    try:
                        with page.context.expect_page(timeout=5000) as popup_info:
                            el.click()
                        new_tab = popup_info.value
                        new_tab.wait_for_load_state("domcontentloaded", timeout=15000)
                        popup_url = new_tab.url
                        new_tab.close()
                        page.goto(popup_url, wait_until="domcontentloaded", timeout=18000)
                        page.wait_for_timeout(2000)
                    except Exception:
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=10000)
                        except Exception:
                            pass
                        page.wait_for_timeout(2000)
            except Exception:
                return False, "job_listing_click_failed"
            # Re-detect after navigation
            page_type = _detect_page_type(page)
            if page_type in ("linkedin", "blocked_ats", "login_required",
                             "search_page", "bad_redirect", "job_listing"):
                return False, f"job_listing→{page_type}"

        # ── RemoteOK sign-up wall ─────────────────────────────────────────────
        if page_type == "remoteok_signup":
            try:
                # Generate a short username from the name
                import re as _re2
                username = _re2.sub(r"[^a-z0-9]", "", full_name.lower())[:20]
                # Fill username
                uname_sel = "input[placeholder*='username' i], input[name*='username' i], input[type='text']:first-of-type"
                uname_el = page.query_selector(uname_sel)
                if uname_el:
                    uname_el.fill(username)
                # Fill email
                email_el = page.query_selector("input[type='email'], input[placeholder*='email' i]")
                if email_el:
                    email_el.fill(email)
                # Click Continue
                continue_btn = page.query_selector(
                    "button:has-text('Continue'), button[type='submit'], input[type='submit']"
                )
                if continue_btn:
                    continue_btn.click()
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    page.wait_for_timeout(3000)
                    # After signup, check if we got redirected back to job page or need to apply
                    page_type = _detect_page_type(page)
                    if page_type not in ("remoteok_signup", "login_required", "bad_redirect"):
                        # Recurse once — now we should be on the job page or ATS form
                        return _try_apply_page(page)
                    return False, "remoteok_signup_failed"
                return False, "remoteok_signup_no_btn"
            except Exception as e:
                return False, f"remoteok_signup_error"

        # ── ATS-specific handlers ─────────────────────────────────────────────
        if page_type == "greenhouse":
            ok = _try_apply_greenhouse(page)
            return ok, "greenhouse"
        if page_type == "lever":
            ok = _try_apply_lever(page)
            return ok, "lever"
        if page_type == "ashby":
            ok = _try_apply_ashby(page)
            return ok, "ashby"

        # ── Generic handler for everything else ───────────────────────────────
        ok = _try_apply_generic(page)
        return ok, page_type

    def _resolve_abs(href: str, base_url: str) -> str:
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{href}"
        return ""

    def _is_cloudflare_challenge(page) -> bool:
        """Return True if page is showing a Cloudflare JS/turnstile challenge."""
        try:
            title = (page.title() or "").lower()
            if "just a moment" in title or "checking your browser" in title:
                return True
            url = page.url.lower()
            if "challenge" in url or "__cf_chl" in url:
                return True
            # Check for CF spinner text in body
            body = page.inner_text("body") if page.query_selector("body") else ""
            if "performing security verification" in body.lower():
                return True
            if "checking if the site connection is secure" in body.lower():
                return True
        except Exception:
            pass
        return False

    def _wait_through_cloudflare(page, max_wait_ms: int = 18000) -> bool:
        """
        Wait up to max_wait_ms for Cloudflare to auto-resolve.
        Returns True if it passed, False if still blocked.
        """
        step = 1500
        waited = 0
        while waited < max_wait_ms:
            page.wait_for_timeout(step)
            waited += step
            if not _is_cloudflare_challenge(page):
                return True
        return False

    with sync_playwright() as pw:
        # Stealth launch args – hide automation fingerprints from Cloudflare
        launch_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--disable-blink-features=AutomationControlled",
            "--disable-automation",
            "--disable-extensions-except=",
            "--disable-default-apps",
            "--no-first-run",
            "--no-default-browser-check",
            "--password-store=basic",
            "--use-mock-keychain",
        ]
        if not config.settings.headless:
            launch_args += ["--start-maximized"]

        STEALTH_UA = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )

        browser = None
        for channel in ["chrome", "msedge"]:
            try:
                browser = pw.chromium.launch(
                    headless=config.settings.headless, channel=channel, args=launch_args
                )
                break
            except Exception:
                continue
        if browser is None:
            browser = pw.chromium.launch(headless=config.settings.headless, args=launch_args)

        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=STEALTH_UA,
            locale="en-US",
            timezone_id="Europe/Budapest",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        # Inject JS to remove webdriver/automation traces on every new page
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
            delete window.__playwright;
            delete window.__pw_manual;
        """)

        # Single persistent page – navigates between jobs without opening/closing tabs
        page = context.new_page()
        try:
            for site in sites:
                if stop_flag.is_set():
                    break

                # ── Step 1: collect job listing URLs from the search page ──
                job_links: list[str] = []
                try:
                    page.goto(site["url"], wait_until="domcontentloaded", timeout=25000)
                    # Wait for/through any Cloudflare challenge
                    if _is_cloudflare_challenge(page):
                        print(f"[EXT] Cloudflare detected on {site['name']}, waiting…", flush=True)
                        passed = _wait_through_cloudflare(page)
                        if not passed:
                            print(f"[EXT] Cloudflare not resolved for {site['name']}, skipping", flush=True)
                            stats["errors"] += 1
                            continue
                    page.wait_for_timeout(2500)
                    anchors = page.query_selector_all(site["job_sel"])
                    seen_hrefs: set[str] = set()
                    must_contain = site.get("url_must_contain")
                    must_not_contain = site.get("url_must_not_contain") or []
                    # Relevance filter: title must contain at least one keyword word
                    kw_words = [w.lower() for w in keyword.split() if len(w) > 2]
                    for a in anchors:
                        try:
                            href = a.get_attribute("href") or ""
                            abs_url = _resolve_abs(href, page.url)
                            if not abs_url or abs_url in seen_hrefs:
                                continue
                            # Filter: must contain required path segment
                            if must_contain and must_contain not in abs_url:
                                continue
                            # Filter: must not contain blocked segments
                            if any(bad in abs_url for bad in must_not_contain):
                                continue
                            # Filter: anchor text must contain at least one keyword word
                            try:
                                anchor_text = (a.inner_text() or "").lower()
                            except Exception:
                                anchor_text = ""
                            if kw_words and anchor_text and not any(w in anchor_text for w in kw_words):
                                continue
                            seen_hrefs.add(abs_url)
                            job_links.append(abs_url)
                            if len(job_links) >= site["max"] * 2:
                                break
                        except Exception:
                            pass
                    # If RemoteOK primary URL got 0 results, try fallback URL
                    if not job_links and site.get("fallback_url"):
                        try:
                            page.goto(site["fallback_url"], wait_until="domcontentloaded", timeout=20000)
                            page.wait_for_timeout(2000)
                            anchors2 = page.query_selector_all(site["job_sel"])
                            for a in anchors2:
                                try:
                                    href = a.get_attribute("href") or ""
                                    abs_url = _resolve_abs(href, page.url)
                                    if not abs_url or abs_url in seen_hrefs:
                                        continue
                                    if must_contain and must_contain not in abs_url:
                                        continue
                                    if any(bad in abs_url for bad in must_not_contain):
                                        continue
                                    seen_hrefs.add(abs_url)
                                    job_links.append(abs_url)
                                    if len(job_links) >= site["max"] * 2:
                                        break
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    job_links = job_links[: site["max"]]
                except Exception:
                    stats["errors"] += 1
                    continue

                # ── Step 2: visit each job page and attempt to apply ───────
                for job_url in job_links:
                    if stop_flag.is_set():
                        break
                    if job_url in applied_set:
                        stats["skipped"] += 1
                        continue

                    stats["scanned"] += 1
                    try:
                        page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
                        page.wait_for_timeout(2000)

                        # ── Detect Apply button / link on the job page ──────
                        apply_url: str | None = None
                        mailto_addr: str | None = None

                        # Check for mailto: links first (email apply)
                        try:
                            for a in page.query_selector_all("a[href^='mailto:']"):
                                href = a.get_attribute("href") or ""
                                if href.startswith("mailto:"):
                                    addr = href[7:].split("?")[0].strip()
                                    if addr:
                                        mailto_addr = addr
                                        break
                        except Exception:
                            pass

                        if mailto_addr:
                            # Log email-apply jobs (can't send email automatically without SMTP)
                            _save_applied(job_url, site["name"], f"email_apply:{mailto_addr}")
                            stats["submitted"] += 1
                            continue

                        # Look for Apply button
                        for sel in APPLY_BUTTON_SELS:
                            try:
                                el = page.query_selector(sel)
                                if not el or not el.is_visible():
                                    continue
                                href = el.get_attribute("href") or ""
                                if href.startswith("mailto:"):
                                    addr = href[7:].split("?")[0].strip()
                                    if addr:
                                        mailto_addr = addr
                                    break
                                abs_url = _resolve_abs(href, page.url) if href else ""
                                if abs_url:
                                    apply_url = abs_url
                                    break
                                else:
                                    # Button with no href → same-page or JS navigation
                                    apply_url = page.url
                                    break
                            except Exception:
                                pass

                        if mailto_addr:
                            _save_applied(job_url, site["name"], f"email_apply:{mailto_addr}")
                            stats["submitted"] += 1
                            continue

                        if not apply_url:
                            # No apply button found — try submitting form on the job page itself
                            apply_url = page.url

                        # Navigate to apply page if different
                        if apply_url != page.url:
                            try:
                                page.goto(apply_url, wait_until="domcontentloaded", timeout=20000)
                                page.wait_for_timeout(2000)
                            except Exception:
                                stats["errors"] += 1
                                continue

                        submitted, method = _try_apply_page(page)

                        if submitted:
                            stats["submitted"] += 1
                            _save_applied(job_url, site["name"], method)
                        else:
                            # Count intentional skips separately from real failures
                            SKIP_METHODS = {"linkedin", "blocked_ats", "login_required",
                                            "search_page", "bad_redirect",
                                            "job_listing_no_apply_btn", "cloudflare_blocked"}
                            if method in SKIP_METHODS or method.startswith("job_listing→"):
                                stats["skipped"] += 1
                            else:
                                stats["failures"] += 1
                            print(f"[EXT-SKIP/FAIL] {job_url} → {method}", flush=True)

                    except Exception:
                        stats["errors"] += 1

        finally:
            try:
                page.close()
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

    return {
        "started_at": _dt.datetime.utcnow().isoformat() + "Z",
        "ended_at": _dt.datetime.utcnow().isoformat() + "Z",
        "stats": stats,
    }

# Maps run_id -> threading.Event; set() signals the bot to stop after the current job.
_stop_flags: dict[int, threading.Event] = {}
# Maps run_id -> active bot instance for immediate hard-stop requests.
_active_bots: dict[int, LinkedInAutoApplyBot] = {}
# Maps user_id -> active networking worker metadata.
_networking_jobs: dict[int, dict[str, object]] = {}
_networking_lock = threading.Lock()


def request_stop(run_id: int) -> None:
    """Signal the worker for run_id to stop gracefully after the current job."""
    flag = _stop_flags.get(run_id)
    if flag:
        flag.set()


def request_stop_now(run_id: int) -> None:
    """Best-effort immediate stop: set flag and close active browser/context if available."""
    flag = _stop_flags.get(run_id)
    if flag:
        flag.set()

    bot = _active_bots.get(run_id)
    if bot:
        try:
            bot.request_hard_stop()
        except Exception:
            pass


def get_active_run_ids() -> set[int]:
    """Return run IDs that still have an active worker/stop flag in this process."""
    return set(_stop_flags.keys()) | set(_active_bots.keys())


def is_run_active(run_id: int) -> bool:
    """Check whether a run ID appears active in this process."""
    return run_id in _stop_flags or run_id in _active_bots


def _resolve_app_module():
    """Return the live Flask app module to avoid duplicate SQLAlchemy instances.

    When running `python app.py`, the module name is `__main__`; importing
    `app` again would create a second module and break db session bindings.
    """
    main_mod = sys.modules.get("__main__")
    if main_mod and hasattr(main_mod, "db") and hasattr(main_mod, "User"):
        return main_mod
    return importlib.import_module("app")


def _user_dir(user_id: int) -> Path:
    """Return (and create) per-user data directory."""
    from pathlib import Path
    d = Path(__file__).resolve().parent / "user_data" / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _network_log_path(user_id: int) -> Path:
    return _user_dir(user_id) / "network_sent.json"


def _is_networking_running(user_id: int) -> bool:
    with _networking_lock:
        info = _networking_jobs.get(user_id)
        if not info:
            return False
        th = info.get("thread")
        if isinstance(th, threading.Thread):
            if th.ident is None:
                return True  # created but not fully started yet
            if th.is_alive():
                return True
        _networking_jobs.pop(user_id, None)
        return False


def get_networking_status(user_id: int) -> dict[str, object]:
    """Return active status for networking worker (follow/unfollow)."""
    running = _is_networking_running(user_id)
    with _networking_lock:
        info = _networking_jobs.get(user_id, {}) if running else {}
        action = str(info.get("action") or "")
        started_at = str(info.get("started_at") or "")
    return {
        "running": running,
        "action": action,
        "started_at": started_at,
    }


def get_network_follow_summary(user_id: int, *, limit: int = 200) -> dict[str, object]:
    """Load tracked followed companies with timestamps from user_data/network_sent.json."""
    path = _network_log_path(user_id)
    if not path.exists():
        return {"total": 0, "items": []}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"total": 0, "items": []}

    if not isinstance(raw, dict):
        return {"total": 0, "items": []}

    items: list[dict[str, str]] = []
    for key, payload in raw.items():
        if not (isinstance(key, str) and key.startswith("__follow__") and isinstance(payload, dict)):
            continue
        company = str(payload.get("company") or "").strip()
        followed_at = str(payload.get("followed_at") or "")
        company_url = str(payload.get("company_url") or "").strip()
        if company:
            items.append({"company": company, "followed_at": followed_at, "company_url": company_url})

    items.sort(key=lambda x: x.get("followed_at", ""), reverse=True)
    return {"total": len(items), "items": items[:limit]}


def build_config_for_user(
    user_id: int,
    *,
    watch_browser: bool = False,
    apply_type_override: str | None = None,
) -> RuntimeConfig:
    """
    Build a RuntimeConfig from the database profile for `user_id`.
    Called inside the app context.
    """
    app_mod = _resolve_app_module()
    db = app_mod.db
    UserProfile = app_mod.UserProfile
    User = app_mod.User
    UPLOAD_FOLDER = app_mod.UPLOAD_FOLDER

    user = db.session.get(User, user_id)
    p: UserProfile = user.profile

    profile = CandidateProfile(
        full_name=p.full_name or "",
        email=p.linkedin_email or user.email,
        phone=p.phone or "",
        location=p.location or "",
        graduation_year=p.graduation_year or "",
        total_experience_years=p.experience_years or "",
        work_authorization_hungary=p.work_auth_answer or "",
        work_authorization_italy=p.work_auth_answer or "",
        salary_hungary=p.salary_answer or "",
        salary_italy=p.salary_answer or "",
        nationality=getattr(p, "nationality", "") or "",
        is_eu_citizen=getattr(p, "is_eu_citizen", False) or False,
        willing_to_relocate=getattr(p, "willing_to_relocate", False) or False,
        willing_to_work_onsite=getattr(p, "willing_to_work_onsite", False) or False,
        willing_to_work_remote=getattr(p, "willing_to_work_remote", True) if getattr(p, "willing_to_work_remote", None) is not None else True,
        current_job_title=getattr(p, "current_job_title", "") or "",
        networking_title=getattr(p, "networking_title", "") or "",
        years_management_experience=getattr(p, "years_management_experience", "0") or "0",
        highest_education=getattr(p, "highest_education", "") or "",
        field_of_study=getattr(p, "field_of_study", "") or "",
        english_proficiency=getattr(p, "english_proficiency", "Professional") or "Professional",
        languages_spoken=getattr(p, "languages_spoken", "") or "",
        has_drivers_license=getattr(p, "has_drivers_license", False) or False,
        drivers_license_category=getattr(p, "drivers_license_category", "") or "",
        linkedin_url=getattr(p, "linkedin_url", "") or "",
        github_url=getattr(p, "github_url", "") or "",
        portfolio_url=getattr(p, "portfolio_url", "") or "",
        gender=getattr(p, "gender", "") or "",
        has_disability=getattr(p, "has_disability", False) or False,
        veteran_status=getattr(p, "veteran_status", "No") or "No",
    )

    settings = BotSettings(
        keywords=p.keywords_list or ["Software Developer"],
        locations=p.locations_list or ["Hungary"],
        workplace_type=(p.workplace_type or "all"),
        apply_type=(apply_type_override or p.apply_type or "easy_apply"),
        max_applications_per_run=p.max_applications,
        max_network_per_run=max(1, min(100, int(getattr(p, "max_network_companies_per_run", 20) or 20))),
        posted_days_ago=p.posted_days_ago,
        headless=not watch_browser,
        watch_hold_seconds=120 if watch_browser else 0,
    )

    ud = _user_dir(user_id)
    cv_path = UPLOAD_FOLDER / p.cv_filename if p.cv_filename else BOT_DIR.parent / "Mikhael_CV.pdf"

    paths = RuntimePaths(
        base_dir=ud,
        cv_path=cv_path,
        applied_log=ud / "applied_jobs.json",
        run_history_log=ud / "run_history.json",
        state_path=ud / "state.json",
        browser_state_path=ud / "playwright_state.json",
    )

    return RuntimeConfig(
        email=p.linkedin_email or user.email,
        password=p.get_linkedin_password(),
        profile=profile,
        settings=settings,
        paths=paths,
    )


def _do_run_watch_subprocess(app, user_id: int, run_id: int, *, apply_type_override: str | None = None) -> None:
    """
    Watch-mode: launch main.py as a brand-new visible process with CREATE_NEW_CONSOLE
    so Chrome always appears on the desktop regardless of how Flask was started.
    A log file bridges output back to the dashboard.
    """
    import subprocess, time as _time

    python_exe = sys.executable
    main_py = str(BOT_DIR / "main.py")
    log_file = _user_dir(user_id) / "watch_run.log"

    # Pick up user settings for limit
    try:
        with app.app_context():
            app_mod = _resolve_app_module()
            UserProfile = app_mod.UserProfile
            p = UserProfile.query.filter_by(user_id=user_id).first()
            limit = str(p.max_applications if p and p.max_applications else 5)
    except Exception:
        limit = "5"

    cmd = [python_exe, main_py, "--limit", limit]
    if apply_type_override:
        cmd += ["--apply-type", apply_type_override]
    # CREATE_NEW_CONSOLE (0x10) gives the subprocess its own visible console window
    # so Chrome/Edge spawned by Playwright will always appear on the desktop.
    CREATE_NEW_CONSOLE = 0x00000010

    with open(log_file, "w", encoding="utf-8") as lf:
        lf.write("[WATCH] Starting bot in visible mode — Chrome window opening on your screen...\n")

    try:
        log_fh = open(log_file, "a", encoding="utf-8")
        proc = subprocess.Popen(
            cmd,
            cwd=str(BOT_DIR),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NEW_CONSOLE,
        )
    except Exception as launch_exc:
        with app.app_context():
            app_mod = _resolve_app_module()
            db = app_mod.db
            BotRun = app_mod.BotRun
            bot_run = db.session.get(BotRun, run_id)
            if bot_run:
                bot_run.status = "error"
                bot_run.finished_at = datetime.utcnow()
                bot_run.log_snippet = f"[WATCH] Failed to launch bot process: {launch_exc}"
                db.session.commit()
        return

    # Poll subprocess + tail log file so the dashboard stays live
    last_size = 0
    while proc.poll() is None:
        _time.sleep(2)
        try:
            with app.app_context():
                app_mod = _resolve_app_module()
                db = app_mod.db
                BotRun = app_mod.BotRun
                bot_run = db.session.get(BotRun, run_id)
                if bot_run and log_file.exists():
                    text = log_file.read_text(encoding="utf-8", errors="replace")
                    if len(text) != last_size:
                        last_size = len(text)
                        bot_run.log_snippet = text[-3000:]
                        db.session.commit()
                # Honour stop flag
                if bot_run and bot_run.status != "running":
                    proc.terminate()
                    break
        except Exception:
            pass

    log_fh.close()

    # Final DB update
    try:
        with app.app_context():
            app_mod = _resolve_app_module()
            db = app_mod.db
            BotRun = app_mod.BotRun
            bot_run = db.session.get(BotRun, run_id)
            if bot_run:
                final_log = log_file.read_text(encoding="utf-8", errors="replace") if log_file.exists() else ""
                bot_run.log_snippet = final_log[-3000:]
                bot_run.status = "done"
                bot_run.finished_at = datetime.utcnow()
                bot_run.submitted = final_log.count("[SUBMITTED]")
                bot_run.skipped   = final_log.count("[SKIPPED]")
                bot_run.failures  = final_log.count("[FAILED]")
                db.session.commit()
    except Exception as fin_exc:
        print(f"[WATCH FINISH ERROR] {fin_exc}", file=sys.stderr)


def _do_run(
    app,
    user_id: int,
    run_id: int,
    watch_browser: bool = False,
    apply_type_override: str | None = None,
) -> None:
    """
    Actually runs the bot in a background thread, inside the Flask app context.
    Updates the BotRun record when done.
    """
    render_env = bool(os.environ.get("RENDER"))
    # Visible watch mode (separate console + desktop browser) is Windows-only.
    # On Render/cloud, keep watch semantics via live dashboard logs in headless mode.
    effective_watch = bool(watch_browser and not render_env and os.name == "nt")

    if effective_watch:
        _do_run_watch_subprocess(app, user_id, run_id, apply_type_override=apply_type_override)
        return

    try:
        with app.app_context():
            app_mod = _resolve_app_module()
            db = app_mod.db
            BotRun = app_mod.BotRun

            bot_run = db.session.get(BotRun, run_id)
            if not bot_run:
                return

            log_lines: list[str] = []

            def _log(msg: str) -> None:
                ts = datetime.utcnow().strftime("%H:%M:%S")
                log_lines.append(f"[{ts}] {msg}")
                # Keep last 300 lines in DB
                if len(log_lines) > 300:
                    log_lines.pop(0)

            try:
                if watch_browser and not effective_watch:
                    _log("Run and Watch requested in cloud mode: using headless browser with live dashboard logs.")

                config = build_config_for_user(
                    user_id,
                    watch_browser=effective_watch,
                    apply_type_override=apply_type_override,
                )
                mode = "visible" if effective_watch else ("cloud-live" if watch_browser else "headless")
                _log(f"Starting bot for user {user_id} ({config.email}) in {mode} mode")
                bot_run.log_snippet = "\n".join(log_lines)
                db.session.commit()

                bot = LinkedInAutoApplyBot(config, dry_run=False, resume=False)
                _active_bots[run_id] = bot

                # Register a stop flag so /stop_run can interrupt between jobs.
                stop_flag = threading.Event()
                _stop_flags[run_id] = stop_flag

                def _check_stop():
                    if stop_flag.is_set():
                        bot.stop_requested = True

                # Wire per-job callback so individual results appear in the log.
                def _on_job_result(result: dict) -> None:
                    status = result.get("status", "?")
                    title = (result.get("title") or "")[:60]
                    company = (result.get("company") or "")[:40]
                    note = result.get("note") or ""
                    _log(f"[{status.upper()}] {title} @ {company} — {note}")

                    _check_stop()  # propagate stop flag to bot after each job result
                    # Keep live dashboard counters in sync while a run is active.
                    normalized = str(status).strip().lower()
                    if normalized == "submitted":
                        bot_run.submitted = (bot_run.submitted or 0) + 1
                    elif normalized == "skipped":
                        bot_run.skipped = (bot_run.skipped or 0) + 1
                    elif normalized == "failed":
                        bot_run.failures = (bot_run.failures or 0) + 1

                    # Store missing skills report if available
                    missing_skills = result.get("missing_skills")
                    if missing_skills and normalized == "submitted":
                        try:
                            MissingSkillsReport = app_mod.MissingSkillsReport
                            report = MissingSkillsReport(
                                user_id=user_id,
                                job_id=result.get("job_id", ""),
                                job_title=title,
                                company_name=company,
                                job_url=result.get("job_url", ""),
                                missing_skills=json.dumps(missing_skills.get("missing_skills", [])),
                                confidence_score=missing_skills.get("match_percentage", 0),
                                created_at=datetime.utcnow(),
                            )
                            db.session.add(report)
                            _log(f"[SKILLS] {len(missing_skills.get('missing_skills', []))} missing skills identified")
                        except Exception as e:
                            _log(f"[WARN] Failed to store missing skills: {e}")

                    bot_run.log_snippet = "\n".join(log_lines)
                    db.session.commit()

                bot._on_job_result = _on_job_result

                bot.run()

                stats = bot.stats
                bot_run.submitted = stats.get("submitted", 0)
                bot_run.skipped = stats.get("skipped", 0)
                bot_run.failures = stats.get("failures", 0)
                if stop_flag.is_set():
                    _log(f"Stopped by user. submitted={bot_run.submitted} skipped={bot_run.skipped} failures={bot_run.failures}")
                    bot_run.status = "stopped"
                else:
                    _log(f"Done. submitted={bot_run.submitted} skipped={bot_run.skipped} failures={bot_run.failures}")
                    bot_run.status = "done"

            except Exception as exc:
                _log(f"ERROR: {exc}")
                import traceback
                _log(traceback.format_exc())
                bot_run.status = "error"

            finally:
                # Clean up stop flag
                _stop_flags.pop(run_id, None)
                _active_bots.pop(run_id, None)
                if bot_run.status == "running":
                    # Only auto-close to "done" if the user didn't stop it
                    bot_run.status = "done"
                bot_run.finished_at = datetime.utcnow()
                bot_run.log_snippet = "\n".join(log_lines)
                db.session.commit()
    except Exception as outer_exc:
        import sys
        import traceback
        tb = traceback.format_exc()
        print(f"\n[_DO_RUN OUTER EXCEPTION run_id={run_id}]\n{outer_exc}\n{tb}\n", file=sys.stderr)
        try:
            with app.app_context():
                app_mod = _resolve_app_module()
                db = app_mod.db
                BotRun = app_mod.BotRun
                bot_run = db.session.get(BotRun, run_id)
                if bot_run:
                    bot_run.status = "error"
                    bot_run.finished_at = datetime.utcnow()
                    bot_run.log_snippet = f"CRITICAL: Worker thread failed to initialize: {outer_exc}\n{tb}"
                    db.session.commit()
        except Exception as inner_exc:
            print(f"[DB ERROR in _do_run outer handler: {inner_exc}]", file=sys.stderr)


def run_for_user_async(
    user_id: int,
    *,
    watch_browser: bool = False,
    apply_type_override: str | None = None,
) -> int:
    """
    Creates a BotRun record and starts the bot in a background thread.
    Returns the run_id.
    """
    # BOT_DISABLED is an explicit kill-switch. Render is allowed with headless fallback.
    if os.environ.get("BOT_DISABLED"):
        app_mod = _resolve_app_module()
        db = app_mod.db
        BotRun = app_mod.BotRun
        run = BotRun(
            user_id=user_id,
            status="error",
            finished_at=datetime.utcnow(),
            log_snippet="Bot is disabled by server configuration (BOT_DISABLED).",
        )
        db.session.add(run)
        db.session.commit()
        return run.id

    from flask import current_app
    app_mod = _resolve_app_module()
    db = app_mod.db
    BotRun = app_mod.BotRun

    # Keep only one active run per user. If an old running row exists,
    # recycle it if recent; otherwise close it as stale.
    # Exception: if the user specifically wants to watch the browser,
    # always start a fresh visible run even if a headless one is active.
    existing = (
        BotRun.query
        .filter_by(user_id=user_id, status="running")
        .order_by(BotRun.started_at.desc())
        .first()
    )
    if existing:
        age = datetime.utcnow() - existing.started_at
        if age < timedelta(hours=8) and not watch_browser:
            return existing.id
        existing.status = "error"
        existing.finished_at = datetime.utcnow()
        note = "Run marked stale after server restart/interruption." if age >= timedelta(hours=8) else "Superseded by visible (Run and Watch) run."
        existing.log_snippet = (existing.log_snippet + "\n" + note).strip() if existing.log_snippet else note
        db.session.commit()

    run = BotRun(user_id=user_id, status="running")
    db.session.add(run)
    db.session.commit()
    run_id = run.id

    # Get the app instance directly (not current_app, which is thread-local)
    app = current_app._get_current_object()

    def worker_thread_wrapper():
        """Wrapper to ensure errors are captured even in daemon threads."""
        import sys
        try:
            _do_run(
                app,
                user_id,
                run_id,
                watch_browser=watch_browser,
                apply_type_override=apply_type_override,
            )
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            print(f"\n[WORKER THREAD ERROR run_id={run_id}]\n{exc}\n{tb}\n", file=sys.stderr)
            try:
                with app.app_context():
                    app_mod = _resolve_app_module()
                    db = app_mod.db
                    BotRun = app_mod.BotRun
                    bot_run = db.session.get(BotRun, run_id)
                    if bot_run:
                        bot_run.status = "error"
                        bot_run.finished_at = datetime.utcnow()
                        bot_run.log_snippet = f"THREAD ERROR: {exc}\n{tb}"
                        db.session.commit()
            except Exception as db_exc:
                print(f"[DB ERROR in wrapper: {db_exc}]", file=sys.stderr)

    def timeout_watchdog():
        """Monitor run timeout and force-close if it exceeds max duration."""
        import time
        # Give 4 min per application + 10 min overhead, capped between 30 min and 8 hours.
        try:
            with app.app_context():
                app_mod2 = _resolve_app_module()
                _up = app_mod2.UserProfile.query.filter_by(user_id=user_id).first()
                max_apps = (_up.max_applications if _up and _up.max_applications else 25)
        except Exception:
            max_apps = 25
        max_duration_seconds = min(max(30 * 60, max_apps * 4 * 60 + 10 * 60), 8 * 60 * 60)
        check_interval = 60  # Check every 60 seconds
        iterations = 0
        while iterations < (max_duration_seconds // check_interval) + 1:
            time.sleep(check_interval)
            iterations += 1
            try:
                with app.app_context():
                    app_mod = _resolve_app_module()
                    db = app_mod.db
                    BotRun = app_mod.BotRun
                    bot_run = db.session.get(BotRun, run_id)
                    if bot_run and bot_run.status == "running":
                        age = (datetime.utcnow() - bot_run.started_at).total_seconds()
                        if age > max_duration_seconds:
                            bot_run.status = "error"
                            bot_run.finished_at = datetime.utcnow()
                            bot_run.log_snippet = f"{bot_run.log_snippet}\n[TIMEOUT] Run exceeded {max_duration_seconds}s limit and was force-closed."
                            db.session.commit()
                            break
                    else:
                        break  # Run finished or not found
            except Exception:
                pass  # Silently ignore watchdog errors

    t = threading.Thread(target=worker_thread_wrapper, daemon=True)
    t.start()

    # Start timeout watchdog in background
    wd = threading.Thread(target=timeout_watchdog, daemon=True)
    wd.start()

    return run_id


def run_for_user_async_retry_failed(user_id: int, *, watch_browser: bool = False) -> int:
    """
    Remove all 'failed' entries from the user's applied_jobs.json so the bot
    will attempt those jobs again, then start a normal async run.
    Failed entries are archived first so the dashboard can still show them.
    Returns the new run_id.
    """
    ud = _user_dir(user_id)
    applied_log = ud / "applied_jobs.json"
    archive_log = ud / "failed_jobs_archive.json"
    if applied_log.exists():
        try:
            data = json.loads(applied_log.read_text(encoding="utf-8"))
            failed = [j for j in data if isinstance(j, dict) and j.get("status") == "failed"]
            cleaned = [j for j in data if not (isinstance(j, dict) and j.get("status") == "failed")]

            if failed:
                try:
                    existing_archive = json.loads(archive_log.read_text(encoding="utf-8")) if archive_log.exists() else []
                    if not isinstance(existing_archive, list):
                        existing_archive = []
                except Exception:
                    existing_archive = []

                archived_at = datetime.utcnow().isoformat() + "Z"
                for entry in failed:
                    entry_copy = dict(entry)
                    entry_copy["archived_at"] = archived_at
                    existing_archive.append(entry_copy)
                archive_log.write_text(json.dumps(existing_archive, ensure_ascii=False, indent=2), encoding="utf-8")

            applied_log.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass  # If corrupt, leave file untouched
    return run_for_user_async(user_id, watch_browser=watch_browser)


def run_networking_for_user_async(user_id: int, *, watch_browser: bool = False) -> tuple[bool, str]:
    """
    Run the LinkedIn networking campaign (follow top companies)
    for the given user in a background thread. No BotRun record is created —
    this is a fire-and-forget side task that logs to stderr.
    """
    if os.environ.get("RENDER") or os.environ.get("BOT_DISABLED"):
        return False, "Networking is disabled in this environment."

    if _is_networking_running(user_id):
        return False, "Networking is already running. Wait for it to finish before starting again."

    from flask import current_app
    app = current_app._get_current_object()

    def _networking_worker():
        import sys
        try:
            with app.app_context():
                config = build_config_for_user(user_id, watch_browser=watch_browser)
                bot = LinkedInAutoApplyBot(config, dry_run=False, resume=False)
                # Compatibility shim: some bot builds may miss the networking helper.
                # Inject a safe fallback so networking can still run.
                if not hasattr(bot, "_get_networking_target_companies"):
                    def _fallback_network_targets() -> list[str]:
                        role_context = " ".join([
                            str(getattr(bot.config.profile, "current_job_title", "") or "").lower(),
                            " ".join(str(k).lower() for k in (getattr(bot.config.settings, "keywords", []) or [])),
                        ])
                        software_tokens = [
                            "software", "engineer", "developer", "backend", "frontend",
                            "full stack", "fullstack", "web", "application",
                        ]
                        software_companies = [
                            "Google", "Microsoft", "Amazon", "Meta", "Apple",
                            "Netflix", "Uber", "Spotify", "LinkedIn", "Salesforce",
                            "Oracle", "IBM", "SAP", "ServiceNow", "Workday",
                        ]
                        general_companies = [
                            "Siemens", "Bosch", "Ericsson", "Nokia", "T-Systems",
                            "Deutsche Telekom", "Accenture", "Capgemini", "Deloitte",
                            "KPMG", "PwC", "Infosys", "Cognizant", "NTT Data",
                            "EPAM", "Endava", "Randstad", "Manpower", "Hays",
                        ]
                        if any(token in role_context for token in software_tokens):
                            return software_companies + general_companies
                        return software_companies

                    bot._get_networking_target_companies = _fallback_network_targets  # type: ignore[attr-defined]
                result = bot.run_networking_campaign()
                sent = result.get("stats", {}).get("sent", 0)
                skipped = result.get("stats", {}).get("skipped", 0)
                failures = result.get("stats", {}).get("failures", 0)
                print(
                    f"[networking user_id={user_id}] sent={sent} skipped={skipped} failures={failures}",
                    file=sys.stderr,
                )
        except Exception as exc:
            import traceback
            print(f"[networking ERROR user_id={user_id}] {exc}\n{traceback.format_exc()}", file=sys.stderr)
        finally:
            with _networking_lock:
                info = _networking_jobs.get(user_id)
                if info and info.get("action") == "follow":
                    _networking_jobs.pop(user_id, None)

    t = threading.Thread(target=_networking_worker, daemon=True)
    with _networking_lock:
        _networking_jobs[user_id] = {
            "thread": t,
            "action": "follow",
            "started_at": datetime.utcnow().isoformat() + "Z",
        }
    t.start()
    return True, "Networking started in watch mode."


def run_network_unfollow_for_user_async(
    user_id: int,
    *,
    company: str | None = None,
    watch_browser: bool = False,
) -> tuple[bool, str]:
    """Run async unfollow job for tracked companies (single-company or all)."""
    if os.environ.get("RENDER") or os.environ.get("BOT_DISABLED"):
        return False, "Unfollow is disabled in this environment."

    if _is_networking_running(user_id):
        return False, "A networking job is already running. Wait for it to finish."

    from flask import current_app
    app = current_app._get_current_object()

    company_name = (company or "").strip()

    def _unfollow_worker():
        import sys
        try:
            with app.app_context():
                config = build_config_for_user(user_id, watch_browser=watch_browser)
                bot = LinkedInAutoApplyBot(config, dry_run=False, resume=False)
                companies = [company_name] if company_name else None
                result = bot.run_unfollow_companies_campaign(companies=companies)
                unfollowed = result.get("stats", {}).get("unfollowed", 0)
                skipped = result.get("stats", {}).get("skipped", 0)
                failures = result.get("stats", {}).get("failures", 0)
                print(
                    f"[unfollow user_id={user_id}] unfollowed={unfollowed} skipped={skipped} failures={failures}",
                    file=sys.stderr,
                )
        except Exception as exc:
            import traceback
            print(f"[unfollow ERROR user_id={user_id}] {exc}\n{traceback.format_exc()}", file=sys.stderr)
        finally:
            with _networking_lock:
                info = _networking_jobs.get(user_id)
                if info and info.get("action") == "unfollow":
                    _networking_jobs.pop(user_id, None)

    t = threading.Thread(target=_unfollow_worker, daemon=True)
    with _networking_lock:
        _networking_jobs[user_id] = {
            "thread": t,
            "action": "unfollow",
            "started_at": datetime.utcnow().isoformat() + "Z",
        }
    t.start()

    if company_name:
        return True, f"Unfollow started for {company_name}."
    return True, "Unfollow started for all tracked companies."


def run_direct_external_for_user_async(user_id: int, *, watch_browser: bool = True) -> tuple[bool, str]:
    """Browse external job boards directly (WeWorkRemotely, RemoteOK, etc.) — no LinkedIn.
    Runs in a background thread and logs progress via _log (streamed to BotRun.log_snippet).
    """
    if os.environ.get("BOT_DISABLED"):
        return False, "Bot is disabled by server configuration."

    from flask import current_app
    app = current_app._get_current_object()
    app_mod = _resolve_app_module()
    db = app_mod.db
    BotRun = app_mod.BotRun

    with app.app_context():
        # Mark any existing running BotRun as stale so it doesn't confuse the dashboard
        existing = (
            BotRun.query
            .filter_by(user_id=user_id, status="running")
            .order_by(BotRun.started_at.desc())
            .first()
        )
        if existing:
            existing.status = "error"
            existing.finished_at = datetime.utcnow()
            existing.log_snippet = ((existing.log_snippet or "") + "\nSuperseded by External Websites run.").strip()
            db.session.commit()

        run = BotRun(user_id=user_id, status="running")
        db.session.add(run)
        db.session.commit()
        run_id = run.id

    # Register stop flag so /stop_run can interrupt external runs too.
    stop_flag = threading.Event()
    _stop_flags[run_id] = stop_flag

    def _worker():
        import sys
        try:
            with app.app_context():
                config = build_config_for_user(
                    user_id,
                    watch_browser=watch_browser,
                    apply_type_override="external_only",
                )
                bot = LinkedInAutoApplyBot(config, dry_run=False, resume=False)
                _active_bots[run_id] = bot

                # Attach a log callback so progress appears in the dashboard
                def _stream_log(msg: str):
                    try:
                        with app.app_context():
                            row = db.session.get(BotRun, run_id)
                            if row:
                                if stop_flag.is_set() or row.status != "running":
                                    bot.stop_requested = True
                                snippet = (row.log_snippet or "") + "\n" + msg
                                row.log_snippet = snippet[-8000:]
                                db.session.commit()
                    except Exception:
                        pass
                bot._log_callback = _stream_log  # type: ignore[attr-defined]

                # Honor stop requests even before the first log line.
                if stop_flag.is_set():
                    bot.stop_requested = True

                if hasattr(bot, "run_direct_external_campaign"):
                    result = bot.run_direct_external_campaign()
                else:
                    result = _run_direct_external_campaign_fallback(config, stop_flag)
                stats = result.get("stats", {})
                summary = (
                    f"[DIRECT-EXT] Done — scanned={stats.get('scanned',0)} "
                    f"submitted={stats.get('submitted',0)} "
                    f"skipped={stats.get('skipped',0)} "
                    f"failures={stats.get('failures',0)}"
                )
                print(summary, file=sys.stderr)
                with app.app_context():
                    row = db.session.get(BotRun, run_id)
                    if row:
                        if stop_flag.is_set() or bot.stop_requested or row.status != "running":
                            row.status = "stopped"
                            summary = (
                                f"[DIRECT-EXT] Stopped — scanned={stats.get('scanned',0)} "
                                f"submitted={stats.get('submitted',0)} "
                                f"skipped={stats.get('skipped',0)} "
                                f"failures={stats.get('failures',0)}"
                            )
                        else:
                            row.status = "done"
                        row.finished_at = datetime.utcnow()
                        row.log_snippet = ((row.log_snippet or "") + "\n" + summary)[-8000:]
                        db.session.commit()
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            print(f"[DIRECT-EXT ERROR user_id={user_id}] {exc}\n{tb}", file=sys.stderr)
            try:
                with app.app_context():
                    row = db.session.get(BotRun, run_id)
                    if row:
                        row.status = "stopped" if stop_flag.is_set() else "error"
                        row.finished_at = datetime.utcnow()
                        row.log_snippet = f"ERROR: {exc}\n{tb}"[-8000:]
                        db.session.commit()
            except Exception:
                pass
        finally:
            _active_bots.pop(run_id, None)
            _stop_flags.pop(run_id, None)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return True, f"Direct external job search started (run_id={run_id})."

