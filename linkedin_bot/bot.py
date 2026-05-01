from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import re
import time
from typing import Any
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from config import RuntimeConfig


class LinkedInAutoApplyBot:
    def __init__(self, config: RuntimeConfig, *, dry_run: bool = False, resume: bool = False, limit: int | None = None):
        self.config = config
        self.dry_run = dry_run
        self.resume = resume
        self.limit = limit or config.settings.max_applications_per_run

        self.applied_jobs = self._read_json(config.paths.applied_log, default=[])
        self.state = self._read_json(config.paths.state_path, default={"combo_index": 0, "job_offset": 0})

        self.stats: dict[str, int] = {
            "scanned": 0,
            "submitted": 0,
            "skipped": 0,
            "dry_run": 0,
            "manual_required": 0,
            "failures": 0,
        }

    def run(self) -> dict[str, Any]:
        start = datetime.now(timezone.utc).isoformat()

        # First run: if no saved session, force a visible browser login so LinkedIn
        # renders the real form (headless is detected and blocked by LinkedIn).
        run_headless = self.config.settings.headless
        if not self.config.paths.browser_state_path.exists():
            run_headless = False  # Must show browser to pass LinkedIn anti-bot on first login

        with sync_playwright() as p:
            try:
                self._run_once(p, headless=run_headless)
            except RuntimeError as exc:
                # If LinkedIn blocks relogin in headless mode, retry once visibly.
                if run_headless and "headless relogin was blocked" in str(exc).lower():
                    self._run_once(p, headless=False)
                else:
                    raise

        end = datetime.now(timezone.utc).isoformat()

        run_result = {
            "started_at": start,
            "ended_at": end,
            "dry_run": self.dry_run,
            "resume": self.resume,
            "limit": self.limit,
            "stats": self.stats,
        }
        self._append_run_history(run_result)
        return run_result

    def _run_once(self, playwright, *, headless: bool) -> None:
        # Prefer installed desktop browsers to avoid requiring Playwright
        # browser downloads on end-user machines.
        browser = None
        for channel in ["chrome", "msedge"]:
            try:
                browser = playwright.chromium.launch(headless=headless, channel=channel)
                break
            except Exception:
                continue
        if browser is None:
            browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(
            storage_state=str(self.config.paths.browser_state_path)
            if self.config.paths.browser_state_path.exists()
            else None
        )
        page = context.new_page()

        try:
            self._login(page)
            # Reset daily state cursor unless resuming
            if not self.resume:
                self.state = {"combo_index": 0, "job_offset": 0}
            self._process_search_combinations(page)
        finally:
            context.storage_state(path=str(self.config.paths.browser_state_path))
            context.close()
            browser.close()

    def _login(self, page) -> None:
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        # Wait for any post-load redirects to settle (LinkedIn may redirect /feed/ → /mynetwork/grow/)
        try:
            page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
        # Already logged in if any authenticated LinkedIn page is shown
        if self._is_authenticated(page):
            return

        # Session expired — delete stale state file and re-login
        expired_in_headless = False
        if self.config.paths.browser_state_path.exists():
            self.config.paths.browser_state_path.unlink()
            expired_in_headless = bool(self.config.settings.headless)
        # Non-headless: fall through to login form below


        # Accept cookie consent if present (it blocks form rendering)
        try:
            consent_btn = page.locator("button[action-type='ACCEPT']")
            if consent_btn.count() > 0:
                consent_btn.first.click(timeout=5000)
                page.wait_for_timeout(1000)
        except Exception:
            pass

        # Navigate directly to /login
        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Accept cookie consent on login page if shown
        try:
            consent_btn = page.locator("button[action-type='ACCEPT']")
            if consent_btn.count() > 0:
                consent_btn.first.click(timeout=5000)
                page.wait_for_timeout(1000)
        except Exception:
            pass

        page.wait_for_timeout(2000)
        # Wait for redirect chain to complete (e.g. /login → /mynetwork/grow/ when session still valid)
        try:
            page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass

        # User may have clicked a saved-account tile / session still active — check if already logged in
        if self._is_authenticated(page):
            return

        email_ok = self._human_type_first(
            page,
            ["#username", "input[name='session_key'][type='text']", "input[autocomplete='username']", "input[type='email']"],
            self.config.email,
        )
        password_ok = self._human_type_first(
            page,
            ["#password", "input[name='session_password']", "input[type='password']"],
            self.config.password,
        )

        if not email_ok or not password_ok:
            if self._is_security_challenge(page):
                self._write_state()
                raise RuntimeError(
                    f"LinkedIn security challenge (2FA/CAPTCHA) detected at {page.url}. Resolve manually and rerun with --resume."
                )
            if expired_in_headless:
                raise RuntimeError(
                    "LinkedIn session expired and headless relogin was blocked by LinkedIn. "
                    "Run once manually (without --headless) to refresh session:\n"
                    "  d:\\cv_portofolio\\.venv\\Scripts\\python.exe main.py --limit 1\n"
                    "Then scheduled/background runs will resume automatically."
                )
            debug_path = self._save_debug_artifacts(page, "login_form_missing")
            raise RuntimeError(
                f"Could not locate LinkedIn login form fields. Page: {page.url}. Debug saved at {debug_path}."
            )

        page.click("button[type='submit']")
        page.wait_for_timeout(3000)

        if self._is_security_challenge(page):
            self._write_state()
            raise RuntimeError(
                "LinkedIn security challenge (2FA/CAPTCHA) detected. Resolve manually and rerun with --resume."
            )

    def _find_apply_button(self, page):
        """Find apply/easy apply element (button or anchor link) using text and aria attributes."""
        # LinkedIn's Easy Apply is rendered as an <a> tag with aria-label
        for selector in [
            "a[aria-label*='Easy Apply']",
            "a:has-text('Easy Apply')",
            "a[aria-label*='easy apply']",
            "button:has-text('Easy Apply')",
            "button[aria-label*='Easy Apply']",
            "button:has-text('Apply')",
            "button[aria-label*='Apply']",
            "a[href*='openSDUIApplyFlow']",
        ]:
            try:
                el = page.query_selector(selector)
                if el:
                    return el
            except Exception:
                continue

        # Fallback: scan buttons and anchors for apply text
        try:
            all_els = page.query_selector_all("button, a")
        except Exception:
            all_els = []
        for el in all_els:
            try:
                txt = (el.inner_text() or "").strip().lower()
                aria = (el.get_attribute("aria-label") or "").lower()
                if "apply" in txt or "apply" in aria:
                    return el
            except Exception:
                continue

        return None

    def _get_easy_apply_url(self, page) -> str | None:
        """Get the Easy Apply flow URL directly from the page anchor href."""
        for selector in [
            "a[aria-label*='Easy Apply']",
            "a[href*='openSDUIApplyFlow']",
            "a:has-text('Easy Apply')",
        ]:
            try:
                el = page.query_selector(selector)
                if el:
                    href = el.get_attribute("href") or ""
                    if href.startswith("/"):
                        href = "https://www.linkedin.com" + href
                    return href or None
            except Exception:
                continue
        return None

    def _is_authenticated(self, page) -> bool:
        url = page.url.lower()
        authenticated_indicators = [
            "linkedin.com/feed",
            "linkedin.com/jobs",
            "linkedin.com/mynetwork",
            "linkedin.com/messaging",
            "linkedin.com/notifications",
            "linkedin.com/in/",
        ]
        if any(token in url for token in authenticated_indicators):
            # Additional check: login pages should not contain these
            if "linkedin.com/login" not in url and "linkedin.com/authwall" not in url:
                return True
        return False


    def _is_security_challenge(self, page) -> bool:
        url = page.url.lower()
        if any(token in url for token in ["checkpoint", "challenge", "captcha", "verify", "security"]):
            return True

        try:
            body_text = (page.inner_text("body") or "").lower()
        except Exception:
            body_text = ""

        challenge_markers = [
            "security check",
            "verify it's you",
            "verify it is you",
            "captcha",
            "unusual activity",
            "are you a robot",
            "challenge",
        ]
        return any(marker in body_text for marker in challenge_markers)

    def _process_search_combinations(self, page) -> None:
        combos = [(k, l) for k in self.config.settings.keywords for l in self.config.settings.locations]
        start_combo = self.state.get("combo_index", 0) if self.resume else 0

        for combo_index, (keyword, location) in enumerate(combos[start_combo:], start=start_combo):
            if self._reached_limit():
                break

            job_urls = self._collect_job_urls(page, keyword, location)
            if not job_urls:
                continue

            start_offset = self.state.get("job_offset", 0) if (self.resume and combo_index == start_combo) else 0
            for job_offset, job_url in enumerate(job_urls[start_offset:], start=start_offset):
                if self._reached_limit():
                    self.state["combo_index"] = combo_index
                    self.state["job_offset"] = job_offset
                    self._write_state()
                    return

                self.stats["scanned"] += 1
                self.state["combo_index"] = combo_index
                self.state["job_offset"] = job_offset
                self._write_state()

                job_id = self._extract_job_id(job_url)
                if self._already_seen(job_id):
                    self.stats["skipped"] += 1
                    continue

                result = self._process_single_job(page, job_url, job_id, location)
                self._record_job(result)
                if hasattr(self, '_on_job_result') and callable(self._on_job_result):
                    try:
                        self._on_job_result(result)
                    except Exception as _cb_exc:
                        import sys
                        print(f"[_on_job_result error] {_cb_exc}", file=sys.stderr)

        self.state["combo_index"] = 0
        self.state["job_offset"] = 0
        self._write_state()

    def _collect_job_urls(self, page, keyword: str, location: str) -> list[str]:
        encoded_keyword = quote_plus(keyword)
        encoded_location = quote_plus(location)
        # f_LF=f_AL filters for Easy Apply only to maximise auto-submit rate
        search_url = (
            "https://www.linkedin.com/jobs/search/"
            f"?keywords={encoded_keyword}&location={encoded_location}"
            f"&f_LF=f_AL&f_TPR=r{self.config.settings.posted_days_ago * 86400}"
        )

        page.goto(search_url, wait_until="domcontentloaded")
        self._human_pause()
        self._progressive_scroll(page, iterations=10)

        # Broad anchor match — job cards use multiple link patterns across LinkedIn versions
        try:
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            anchors = page.query_selector_all("a")
        except Exception:
            anchors = []
        urls: list[str] = []
        for anchor in anchors:
            try:
                href = anchor.get_attribute("href")
            except Exception:
                continue
            if not href:
                continue
            if href.startswith("/"):
                href = f"https://www.linkedin.com{href}"
            if "/jobs/view/" in href:
                clean = href.split("?")[0]
                if clean not in urls:
                    urls.append(clean)

        return urls

    def _process_single_job(self, page, job_url: str, job_id: str, location: str) -> dict[str, Any]:
        for attempt in range(self.config.settings.retries_per_job + 1):
            try:
                page.goto(job_url, wait_until="domcontentloaded")
                self._human_pause()

                title = self._text_or_empty(page, "h1")
                company = (self._text_or_empty(page, ".jobs-unified-top-card__company-name")
                           or self._text_or_empty(page, "a[data-tracking-control-name*='company']")
                           or self._text_or_empty(page, ".job-details-jobs-unified-top-card__company-name"))
                place = (self._text_or_empty(page, ".jobs-unified-top-card__bullet")
                         or self._text_or_empty(page, ".job-details-jobs-unified-top-card__tertiary-description")
                         or self._text_or_empty(page, "span[class*='workplace-type']"))

                apply_element = self._find_apply_button(page)
                if not apply_element:
                    self.stats["skipped"] += 1
                    return self._job_record(job_id, job_url, title, company, place, "skipped", "No apply button")

                # Detect Easy Apply by href or text
                href = (apply_element.get_attribute("href") or "").lower()
                button_text = (apply_element.inner_text() or "").strip().lower()
                aria = (apply_element.get_attribute("aria-label") or "").lower()
                is_easy_apply = "opensdui" in href or "easy apply" in button_text or "easy apply" in aria

                if is_easy_apply:
                    if self.dry_run:
                        self.stats["dry_run"] += 1
                        return self._job_record(job_id, job_url, title, company, place, "dry_run", "Easy Apply found")

                    ok, fail_reason = self._run_easy_apply(page, location)
                    if ok:
                        self.stats["submitted"] += 1
                        return self._job_record(job_id, job_url, title, company, place, "submitted", "Easy Apply submitted")

                    self.stats["failures"] += 1
                    return self._job_record(job_id, job_url, title, company, place, "failed", fail_reason or "Easy Apply flow failed")

                external_url = self._handle_external_apply(page)
                self.stats["manual_required"] += 1
                return self._job_record(
                    job_id,
                    job_url,
                    title,
                    company,
                    place,
                    "manual_required",
                    f"External apply: {external_url or 'opened'}",
                )

            except PlaywrightTimeoutError:
                if attempt >= self.config.settings.retries_per_job:
                    self.stats["failures"] += 1
                    return self._job_record(job_id, job_url, "", "", "", "failed", "Timeout")
                self._human_pause()
            except Exception as exc:
                if attempt >= self.config.settings.retries_per_job:
                    self.stats["failures"] += 1
                    return self._job_record(job_id, job_url, "", "", "", "failed", f"Unhandled error: {exc}")
                self._human_pause()

        self.stats["failures"] += 1
        return self._job_record(job_id, job_url, "", "", "", "failed", "Unknown failure")

    def _run_easy_apply(self, page, location: str) -> tuple[bool, str]:
        # Try to get the direct URL for the Easy Apply flow
        apply_url = self._get_easy_apply_url(page)
        if apply_url:
            page.goto(apply_url, wait_until="domcontentloaded")
            self._human_pause()
        else:
            apply_btn = self._find_apply_button(page)
            if not apply_btn:
                return False, "No apply button found"
            apply_btn.click()
            self._human_pause()

        file_input = page.query_selector("input[type='file']")
        if file_input and self.config.paths.cv_path.exists():
            file_input.set_input_files(str(self.config.paths.cv_path))
            self._human_pause()

        for step in range(10):
            self._autofill_visible_fields(page, location)

            submit_btn = page.query_selector("button[aria-label*='Submit application'], button:has-text('Submit application')")
            if submit_btn:
                submit_btn.click()
                self._human_pause()
                self._close_apply_modal(page)
                return True, ""

            next_btn = page.query_selector("button[aria-label='Continue to next step'], button:has-text('Next'), button:has-text('Review')")
            if not next_btn:
                # Check for validation errors on the page
                errors = page.query_selector_all("[data-test-form-element-error-message], .artdeco-inline-feedback--error")
                error_texts = []
                for err in errors[:5]:
                    try:
                        error_texts.append((err.inner_text() or "").strip())
                    except Exception:
                        pass
                reason = f"Stuck on step {step+1}"
                if error_texts:
                    reason += f" — validation errors: {'; '.join(error_texts)}"
                reason += f" | URL: {page.url}"
                # Capture debug artefacts for offline diagnosis
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                log_dir = self.config.paths.base_dir.parent.parent / "linkedin_bot" / "logs"
                try:
                    page.screenshot(path=str(log_dir / f"easyfail_step{step+1}_{ts}.png"))
                    (log_dir / f"easyfail_step{step+1}_{ts}.html").write_text(page.content(), encoding="utf-8")
                except Exception:
                    pass
                self._dismiss_apply_flow(page)
                return False, reason
            next_btn.click()
            self._human_pause()

        self._dismiss_apply_flow(page)
        return False, "Exceeded max steps (10)"

    def _autofill_visible_fields(self, page, location: str) -> None:
        profile = self.config.profile
        work_auth = profile.work_authorization_hungary if "hungary" in location.lower() else profile.work_authorization_italy
        salary = profile.salary_hungary if "hungary" in location.lower() else profile.salary_italy

        fill_map = {
            "first name": profile.full_name.split(" ")[0],
            "last name": profile.full_name.split(" ")[-1],
            "full name": profile.full_name,
            "name": profile.full_name,
            "email": profile.email,
            "phone": profile.phone,
            "mobile": profile.phone,
            "city": profile.location,
            "location": profile.location,
            "experience": profile.total_experience_years,
            "salary": salary,
            "authorization": work_auth,
            "work permit": work_auth,
            "graduation": profile.graduation_year,
        }

        try:
            inputs = page.query_selector_all("input, textarea")
        except Exception:
            inputs = []

        for input_el in inputs:
            input_type = (input_el.get_attribute("type") or "text").lower()
            if input_type in {"hidden", "submit", "button", "checkbox", "radio", "file"}:
                continue

            value = (input_el.input_value() or "").strip()
            if value:
                continue

            field_id = input_el.get_attribute("id") or ""
            label_text = ""
            try:
                if field_id:
                    lbl = page.query_selector(f"label[for='{field_id}']")
                    if lbl:
                        label_text = (lbl.inner_text() or "").strip()
                if not label_text:
                    parent_label = input_el.query_selector("xpath=ancestor::label[1]")
                    if parent_label:
                        label_text = (parent_label.inner_text() or "").strip()
                if not label_text:
                    parent_fieldset = input_el.query_selector("xpath=ancestor::fieldset[1]")
                    if parent_fieldset:
                        label_text = (parent_fieldset.inner_text() or "").strip().split("\n")[0]
            except Exception:
                label_text = ""

            metadata = " ".join(
                filter(
                    None,
                    [
                        input_el.get_attribute("name"),
                        field_id,
                        input_el.get_attribute("placeholder"),
                        input_el.get_attribute("aria-label"),
                        label_text,
                    ],
                )
            ).lower()

            chosen = None
            for key, mapped in fill_map.items():
                if key in metadata and mapped:
                    chosen = str(mapped)
                    break

            # Fallback for required numeric experience questions like
            # "How many years ..." when LinkedIn omits useful input attributes.
            if not chosen and input_type == "number":
                if "year" in metadata or "experience" in metadata:
                    chosen = str(profile.total_experience_years or "0")
                else:
                    chosen = "0"

            if chosen:
                try:
                    input_el.fill(chosen)
                    self._human_pause(0.2, 0.6)
                except Exception:
                    continue

        # Fill empty selects with best-effort answers.
        try:
            selects = page.query_selector_all("select")
        except Exception:
            selects = []
        for sel in selects:
            try:
                current = (sel.input_value() or "").strip().lower()
            except Exception:
                current = ""
            if current:
                continue

            try:
                meta = " ".join(
                    filter(
                        None,
                        [
                            sel.get_attribute("name"),
                            sel.get_attribute("id"),
                            sel.get_attribute("aria-label"),
                            (sel.query_selector("xpath=ancestor::fieldset[1]").inner_text() if sel.query_selector("xpath=ancestor::fieldset[1]") else ""),
                        ],
                    )
                ).lower()
            except Exception:
                meta = ""

            pick_value = None
            try:
                options = sel.query_selector_all("option")
            except Exception:
                options = []

            non_empty = []
            for opt in options:
                try:
                    val = (opt.get_attribute("value") or "").strip()
                    txt = (opt.inner_text() or "").strip().lower()
                except Exception:
                    continue
                if not val:
                    continue
                if txt in {"select", "choose", "please select"}:
                    continue
                non_empty.append((val, txt))

            if not non_empty:
                continue

            if "authorization" in meta or "work permit" in meta or "eligible" in meta:
                target_yes = (work_auth or "yes").strip().lower().startswith("y")
                for val, txt in non_empty:
                    if target_yes and "yes" in txt:
                        pick_value = val
                        break
                    if not target_yes and "no" in txt:
                        pick_value = val
                        break
            elif "language" in meta and "hungarian" in meta:
                for val, txt in non_empty:
                    if "none" in txt:
                        pick_value = val
                        break

            if not pick_value:
                pick_value = non_empty[0][0]

            try:
                sel.select_option(value=pick_value)
                self._human_pause(0.2, 0.6)
            except Exception:
                continue

        # Fill unanswered radio groups.
        try:
            radios = page.query_selector_all("input[type='radio']")
        except Exception:
            radios = []

        groups: dict[str, list[Any]] = {}
        for radio in radios:
            name = (radio.get_attribute("name") or "").strip()
            if not name:
                continue
            groups.setdefault(name, []).append(radio)

        for _, group in groups.items():
            try:
                if any(r.is_checked() for r in group):
                    continue
            except Exception:
                pass

            prompt = ""
            try:
                prompt = (group[0].query_selector("xpath=ancestor::fieldset[1]").inner_text() or "").lower()
            except Exception:
                prompt = ""

            choose_yes = None
            if any(token in prompt for token in ["authorized", "work permit", "eligible to work"]):
                choose_yes = (work_auth or "yes").strip().lower().startswith("y")
            elif any(token in prompt for token in ["commut", "on-site", "onsite", "relocat", "travel"]):
                choose_yes = True

            chosen_radio = None
            for radio in group:
                try:
                    rid = radio.get_attribute("id") or ""
                    lbl = page.query_selector(f"label[for='{rid}']") if rid else None
                    txt = ((lbl.inner_text() if lbl else "") or "").strip().lower()
                except Exception:
                    txt = ""

                if choose_yes is True and "yes" in txt:
                    chosen_radio = radio
                    break
                if choose_yes is False and "no" in txt:
                    chosen_radio = radio
                    break

            if not chosen_radio:
                chosen_radio = group[0]

            try:
                chosen_radio.check(force=True)
                self._human_pause(0.2, 0.6)
            except Exception:
                continue

        # Tick required consent checkboxes if empty.
        try:
            checkboxes = page.query_selector_all("input[type='checkbox'][required]")
        except Exception:
            checkboxes = []
        for cb in checkboxes:
            try:
                if not cb.is_checked():
                    cb.check(force=True)
                    self._human_pause(0.2, 0.6)
            except Exception:
                continue

    def _handle_external_apply(self, page) -> str | None:
        btn = self._find_apply_button(page)
        if not btn:
            return None

        external_url = None
        try:
            with page.expect_popup(timeout=3000) as popup_info:
                btn.click()
            popup = popup_info.value
            popup.wait_for_load_state("domcontentloaded", timeout=5000)
            external_url = popup.url
            popup.close()
        except Exception:
            try:
                btn.click()
                self._human_pause()
                external_url = page.url
            except Exception:
                return None

        return external_url

    def _dismiss_apply_flow(self, page) -> None:
        discard = page.query_selector("button:has-text('Discard')")
        close = page.query_selector("button[aria-label='Dismiss']")
        if close:
            close.click()
            self._human_pause(0.2, 0.8)
        if discard:
            discard.click()
            self._human_pause(0.2, 0.8)

    def _close_apply_modal(self, page) -> None:
        done = page.query_selector("button:has-text('Done')")
        if done:
            done.click()
            self._human_pause(0.2, 0.8)

    def _already_seen(self, job_id: str) -> bool:
        return any(entry.get("job_id") == job_id for entry in self.applied_jobs)

    def _record_job(self, job: dict[str, Any]) -> None:
        # Persist all terminal outcomes so the same job is never retried.
        # "failed" jobs are recorded so repeat runs skip them instead of
        # hitting the same broken form every time.
        if job.get("status") not in {"submitted", "manual_required", "failed"}:
            return
        self.applied_jobs.append(job)
        self._write_json(self.config.paths.applied_log, self.applied_jobs)

    def _append_run_history(self, result: dict[str, Any]) -> None:
        history = self._read_json(self.config.paths.run_history_log, default=[])
        history.append(result)
        self._write_json(self.config.paths.run_history_log, history)

    def _job_record(
        self,
        job_id: str,
        job_url: str,
        title: str,
        company: str,
        location: str,
        status: str,
        note: str,
    ) -> dict[str, Any]:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "job_id": job_id,
            "job_url": job_url,
            "title": title.strip(),
            "company": company.strip(),
            "location": location.strip(),
            "status": status,
            "note": note,
            "profile_snapshot": asdict(self.config.profile),
        }

    def _extract_job_id(self, url: str) -> str:
        match = re.search(r"/jobs/view/(\d+)", url)
        return match.group(1) if match else url

    def _progressive_scroll(self, page, iterations: int = 8) -> None:
        for _ in range(iterations):
            page.mouse.wheel(0, random.randint(600, 1200))
            self._human_pause(0.3, 0.8)

    def _human_pause(self, min_seconds: float | None = None, max_seconds: float | None = None) -> None:
        min_wait = min_seconds if min_seconds is not None else self.config.settings.random_wait_min_seconds
        max_wait = max_seconds if max_seconds is not None else self.config.settings.random_wait_max_seconds
        time.sleep(random.uniform(min_wait, max_wait))

    def _human_type_first(self, page, selectors: list[str], text: str) -> bool:
        for selector in selectors:
            try:
                self._human_type(page, selector, text)
                return True
            except Exception:
                continue
        return False

    def _human_type(self, page, selector: str, text: str) -> None:
        locator = page.locator(selector)
        locator.wait_for(state="attached", timeout=10000)

        # Try direct fill first because login pages can show overlays that block click.
        try:
            locator.fill("")
            for ch in text:
                locator.type(ch, delay=random.uniform(30, 90))
            return
        except Exception:
            pass

        page.click(selector, timeout=10000)
        for ch in text:
            page.keyboard.type(ch)
            time.sleep(random.uniform(0.03, 0.09))

    def _text_or_empty(self, page, selector: str) -> str:
        el = page.query_selector(selector)
        return (el.inner_text() if el else "") or ""

    def _save_debug_artifacts(self, page, prefix: str) -> str:
        logs_dir = self.config.paths.base_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        html_path = logs_dir / f"{prefix}_{ts}.html"
        png_path = logs_dir / f"{prefix}_{ts}.png"

        try:
            html_path.write_text(page.content(), encoding="utf-8")
        except Exception:
            pass

        try:
            page.screenshot(path=str(png_path), full_page=True)
        except Exception:
            pass

        return str(logs_dir)

    def _read_json(self, path: Path, *, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def _write_json(self, path: Path, content: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(content, f, indent=2, ensure_ascii=True)

    def _write_state(self) -> None:
        self._write_json(self.config.paths.state_path, self.state)

    def _reached_limit(self) -> bool:
        # Limit by processed jobs so dry-runs and mixed flows terminate predictably.
        processed = (
            self.stats["submitted"]
            + self.stats["dry_run"]
            + self.stats["manual_required"]
            + self.stats["skipped"]
            + self.stats["failures"]
        )
        return processed >= self.limit
