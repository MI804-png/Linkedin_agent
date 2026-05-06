from __future__ import annotations

from dataclasses import asdict
    def _direct_external_collect_jobs(self, page, site: dict) -> list[str]:
        """Return a de-duplicated list of job detail/apply URLs from the search page."""
        urls: list[str] = []
        seen: set[str] = set()

        def _is_probable_job_url(href: str) -> bool:
            low = (href or "").lower()
            if not low or low.startswith("javascript") or low.startswith("mailto:"):
                return False
            if site.get("name") == "WeWorkRemotely":
                return "/remote-jobs/" in low and "/company/" not in low and "/listing_ads/" not in low
            if site.get("name") == "RemoteOK":
                return "/remote-jobs/" in low
            if site.get("name") == "Jobicy":
                if "/jobs/" not in low:
                    return False
                tail = low.split("/jobs/", 1)[1]
                return any(ch.isdigit() for ch in tail[:8])
            blocked = (
                "/company", "/companies", "/blog", "/about", "/privacy", "/terms",
                "linkedin.com", "twitter.com", "facebook.com", "instagram.com"
            )
            return not any(b in low for b in blocked)

        for selector in site["card_selectors"]:
            try:
                cards = page.query_selector_all(selector)
                for card in cards:
                    try:
                        hrefs: list[str] = []

                        if site.get("name") == "RemoteOK":
                            try:
                                links = card.query_selector_all("a[href*='/remote-jobs/']")
                                for lk in links:
                                    hrefs.append(lk.get_attribute("href") or "")
                            except Exception:
                                pass

                        if not hrefs:
                            link = card.query_selector("a[href]")
                            if link:
                                hrefs.append(link.get_attribute("href") or "")
                            else:
                                own_href = card.get_attribute("href") or ""
                                if own_href:
                                    hrefs.append(own_href)

                        for href in hrefs:
                            href = (href or "").strip()
                            if not href or not _is_probable_job_url(href):
                                continue
                            if href.startswith("/"):
                                parts = page.url.split("/")
                                if len(parts) >= 3:
                                    href = f"{parts[0]}//{parts[2]}{href}"
                            if href in seen:
                                continue
                            seen.add(href)
                            urls.append(href)
                    except Exception:
                        continue
                if urls:
                    break
            except Exception:
                continue

        if not urls and site.get("name") == "WeWorkRemotely":
            try:
                links = page.query_selector_all("a[href*='/remote-jobs/']")
                for lk in links:
                    href = (lk.get_attribute("href") or "").strip()
                    if not href:
                        continue
                    if href.startswith("/"):
                        href = f"https://weworkremotely.com{href}"
                    low = href.lower()
                    if "/company/" in low or "/listing_ads/" in low:
                        continue
                    if href not in seen:
                        seen.add(href)
                        urls.append(href)
            except Exception:
                pass

        return urls[:20]

    def _find_best_apply_link(self, page, site: dict) -> tuple[Any | None, str]:
        """Find apply action using site selectors first, then robust generic fallbacks."""
        broken_domains = ("aiok.co", "remoteok.com/l/")

        def _is_broken_href(href: str) -> bool:
            low = (href or "").lower()
            if not low.startswith("http"):
                return False
            try:
                host = low.split("/")[2]
            except Exception:
                return False
            for d in broken_domains:
                if "/" in d:
                    if d in low:
                        return True
                else:
                    if host == d or host.endswith(f".{d}"):
                        return True
            return False

        for sel in site.get("apply_btn_selectors", []):
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1200):
                    href = (btn.get_attribute("href") or "").strip()
                    if _is_broken_href(href):
                        continue
                    return btn, href
            except Exception:
                continue

        generic_selectors = [
            "a:has-text('Apply now')",
            "a:has-text('Apply for this job')",
            "a:has-text('Apply for this position')",
            "a:has-text('Apply')",
            "button:has-text('Apply now')",
            "button:has-text('Apply')",
            "a[href*='apply']",
            "a[href*='careers']",
            "a[href*='jobs']",
        ]
        for sel in generic_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=900):
                    href = (btn.get_attribute("href") or "").strip()
                    if _is_broken_href(href):
                        continue
                    return btn, href
            except Exception:
                continue

        try:
            anchors = page.query_selector_all("a[href]")
        except Exception:
            anchors = []

        blocked_domains = (
            "remoteok.com", "weworkremotely.com", "jobicy.com", "europeremotejobs.com",
            "linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com", "t.me"
        )

        for a in anchors[:150]:
            try:
                href = (a.get_attribute("href") or "").strip()
                txt = (a.inner_text() or "").strip().lower()
                if not href or href.startswith("/"):
                    continue
                hlow = href.lower()
                if not hlow.startswith("http"):
                    continue
                if any(d in hlow for d in blocked_domains):
                    continue
                if _is_broken_href(href):
                    continue
                if any(k in txt for k in ("apply", "job", "position", "career", "open role")):
                    return None, href
            except Exception:
                continue

        for a in anchors[:150]:
            try:
                href = (a.get_attribute("href") or "").strip()
                if not href or href.startswith("/"):
                    continue
                hlow = href.lower()
                if not hlow.startswith("http"):
                    continue
                if any(d in hlow for d in blocked_domains):
                    continue
                if _is_broken_href(href):
                    continue
                return None, href
            except Exception:
                continue

        return None, ""

    def _open_external_apply_target(self, context, page, apply_btn, btn_href: str, site: dict):
        """Open apply destination from button/href and return a target page when it becomes external."""
        target_page = None
        note = ""

        normalized_href = (btn_href or "").strip()
        if normalized_href.startswith("/"):
            parts = page.url.split("/")
            if len(parts) >= 3:
                normalized_href = f"{parts[0]}//{parts[2]}{normalized_href}"

        current_host = ""
        try:
            current_host = page.url.split("/")[2].lower()
        except Exception:
            current_host = ""

        def _is_broken_host(href: str) -> bool:
            low = (href or "").lower()
            if not low.startswith("http"):
                return False
            try:
                host = low.split("/")[2]
            except Exception:
                return False
            return host == "aiok.co" or host.endswith(".aiok.co")

        def _is_externalish(href: str) -> bool:
            low = (href or "").lower()
            if not low:
                return False
            if "/l/" in low or "apply" in low:
                return True
            if low.startswith("http"):
                try:
                    host = low.split("/")[2]
                    return host != current_host
                except Exception:
                    return True
            return False

        if normalized_href and _is_broken_host(normalized_href):
            note = f"skipped broken redirect domain: {normalized_href[:80]}"
            normalized_href = ""

        if normalized_href and _is_externalish(normalized_href):
            try:
                target_page = context.new_page()
                self._setup_page_as_human(target_page)
                target_page.goto(normalized_href, wait_until="domcontentloaded", timeout=18000)
                self._human_reading_pause(0.8, 1.6)
                final_url = target_page.url
                if _is_broken_host(final_url):
                    try:
                        target_page.close()
                    except Exception:
                        pass
                    note = f"redirect ended at dead domain: {final_url[:80]}"
                else:
                    return target_page, "opened apply href"
            except Exception as exc:
                note = f"open href failed: {exc}"

        if apply_btn is not None:
            before_url = page.url
            try:
                with page.expect_popup(timeout=3500) as popup_info:
                    self._human_move_mouse_to(page, apply_btn)
                    self._human_pause(0.1, 0.25)
                    apply_btn.click(timeout=3500)
                target_page = popup_info.value
                self._setup_page_as_human(target_page)
                target_page.wait_for_load_state("domcontentloaded", timeout=15000)
                self._human_reading_pause(0.8, 1.6)
                return target_page, "opened popup from apply click"
            except Exception:
                try:
                    self._human_move_mouse_to(page, apply_btn)
                    self._human_pause(0.1, 0.2)
                    apply_btn.click(timeout=3000)
                except Exception:
                    pass

            try:
                page.wait_for_load_state("domcontentloaded", timeout=9000)
            except Exception:
                pass

            after_url = page.url
            if after_url != before_url:
                try:
                    after_host = after_url.split("/")[2].lower()
                except Exception:
                    after_host = ""
                if after_host and after_host != current_host:
                    return page, "navigated to external host after apply click"
                if _is_externalish(after_url):
                    return page, "navigated to external apply route after click"

        return None, note or "no external destination opened"

    def _direct_external_apply_one(self, context, job_url: str, site: dict, stats: dict) -> bool:
        """Open one job page and attempt to apply. Returns True if submitted."""
        page = context.new_page()
        self._setup_page_as_human(page)
        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=18000)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            self._human_reading_pause(1.2, 2.8)

            page_issue = self._detect_external_page_error(page, job_url)
            if page_issue:
                self._log(f"[DIRECT-EXT] Skipping - {page_issue}")
                stats["skipped"] += 1
                return False

            wall = self._detect_external_account_wall(page)
            if wall:
                self._log(f"[DIRECT-EXT] Account wall on {job_url[:60]}: {wall}")
                login_ok, login_note = self._try_external_login(page)
                if login_ok:
                    self._log(f"[DIRECT-EXT] {login_note}")
                    self._human_reading_pause(0.6, 1.2)
                else:
                    self._log(f"[DIRECT-EXT] {login_note}")
                    stats["skipped"] += 1
                    return False

            title = ""
            company = ""
            try:
                title = (page.locator("h1").first.inner_text(timeout=2000) or "").strip()[:80]
            except Exception:
                pass
            try:
                company = (page.locator("[class*='company']").first.inner_text(timeout=1500) or "").strip()[:50]
            except Exception:
                pass
            self._log(f"[DIRECT-EXT] Applying: {title} @ {company} | {job_url[:60]}")

            apply_btn, btn_href = self._find_best_apply_link(page, site)
            if not apply_btn and not btn_href:
                self._log(f"[DIRECT-EXT] No apply button found on {job_url[:60]}")
                stats["skipped"] += 1
                return False

            ext_page, ext_note = self._open_external_apply_target(context, page, apply_btn, btn_href, site)

            if ext_page is not None:
                self._current_report = {"qa_pairs": {}, "uploaded_files": [], "external_ats": {}}
                self._log(f"[DIRECT-EXT] Apply route opened: {ext_note}")

                err = self._detect_external_page_error(ext_page, ext_page.url)
                if err:
                    self._log(f"[DIRECT-EXT] {err}")
                    stats["skipped"] += 1
                    return False

                wall2 = self._detect_external_account_wall(ext_page)
                if wall2:
                    self._log(f"[DIRECT-EXT] {wall2}")
                    login_ok, login_note = self._try_external_login(ext_page)
                    if login_ok:
                        self._log(f"[DIRECT-EXT] {login_note}")
                        self._human_reading_pause(0.6, 1.2)
                    else:
                        self._log(f"[DIRECT-EXT] {login_note}")
                        stats["skipped"] += 1
                        return False

                ats = self._detect_ats(ext_page.url)
                self._log(f"[DIRECT-EXT] ATS: {ats} | {ext_page.url[:70]}")
                try:
                    ok, note = self._fill_generic_external(ext_page)
                except Exception as fill_exc:
                    ok, note = False, f"ATS fill exception: {fill_exc}"
                if ok:
                    stats["submitted"] += 1
                    self._log(f"[DIRECT-EXT] Submitted via {ats}: {note}")
                    return True
                self._log(f"[DIRECT-EXT] Could not submit: {note}")
                stats["failures"] += 1
                return False

            self._current_report = {"qa_pairs": {}, "uploaded_files": [], "external_ats": {}}
            if apply_btn is not None:
                self._human_move_mouse_to(page, apply_btn)
                self._human_pause(0.1, 0.25)
                apply_btn.click(timeout=3000)
            self._human_reading_pause(0.8, 1.8)

            wall3 = self._detect_external_account_wall(page)
            if wall3:
                self._log(f"[DIRECT-EXT] {wall3}")
                login_ok, login_note = self._try_external_login(page)
                if login_ok:
                    self._log(f"[DIRECT-EXT] {login_note}")
                    self._human_reading_pause(0.5, 1.0)
                else:
                    self._log(f"[DIRECT-EXT] {login_note}")
                    stats["skipped"] += 1
                    return False

            try:
                ok, note = self._fill_generic_external(page)
            except Exception as fill_exc:
                ok, note = False, f"Inline fill exception: {fill_exc}"
            if ok:
                stats["submitted"] += 1
                self._log(f"[DIRECT-EXT] Submitted inline: {note}")
                return True
            self._log(f"[DIRECT-EXT] Inline fill failed: {note}")
            stats["failures"] += 1
            return False
        finally:
            try:
                page.close()
            except Exception:
                pass

        if any(k in q for k in years_kws):
            return str(profile.total_experience_years or "3")
        if any(k in q for k in auth_kws):
            return str(work_auth or "Open to discussion")
        if any(k in q for k in eu_kws):
            return "yes" if profile.is_eu_citizen else "no"
        if any(k in q for k in nationality_kws):
            return profile.nationality or None
        if any(k in q for k in salary_kws):
            return str(salary or "Open to discussion")
        if any(k in q for k in notice_kws):
            return "Immediate"
        if any(k in q for k in relocate_kws):
            return "yes" if profile.willing_to_relocate else "no"
        if any(k in q for k in onsite_kws):
            return "yes" if profile.willing_to_work_onsite else "no"
        if any(k in q for k in travel_kws):
            return "yes" if profile.willing_to_relocate else "no"
        if any(k in q for k in remote_kws):
            return "yes" if profile.willing_to_work_remote else "no"
        if any(k in q for k in education_level_kws):
            return profile.highest_education or "Bachelor's Degree"
        if any(k in q for k in education_year_kws):
            return str(profile.graduation_year or "2027")
        if any(k in q for k in field_study_kws):
            return profile.field_of_study or "Computer Science"
        if any(k in q for k in language_proficiency_kws):
            return profile.english_proficiency or "Professional"
        if any(k in q for k in languages_spoken_kws):
            return profile.languages_spoken or "English, Arabic"
        if any(k in q for k in driver_cat_kws):
            return profile.drivers_license_category if profile.has_drivers_license else "None"
        if any(k in q for k in driver_kws):
            return "yes" if profile.has_drivers_license else "no"
        if any(k in q for k in linkedin_kws):
            return profile.linkedin_url or None
        if any(k in q for k in github_kws):
            return profile.github_url or None
        if any(k in q for k in portfolio_kws):
            return profile.portfolio_url or profile.github_url or None
        if any(k in q for k in job_title_kws):
            return profile.current_job_title or None
        if any(k in q for k in management_kws):
            return profile.years_management_experience or "0"
        if any(k in q for k in disability_kws):
            return "yes" if profile.has_disability else "no"
        if any(k in q for k in veteran_kws):
            return profile.veteran_status or "No"
        if any(k in q for k in gender_kws):
            return profile.gender or None
        if any(k in q for k in source_kws):
            return "LinkedIn"

        # Identity/contact style prompts (many languages)
        if any(k in q for k in ("email", "e-mail", "mail")):
            return profile.email or None
        if any(k in q for k in ("phone", "mobile", "telefono", "telefon", "tel")):
            return profile.phone or None
        if any(k in q for k in ("full name", "nome", "name", "nom", "nombre")):
            return profile.full_name or None
        if any(k in q for k in ("location", "city", "citta", "stadt", "ville", "ciudad")):
            return profile.location or None

        return None

    def _is_yes_token(self, text: str) -> bool:
        t = (text or "").strip().lower()
        yes_tokens = (
            "yes", "y", "true", "si", "sÃ¬", "ja", "oui", "sim", "evet", "igen",
            "available", "authorized", "eligible", "consent", "accept", "agree",
            "disponibile", "autorizzato", "eligible to work",
        )
        return any(tok == t or tok in t for tok in yes_tokens)

    def _is_no_token(self, text: str) -> bool:
        t = (text or "").strip().lower()
        no_tokens = (
            "no", "n", "false", "non", "nein", "pas", "nao", "nÃ£o",
            "not authorized", "not eligible", "none", "nessuno", "ninguno",
        )
        return any(tok == t or tok in t for tok in no_tokens)

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
        # When running visibly, force the window to appear maximized in the foreground.
        # slow_mo adds a delay (ms) between each Playwright action so a human can follow along.
        visible_args = [] if headless else ["--start-maximized", "--window-position=0,0"]
        launch_kw: dict = {"headless": headless, "args": visible_args}
        if not headless:
            launch_kw["slow_mo"] = 120  # 120 ms between actions â€“ watchable but not sluggish
        for channel in ["chrome", "msedge"]:
            try:
                browser = playwright.chromium.launch(channel=channel, **launch_kw)
                break
            except Exception:
                continue
        if browser is None:
            browser = playwright.chromium.launch(**launch_kw)
        self._active_browser = browser

        # On Windows, try to bring the new browser window to the foreground so it
        # doesn't hide behind VS Code or other applications.
        if not headless:
            try:
                import time as _time, subprocess as _sp
                _time.sleep(1.5)  # give Chrome a moment to open
                _sp.run(
                    ["powershell", "-WindowStyle", "Hidden", "-Command",
                     "Add-Type -TypeDefinition '"
                     "using System; using System.Runtime.InteropServices;"
                     "public class WU { [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr h); }';"
                     "$p=Get-Process chrome,msedge -EA SilentlyContinue"
                     " | Sort StartTime -Desc | Select -First 1;"
                     "if($p -and $p.MainWindowHandle -ne 0){[WU]::SetForegroundWindow($p.MainWindowHandle)}"],
                    shell=False, timeout=5
                )
            except Exception:
                pass
        context = browser.new_context(
            storage_state=str(self.config.paths.browser_state_path)
            if self.config.paths.browser_state_path.exists()
            else None
        )
        self._active_context = context
        page = context.new_page()

        try:
            self._login(page)
            # Reset daily state cursor unless resuming
            if not self.resume:
                self.state = {"combo_index": 0, "job_offset": 0, "priority_index": 0}
            self._process_search_combinations(page)
        finally:
            hold_seconds = 0
            try:
                hold_seconds = int(getattr(self.config.settings, "watch_hold_seconds", 0) or 0)
            except Exception:
                hold_seconds = 0
            if not headless and hold_seconds > 0:
                try:
                    page.bring_to_front()
                except Exception:
                    pass
                print(f"[WATCH] Run finished. Keeping browser open for {hold_seconds}s.")
                try:
                    page.wait_for_timeout(hold_seconds * 1000)
                except Exception:
                    time.sleep(hold_seconds)
            context.storage_state(path=str(self.config.paths.browser_state_path))
            context.close()
            browser.close()
            self._active_context = None
            self._active_browser = None

    def _login(self, page) -> None:
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        # Wait for any post-load redirects to settle (LinkedIn may redirect /feed/ â†’ /mynetwork/grow/)
        try:
            page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
        # Already logged in if any authenticated LinkedIn page is shown
        if self._is_authenticated(page):
            return

        # Session expired â€” delete stale state file and re-login
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
        # Wait for redirect chain to complete (e.g. /login â†’ /mynetwork/grow/ when session still valid)
        try:
            page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass

        # User may have clicked a saved-account tile / session still active â€” check if already logged in
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

    def _normalize_job_url(self, href: str) -> str | None:
        if not href:
            return None
        full_url = href
        if href.startswith("/"):
            full_url = f"https://www.linkedin.com{href}"
        if "/jobs/view/" not in full_url:
            return None
        return full_url.split("?")[0]

    def _collect_priority_job_urls(self, page) -> list[dict[str, Any]]:
        if not self.config.settings.prioritize_recommended_jobs:
            return []

        ranked: dict[str, dict[str, Any]] = {}

        # User-maintained file containing LinkedIn job links copied from Gmail alerts.
        gmail_links = self._read_priority_links_from_file()
        for url in gmail_links:
            ranked[url] = {
                "url": url,
                "priority_score": 300,
                "source": "gmail_alert",
            }

        if self.config.settings.scan_linkedin_notifications:
            for scraper in (
                self._collect_notification_job_urls,       # /notifications/ page
                self._collect_jobs_recommended_page_urls,  # /jobs/ recommended section
                self._collect_profile_activity_job_urls,   # /feed/ + /mynetwork/ profile activity
            ):
                for item in scraper(page):
                    url = item["url"]
                    existing = ranked.get(url)
                    if not existing or item["priority_score"] > existing["priority_score"]:
                        ranked[url] = item

        return sorted(
            ranked.values(),
            key=lambda item: (item.get("priority_score", 0), item.get("url", "")),
            reverse=True,
        )

    def _read_priority_links_from_file(self) -> list[str]:
        path = self.config.paths.gmail_alert_links_path
        if not path.exists():
            return []

        seen: set[str] = set()
        urls: list[str] = []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        for raw_match in re.findall(r"https?://[^\s<>'\"]+", content):
            clean = self._normalize_job_url(raw_match)
            if clean and clean not in seen:
                urls.append(clean)
                seen.add(clean)
        return urls

    def _collect_notification_job_urls(self, page) -> list[dict[str, Any]]:
        try:
            page.goto("https://www.linkedin.com/notifications/", wait_until="domcontentloaded", timeout=60_000)
            self._human_pause()
            self._progressive_scroll(page, iterations=5)
            page.wait_for_load_state("domcontentloaded", timeout=10_000)
            anchors = page.query_selector_all("a[href*='/jobs/view/']")
        except Exception:
            return []

        recommended_tokens = (
            "recommended",
            "for you",
            "matches your profile",
            "job alert",
            "new jobs",
            "we found",
            "you may be interested",
        )

        ranked: dict[str, dict[str, Any]] = {}
        for anchor in anchors:
            try:
                href = anchor.get_attribute("href") or ""
                url = self._normalize_job_url(href)
                if not url:
                    continue

                anchor_text = (anchor.inner_text() or "").strip().lower()
                card_text = ""
                try:
                    card_text = (
                        anchor.evaluate(
                            "el => (el.closest('li, article, div') && el.closest('li, article, div').innerText) || ''"
                        )
                        or ""
                    ).strip().lower()
                except Exception:
                    card_text = ""

                combined = f"{anchor_text} {card_text}".strip()
                score = 220 if any(tok in combined for tok in recommended_tokens) else 180
                source = "linkedin_notification_recommended" if score >= 220 else "linkedin_notification"

                existing = ranked.get(url)
                if not existing or score > existing["priority_score"]:
                    ranked[url] = {
                        "url": url,
                        "priority_score": score,
                        "source": source,
                    }
            except Exception:
                continue

        return list(ranked.values())

    def _collect_jobs_recommended_page_urls(self, page) -> list[dict[str, Any]]:
        """Scrape the LinkedIn Jobs homepage 'Recommended for you' section."""
        ranked: dict[str, dict[str, Any]] = {}
        try:
            page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded", timeout=60_000)
            self._human_pause()
            self._progressive_scroll(page, iterations=6)
            page.wait_for_load_state("domcontentloaded", timeout=10_000)
            anchors = page.query_selector_all("a[href*='/jobs/view/']")
        except Exception:
            return []

        recommended_section_tokens = (
            "recommended for you",
            "based on your profile",
            "because you viewed",
            "because you applied",
            "top job picks",
            "jobs you may like",
            "suggested for you",
        )

        for anchor in anchors:
            try:
                href = anchor.get_attribute("href") or ""
                url = self._normalize_job_url(href)
                if not url:
                    continue

                card_text = ""
                try:
                    card_text = (
                        anchor.evaluate(
                            "el => { let n = el.closest('section, li, article, div[data-job-id]'); return n ? n.innerText : ''; }"
                        )
                        or ""
                    ).strip().lower()
                except Exception:
                    card_text = ""

                is_recommended = any(tok in card_text for tok in recommended_section_tokens)
                score = 250 if is_recommended else 200
                source = "jobs_page_recommended" if is_recommended else "jobs_page"

                existing = ranked.get(url)
                if not existing or score > existing["priority_score"]:
                    ranked[url] = {"url": url, "priority_score": score, "source": source}
            except Exception:
                continue

        return list(ranked.values())

    def _collect_profile_activity_job_urls(self, page) -> list[dict[str, Any]]:
        """Scrape job links surfaced in the LinkedIn feed and 'My Network' page that relate
        to the current user's profile activity (e.g. 'People in your network are hiring')."""
        ranked: dict[str, dict[str, Any]] = {}

        sources = [
            ("https://www.linkedin.com/feed/", 4),
            ("https://www.linkedin.com/mynetwork/", 4),
        ]

        activity_tokens = (
            "hiring",
            "job opening",
            "open role",
            "is hiring",
            "recommended",
            "your network",
            "people you know",
            "for you",
        )

        for url_to_visit, scroll_iters in sources:
            try:
                page.goto(url_to_visit, wait_until="domcontentloaded", timeout=60_000)
                # Keep job-page stabilization very short so we click Apply faster.
                self._human_pause(0.1, 0.25)
                self._progressive_scroll(page, iterations=scroll_iters)
                page.wait_for_load_state("domcontentloaded", timeout=10_000)
                anchors = page.query_selector_all("a[href*='/jobs/view/']")
            except Exception:
                continue

            for anchor in anchors:
                try:
                    href = anchor.get_attribute("href") or ""
                    url = self._normalize_job_url(href)
                    if not url:
                        continue

                    card_text = ""
                    try:
                        card_text = (
                            anchor.evaluate(
                                "el => { let n = el.closest('div[data-urn], li, article'); return n ? n.innerText : ''; }"
                            )
                            or ""
                        ).strip().lower()
                    except Exception:
                        card_text = ""

                    is_activity = any(tok in card_text for tok in activity_tokens)
                    score = 210 if is_activity else 170
                    source = "profile_activity_recommended" if is_activity else "feed_job_link"

                    existing = ranked.get(url)
                    if not existing or score > existing["priority_score"]:
                        ranked[url] = {"url": url, "priority_score": score, "source": source}
                except Exception:
                    continue

        return list(ranked.values())

    def _process_search_combinations(self, page) -> None:
        priority_jobs = self._collect_priority_job_urls(page)
        start_priority = self.state.get("priority_index", 0) if self.resume else 0

        for priority_index, item in enumerate(priority_jobs[start_priority:], start=start_priority):
            if self._reached_limit():
                self.state["priority_index"] = priority_index
                self._write_state()
                return

            job_url = item["url"]
            self.stats["scanned"] += 1
            self.state["priority_index"] = priority_index
            self._write_state()

            job_id = self._extract_job_id(job_url)
            if self._already_seen(job_id):
                self.stats["skipped"] += 1
                continue

            if self.stop_requested:
                self.state["priority_index"] = priority_index
                self._write_state()
                return

            result = self._process_single_job(page, job_url, job_id, "")
            result["priority_source"] = item.get("source", "priority_queue")
            result["priority_score"] = item.get("priority_score", 0)
            self._record_job(result)
            if hasattr(self, '_on_job_result') and callable(self._on_job_result):
                try:
                    self._on_job_result(result)
                except Exception as _cb_exc:
                    import sys
                    print(f"[_on_job_result error] {_cb_exc}", file=sys.stderr)

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

                if self.stop_requested:
                    self.state["combo_index"] = combo_index
                    self.state["job_offset"] = job_offset
                    self._write_state()
                    return

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
        self.state["priority_index"] = 0
        self._write_state()

    def _sync_search_apply_filter(self, page, apply_type: str) -> None:
        desired_easy_apply = apply_type == "easy_apply"
        chip_selectors = [
            "button[aria-label*='Easy Apply']",
            "button:has-text('Easy Apply')",
            "[role='button']:has-text('Easy Apply')",
        ]

        for selector in chip_selectors:
            try:
                chip = page.locator(selector).first
                if chip.count() == 0:
                    continue

                aria_pressed = (chip.get_attribute("aria-pressed") or "").strip().lower()
                class_name = (chip.get_attribute("class") or "").strip().lower()
                is_selected = aria_pressed == "true" or "selected" in class_name or "active" in class_name

                if is_selected == desired_easy_apply:
                    return

                print(f"[INFO] Toggling Easy Apply search chip for apply_type={apply_type}")
                chip.click(timeout=10_000)
                self._human_pause(0.6, 1.2)
                return
            except Exception:
                continue

    def _collect_job_urls(self, page, keyword: str, location: str) -> list[str]:
        encoded_keyword = quote_plus(keyword)
        encoded_location = quote_plus(location)
        wt_map = {
            "on_site": "1",
            "remote": "2",
            "hybrid": "3",
        }
        wt_value = wt_map.get((self.config.settings.workplace_type or "").strip().lower())
        apply_type = (getattr(self.config.settings, "apply_type", "easy_apply") or "easy_apply").strip().lower()
        search_url = (
            "https://www.linkedin.com/jobs/search/"
            f"?keywords={encoded_keyword}&location={encoded_location}"
            f"&f_TPR=r{self.config.settings.posted_days_ago * 86400}"
        )
        if apply_type == "easy_apply":
            search_url += "&f_LF=f_AL"
        if wt_value:
            search_url += f"&f_WT={wt_value}"

        # Retry navigation up to 3 times to handle transient network timeouts.
        nav_timeout = 30_000
        for _nav_attempt in range(3):
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=nav_timeout)
                break
            except Exception as _nav_err:
                if _nav_attempt == 2:
                    raise
                import time as _time
                _time.sleep(2)
        self._human_pause()
        self._sync_search_apply_filter(page, apply_type)
        self._progressive_scroll(page, iterations=10)

        # Broad anchor match â€” job cards use multiple link patterns across LinkedIn versions
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
        # Reset per-job submission report
        self._current_report = {"qa_pairs": {}, "uploaded_files": [], "external_ats": {}}
        for attempt in range(self.config.settings.retries_per_job + 1):
            try:
                for _nav_attempt in range(3):
                    try:
                        page.goto(job_url, wait_until="domcontentloaded", timeout=30_000)
                        break
                    except Exception:
                        if _nav_attempt == 2:
                            raise
                        import time as _time
                        _time.sleep(2)

                # Verify we actually landed on the job page (LinkedIn may redirect
                # to /feed/, /mynetwork/, error pages, or "grow your network" pages)
                landed_url = page.url or ""
                if "/jobs/view/" not in landed_url:
                    import sys as _sys
                    print(
                        f"[SKIP] Redirected away from job page.\n"
                        f"  Expected: {job_url}\n"
                        f"  Landed:   {landed_url}",
                        file=_sys.stderr,
                    )
                    self.stats["skipped"] += 1
                    return self._job_record(job_id, job_url, "", "", "", "skipped", f"Redirected to {landed_url}")

                # Check for LinkedIn error messages ("job posting has been removed" etc.)
                try:
                    error_heading = page.query_selector("h1.artdeco-empty-state__headline, .error-headline, h2.t-20")
                    if error_heading:
                        err_text = (error_heading.inner_text() or "").strip().lower()
                        if any(kw in err_text for kw in ("unable to load", "no longer available", "job posting", "removed", "not found")):
                            import sys as _sys
                            print(f"[SKIP] LinkedIn error page: {err_text!r}", file=_sys.stderr)
                            self.stats["skipped"] += 1
                            return self._job_record(job_id, job_url, "", "", "", "skipped", f"Error page: {err_text}")
                except Exception:
                    pass

                self._human_pause()

                title = (
                    self._text_or_empty(page, ".job-details-jobs-unified-top-card__job-title h1")
                    or self._text_or_empty(page, "h1.t-24")
                    or self._text_or_empty(page, ".t-24[data-qa='title']")
                    or self._text_or_empty(page, "[data-qa='top-card-title']")
                    or self._text_or_empty(page, "h1")
                )
                company = (
                    self._text_or_empty(page, ".job-details-jobs-unified-top-card__company-name a")
                    or self._text_or_empty(page, ".job-details-jobs-unified-top-card__company-name")
                    or self._text_or_empty(page, ".jobs-unified-top-card__company-name a")
                    or self._text_or_empty(page, ".jobs-unified-top-card__company-name")
                    or self._text_or_empty(page, ".jobs-unified-top-card__primary-description a")
                    or self._text_or_empty(page, ".job-details-jobs-unified-top-card__primary-description a")
                    or self._text_or_empty(page, "[data-qa='top-card-company-name']")
                    or self._text_or_empty(page, "a[data-tracking-control-name*='company']")
                    or self._text_or_empty(page, ".topcard__org-name-link")
                )

                # Fallback parse from browser title if LinkedIn DOM selectors miss.
                if not title or not company:
                    try:
                        page_title = (page.title() or "").strip()
                        cleaned = re.sub(r"\s*\|\s*LinkedIn.*$", "", page_title, flags=re.I)
                        if " - " in cleaned:
                            left, right = cleaned.split(" - ", 1)
                            if not title and left.strip():
                                title = left.strip()
                            if not company and right.strip():
                                company = right.strip()
                    except Exception:
                        pass
                
                # Debug: if extraction failed, save page for inspection
                if not title or not company:
                    import sys as _sys
                    print(f"[DEBUG] Extraction failed - title={title!r} company={company!r}", file=_sys.stderr)
                    self._save_debug_artifacts(page, f"job_detail_extraction_fail_{job_id}")
                
                requirements = self._extract_job_requirements(page)
                place = (
                    self._text_or_empty(page, ".job-details-jobs-unified-top-card__tertiary-description")
                    or self._text_or_empty(page, ".jobs-unified-top-card__bullet")
                    or self._text_or_empty(page, "span[class*='workplace-type']")
                )

                # Extract skills from job description for skill gap analysis
                missing_skills_data = None
                try:
                    job_skills = extract_skills_from_text(requirements)
                    user_skills = get_user_skills(self.config.profile, self.config.settings)
                    skills_analysis = compare_skills(job_skills, user_skills)
                    missing_skills_data = {
                        "missing_skills": skills_analysis.get("missing", []),
                        "matched_skills": skills_analysis.get("matched", []),
                        "match_percentage": skills_analysis.get("match_percentage", 0),
                        "job_skills": job_skills
                    }
                except Exception as e:
                    import sys as _sys
                    print(f"[WARN] Skill extraction failed: {e}", file=_sys.stderr)
                    missing_skills_data = None

                # Store for AI context inside autofill/dropdown helpers
                self._current_title = title
                self._current_company = company

                apply_element = self._find_apply_button(page)
                if not apply_element:
                    self.stats["skipped"] += 1
                    return self._job_record(job_id, job_url, title, company, place, "skipped", "No apply button", missing_skills=missing_skills_data)

                # Detect Easy Apply by href or text
                href = (apply_element.get_attribute("href") or "").lower()
                button_text = (apply_element.inner_text() or "").strip().lower()
                aria = (apply_element.get_attribute("aria-label") or "").lower()
                is_easy_apply = "opensdui" in href or "easy apply" in button_text or "easy apply" in aria

                apply_type = getattr(self.config.settings, "apply_type", "easy_apply")

                # Filter by apply_type setting
                if is_easy_apply and apply_type == "external_only":
                    self.stats["skipped"] += 1
                    return self._job_record(job_id, job_url, title, company, place, "skipped", "Easy Apply skipped (external_only mode)", missing_skills=missing_skills_data)

                if not is_easy_apply and apply_type == "easy_apply":
                    self.stats["skipped"] += 1
                    return self._job_record(job_id, job_url, title, company, place, "skipped", "External job skipped (easy_apply mode)", missing_skills=missing_skills_data)

                if is_easy_apply:
                    if self.dry_run:
                        self.stats["dry_run"] += 1
                        return self._job_record(job_id, job_url, title, company, place, "dry_run", "Easy Apply found", missing_skills=missing_skills_data)

                    ok, fail_reason = self._run_easy_apply(
                        page,
                        location,
                        title=title,
                        company=company,
                        requirements=requirements,
                    )
                    if ok:
                        self.stats["submitted"] += 1
                        self._save_job_requirements(job_id, title, company, job_url, requirements)
                        hr_msg_result = self._try_message_poster(page, job_url, title, company)
                        note = "Easy Apply submitted"
                        if hr_msg_result:
                            note = f"{note} | HR: {hr_msg_result}"
                        return self._job_record(job_id, job_url, title, company, place, "submitted", note, report=self._current_report, missing_skills=missing_skills_data)

                    if fail_reason and fail_reason.lower().startswith("external apply detected"):
                        self.stats["manual_required"] += 1
                        return self._job_record(
                            job_id,
                            job_url,
                            title,
                            company,
                            place,
                            "manual_required",
                            fail_reason,
                            missing_skills=missing_skills_data,
                        )

                    self.stats["failures"] += 1
                    return self._job_record(job_id, job_url, title, company, place, "failed", fail_reason or "Easy Apply flow failed", missing_skills=missing_skills_data)

                # Non-Easy-Apply job: try to fill external ATS form automatically
                ext_ok, ext_note = self._apply_on_external_site(page)
                if ext_ok:
                    self.stats["submitted"] += 1
                    self._save_job_requirements(job_id, title, company, job_url, requirements)
                    return self._job_record(
                        job_id, job_url, title, company, place,
                        "submitted", f"External ATS: {ext_note}", report=self._current_report,
                        missing_skills=missing_skills_data,
                    )
                else:
                    self.stats["manual_required"] += 1
                    return self._job_record(
                        job_id, job_url, title, company, place,
                        "manual_required", f"External (partial): {ext_note}", report=self._current_report,
                        missing_skills=missing_skills_data,
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

    def _detect_form_errors(self, page) -> list[str]:
        """Detect and return validation error messages on the current form."""
        errors: list[str] = []
        try:
            # Prefer scanning inside the Easy Apply modal only.
            modal = None
            for modal_sel in [
                ".jobs-easy-apply-content",
                ".jobs-apply-form",
                "div[role='dialog']",
            ]:
                try:
                    modal = page.query_selector(modal_sel)
                    if modal:
                        break
                except Exception:
                    continue

            scan_root = modal if modal else page

            # Look for validation messages that belong to form fields.
            error_selectors = [
                ".artdeco-inline-feedback--error",
                ".form-field__error-message",
                "[data-test-id*='error']",
                "span:has-text('Please enter a valid')",
                "span.artdeco-inline-feedback__message",
            ]
            for sel in error_selectors:
                try:
                    err_els = scan_root.query_selector_all(sel)
                    for err in err_els:
                        msg = (err.inner_text() or "").strip()
                        if not msg or len(msg) >= 220:
                            continue
                        low = msg.lower()
                        # Ignore global LinkedIn toasts/alerts that are not field validation.
                        if any(token in low for token in (
                            "active job alerts",
                            "you have reached the limit",
                            "dismiss",
                            "premium",
                        )):
                            continue
                        if msg not in errors:
                            errors.append(msg)
                except Exception:
                    continue
        except Exception:
            pass
        return errors

    def _is_generic_required_error(self, msg: str) -> bool:
        low = (msg or "").strip().lower()
        return low in {
            "required",
            "this field is required",
            "please fill out this field",
            "field is required",
            "required field",
        } or low.startswith("required")

    def _run_easy_apply(
        self,
        page,
        location: str,
        *,
        title: str = "",
        company: str = "",
        requirements: str = "",
    ) -> tuple[bool, str]:
        # â”€â”€ Step 1: open the Easy Apply flow â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Click first (faster and avoids full-page reload). Fall back to direct URL.
        apply_url = self._get_easy_apply_url(page)
        apply_btn = self._find_apply_button(page)
        if not apply_btn and not apply_url:
            return False, "No apply button found"

        clicked = False
        if apply_btn:
            # Try up to 3 click strategies before fallback navigation.
            for _ in range(3):
                try:
                    apply_btn.click(timeout=3000)
                    print("[EASY_APPLY] Opened via click")
                    clicked = True
                    break
                except Exception:
                    pass
                try:
                    page.locator(
                        "button#jobs-apply-button-id, "
                        "button[aria-label*='Easy Apply'], "
                        "a[aria-label*='Easy Apply']"
                    ).first.click(timeout=3000, force=True)
                    print("[EASY_APPLY] Opened via forced locator click")
                    clicked = True
                    break
                except Exception:
                    pass
                self._human_pause(0.2, 0.4)

        # Quick check whether the flow opened from click before reloading the page.
        if clicked:
            try:
                page.wait_for_selector(
                    ".jobs-easy-apply-content, [data-test-modal], button[aria-label*='Continue to next step']",
                    timeout=3500,
                )
            except Exception:
                clicked = False

        if not clicked and apply_url:
            print("[EASY_APPLY] Falling back to direct apply URL")
            page.goto(apply_url, wait_until="domcontentloaded", timeout=15000)
            self._human_pause(0.3, 0.7)
            clicked = True

        if not clicked:
            return False, "Could not open Easy Apply"

        # â”€â”€ Step 2: wait for the modal/flow to actually render â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Use real wait_for_selector (up to 8 s) so we don't proceed on a blank page.
        MODAL_SELECTORS = [
            ".jobs-easy-apply-content",
            "[data-test-modal]",
            "button[aria-label*='Continue to next step']",
            "button[aria-label*='Continue']",
            "button:has-text('Continue')",
            "button:has-text('Next')",
            "button:has-text('Review')",
            "button[aria-label*='Submit application']",
            "button:has-text('Submit application')",
        ]
        flow_ready = False
        for sel in MODAL_SELECTORS:
            try:
                page.wait_for_selector(sel, timeout=5000)
                flow_ready = True
                break
            except Exception:
                continue

        if not flow_ready:
            # One last check: if the Easy Apply button is gone the flow may have
            # opened as a full-page redirect; accept that too.
            if not page.query_selector("button#jobs-apply-button-id"):
                flow_ready = True  # button consumed â†’ assume flow is open

        if not flow_ready:
            # Could be the daily limit dialog instead of the form
            if self._check_easy_apply_limit(page):
                return False, "Daily Easy Apply limit reached"
            self._dismiss_apply_flow(page)
            return False, f"Easy Apply dialog did not open after clicking | URL: {page.url}"

        # â”€â”€ Handle Resume / Cover-letter file pickers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # LinkedIn stores previously uploaded files as radio buttons.
        # Only upload a NEW file when there is no existing selection,
        # to avoid accumulating duplicate copies.
        self._handle_file_inputs(page, title=title, company=company, requirements=requirements)
        # Wait for LinkedIn to finish processing any uploaded file before proceeding.
        self._wait_for_upload_processing(page)

        for step in range(12):
            # Dismiss any LinkedIn toast notifications that may overlap the form
            # (e.g. "You have reached the limit of 20 active job alerts").
            self._dismiss_linkedin_toasts(page)

            # Check for the daily Easy Apply limit dialog
            if self._check_easy_apply_limit(page):
                self.stop_requested = True  # no more applications today
                return False, "Daily Easy Apply limit reached"

            # Check stop flag between Easy Apply steps so a stop request
            # takes effect mid-job rather than waiting for the next job.
            if self.stop_requested:
                self._dismiss_apply_flow(page)
                return False, "Stopped by user"

            if "linkedin.com" not in (page.url or "").lower():
                return False, f"External apply detected | URL: {page.url}"
            # Sometimes Easy Apply exits to similar-jobs listing instead of the form.
            # Treat this as an external/manual flow to avoid looping until max steps.
            if "/jobs/collections/" in (page.url or "").lower():
                return False, f"External apply detected | URL: {page.url}"

            self._autofill_visible_fields(
                page,
                location,
                title=title,
                company=company,
                requirements=requirements,
            )

            # Check for validation errors after autofill
            validation_errors = self._detect_form_errors(page)
            if validation_errors:
                # Log the errors for debugging
                print(f"[VALIDATION] Step {step+1} errors: {validation_errors[:3]}")
                # Try one more autofill pass in case fields were refilled
                self._human_pause(0.5, 1.0)
                self._autofill_visible_fields(
                    page,
                    location,
                    title=title,
                    company=company,
                    requirements=requirements,
                )
                self._human_pause(0.5, 1.0)
                validation_errors = self._detect_form_errors(page)
                if validation_errors:
                    # Only fail fast on specific blocking validation messages.
                    # Generic "Required" often appears transiently before user actions.
                    blocking = [e for e in validation_errors if not self._is_generic_required_error(e)]
                    if blocking:
                        reason = f"Form validation failed on step {step+1}: {'; '.join(blocking[:2])}"
                        self._dismiss_apply_flow(page)
                        return False, reason

                    missing_prompts = self._collect_missing_required_prompts(page)
                    if missing_prompts:
                        print(f"[VALIDATION] Step {step+1} missing prompts: {missing_prompts[:4]}")

            actions = self._collect_apply_actions(page)
            selected_kind = self._ai_choose_apply_action(page, actions, step=step + 1, title=title, company=company)
            selected_btn = None
            for a in actions:
                if a.get("kind") == selected_kind:
                    selected_btn = a.get("element")
                    break

            if selected_kind == "submit" and selected_btn:
                try:
                    # Final pass: ensure required fields and consent checkboxes are satisfied.
                    self._autofill_visible_fields(
                        page,
                        location,
                        title=title,
                        company=company,
                        requirements=requirements,
                    )
                    selected_btn.click()
                    self._human_pause()
                    if "linkedin.com" not in (page.url or "").lower():
                        return False, f"External apply detected | URL: {page.url}"
                    self._close_apply_modal(page)
                    return True, ""
                except Exception:
                    pass

            if not selected_btn:
                # If the original Easy Apply button is still present, dialog likely never opened.
                if page.query_selector("button#jobs-apply-button-id"):
                    self._dismiss_apply_flow(page)
                    return False, f"Easy Apply dialog did not open | URL: {page.url}"

                # Check for validation errors on the page
                errors = page.query_selector_all("[data-test-form-element-error-message], .artdeco-inline-feedback--error")
                error_texts = []
                for err in errors[:5]:
                    try:
                        error_texts.append((err.inner_text() or "").strip())
                    except Exception:
                        pass
                missing_prompts = self._collect_missing_required_prompts(page)
                reason = f"Stuck on step {step+1}"
                if error_texts:
                    reason += f" â€” validation errors: {'; '.join(error_texts)}"
                if missing_prompts:
                    reason += f" â€” missing answers: {'; '.join(missing_prompts[:4])}"
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

            try:
                # Final pass: ensure required fields and consent checkboxes are satisfied.
                self._autofill_visible_fields(
                    page,
                    location,
                    title=title,
                    company=company,
                    requirements=requirements,
                )
                selected_btn.click()
                self._human_pause()
                if "linkedin.com" not in (page.url or "").lower():
                    return False, f"External apply detected | URL: {page.url}"
            except Exception:
                # Keep old behavior if selected button interaction failed.
                pass

            # After clicking Next, new required fields may have appeared (or
            # existing ones show validation errors). Try to autofill them and
            # click Next up to 2 extra times before giving up.
            for _retry in range(2):
                post_errors = page.query_selector_all(
                    "[data-test-form-element-error-message], .artdeco-inline-feedback--error"
                )
                if not post_errors:
                    break  # No errors â€” page advanced fine.

                # Try to fill whatever is still empty/invalid and retry click.
                self._autofill_visible_fields(
                    page,
                    location,
                    title=title,
                    company=company,
                    requirements=requirements,
                )
                self._fill_required_fields_fallback(page, location)
                self._force_fill_experience_fields(page, self.config.profile.total_experience_years)
                self._human_pause(0.5, 1.0)

                retry_btn = page.query_selector(
                    "button[aria-label='Continue to next step'], "
                    "button[aria-label*='Review your application'], "
                    "button:has-text('Review'), button:has-text('Next')"
                )
                if not retry_btn:
                    break
                try:
                    retry_btn.click()
                    self._human_pause()
                except Exception:
                    break

            # Final error check after retries.
            post_errors = page.query_selector_all("[data-test-form-element-error-message], .artdeco-inline-feedback--error")
            if post_errors:
                stuck_errors = []
                for err in post_errors[:5]:
                    try:
                        stuck_errors.append((err.inner_text() or "").strip())
                    except Exception:
                        pass
                missing_prompts = self._collect_missing_required_prompts(page)
                reason = f"Stuck on step {step+1} (validation)"
                if stuck_errors:
                    reason += f" â€” errors: {'; '.join(stuck_errors)}"
                if missing_prompts:
                    reason += f" â€” unanswered: {'; '.join(missing_prompts[:4])}"
                reason += f" | URL: {page.url}"
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                log_dir = self.config.paths.base_dir.parent.parent / "linkedin_bot" / "logs"
                try:
                    page.screenshot(path=str(log_dir / f"stuck_{step+1}_{ts}.png"))
                    (log_dir / f"stuck_{step+1}_{ts}.html").write_text(page.content(), encoding="utf-8")
                except Exception:
                    pass
                self._dismiss_apply_flow(page)
                return False, reason

        self._dismiss_apply_flow(page)
        return False, "Exceeded max steps (12)"

    def _fill_date_range_pickers(self, page) -> None:
        """Fill Month/Year dropdowns for date range pickers (From/To employment dates).
        LinkedIn often uses: <label>From</label> + <select name='month'> + <select name='year'>
                            <label>To</label> + <select name='month'> + <select name='year'>
        """
        try:
            # Find all Month dropdowns
            month_selects = page.query_selector_all("select[name*='month' i]")
            if not month_selects:
                return

            for i, month_sel in enumerate(month_selects):
                try:
                    # Get the label before this select (usually "From" or "To")
                    parent = month_sel
                    label_text = ""
                    for _ in range(5):
                        try:
                            prev_el = parent.query_selector("xpath=preceding-sibling::*[1]")
                            if not prev_el:
                                break
                            t = (prev_el.inner_text() or "").lower()
                            if "from" in t or "to" in t or "start" in t or "end" in t:
                                label_text = t
                                break
                            parent = prev_el
                        except Exception:
                            break

                    # Get associated year select (should be next sibling or in same parent)
                    year_sel = None
                    try:
                        year_sel = month_sel.query_selector("xpath=following-sibling::select[1]")
                    except Exception:
                        pass

                    if not year_sel:
                        try:
                            parent_container = month_sel.query_selector("xpath=ancestor::div[1]")
                            year_sel = parent_container.query_selector("select[name*='year' i]")
                        except Exception:
                            pass

                    # Pick a month and year based on whether it's From or To
                    if "from" in label_text or "start" in label_text:
                        # Start date: use 2 years ago
                        pick_month = "01"
                        pick_year = str(datetime.now().year - 2)
                    else:
                        # End date / To: use current date or "Currently working"
                        # But if there's a "Currently working" option, prefer that
                        try:
                            current_opt = month_sel.query_selector("option:has-text('Current'), option:has-text('current'), option:has-text('Present')")
                            if current_opt:
                                month_sel.select_option(label=current_opt.inner_text())
                                self._human_pause(0.2, 0.4)
                                continue
                        except Exception:
                            pass
                        pick_month = str(datetime.now().month).zfill(2)
                        pick_year = str(datetime.now().year)

                    # Fill month select
                    try:
                        month_sel.select_option(value=pick_month)
                    except Exception:
                        try:
                            # Fallback: select by label
                            month_names = ["January", "February", "March", "April", "May", "June",
                                          "July", "August", "September", "October", "November", "December"]
                            month_idx = int(pick_month) - 1
                            if 0 <= month_idx < 12:
                                month_sel.select_option(label=month_names[month_idx])
                        except Exception:
                            pass

                    self._human_pause(0.2, 0.4)

                    # Fill year select
                    if year_sel:
                        try:
                            year_sel.select_option(value=pick_year)
                        except Exception:
                            try:
                                year_sel.select_option(label=pick_year)
                            except Exception:
                                pass
                        self._human_pause(0.2, 0.4)
                except Exception:
                    continue
        except Exception:
            pass

    def _autofill_visible_fields(
        self,
        page,
        location: str,
        *,
        title: str = "",
        company: str = "",
        requirements: str = "",
    ) -> None:
        # First, fill any date range pickers (Month/Year dropdowns for From/To dates)
        self._fill_date_range_pickers(page)
        self._human_pause(0.5, 1.0)

        profile = self.config.profile
        work_auth = profile.work_authorization_hungary if "hungary" in location.lower() else profile.work_authorization_italy
        salary = profile.salary_hungary if "hungary" in location.lower() else profile.salary_italy

        fill_map = {
            "first name": profile.full_name.split(" ")[0],
            "last name": profile.full_name.split(" ")[-1],
            "full name": profile.full_name,
            "name": profile.full_name,
            "full legal name": profile.full_name,
            "legal name": profile.full_name,
            "email": profile.email,
            "phone": profile.phone,
            "mobile": profile.phone,
            "city": profile.location,
            "location": profile.location,
            # English experience/salary
            "experience": profile.total_experience_years,
            "how many year": profile.total_experience_years,
            "years of experience": profile.total_experience_years,
            "salary": salary,
            "compensation": salary,
            "salary expect": salary,
            "confirm your salary": salary,
            "expected salary": salary,
            "desired salary": salary,
            "aspettativa": salary,
            "authorization": work_auth,
            "work permit": work_auth,
            "graduation": profile.graduation_year,
            # Notice period (text field variant)
            "notice period": "Immediate",
            "preavviso": "0",
            "periodo di preavviso": "0",
            # "How did you first hear about this job?"
            "first hear": "LinkedIn",
            "come hai conosciuto": "LinkedIn",
            "come sei venuto a conoscenza": "LinkedIn",
            # Italian experience fields
            "anni di esperienza": profile.total_experience_years,
            "anni di lavoro": profile.total_experience_years,
            "quanti anni": profile.total_experience_years,
            "anni lavorat": profile.total_experience_years,
            "anni con": profile.total_experience_years,
            "anni nel": profile.total_experience_years,
            "anni nello": profile.total_experience_years,
            # German experience fields
            "wie viele jahre": profile.total_experience_years,
            "jahre erfahrung": profile.total_experience_years,
            "erfahrung haben sie": profile.total_experience_years,
            "erfahrung mit": profile.total_experience_years,
            "erfahrung in": profile.total_experience_years,
            "jahre mit": profile.total_experience_years,
            # Italian salary
            "aspettativa econom": salary,
            "ral attuale": salary,
            "ral ": salary,
            "retribuzione": salary,
            "stipendio": salary,
        }

        try:
            inputs = page.query_selector_all("input, textarea")
        except Exception:
            inputs = []

        for input_el in inputs:
            input_type = (input_el.get_attribute("type") or "text").lower()
            if input_type in {"hidden", "submit", "button", "checkbox", "radio", "file"}:
                continue

            # Detect email fields early so we can override stale browser autofill values.
            email_meta_hint = " ".join(
                filter(
                    None,
                    [
                        input_el.get_attribute("name"),
                        input_el.get_attribute("id"),
                        input_el.get_attribute("placeholder"),
                        input_el.get_attribute("aria-label"),
                        input_type,
                    ],
                )
            ).lower()
            is_email_field = input_type == "email" or any(
                k in email_meta_hint for k in ("email", "e-mail", "mail")
            )

            input_mode = (input_el.get_attribute("inputmode") or "").lower()
            input_pattern = (input_el.get_attribute("pattern") or "").lower()
            numeric_like_input = (
                input_type == "number"
                or input_mode in {"numeric", "decimal"}
                or bool(re.search(r"\\d", input_pattern))
            )

            value = (input_el.input_value() or "").strip()
            value_low = value.lower()
            placeholder_like_value = value_low in {
                "select", "select an option", "choose", "choose one",
                "month", "year", "n/a", "none", "null",
            }
            # Skip already-filled fields, BUT for number inputs "0" is a LinkedIn
            # default placeholder that usually fails their own validation â€” refill it.
            force_fix_email = (
                is_email_field
                and bool(profile.email)
                and value.lower() != profile.email.strip().lower()
            )
            if value and not placeholder_like_value and not (numeric_like_input and value in {"0", "0.0"}) and not force_fix_email:
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
                    # LinkedIn uses <fieldset><legend> for experience questions
                    parent_fieldset = input_el.query_selector("xpath=ancestor::fieldset[1]")
                    if parent_fieldset:
                        legend = parent_fieldset.query_selector("legend")
                        if legend:
                            label_text = (legend.inner_text() or "").strip()
                        else:
                            label_text = (parent_fieldset.inner_text() or "").strip().split("\n")[0]
                if not label_text:
                    # Walk up to enclosing div and grab first span/h3 text
                    for _ in range(5):
                        try:
                            parent = input_el.query_selector("xpath=..")
                            if not parent:
                                break
                            span = parent.query_selector("span, h3, h4, label")
                            if span:
                                t = (span.inner_text() or "").strip()
                                if len(t) > 4:
                                    label_text = t
                                    break
                        except Exception:
                            break
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
            if force_fix_email:
                chosen = profile.email.strip()
            for key, mapped in fill_map.items():
                if key in metadata and mapped:
                    chosen = str(mapped)
                    break

            # Fallback for ANY number input that was not matched above.
            # Italian LinkedIn asks "Quanti anni ... con [Tech]?" â€” label contains
            # "anni" even when technology name is not in fill_map.
            if not chosen and numeric_like_input:
                year_kws = (
                    "year", "anni", "experience", "esperienza",
                    "how many", "quanti", "erfahrung", "jahre",
                )
                salary_kws = (
                    "salary", "aspettativa", "ral", "retribuzione", "stipendio",
                    "compensation", "wage",
                )
                if any(kw in metadata for kw in year_kws):
                    chosen = str(profile.total_experience_years or "3")
                elif any(kw in metadata for kw in salary_kws):
                    chosen = str(salary or "35000")
                else:
                    # Unknown numeric question: use safe value that passes field constraints.
                    chosen = self._fallback_numeric_value(input_el)

            # AI fallback: for any text/textarea with no matched answer, ask Ollama.
            # This handles open-ended questions like "Why do you want this role?",
            # "Describe yourself", custom screening questions in any language.
            if not chosen and input_type in ("text", "textarea", ""):
                question_text = label_text or metadata
                inferred = self._infer_profile_answer(question_text, location)
                if inferred:
                    chosen = inferred
                motivation_kws = (
                    "motivation", "motivational", "cover letter", "lettera di presentazione",
                    "why do you want", "why this role", "why this company",
                    "perche", "pourquoi", "por que", "warum",
                )
                if any(k in question_text.lower() for k in motivation_kws):
                    chosen = self._generate_motivation_letter(
                        question=question_text,
                        job_title=title,
                        company=company,
                        requirements=requirements,
                    )
                if len(question_text) > 10:  # Only if we have a real question
                    if not chosen:
                        ai_resp = self._ai_answer(question_text, job_title=title, company=company)
                        if ai_resp:
                            chosen = ai_resp
                if not chosen:
                    # Unknown text question fallback.
                    chosen = self._text_unknown_fallback(metadata)

            if chosen:
                # Track Q&A for submission report â€” only real visible questions.
                # Skip internal/hidden field names (recaptcha, search tokens, etc.)
                _skip_kws = ("recaptcha", "g-recaptcha", "search", "token", "csrf",
                             "hidden", "_key", "_id", "_val", "__")
                q_text = (label_text or "").strip()
                if q_text and not any(k in q_text.lower() for k in _skip_kws):
                    self._current_report["qa_pairs"][q_text] = chosen[:200]
                try:
                    # Detect decimal field (step attribute like "0.1", "0.01", "any")
                    step_attr = (input_el.get_attribute("step") or "").strip()
                    is_decimal = (step_attr and step_attr not in ("1", "")) or input_mode == "decimal"
                    if is_decimal:
                        try:
                            fval = float(chosen)
                            if fval <= 0:
                                chosen = self._fallback_numeric_value(input_el)
                                fval = float(chosen)
                            chosen = f"{fval:.1f}"
                        except ValueError:
                            chosen = self._fallback_numeric_value(input_el)

                    is_location_field = any(kw in metadata for kw in ("city", "location", "location (city)"))

                    if is_location_field and input_type in ("text", "search", ""):
                        # Typeahead field: explicitly select a suggestion when available.
                        picked = self._fill_location_typeahead(page, input_el, chosen)
                        if not picked:
                            input_el.triple_click()
                            input_el.type(chosen, delay=60)
                            self._human_pause(0.2, 0.4)
                            page.keyboard.press("ArrowDown")
                            page.keyboard.press("Enter")
                            self._human_pause(0.2, 0.4)
                    elif numeric_like_input or is_decimal:
                        # Focus first so React registers the interaction
                        try:
                            input_el.focus()
                        except Exception:
                            pass
                        # Use JS nativeInputValueSetter â€” fires React synthetic onChange
                        set_ok = False
                        try:
                            page.evaluate("""
                            (el, val) => {
                                var setter = Object.getOwnPropertyDescriptor(
                                    window.HTMLInputElement.prototype, 'value').set;
                                setter.call(el, val);
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                                el.dispatchEvent(new Event('blur',  { bubbles: true }));
                            }
                            """, input_el, chosen)
                            set_ok = True
                        except Exception:
                            pass
                        if not set_ok:
                            # Fallback: triple-click and type
                            try:
                                input_el.triple_click()
                                page.keyboard.type(chosen, delay=40)
                                page.keyboard.press("Tab")
                            except Exception:
                                pass
                        self._human_pause(0.2, 0.4)
                    else:
                        # Text / textarea: triple_click to select all then type replacement
                        input_el.triple_click()
                        self._human_pause(0.1, 0.2)
                        page.keyboard.type(chosen, delay=35)
                        page.keyboard.press("Tab")
                        self._human_pause(0.2, 0.4)
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
                selected_text = ""
                selected_opt = sel.query_selector("option:checked")
                if selected_opt:
                    selected_text = (selected_opt.inner_text() or "").strip().lower()
            except Exception:
                current = ""
                selected_text = ""
            has_meaningful_value = (
                bool(current)
                and not self._is_placeholder_option_value(current)
                and not self._is_placeholder_option_text(selected_text)
            )
            if has_meaningful_value:
                continue

            try:
                # Walk up the DOM to collect as much context as possible so keyword
                # matching works even when the question text is outside the fieldset.
                ancestor_fieldset = sel.query_selector("xpath=ancestor::fieldset[1]")
                ancestor_div = sel.query_selector("xpath=ancestor::div[3]")
                meta = " ".join(
                    filter(
                        None,
                        [
                            sel.get_attribute("name"),
                            sel.get_attribute("id"),
                            sel.get_attribute("aria-label"),
                            (ancestor_fieldset.inner_text() if ancestor_fieldset else ""),
                            (ancestor_div.inner_text() if ancestor_div else ""),
                        ],
                    )
                ).lower()
            except Exception:
                meta = ""

            try:
                req_attr = (sel.get_attribute("required") or "").strip().lower()
                aria_req = (sel.get_attribute("aria-required") or "").strip().lower()
            except Exception:
                req_attr = ""
                aria_req = ""
            is_required_select = (
                req_attr in {"required", "true", "1"}
                or aria_req == "true"
                or "required" in meta
                or "obbligatorio" in meta
                or "pflicht" in meta
            )

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
                if self._is_placeholder_option_text(txt):
                    continue
                non_empty.append((val, txt))

            if not non_empty:
                continue

            inferred_answer = self._infer_profile_answer(meta, location) or ""

            if any(k in meta for k in ("email", "e-mail", "mail", "correo", "posta elettronica")):
                # Some Easy Apply forms ask contact method/email-routing with a select.
                # User preference: default to the second available answer when present.
                if len(non_empty) >= 2:
                    pick_value = non_empty[1][0]
                else:
                    pick_value = non_empty[0][0]
            elif "authorization" in meta or "work permit" in meta or "eligible" in meta:
                target_yes = self._is_yes_token(work_auth or "yes")
                for val, txt in non_empty:
                    if target_yes and self._is_yes_token(txt):
                        pick_value = val
                        break
                    if not target_yes and self._is_no_token(txt):
                        pick_value = val
                        break
            elif any(k in meta for k in ("eu citizen", "european union citizen", "eu citizenship",
                                         "cittadino ue", "cittadinanza ue")):
                target_yes = profile.is_eu_citizen
                for val, txt in non_empty:
                    if target_yes and self._is_yes_token(txt):
                        pick_value = val
                        break
                    if not target_yes and self._is_no_token(txt):
                        pick_value = val
                        break
            elif "proficiency" in meta and "english" in meta:
                pref_order = ["professional", "advanced", "fluent", "full professional", "c2", "c1"]
                for pref in pref_order:
                    for val, txt in non_empty:
                        if pref in txt:
                            pick_value = val
                            break
                    if pick_value:
                        break
            elif (
                "how many year" in meta
                or "quanti anni" in meta
                or "anni di esperienza" in meta
                or "anni di lavoro" in meta
                or ("year" in meta and ("experience" in meta or "abap" in meta or "sap" in meta))
                or ("anni" in meta and ("esperienza" in meta or "lavoro" in meta))
            ):
                pick_value = self._pick_years_option(non_empty, profile.total_experience_years)
            elif "language" in meta and "hungarian" in meta:
                for val, txt in non_empty:
                    if "none" in txt:
                        pick_value = val
                        break
            elif any(k in meta for k in ("privacy", "policy", "terms", "consent", "gdpr", "recruitment privacy", "statement")):
                positive_tokens = ("agree", "accept", "consent", "acknowledge", "read", "understand", "yes", "i do")
                for val, txt in non_empty:
                    if any(tok in txt for tok in positive_tokens):
                        pick_value = val
                        break
            elif any(k in meta for k in ("location", "city", "citta", "stadt", "ville", "ciudad", "based", "living")):
                pick_value = self._pick_location_option(non_empty, profile.location, location)

            # Generic inferred-answer matching for multilingual selects.
            if not pick_value and inferred_answer:
                if self._is_yes_token(inferred_answer):
                    for val, txt in non_empty:
                        if self._is_yes_token(txt):
                            pick_value = val
                            break
                elif self._is_no_token(inferred_answer):
                    for val, txt in non_empty:
                        if self._is_no_token(txt):
                            pick_value = val
                            break
                elif re.search(r"\b\d{1,2}\b", inferred_answer):
                    pick_value = self._pick_years_option(non_empty, inferred_answer)
                else:
                    answer_tokens = [t for t in re.findall(r"[a-zA-Z0-9#+.]+", inferred_answer.lower()) if len(t) > 2]
                    for val, txt in non_empty:
                        if any(tok in txt for tok in answer_tokens[:4]):
                            pick_value = val
                            break

            if not pick_value:
                # Generic yes/no fallback: if the options are clearly yes/no, pick
                # based on whether this is a capability/availability question.
                # For location/commute questions the user can't guarantee â†’ pick first.
                # For capability questions ("have you done X?") â†’ pick yes (first option).
                if len(non_empty) == 2:
                    opt_texts = [t for _, t in non_empty]
                    has_yes = any(self._is_yes_token(t) for t in opt_texts)
                    has_no = any(self._is_no_token(t) for t in opt_texts)
                    if has_yes and has_no:
                        # Commute/location questions: answer yes (can cover hours / live nearby)
                        commute_kws = ("vicinanze", "coprire", "distanza", "raggiungere",
                                       "commute", "nearby", "travel", "sede", "orari",
                                       "kuendigungsfrist", "disponibil")
                        choose_yes = any(k in meta for k in commute_kws) or True  # default yes
                        for val, txt in non_empty:
                            if choose_yes and self._is_yes_token(txt):
                                pick_value = val
                                break
                            if not choose_yes and self._is_no_token(txt):
                                pick_value = val
                                break

            # AI fallback: ask Ollama to pick the best option for any unknown question.
            # This handles arbitrary multilingual dropdowns without needing keyword rules.
            if not pick_value:
                ai_pick = self._ai_pick_dropdown_option(
                    question=meta,
                    options=non_empty,
                    job_title=getattr(self, "_current_title", ""),
                    company=getattr(self, "_current_company", ""),
                )
                if ai_pick:
                    pick_value = ai_pick

            if not pick_value:
                # Optional unknown dropdowns: don't guess random answers.
                if not is_required_select:
                    continue
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

            is_required_group = any(
                tok in prompt for tok in (
                    "required", "obbligatorio", "pflicht", "mandatory", "*"
                )
            )

            choose_yes = None
            if any(token in prompt for token in ["authorized", "work permit", "eligible to work"]):
                choose_yes = self._is_yes_token(work_auth or "yes")
            elif any(k in prompt for k in ("eu citizen", "european union citizen", "eu citizenship",
                                           "cittadino ue", "cittadinanza ue")):
                choose_yes = profile.is_eu_citizen
            elif any(token in prompt for token in ["on-site", "onsite", "on site", "commut",
                                                    "in-office", "in office", "presenza"]):
                choose_yes = profile.willing_to_work_onsite
            elif any(token in prompt for token in ["relocat", "trasfer", "umzug"]):
                choose_yes = profile.willing_to_relocate
            elif any(token in prompt for token in ["travel", "viagg", "reisen"]):
                choose_yes = profile.willing_to_relocate
            elif any(token in prompt for token in ["remote", "hybrid", "work from home", "wfh"]):
                choose_yes = profile.willing_to_work_remote
            elif any(token in prompt for token in ["disability", "disabilita", "behinderung"]):
                choose_yes = profile.has_disability
            elif any(token in prompt for token in ["driver", "driving license", "patente"]):
                choose_yes = profile.has_drivers_license
            else:
                inferred_prompt_answer = self._infer_profile_answer(prompt, location)
                if inferred_prompt_answer is not None:
                    if self._is_yes_token(inferred_prompt_answer):
                        choose_yes = True
                    elif self._is_no_token(inferred_prompt_answer):
                        choose_yes = False

            chosen_radio = None
            if "proficiency" in prompt and "english" in prompt:
                for radio in group:
                    try:
                        rid = radio.get_attribute("id") or ""
                        lbl = page.query_selector(f"label[for='{rid}']") if rid else None
                        txt = ((lbl.inner_text() if lbl else "") or "").strip().lower()
                    except Exception:
                        txt = ""
                    if any(token in txt for token in ["professional", "advanced", "fluent", "c1", "c2"]):
                        chosen_radio = radio
                        break

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
                if choose_yes is True and self._is_yes_token(txt):
                    chosen_radio = radio
                    break
                if choose_yes is False and self._is_no_token(txt):
                    chosen_radio = radio
                    break

            if not chosen_radio:
                # Optional unknown radio groups: only answer if inferable from profile.
                if choose_yes is None and not is_required_group:
                    continue
                chosen_radio = group[0]

            try:
                chosen_radio.check(force=True)
                self._human_pause(0.2, 0.6)
            except Exception:
                continue

        # Tick required/consent checkboxes in a language-agnostic way.
        # Prefer structural signals (required attrs, validation errors, asterisk labels)
        # over language-specific text.
        try:
            checkboxes = page.query_selector_all("input[type='checkbox']")
        except Exception:
            checkboxes = []

        # Keep broad keywords as a secondary hint across common languages.
        policy_kws = (
            "policy", "privacy", "terms", "consent", "gdpr", "data processing",
            "trattamento", "termini", "condizioni", "informativa",
            # Italian consent phrases
            "presto", "consenso", "accettare", "accetto", "dichiaro",
            "letto", "accettazione", "conferma",
            # Other common languages
            "datenschutz", "einwilligung", "zustimmung", "bedingungen",
            "confidentialite", "consentement", "conditions",
            "acepto", "consiento", "privacidad", "terminos",
            "aceitar", "consentimento", "privacidade", "termos",
        )

        visible_enabled_count = 0
        for cb in checkboxes:
            try:
                if cb.is_visible() and not cb.is_disabled():
                    visible_enabled_count += 1
            except Exception:
                continue

        for cb in checkboxes:
            try:
                if cb.is_checked():
                    continue
                if cb.is_disabled():
                    continue
                if not cb.is_visible():
                    continue
            except Exception:
                continue

            try:
                cb_id = cb.get_attribute("id") or ""
                label_txt = ""
                if cb_id:
                    lbl = page.query_selector(f"label[for='{cb_id}']")
                    if lbl:
                        label_txt = (lbl.inner_text() or "").strip()
                if not label_txt:
                    # Also check the parent container for any text
                    try:
                        parent = cb.query_selector("xpath=..")
                        if parent:
                            label_txt = (parent.inner_text() or "").strip()
                    except Exception:
                        pass
                meta = " ".join(
                    filter(
                        None,
                        [
                            cb.get_attribute("name"),
                            cb_id,
                            cb.get_attribute("aria-label"),
                            label_txt,
                        ],
                    )
                ).lower()
            except Exception:
                meta = ""

            required_flag = False
            try:
                required_flag = (cb.get_attribute("required") is not None) or ((cb.get_attribute("aria-required") or "").lower() == "true")
            except Exception:
                required_flag = False

            has_error_nearby = False
            try:
                has_error_nearby = bool(
                    cb.query_selector(
                        "xpath=ancestor::*[contains(@class,'fb-form-element') or contains(@class,'jobs-easy-apply-form-section')][1]"
                    )
                ) and bool(
                    cb.query_selector(
                        "xpath=ancestor::*[contains(@class,'fb-form-element') or contains(@class,'jobs-easy-apply-form-section')][1]//*[contains(@class,'inline-feedback--error') or contains(@class,'form-element-error-message')]"
                    )
                )
            except Exception:
                has_error_nearby = False

            has_required_marker = "*" in (label_txt or "")
            is_policy = any(k in meta for k in policy_kws)
            looks_mandatory = required_flag or has_error_nearby or has_required_marker

            # If there is exactly one checkbox in the visible form and it's empty,
            # it is almost always the mandatory consent checkbox regardless of language.
            single_checkbox_fallback = visible_enabled_count == 1

            if not (looks_mandatory or is_policy or single_checkbox_fallback):
                continue

            try:
                cb.check(force=True)
                self._human_pause(0.2, 0.6)
            except Exception:
                # Fallback: JS click
                try:
                    page.evaluate("el => el.click()", cb)
                    self._human_pause(0.2, 0.4)
                except Exception:
                    pass

        # Final safety pass for tech-specific experience prompts that can be
        # rendered outside normal input/label associations.
        self._fill_required_fields_fallback(page, location)
        self._force_fill_experience_fields(page, profile.total_experience_years)

    def _fill_required_fields_fallback(self, page, location: str) -> None:
        """Universal required-field fallback across different question widgets."""
        profile = self.config.profile
        salary = profile.salary_hungary if "hungary" in (location or "").lower() else profile.salary_italy
        city_only = (profile.location or "").split(",")[0].strip() or (profile.location or "")

        # Inputs / textareas / selects marked required by HTML or ARIA.
        try:
            required_controls = page.query_selector_all(
                "input[required], textarea[required], select[required], "
                "input[aria-required='true'], textarea[aria-required='true'], select[aria-required='true'], "
                "input[aria-invalid='true'], textarea[aria-invalid='true'], select[aria-invalid='true']"
            )
        except Exception:
            required_controls = []

        for el in required_controls:
            try:
                if not el.is_visible() or el.is_disabled():
                    continue
            except Exception:
                continue

            try:
                tag = (el.evaluate("node => node.tagName") or "").lower()
            except Exception:
                tag = ""
            try:
                t = (el.get_attribute("type") or "text").lower()
            except Exception:
                t = "text"
            try:
                input_mode = (el.get_attribute("inputmode") or "").lower()
            except Exception:
                input_mode = ""
            try:
                input_pattern = (el.get_attribute("pattern") or "").lower()
            except Exception:
                input_pattern = ""
            numeric_like = (
                t == "number"
                or input_mode in {"numeric", "decimal"}
                or bool(re.search(r"\\d", input_pattern))
            )
            try:
                current = (el.input_value() or "").strip()
            except Exception:
                current = ""
            if current and not (numeric_like and current in {"0", "0.0"}):
                continue

            try:
                legend_txt = ""
                field_label = ""
                el_id = (el.get_attribute("id") or "").strip()
                if el_id:
                    lbl = page.query_selector(f"label[for='{el_id}']")
                    if lbl:
                        field_label = (lbl.inner_text() or "").strip()
                if not field_label:
                    parent_label = el.query_selector("xpath=ancestor::label[1]")
                    if parent_label:
                        field_label = (parent_label.inner_text() or "").strip()
                try:
                    fs = el.query_selector("xpath=ancestor::fieldset[1]")
                    legend_txt = (fs.inner_text() if fs else "") or ""
                except Exception:
                    legend_txt = ""

                meta = " ".join(
                    filter(
                        None,
                        [
                            el.get_attribute("name"),
                            el.get_attribute("id"),
                            el.get_attribute("aria-label"),
                            el.get_attribute("placeholder"),
                            field_label,
                            legend_txt,
                        ],
                    )
                ).lower()
            except Exception:
                meta = ""

            fill_val = ""
            if tag == "select":
                try:
                    options = el.query_selector_all("option")
                except Exception:
                    options = []
                choice = None
                yn_meta = meta

                inferred_answer = self._infer_profile_answer(yn_meta, location) or ""
                wants_yes = self._is_yes_token(inferred_answer)
                wants_no = self._is_no_token(inferred_answer)

                yes_like = (
                    "yes", "si", "sÃ¬", "ja", "oui", "sim", "true", "agree", "accept", "consent"
                )
                no_like = (
                    "no", "non", "nein", "falso", "false", "decline", "deny"
                )
                notice_like = ("immediate", "subito", "now", "asap", "0", "no notice")
                source_like = ("linkedin",)
                city_tokens = [tkn for tkn in re.findall(r"[a-zA-Z]+", city_only.lower()) if len(tkn) > 2]
                for opt in options:
                    try:
                        val = (opt.get_attribute("value") or "").strip()
                        txt = (opt.inner_text() or "").strip().lower()
                    except Exception:
                        continue
                    if not val or self._is_placeholder_option_text(txt):
                        continue
                    if any(k in yn_meta for k in ("notice", "preavviso", "availability", "start date")) and any(k in txt for k in notice_like):
                        choice = val
                        break
                    if any(k in yn_meta for k in ("first hear", "heard about", "come hai conosciuto", "source")) and any(k in txt for k in source_like):
                        choice = val
                        break
                    if any(k in yn_meta for k in ("city", "location", "citta", "stadt", "ville", "ciudad")) and any(tok in txt for tok in city_tokens):
                        choice = val
                        break
                    if wants_yes and any(k in txt for k in yes_like):
                        choice = val
                        break
                    if wants_no and any(k in txt for k in no_like):
                        choice = val
                        break
                    if any(k in yn_meta for k in ("year", "years", "experience", "esperienza", "quanti anni", "anni di esperienza")):
                        maybe = self._pick_years_option([(val, txt)], profile.total_experience_years)
                        if maybe:
                            choice = maybe
                            break
                    choice = val
                    break
                if choice:
                    try:
                        el.select_option(value=choice)
                    except Exception:
                        pass
                continue

            if numeric_like:
                is_decimal = input_mode == "decimal"
                step_attr = ""
                try:
                    step_attr = (el.get_attribute("step") or "").strip().lower()
                except Exception:
                    step_attr = ""
                if step_attr and step_attr not in ("", "1"):
                    is_decimal = True
                if any(k in meta for k in ("decimal", "decim", "0.0")):
                    is_decimal = True

                if any(k in meta for k in ("salary", "stipendio", "ral", "compensation", "pay")):
                    fill_val = str(salary or "35000")
                elif any(k in meta for k in ("year", "experience", "anni", "esperienza", "quanti")):
                    fill_val = str(profile.total_experience_years or "3")
                elif any(k in meta for k in ("notice", "preavviso", "availability", "start date")):
                    fill_val = "1"  # minimum positive value â€” "available in 1 day/week"
                else:
                    fill_val = self._fallback_numeric_value(el)

                if is_decimal:
                    try:
                        fval = float(fill_val)
                        if fval <= 0:
                            fval = 0.1
                        fill_val = f"{fval:.1f}"
                    except Exception:
                        fill_val = "0.1"
                else:
                    try:
                        ival = int(float(fill_val))
                        if ival < 0:
                            ival = 0
                        fill_val = str(ival)
                    except Exception:
                        fill_val = "1"

                try:
                    page.evaluate(
                        """
                        (input, val) => {
                            input.focus();
                            var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            setter.call(input, val);
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                            input.dispatchEvent(new Event('change', { bubbles: true }));
                            input.dispatchEvent(new Event('blur', { bubbles: true }));
                        }
                        """,
                        el,
                        fill_val,
                    )
                except Exception:
                    try:
                        el.fill(fill_val)
                    except Exception:
                        pass
                continue

            if t in {"email"}:
                fill_val = profile.email or ""
            elif t in {"tel"}:
                fill_val = profile.phone or ""
            elif t in {"date"}:
                # Safe default ISO date accepted by browser controls.
                fill_val = "2026-01-01"
            elif t in {"url"}:
                fill_val = "https://www.linkedin.com/in/"
            else:
                if any(k in meta for k in ("city", "location", "location (city)", "citta", "ciudad", "stadt", "ville")):
                    fill_val = city_only
                elif any(k in meta for k in ("notice", "preavviso", "availability", "start date")):
                    fill_val = "Immediate"
                elif any(k in meta for k in ("first hear", "heard about", "come hai conosciuto", "source")):
                    fill_val = "LinkedIn"
                else:
                    inferred = self._infer_profile_answer(meta, location)
                    fill_val = inferred or self._text_unknown_fallback(meta)

            if fill_val:
                is_location_meta = any(k in meta for k in ("city", "location", "location (city)", "citta", "ciudad", "stadt", "ville"))
                if is_location_meta and t in {"text", "search", ""}:
                    if self._fill_location_typeahead(page, el, fill_val):
                        continue
                try:
                    el.fill(fill_val)
                except Exception:
                    try:
                        el.click()
                        page.keyboard.type(fill_val, delay=20)
                        page.keyboard.press("Tab")
                    except Exception:
                        pass

        # Required radio groups: pick first visible option if unanswered.
        try:
            radios = page.query_selector_all("input[type='radio'][required], input[type='radio'][aria-required='true']")
        except Exception:
            radios = []
        groups: dict[str, list[Any]] = {}
        for r in radios:
            try:
                n = (r.get_attribute("name") or "").strip()
            except Exception:
                n = ""
            if n:
                groups.setdefault(n, []).append(r)
        for _, grp in groups.items():
            try:
                if any(x.is_checked() for x in grp):
                    continue
            except Exception:
                pass
            for x in grp:
                try:
                    if x.is_visible() and not x.is_disabled():
                        x.check(force=True)
                        break
                except Exception:
                    continue

        # Required checkboxes: ensure checked.
        try:
            req_cbs = page.query_selector_all("input[type='checkbox'][required], input[type='checkbox'][aria-required='true']")
        except Exception:
            req_cbs = []
        for cb in req_cbs:
            try:
                if cb.is_visible() and not cb.is_disabled() and not cb.is_checked():
                    cb.check(force=True)
            except Exception:
                try:
                    page.evaluate("el => el.click()", cb)
                except Exception:
                    pass

        # Custom text widgets (contenteditable) sometimes used in multilingual forms.
        try:
            custom_boxes = page.query_selector_all("[contenteditable='true'][role='textbox']")
        except Exception:
            custom_boxes = []
        for box in custom_boxes:
            try:
                txt = (box.inner_text() or "").strip()
                if txt:
                    continue
                box.click()
                page.keyboard.type("Motivated to contribute and open to discussion.", delay=15)
                page.keyboard.press("Tab")
            except Exception:
                continue

    def _force_fill_experience_fields(self, page, years_value: str) -> None:
        """Force-fill experience questions in complex LinkedIn form layouts."""
        try:
            years_float = float((years_value or "3").strip())
        except Exception:
            years_float = 3.0
        years_int = int(years_float)
        years_int = max(0, min(99, years_int))
        years_text = str(years_int)
        years_decimal_text = f"{max(0.1, float(years_int)):.1f}"

        prompt_kws = (
            "experience", "years", "how many", "quanti", "anni", "esperienza",
            "c#", "csharp", ".net", "dotnet", "java", "javascript", "python",
            "kotlin", "swift", "azure", "aws", "react", "angular", "node",
            "consulting", "consulen", "consultan", "iam", "identity", "access management",
            "ssis", "ssrs", "rtos", "agile", "devops", "terraform", "kubernetes", "docker",
            "sql", "mysql", "postgres", "oracle", "mongodb", "redis", "spring", "flask",
        )

        try:
            fieldsets = page.query_selector_all("fieldset")
        except Exception:
            fieldsets = []

        for fs in fieldsets:
            try:
                legend = fs.query_selector("legend")
                prompt = ((legend.inner_text() if legend else fs.inner_text()) or "").lower()
            except Exception:
                prompt = ""

            if not prompt or not any(k in prompt for k in prompt_kws):
                continue

            try:
                num_inputs = fs.query_selector_all(
                    "input[type='number'], input[inputmode='numeric'], input[inputmode='decimal'], "
                    "input[type='text'][inputmode='numeric'], input[type='text'][inputmode='decimal']"
                )
            except Exception:
                num_inputs = []

            for el in num_inputs:
                try:
                    current = (el.input_value() or "").strip()
                except Exception:
                    current = ""
                if current and current != "0":
                    continue
                try:
                    step_attr = (el.get_attribute("step") or "").strip().lower()
                    input_mode = (el.get_attribute("inputmode") or "").strip().lower()
                    is_decimal = (input_mode == "decimal") or (step_attr and step_attr not in ("", "1"))
                    val_to_set = years_decimal_text if is_decimal else years_text
                    page.evaluate(
                        """
                        (input, val) => {
                            input.focus();
                            var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            setter.call(input, val);
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                            input.dispatchEvent(new Event('change', { bubbles: true }));
                            input.dispatchEvent(new Event('blur', { bubbles: true }));
                        }
                        """,
                        el,
                        val_to_set,
                    )
                except Exception:
                    try:
                        el.fill(val_to_set)
                    except Exception:
                        pass

            try:
                txt_inputs = fs.query_selector_all("input[type='text']")
            except Exception:
                txt_inputs = []
            for el in txt_inputs:
                try:
                    if (el.input_value() or "").strip():
                        continue
                    el.fill(years_text)
                except Exception:
                    pass

            try:
                selects = fs.query_selector_all("select")
            except Exception:
                selects = []
            for sel in selects:
                try:
                    opts = sel.query_selector_all("option")
                except Exception:
                    opts = []
                non_empty: list[tuple[str, str]] = []
                for o in opts:
                    try:
                        val = (o.get_attribute("value") or "").strip()
                        txt = (o.inner_text() or "").strip().lower()
                    except Exception:
                        continue
                    if val:
                        non_empty.append((val, txt))
                choice = self._pick_years_option(non_empty, years_text)
                if not choice:
                    continue
                try:
                    sel.select_option(value=choice)
                except Exception:
                    pass

        # Global fallback for empty numeric inputs in the modal.
        try:
            loose_numeric = page.query_selector_all(
                "input[type='number'], input[inputmode='numeric'], input[inputmode='decimal'], "
                "input[type='text'][inputmode='numeric'], input[type='text'][inputmode='decimal']"
            )
        except Exception:
            loose_numeric = []
        for el in loose_numeric:
            try:
                current = (el.input_value() or "").strip()
                if current and current not in {"0", "0.0"}:
                    continue
                step_attr = (el.get_attribute("step") or "").strip().lower()
                input_mode = (el.get_attribute("inputmode") or "").strip().lower()
                is_decimal = (input_mode == "decimal") or (step_attr and step_attr not in ("", "1"))
                val_to_set = years_decimal_text if is_decimal else years_text
                page.evaluate(
                    """
                    (input, val) => {
                        input.focus();
                        var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        setter.call(input, val);
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        input.dispatchEvent(new Event('blur', { bubbles: true }));
                    }
                    """,
                    el,
                    val_to_set,
                )
            except Exception:
                try:
                    el.fill(val_to_set)
                except Exception:
                    pass

    def _pick_years_option(self, options: list[tuple[str, str]], years_value: str) -> str | None:
        """Pick the closest numeric years option, capped to available values."""
        try:
            years = int(float((years_value or "0").strip()))
        except Exception:
            years = 0

        candidates: list[tuple[int, str]] = []
        for val, txt in options:
            src = f"{val} {txt}"
            m = re.search(r"\b(\d{1,2})\b", src)
            if not m:
                continue
            try:
                num = int(m.group(1))
            except Exception:
                continue
            candidates.append((num, val))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0])
        best_val = candidates[0][1]
        for num, val in candidates:
            if num <= years:
                best_val = val
            else:
                break
        return best_val

    def _collect_missing_required_prompts(self, page) -> list[str]:
        prompts: list[str] = []
        try:
            required_fields = page.query_selector_all("input[required], textarea[required], select[required], [aria-required='true']")
        except Exception:
            required_fields = []

        for field in required_fields:
            try:
                tag = (field.evaluate("el => el.tagName") or "").lower()
            except Exception:
                tag = ""
            try:
                value = (field.input_value() or "").strip()
            except Exception:
                value = ""

            if tag == "select":
                if value:
                    continue
            else:
                if value:
                    continue

            label_text = ""
            try:
                fid = field.get_attribute("id") or ""
                if fid:
                    lbl = page.query_selector(f"label[for='{fid}']")
                    if lbl:
                        label_text = (lbl.inner_text() or "").strip()
                if not label_text:
                    fs = field.query_selector("xpath=ancestor::fieldset[1]")
                    if fs:
                        label_text = (fs.inner_text() or "").strip().split("\n")[0]
                if not label_text:
                    label_text = (field.get_attribute("aria-label") or "").strip()
            except Exception:
                label_text = ""

            if label_text:
                prompts.append(label_text)

        # Preserve order and uniqueness.
        return list(dict.fromkeys(prompts))

    def _try_click_apply_on_external(self, page) -> bool:
        """Scan external page for Apply button and click it."""
        self._human_pause(1.2, 2.5)
        # Direct selector scan first
        for selector in [
            "button:has-text('Apply')",
            "a:has-text('Apply')",
            "button[id*='apply']",
            "a[id*='apply']",
            "button[class*='apply']",
            "a[class*='apply']",
            "input[type='submit'][value*='pply']",
        ]:
            try:
                el = page.query_selector(selector)
                if el and el.is_visible():
                    el.click()
                    self._human_pause(0.5, 1.2)
                    return True
            except Exception:
                continue
        # Broader text scan
        try:
            for el in page.query_selector_all("button, a, input[type='submit']"):
                try:
                    txt = (el.inner_text() or el.get_attribute("value") or "").strip().lower()
                    if txt.startswith("apply") and el.is_visible():
                        el.click()
                        self._human_pause(0.5, 1.2)
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    # â”€â”€ Job requirements storage (for interview prep) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _save_job_requirements(self, job_id: str, title: str, company: str,
                                job_url: str, requirements: str) -> None:
        """Persist the full job description text so we can generate a study guide later."""
        try:
            dir_ = self.config.paths.study_guides_dir
            dir_.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^\w\-]", "_", f"{company}_{title}")[:60]
            req_file = dir_ / f"{job_id}_{slug}_requirements.txt"
            req_file.write_text(
                f"Title: {title}\nCompany: {company}\nURL: {job_url}\n\n{requirements}",
                encoding="utf-8",
            )
        except Exception:
            pass

    # â”€â”€ Interview invite detection & study guide generation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    _INTERVIEW_KEYWORDS = (
        "interview", "schedule", "chat with", "call with", "speak with",
        "move forward", "next step", "advance your application", "review your profile",
        "hiring team", "meet the team", "colloquio", "vorstellungsgesprÃ¤ch",
        "entretien", "entrevista", "congratulations", "selected",
    )

    def _scan_messages_for_invites(self, page) -> list[dict]:
        """Scan LinkedIn Messages inbox for interview invitation messages.
        Returns list of dicts: {sender, snippet, matched_keyword, timestamp}
        """
        invites: list[dict] = []
        try:
            page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded", timeout=30000)
            self._human_pause(2.0, 3.5)
            # Wait for conversation list to render
            page.wait_for_selector(".msg-conversations-container__conversations-list, .msg-conversation-listitem", timeout=12000)
            self._human_pause(1.0, 2.0)
            convos = page.query_selector_all(
                ".msg-conversation-listitem__link, .msg-conversations-container__convo-item"
            )
            if not convos:
                convos = page.query_selector_all("li.msg-conversation-listitem")

            for convo in convos[:30]:  # Check the 30 most recent threads
                try:
                    # Extract preview text + sender from the conversation row
                    snippet = (convo.inner_text() or "").lower()
                    if any(kw in snippet for kw in self._INTERVIEW_KEYWORDS):
                        full_text = convo.inner_text() or ""
                        lines = [l.strip() for l in full_text.splitlines() if l.strip()]
                        sender = lines[0] if lines else "Unknown"
                        # Extract timestamp token (LinkedIn shows "2h", "Mon", etc.)
                        ts = lines[-1] if len(lines) > 1 else ""
                        matched = next(kw for kw in self._INTERVIEW_KEYWORDS if kw in snippet)
                        invites.append({"sender": sender, "snippet": full_text[:300], "matched_keyword": matched, "timestamp": ts})
                except Exception:
                    continue
        except Exception:
            pass
        return invites

    def _generate_study_guide(self, title: str, company: str, requirements: str,
                               message_snippet: str = "") -> str:
        """Ask Ollama to produce a focused interview study guide.
        Returns the guide text, or empty string on failure.
        """
        if not requirements.strip():
            return ""
        prompt = (
            f"I have a job interview coming up for the role of '{title}' at '{company}'.\n\n"
            f"Here are the job requirements:\n{requirements[:3000]}\n\n"
        )
        if message_snippet:
            prompt += f"The recruiter's message: {message_snippet[:400]}\n\n"
        prompt += (
            "Please give me a concise interview study guide. Include:\n"
            "1. Key technical topics to review (with brief explanations)\n"
            "2. Likely interview questions and how to approach them\n"
            "3. Technologies/frameworks I should brush up on\n"
            "4. Soft skills and culture points this company likely values\n"
            "5. A suggested 1-week study plan\n\n"
            "Be specific to the role and company. Use bullet points."
        )
        try:
            resp = _requests.post(
                self._OLLAMA_URL,
                json={"model": self._OLLAMA_MODEL, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.3, "num_predict": 1200}},
                timeout=60,
            )
            if resp.status_code == 200:
                return resp.json().get("response", "").strip()
        except Exception:
            pass
        return ""

    def _save_study_guide(self, job_id: str, title: str, company: str, guide: str) -> Path | None:
        """Write the study guide to study_guides/<id>_<company>_<title>_GUIDE.md"""
        try:
            dir_ = self.config.paths.study_guides_dir
            dir_.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^\w\-]", "_", f"{company}_{title}")[:60]
            guide_file = dir_ / f"{job_id}_{slug}_GUIDE.md"
            header = (
                f"# Interview Study Guide\n\n"
                f"**Role:** {title}  \n"
                f"**Company:** {company}  \n"
                f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  \n\n"
                f"---\n\n"
            )
            guide_file.write_text(header + guide, encoding="utf-8")
            return guide_file
        except Exception:
            return None

    def run_interview_prep(self) -> dict[str, Any]:
        """Scan LinkedIn messages for interview invites and generate study guides.
        For each detected invite, matches against applied_jobs.json to find the
        job requirements and produces a Markdown study guide in study_guides/.
        """
        results: list[dict] = []

        with sync_playwright() as p:
            browser = None
            for channel in ["chrome", "msedge"]:
                try:
                    browser = p.chromium.launch(
                        headless=self.config.settings.headless,
                        channel=channel,
                    )
                    break
                except Exception:
                    continue
            if not browser:
                browser = p.chromium.launch(headless=self.config.settings.headless)

            context = browser.new_context(
                storage_state=str(self.config.paths.browser_state_path)
                if self.config.paths.browser_state_path.exists()
                else None
            )
            page = context.new_page()

            try:
                invites = self._scan_messages_for_invites(page)
                print(f"[PREP] Found {len(invites)} potential interview invite(s) in messages.")

                # Build a lookup from submitted jobs
                applied = self._read_json(self.config.paths.applied_log, default=[])
                submitted = [j for j in applied if j.get("status") == "submitted"]

                for invite in invites:
                    sender = invite["sender"]
                    snippet = invite["snippet"]
                    print(f"\n[PREP] Invite from: {sender!r}  ({invite['matched_keyword']!r})")

                    # Match sender company to submitted jobs
                    matched_job = None
                    sender_lower = sender.lower()
                    for job in submitted:
                        company_lower = (job.get("company") or "").lower()
                        if company_lower and company_lower in sender_lower:
                            matched_job = job
                            break
                    # Fallback: most recent submitted job if no company match
                    if not matched_job and submitted:
                        matched_job = submitted[-1]

                    title = (matched_job or {}).get("title", "Unknown Role")
                    company = (matched_job or {}).get("company", sender)
                    job_id = (matched_job or {}).get("job_id", "unknown")
                    job_url = (matched_job or {}).get("job_url", "")

                    # Load saved requirements file if it exists
                    requirements = ""
                    req_candidates = list(self.config.paths.study_guides_dir.glob(f"{job_id}_*_requirements.txt"))
                    if req_candidates:
                        try:
                            requirements = req_candidates[0].read_text(encoding="utf-8")
                        except Exception:
                            pass

                    if not requirements and matched_job:
                        # Fallback: scrape the job page live
                        try:
                            page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
                            self._human_pause(2.0, 3.0)
                            requirements = self._extract_job_requirements(page)
                        except Exception:
                            pass

                    print(f"[PREP] Generating study guide for: {title} @ {company} ...")
                    guide = self._generate_study_guide(title, company, requirements, message_snippet=snippet)

                    if guide:
                        guide_file = self._save_study_guide(job_id, title, company, guide)
                        print(f"[PREP] Study guide saved â†’ {guide_file}")
                        results.append({"sender": sender, "title": title, "company": company, "guide_file": str(guide_file)})
                    else:
                        print(f"[PREP] Could not generate guide (Ollama unavailable?). Saving blank stub.")
                        guide_file = self._save_study_guide(job_id, title, company,
                                                            f"Requirements:\n\n{requirements[:2000]}")
                        results.append({"sender": sender, "title": title, "company": company, "guide_file": str(guide_file)})
            finally:
                context.storage_state(path=str(self.config.paths.browser_state_path))
                context.close()
                browser.close()

        return {"invites_found": len(results), "guides": results}

    # â”€â”€ External ATS auto-apply â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _EXTERNAL_ATS_PATTERNS: dict[str, tuple[str, ...]] = {
        "greenhouse": ("boards.greenhouse.io", "job-boards.greenhouse.io"),
        "lever":      ("jobs.lever.co",),
        "teamtailor": ("teamtailor.com",),
        "workday":    ("myworkdayjobs.com",),
        "ashby":      ("ashbyhq.com", "jobs.ashbyhq.com"),
        "smartrecruiters": ("jobs.smartrecruiters.com",),
        "bamboohr":   ("bamboohr.com",),
        "jobvite":    ("jobs.jobvite.com", "jobvite.com"),
        "icims":      ("icims.com", "icims.jobs"),
        "recruitee":  ("recruitee.com",),
        "personio":   ("personio.com",),
        "successfactors": ("jobs.sap.com", "successfactors.com"),
        "oracle_hcm": ("fa-emea-saasfaprod1.fa.ocs.oraclecloud.com", "oraclecloud.com"),
        "taleo":      ("taleo.net",),
        "workable":   ("workable.com",),
        "applytojob": ("applytojob.com",),
    }

    def _detect_ats(self, url: str) -> str:
        u = url.lower()
        for ats_name, patterns in self._EXTERNAL_ATS_PATTERNS.items():
            if any(p in u for p in patterns):
                return ats_name
        return "generic"

    def _detect_external_page_error(self, page, url: str) -> str | None:
        """Return a description string when the external page is an error page (404, 410, 500, expired).
        Returns None when the page looks healthy."""
        try:
            broken_domains = {"aiok.co"}

            # Check HTTP status via page title / body text
            title = (page.title() or "").lower()
            error_titles = ("not found", "404", "page not found", "job not found",
                            "position not found", "this job is no longer available",
                            "job expired", "listing expired", "no longer accepting",
                            "500", "server error", "internal server error",
                            "403", "forbidden", "access denied", "410", "gone",
                            "this site can't be reached", "dns_probe", "err_name_not_resolved")
            for t in error_titles:
                if t in title:
                    return f"External page error ({t!r} in title): {url[:80]}"

            # Check page body for common error phrases
            error_phrases = [
                ("text=/this job is no longer available/i", "Job listing no longer available"),
                ("text=/this position has been filled/i", "Position already filled"),
                ("text=/this posting has expired/i", "Job posting expired"),
                ("text=/job listing not found/i", "Job listing not found"),
                ("text=/page not found/i", "Page not found on external site"),
                ("text=/404/", "External site returned 404"),
                ("text=/we couldn't find that page/i", "Page not found on external site"),
                ("text=/no longer accepting applications/i", "No longer accepting applications"),
                ("text=/application period has closed/i", "Application period closed"),
                ("text=/this site can't be reached/i", "External site unreachable"),
                ("text=/dns address could not be found/i", "External DNS lookup failed"),
                ("text=/server ip address could not be found/i", "External DNS lookup failed"),
                ("text=/err_name_not_resolved/i", "External URL hostname does not resolve"),
                ("text=/dns_probe/i", "External DNS probe error"),
            ]
            for selector, reason in error_phrases:
                try:
                    if page.locator(selector).first.is_visible(timeout=800):
                        return f"{reason}: {url[:80]}"
                except Exception:
                    continue

            # If the URL itself signals an error path
            url_low = url.lower()
            if any(x in url_low for x in ("/404", "/not-found", "/error", "/expired")):
                return f"External URL indicates error page: {url[:80]}"

            # Known broken redirect domains should be treated as invalid apply targets.
            try:
                host = url_low.split("/")[2]
            except Exception:
                host = ""
            if host and any(host == d or host.endswith(f".{d}") for d in broken_domains):
                return f"External redirect domain is unreachable ({host})"

        except Exception:
            pass
        return None

    def _detect_external_account_wall(self, page) -> str | None:
        """Return a reason when the page is genuinely blocked behind auth/verification.

        Important: this must not trigger on harmless header buttons like "Log in" in site nav.
        """
        hard_checks = [
            ("text=/verify your email|check your inbox|enter verification code|one-time code|otp/i", "External site requires email or OTP verification"),
            ("text=/captcha|i am not a robot|recaptcha|cloudflare/i", "External site requires CAPTCHA verification"),
            ("text=/create account to apply|register to apply|sign up to apply/i", "External site requires account registration before applying"),
            ("text=/sign in to apply|log in to apply|login to apply|continue to application/i", "External site requires login before applying"),
        ]
        for selector, reason in hard_checks:
            try:
                if page.locator(selector).first.is_visible(timeout=1000):
                    return reason
            except Exception:
                continue

        # Password form is a strong sign of auth wall only when application wording is present.
        try:
            password_input = page.query_selector("input[type='password']")
            if password_input and password_input.is_visible():
                body = (page.locator("body").inner_text(timeout=1200) or "").lower()
                if any(k in body for k in ["apply", "application", "continue", "sign in", "log in"]):
                    return "External site shows an account password form before application"
        except Exception:
            pass

        return None

    def _try_external_login(self, page) -> tuple[bool, str]:
        """Attempt a best-effort login on external ATS pages using configured credentials."""
        email_value = (self.config.profile.email or "").strip()
        password_value = (self.config.password or "").strip()
        if not email_value or not password_value:
            return False, "Missing credentials for external login attempt"

        email_selectors = [
            "input[type='email']",
            "input[name*='email' i]",
            "input[id*='email' i]",
            "input[name*='user' i]",
            "input[name*='login' i]",
        ]
        pass_selectors = [
            "input[type='password']",
            "input[name*='password' i]",
            "input[id*='password' i]",
        ]
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Sign in')",
            "button:has-text('Log in')",
            "button:has-text('Continue')",
        ]

        email_el = None
        pass_el = None
        for sel in email_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=1000):
                    email_el = el
                    break
            except Exception:
                continue
        for sel in pass_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=1000):
                    pass_el = el
                    break
            except Exception:
                continue

        if not email_el or not pass_el:
            return False, "No visible login form fields detected"

        try:
            self._ats_human_fill_element(email_el, email_value, page=page)
            self._human_pause(0.2, 0.4)
            self._ats_human_fill_element(pass_el, password_value, page=page)

            clicked = False
            for sel in submit_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=900):
                        self._human_move_mouse_to(page, btn)
                        self._human_pause(0.1, 0.25)
                        btn.click(timeout=2500)
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                try:
                    pass_el.press("Enter")
                    clicked = True
                except Exception:
                    pass

            if not clicked:
                return False, "Login form found, but no submit action available"

            try:
                page.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
            self._human_reading_pause(0.6, 1.4)

            try:
                still_pass = page.locator("input[type='password']").first
                if still_pass.is_visible(timeout=1200):
                    return False, "Credentials rejected or extra verification required"
            except Exception:
                pass

            return True, "External login submitted"
        except Exception as exc:
            return False, f"External login attempt failed: {exc}"

    def _apply_on_external_site(self, linkedin_page) -> tuple[bool, str]:
        """Open external ATS URL, fill the form with profile data, and submit.
        Returns (success, note). Keeps the page open if it can't submit so the
        user can finish manually in the visible browser window.
        """
        btn = self._find_apply_button(linkedin_page)
        if not btn:
            return False, "No apply button found"

        ext_page = None
        external_url = ""
        button_href = ""
        linkedin_url_before_click = linkedin_page.url or ""

        try:
            button_href = (btn.get_attribute("href") or "").strip()
            if button_href.startswith("/"):
                button_href = f"https://www.linkedin.com{button_href}"
        except Exception:
            button_href = ""

        try:
            try:
                btn.scroll_into_view_if_needed(timeout=2000)
            except Exception:
                pass

            with linkedin_page.expect_popup(timeout=5000) as popup_info:
                btn.click(force=True)
            ext_page = popup_info.value
            # Inject stealth JS before the page runs its own scripts
            self._setup_page_as_human(ext_page)
            ext_page.wait_for_load_state("domcontentloaded", timeout=12000)
            # Reading pause â€” as if the user is looking at the page
            self._human_reading_pause(0.8, 2.0)
            external_url = ext_page.url
        except Exception:
            try:
                btn.click(force=True)
                self._human_pause(2.0, 3.0)
                external_url = linkedin_page.url
                ext_page = linkedin_page
            except Exception as e:
                if button_href:
                    try:
                        ext_page = linkedin_page.context.new_page()
                        self._setup_page_as_human(ext_page)
                        ext_page.goto(button_href, wait_until="domcontentloaded", timeout=15000)
                        self._human_reading_pause(0.8, 2.0)
                        external_url = ext_page.url
                    except Exception as href_exc:
                        return False, f"Could not open external page: click={e}; href={href_exc}"
                else:
                    return False, f"Could not open external page: {e}"

        if (
            ext_page is linkedin_page
            and external_url
            and "/jobs/view/" in external_url
            and external_url == linkedin_url_before_click
        ):
            if button_href:
                try:
                    ext_page = linkedin_page.context.new_page()
                    self._setup_page_as_human(ext_page)
                    ext_page.goto(button_href, wait_until="domcontentloaded", timeout=15000)
                    self._human_reading_pause(0.8, 2.0)
                    external_url = ext_page.url
                except Exception as href_exc:
                    return False, f"Apply click did not leave LinkedIn job page: {href_exc}"
            else:
                return False, "Apply click did not leave LinkedIn job page"

        if not external_url or not ext_page:
            return False, "External page not opened"

        if "/jobs/view/" in external_url and "linkedin.com" in external_url:
            return False, f"Apply stayed on LinkedIn job page: {external_url[:80]}"

        # â”€â”€ Check that the external page actually loaded successfully â”€â”€â”€â”€â”€â”€
        page_issue = self._detect_external_page_error(ext_page, external_url)
        if page_issue:
            self._current_report.setdefault("external_ats", {}).update({
                "ats": "error",
                "external_url": external_url,
                "submit_clicked": False,
                "submit_confirmed": False,
                "manual_takeover_reason": page_issue,
                "result_note": page_issue,
            })
            return False, page_issue

        account_wall = self._detect_external_account_wall(ext_page)
        if account_wall:
            self._current_report.setdefault("external_ats", {})
            self._current_report["external_ats"].update({
                "ats": "account_wall",
                "external_url": external_url,
                "submit_clicked": False,
                "submit_confirmed": False,
                "manual_takeover_reason": account_wall,
                "result_note": account_wall,
            })
            return False, account_wall

        ats = self._detect_ats(external_url)
        self._log(f"[EXT] ATS detected: {ats} | {external_url[:80]}")
        self._current_report.setdefault("external_ats", {})
        self._current_report["external_ats"].update({
            "ats": ats,
            "external_url": external_url,
            "submit_clicked": False,
            "submit_confirmed": False,
            "manual_takeover_reason": "",
        })

        try:
            if ats == "greenhouse":
                ok, note = self._fill_greenhouse(ext_page)
            elif ats == "lever":
                ok, note = self._fill_lever(ext_page)
            elif ats == "teamtailor":
                ok, note = self._fill_teamtailor(ext_page)
            elif ats in ("workday", "ashby", "smartrecruiters", "bamboohr"):
                # Complex SPAs â€” fill what we can via generic helper
                ok, note = self._fill_generic_external(ext_page)
            else:
                ok, note = self._fill_generic_external(ext_page)
        except Exception as e:
            ok, note = False, f"ATS fill error: {e}"

        ext_rep = self._current_report.setdefault("external_ats", {})
        ext_rep["result_note"] = note
        if ok:
            ext_rep.setdefault("submit_confirmed", True)
        else:
            ext_rep["manual_takeover_reason"] = note

        # Don't close the popup â€” leave it open so the user can review/finish
        return ok, f"{ats}|{note}|{external_url[:80]}"

    # â”€â”€ Human-like behaviour helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _human_move_mouse_to(self, page, el) -> None:
        """Move the mouse in a natural curved path to *el*, ending with hover."""
        try:
            box = el.bounding_box()
            if not box:
                return
            # Target centre with a small random offset so it never hits exactly
            tx = box["x"] + box["width"] * random.uniform(0.3, 0.7)
            ty = box["y"] + box["height"] * random.uniform(0.25, 0.75)
            # Current mouse position is unknown â€” start from a plausible offset
            sx = tx + random.uniform(-250, 250)
            sy = ty + random.uniform(-150, 150)
            sx = max(0, sx)
            sy = max(0, sy)
            steps = random.randint(8, 18)
            for i in range(1, steps + 1):
                t = i / steps
                # Simple ease-in-out cubic
                t2 = t * t * (3 - 2 * t)
                # Add small random jitter to each step
                jx = random.uniform(-4, 4)
                jy = random.uniform(-3, 3)
                ix = sx + (tx - sx) * t2 + jx
                iy = sy + (ty - sy) * t2 + jy
                page.mouse.move(ix, iy)
                time.sleep(random.uniform(0.004, 0.018))
        except Exception:
            pass

    def _human_scroll_to_element(self, page, el) -> None:
        """Scroll to *el* naturally (slow incremental scroll then snap)."""
        try:
            el.scroll_into_view_if_needed(timeout=1500)
            # Small extra pause to let lazy-loaded content settle
            self._human_pause(0.1, 0.3)
        except Exception:
            pass

    def _human_reading_pause(self, min_s: float = 0.6, max_s: float = 2.2) -> None:
        """Pause as if the user is reading the page."""
        time.sleep(random.uniform(min_s, max_s))

    def _setup_page_as_human(self, page) -> None:
        """Inject JS that removes bot-detection signals from the page context."""
        try:
            stealth_js = """
                // Hide navigator.webdriver
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                // Spoof plugins length
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                // Spoof languages
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                // Remove automated Chrome flag from window.chrome
                window.chrome = {runtime: {}};
                // Spoof permissions query
                const origQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (p) =>
                    p.name === 'notifications'
                        ? Promise.resolve({state: Notification.permission})
                        : origQuery(p);
            """
            page.add_init_script(stealth_js)
        except Exception:
            pass

    # â”€â”€ Per-ATS fill helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _ats_human_fill_element(self, el, value: str, page=None) -> bool:
        """Fill an input like a real user: scroll to it, move mouse, hover, click, then type
        character-by-character with realistic, variable inter-key delays."""
        try:
            if value is None:
                return False
            txt = str(value).strip()
            if not txt:
                return False
            if not el.is_visible():
                return False

            # Avoid clobbering fields that are already filled.
            try:
                existing = (el.input_value() or "").strip()
                if existing:
                    return False
            except Exception:
                pass

            # Scroll so the element is visible, then move mouse naturally
            self._human_scroll_to_element(page or el.page if hasattr(el, 'page') else None, el) if page else None
            try:
                el.scroll_into_view_if_needed(timeout=1500)
            except Exception:
                pass

            if page:
                self._human_move_mouse_to(page, el)
                self._human_pause(0.08, 0.22)  # hover dwell

            # Hover then click
            try:
                el.hover(timeout=1500)
                self._human_pause(0.06, 0.18)
            except Exception:
                pass
            el.click(timeout=2000)
            self._human_pause(0.1, 0.3)

            # Clear then type with human-like inter-key delays
            try:
                el.fill("")
                for ch in txt:
                    el.type(ch, delay=0)
                    # Vary delay: spaces and punctuation are slightly slower
                    if ch in (' ', '.', ',', '@', '-', '_'):
                        time.sleep(random.uniform(0.06, 0.18))
                    else:
                        time.sleep(random.uniform(0.03, 0.11))
                    # Rare brief pause mid-word simulating thought
                    if random.random() < 0.03:
                        time.sleep(random.uniform(0.15, 0.45))
            except Exception:
                try:
                    el.fill(txt)
                except Exception:
                    return False

            # Occasionally press Tab to move focus naturally
            if random.random() < 0.4:
                try:
                    el.press("Tab")
                except Exception:
                    pass

            self._human_pause(0.12, 0.35)
            return True
        except Exception:
            return False

    def _ats_extract_prompt(self, page, el) -> str:
        """Extract best-effort prompt/label text for an external form element."""
        parts: list[str] = []
        try:
            for attr in ("placeholder", "aria-label", "name", "id"):
                v = (el.get_attribute(attr) or "").strip()
                if v:
                    parts.append(v)
        except Exception:
            pass

        try:
            el_id = (el.get_attribute("id") or "").strip()
            if el_id:
                lbl = page.query_selector(f"label[for='{el_id}']")
                if lbl:
                    t = (lbl.inner_text() or "").strip()
                    if t:
                        parts.append(t)
        except Exception:
            pass

        try:
            nearby = el.query_selector("xpath=ancestor::*[self::label or self::fieldset or self::div][1]")
            if nearby:
                t = (nearby.inner_text() or "").strip()
                if t:
                    parts.append(t[:220])
        except Exception:
            pass

        return " ".join(parts).strip()

    def _ats_detect_submit_success(self, page, before_url: str) -> bool:
        """Best-effort success detection after clicking submit/apply."""
        try:
            page.wait_for_load_state("domcontentloaded", timeout=6000)
        except Exception:
            pass

        self._human_pause(0.5, 1.2)
        now_url = (page.url or "").lower()
        before = (before_url or "").lower()
        if now_url and before and now_url != before and any(k in now_url for k in (
            "thank", "success", "confirmation", "submitted", "complete", "application"
        )):
            return True

        success_text_selectors = [
            "text=/application (submitted|received|complete)/i",
            "text=/thank you for applying/i",
            "text=/thanks for applying/i",
            "text=/your application has been submitted/i",
            "text=/candidatura inviata/i",
            "text=/bewerbung (eingereicht|gesendet)/i",
        ]
        for sel in success_text_selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=1500):
                    return True
            except Exception:
                continue
        return False

    def _ats_click_next_step(self, page) -> bool:
        """Click Next/Continue style controls for multi-step external forms."""
        selectors = [
            "button:has-text('Continue')",
            "button:has-text('Next')",
            "button:has-text('Review')",
            "button:has-text('Save and continue')",
            "button:has-text('Proceed')",
            "button:has-text('Continue application')",
            "button:has-text('Avanti')",
            "button:has-text('Continua')",
            "button:has-text('Weiter')",
            "button:has-text('Suivant')",
            "button[aria-label*='Continue']",
            "button[aria-label*='Next']",
        ]
        for sel in selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click(timeout=3000)
                    self._human_pause(1.0, 2.0)
                    return True
            except Exception:
                continue
        return False

    def _ats_try_fill(self, page, selector: str, value: str) -> bool:
        """Try to fill a single input on an external ATS page. Returns True if filled."""
        try:
            el = page.query_selector(selector)
            if el:
                return self._ats_human_fill_element(el, value)
        except Exception:
            pass
        return False

    def _ats_upload_cv(self, page) -> bool:
        """Upload CV to the first visible file input found on the page."""
        preferred_cv = self._resolve_latest_cv_path()
        if not preferred_cv:
            return False
        cv = str(preferred_cv)
        try:
            file_inputs = page.query_selector_all("input[type=file]")
            for fi in file_inputs:
                try:
                    if fi.is_visible() or True:  # some are hidden but still work
                        fi.set_input_files(cv)
                        self._human_pause(1.5, 3.0)
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _ats_submit(self, page, extra_selectors: list[str] | None = None) -> bool:
        """Click the first visible submit/apply button on the page."""
        selectors = [
            "input[type=submit]",
            "button[type=submit]",
            "button:has-text('Submit')",
            "button:has-text('Apply')",
            "button:has-text('Send Application')",
            "button:has-text('Submit Application')",
            "button:has-text('Invia')",
            "button:has-text('Absenden')",
        ]
        if extra_selectors:
            selectors = extra_selectors + selectors
        for sel in selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    self._human_pause(2.0, 3.5)
                    return True
            except Exception:
                continue
        return False

    def _fill_greenhouse(self, page) -> tuple[bool, str]:
        """Fill boards.greenhouse.io application form."""
        p = self.config.profile
        parts = p.full_name.strip().split(None, 1)
        first, last = parts[0], (parts[1] if len(parts) > 1 else "")

        self._ats_try_fill(page, "#first_name", first)
        self._ats_try_fill(page, "#last_name", last)
        self._ats_try_fill(page, "#email", p.email)
        self._ats_try_fill(page, "#phone", p.phone)
        self._ats_try_fill(page, "input[name*='linkedin' i]", p.linkedin_url)
        self._ats_try_fill(page, "input[name*='website' i]", p.github_url)
        self._ats_upload_cv(page)

        ok = self._ats_submit(page, ["#submit_app"])
        return ok, ("Greenhouse submitted" if ok else "Greenhouse submit failed")

    def _fill_lever(self, page) -> tuple[bool, str]:
        """Fill jobs.lever.co application form."""
        p = self.config.profile

        self._ats_try_fill(page, "input[name=name]", p.full_name)
        self._ats_try_fill(page, "input[name=email]", p.email)
        self._ats_try_fill(page, "input[name=phone]", p.phone)
        self._ats_try_fill(page, "input[name*='linkedin' i]", p.linkedin_url)
        self._ats_try_fill(page, "input[name*='LinkedIn']", p.linkedin_url)
        self._ats_try_fill(page, "input[name*='github' i]", p.github_url)
        self._ats_try_fill(page, "input[name*='website' i]", p.portfolio_url or p.github_url)
        self._ats_upload_cv(page)

        ok = self._ats_submit(page, [".template-btn-submit", ".postings-btn"])
        return ok, ("Lever submitted" if ok else "Lever submit failed")

    def _fill_teamtailor(self, page) -> tuple[bool, str]:
        """Fill Teamtailor application form."""
        p = self.config.profile
        parts = p.full_name.strip().split(None, 1)
        first, last = parts[0], (parts[1] if len(parts) > 1 else "")

        filled = 0
        filled += self._ats_try_fill(page, "input[name*='first_name' i], input[id*='first_name' i]", first)
        filled += self._ats_try_fill(page, "input[name*='last_name' i], input[id*='last_name' i]", last)
        # fallback: single name field
        if filled == 0:
            self._ats_try_fill(page, "input[name*='name' i]:not([name*='last' i]):not([name*='first' i])", p.full_name)
        self._ats_try_fill(page, "input[type=email]", p.email)
        self._ats_try_fill(page, "input[type=tel], input[name*='phone' i]", p.phone)
        self._ats_try_fill(page, "input[name*='linkedin' i]", p.linkedin_url)
        self._ats_upload_cv(page)

        ok = self._ats_submit(page)
        return ok, ("Teamtailor submitted" if ok else "Teamtailor submit failed")

    def _fill_generic_external(self, page) -> tuple[bool, str]:
        """Best-effort generic form fill for any external ATS page."""
        p = self.config.profile
        parts = p.full_name.strip().split(None, 1)
        first, last = parts[0], (parts[1] if len(parts) > 1 else "")

        # Map of (lowercase keywords in label/name/placeholder) â†’ value to fill
        fill_map: list[tuple[tuple[str, ...], str]] = [
            (("first name", "firstname", "first_name", "nome", "vorname", "keresztnÃ©v"), first),
            (("last name", "lastname", "last_name", "surname", "cognome", "nachname", "vezetÃ©knÃ©v"), last),
            (("full name", "your name", "teljes nÃ©v"), p.full_name),
            (("email", "e-mail"), p.email),
            (("phone", "telephone", "telefono", "telefon", "mobile", "mobil"), p.phone),
            (("linkedin",), p.linkedin_url),
            (("github",), p.github_url),
            (("website", "portfolio"), p.portfolio_url or p.github_url),
        ]

        total_filled = 0
        total_selects = 0
        total_checks = 0
        uploaded = False
        steps_attempted = 0

        ext_rep = self._current_report.setdefault("external_ats", {})
        ext_rep.update({
            "fields_filled": 0,
            "selects_filled": 0,
            "checkboxes_checked": 0,
            "steps_attempted": 0,
            "cv_uploaded": False,
            "submit_clicked": False,
            "submit_confirmed": False,
            "manual_takeover_reason": "",
        })

        for _step in range(5):
            steps_attempted += 1
            step_progress = 0

            # Reading pause at the start of every step/page as if user is looking at the form
            self._human_reading_pause(0.5, 1.4)

            account_wall = self._detect_external_account_wall(page)
            if account_wall:
                ext_rep.update({
                    "fields_filled": total_filled,
                    "selects_filled": total_selects,
                    "checkboxes_checked": total_checks,
                    "steps_attempted": steps_attempted,
                    "cv_uploaded": uploaded,
                    "submit_confirmed": False,
                    "manual_takeover_reason": account_wall,
                })
                return False, account_wall

            # Fill text-like inputs and textareas.
            try:
                inputs = page.query_selector_all(
                    "input[type=text], input[type=email], input[type=tel], input[type=url], "
                    "input[type=number], input[type=search], input[type=date], input:not([type]), textarea"
                )
            except Exception:
                inputs = []

            for inp in inputs:
                try:
                    if not inp.is_visible():
                        continue
                    if (inp.get_attribute("disabled") is not None) or (inp.get_attribute("readonly") is not None):
                        continue

                    metadata = self._ats_extract_prompt(page, inp)
                    key = metadata.lower()
                    value = None

                    for keys, mapped_value in fill_map:
                        if any(k in key for k in keys):
                            value = mapped_value
                            break

                    if value is None:
                        value = self._infer_profile_answer(metadata, location=p.location)

                    input_type = (inp.get_attribute("type") or "").strip().lower()
                    if value is None and input_type in ("number",):
                        value = self._fallback_numeric_value(inp)
                    if value is None and input_type in ("url",):
                        value = p.linkedin_url or p.github_url or p.portfolio_url
                    if value is None and "cover letter" in key:
                        value = "I am excited to apply and believe my software engineering background is a strong fit for this role."
                    if value is None:
                        value = self._text_unknown_fallback(metadata)

                    if self._ats_human_fill_element(inp, value, page=page):
                        total_filled += 1
                        step_progress += 1
                        # Brief inter-field pause, like a human tabbing through a form
                        self._human_pause(0.15, 0.45)
                except Exception:
                    continue

            # Fill select dropdowns.
            try:
                for sel in page.query_selector_all("select"):
                    try:
                        if not sel.is_visible():
                            continue
                        if (sel.get_attribute("disabled") is not None):
                            continue

                        current_value = (sel.input_value() or "").strip()
                        if current_value and not self._is_placeholder_option_value(current_value):
                            continue

                        prompt = self._ats_extract_prompt(page, sel)
                        inferred = self._infer_profile_answer(prompt, location=p.location)

                        options: list[tuple[str, str]] = []
                        for opt in sel.query_selector_all("option"):
                            try:
                                txt = (opt.inner_text() or "").strip()
                                val = (opt.get_attribute("value") or "").strip()
                                if txt and not self._is_placeholder_option_text(txt):
                                    options.append((txt, val))
                            except Exception:
                                continue

                        if not options:
                            continue

                        target_value = None
                        if inferred:
                            inf_low = inferred.lower()
                            # yes/no style pick
                            for txt, val in options:
                                t = txt.lower()
                                if self._is_yes_token(inf_low) and self._is_yes_token(t):
                                    target_value = val or txt
                                    break
                                if self._is_no_token(inf_low) and self._is_no_token(t):
                                    target_value = val or txt
                                    break
                                if inf_low in t:
                                    target_value = val or txt
                                    break

                        if not target_value:
                            picked = self._pick_location_option(options, p.location, "")
                            if picked:
                                target_value = picked

                        if not target_value:
                            txt, val = options[0]
                            target_value = val or txt

                        try:
                            sel.select_option(value=target_value)
                        except Exception:
                            sel.select_option(label=target_value)
                        self._human_pause(0.1, 0.35)
                        total_selects += 1
                        step_progress += 1
                    except Exception:
                        continue
            except Exception:
                pass

            # Tick obvious consent/terms checkboxes and yes/no eligibility answers.
            try:
                for cb in page.query_selector_all("input[type=checkbox]"):
                    try:
                        if not cb.is_visible():
                            continue
                        if cb.is_checked():
                            continue
                        prompt = self._ats_extract_prompt(page, cb)
                        low = prompt.lower()
                        inferred = self._infer_profile_answer(prompt, location=p.location) or ""
                        if (
                            "consent" in low or "privacy" in low or "terms" in low
                            or "gdpr" in low or "agree" in low or self._is_yes_token(inferred)
                        ):
                            cb.check(timeout=2000)
                            self._human_pause(0.08, 0.2)
                            total_checks += 1
                            step_progress += 1
                    except Exception:
                        continue
            except Exception:
                pass

            if not uploaded:
                uploaded = self._ats_upload_cv(page)
                if uploaded:
                    step_progress += 1
                    ext_rep["cv_uploaded"] = True

            before_submit_url = page.url or ""
            submitted_click = self._ats_submit(page)
            if submitted_click:
                ext_rep["submit_clicked"] = True
            if submitted_click and self._ats_detect_submit_success(page, before_submit_url):
                ext_rep.update({
                    "fields_filled": total_filled,
                    "selects_filled": total_selects,
                    "checkboxes_checked": total_checks,
                    "steps_attempted": steps_attempted,
                    "cv_uploaded": uploaded,
                    "submit_confirmed": True,
                    "manual_takeover_reason": "",
                })
                return True, (
                    f"generic({total_filled} fields, {total_selects} selects, "
                    f"{total_checks} checks) submitted"
                )

            # If submit didn't finish, try navigating to next step and continue.
            moved = self._ats_click_next_step(page)
            if moved:
                continue

            # No step movement and no meaningful progress => stop trying.
            if step_progress == 0:
                break

        ext_rep.update({
            "fields_filled": total_filled,
            "selects_filled": total_selects,
            "checkboxes_checked": total_checks,
            "steps_attempted": steps_attempted,
            "cv_uploaded": uploaded,
            "submit_confirmed": False,
            "manual_takeover_reason": "Could not confirm submission on external site.",
        })

        return False, (
            f"generic({total_filled} fields, {total_selects} selects, {total_checks} checks) "
            "requires manual review"
        )

    def _handle_external_apply(self, page) -> str | None:
        btn = self._find_apply_button(page)
        if not btn:
            return None

        external_url = None
        ext_page = None
        try:
            with page.expect_popup(timeout=3000) as popup_info:
                btn.click()
            ext_page = popup_info.value
            ext_page.wait_for_load_state("domcontentloaded", timeout=5000)
            external_url = ext_page.url
            # Try clicking Apply on the external page before closing
            try:
                self._try_click_apply_on_external(ext_page)
            except Exception:
                pass
            try:
                ext_page.close()
            except Exception:
                pass
        except Exception:
            try:
                btn.click()
                self._human_pause()
                external_url = page.url
                ext_page = page
                # Try clicking Apply on the redirected page
                try:
                    self._try_click_apply_on_external(page)
                except Exception:
                    pass
            except Exception:
                return None

        return external_url

    def _extract_job_requirements(self, page) -> str:
        """Extract a compact job requirements text block from the job page."""
        selectors = [
            ".jobs-description-content__text",
            ".jobs-box__html-content",
            "#job-details",
            ".description__text",
        ]
        for sel in selectors:
            try:
                text = (page.inner_text(sel) or "").strip()
            except Exception:
                text = ""
            if text:
                text = re.sub(r"\s+", " ", text).strip()
                return text[:3500]
        return ""

    def _slugify_for_filename(self, value: str, *, fallback: str = "item") -> str:
        s = (value or "").strip().lower()
        s = re.sub(r"[^a-z0-9]+", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        if not s:
            return fallback
        return s[:64]

    def _letters_output_dir(self) -> Path:
        # Prefer webapp user_data folder so dashboard sees the files immediately.
        preferred = self.config.paths.webapp_letters_dir
        out_dir = preferred if preferred.parent.exists() else self.config.paths.base_dir / "generated_letters"
        out_dir.mkdir(parents=True, exist_ok=True)
        # Legacy cleanup: keep output document-only (PDF/DOCX), never TXT.
        try:
            for old_txt in out_dir.glob("motivation_letter_*.txt"):
                old_txt.unlink()
            for old_txt in out_dir.glob("cover_letter_*.txt"):
                old_txt.unlink()
        except Exception:
            pass
        return out_dir

    def _letter_stem(self, *, title: str = "", company: str = "") -> str:
        company_slug = self._slugify_for_filename(company, fallback="company")
        title_slug = self._slugify_for_filename(title, fallback="role")
        return f"{company_slug}__{title_slug}"

    def _persist_company_motivation_letter(self, *, title: str = "", company: str = "", body: str = "") -> Path | None:
        """Write a professional motivation letter as both PDF and DOCX per company/role."""
        if not body:
            return None
        try:
            out_dir = self._letters_output_dir()
            stem = self._letter_stem(title=title, company=company)
            pdf_path = out_dir / f"motivation_letter_{stem}.pdf"
            docx_path = out_dir / f"motivation_letter_{stem}.docx"

            profile = self.config.profile
            today = datetime.now().strftime("%d %B %Y")
            candidate = profile.full_name or "Candidate"
            email = profile.email or ""
            phone = profile.phone or ""
            location = profile.location or ""
            role = title or "Software Developer"
            comp = company or "Hiring Company"

            # â”€â”€ Build structured lines â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            header = [
                candidate,
                " | ".join(filter(None, [email, phone, location])),
                "",
                today,
                "",
                f"Re: {role} position at {comp}",
                "",
                "Dear Hiring Manager,",
                "",
            ]
            body_paras: list[str] = []
            for para in re.split(r"\n+", body.strip()):
                para = re.sub(r"\s+", " ", para).strip()
                if para:
                    body_paras.append(para)
            footer = [
                "",
                "Yours sincerely,",
                "",
                candidate,
                " | ".join(filter(None, [email, phone])),
            ]

            all_lines = header + body_paras + footer

            # â”€â”€ PDF â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            def _esc(s: str) -> str:
                return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

            stream_parts = ["BT"]
            # Name/title in 13pt bold (simulated), body in 11pt
            stream_parts += ["/F1 13 Tf", "50 760 Td", f"({_esc(candidate)}) Tj"]
            stream_parts += ["/F1 10 Tf", "0 -16 Td"]
            skip_big = True
            for ln in all_lines[1:]:
                txt = _esc((ln or "").strip())
                stream_parts.append("0 -14 Td")
                stream_parts.append(f"({txt}) Tj")
            stream_parts.append("ET")
            stream = "\n".join(stream_parts)
            stream_bytes = stream.encode("latin-1", errors="replace")
            objs = [
                "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
                "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
                "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\nendobj\n",
                f"4 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n{stream}\nendstream\nendobj\n",
                "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
            ]
            hdr = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
            offs = [0]
            payload = bytearray(hdr)
            for obj in objs:
                offs.append(len(payload))
                payload.extend(obj.encode("latin-1", errors="replace"))
            xref_start = len(payload)
            payload.extend(f"xref\n0 {len(objs)+1}\n".encode("ascii"))
            payload.extend(b"0000000000 65535 f \n")
            for off in offs[1:]:
                payload.extend(f"{off:010d} 00000 n \n".encode("ascii"))
            payload.extend(f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\n".encode("ascii"))
            payload.extend(f"startxref\n{xref_start}\n%%EOF\n".encode("ascii"))
            pdf_path.write_bytes(bytes(payload))

            # â”€â”€ DOCX â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            def _wx(s: str) -> str:
                return xml_escape((s or "").strip())

            def _para(text: str, bold: bool = False, size: int = 22, spacing_after: int = 80) -> str:
                rpr = f"<w:rPr>{'<w:b/>' if bold else ''}<w:sz w:val='{size}'/><w:szCs w:val='{size}'/></w:rPr>"
                ppr = f"<w:pPr><w:spacing w:after='{spacing_after}'/></w:pPr>"
                if not text:
                    return f"<w:p>{ppr}</w:p>"
                return f"<w:p>{ppr}<w:r>{rpr}<w:t xml:space='preserve'>{_wx(text)}</w:t></w:r></w:p>"

            paras_xml = []
            # Candidate name â€” bold, large
            paras_xml.append(_para(candidate, bold=True, size=28, spacing_after=40))
            # Contact line
            contact = " | ".join(filter(None, [email, phone, location]))
            if contact:
                paras_xml.append(_para(contact, size=18, spacing_after=120))
            # Date
            paras_xml.append(_para(today, size=20, spacing_after=40))
            # Re: line
            paras_xml.append(_para(f"Re: {role} position at {comp}", bold=True, size=22, spacing_after=120))
            # Salutation
            paras_xml.append(_para("Dear Hiring Manager,", size=22, spacing_after=80))
            # Body paragraphs
            for bp in body_paras:
                paras_xml.append(_para(bp, size=22, spacing_after=80))
            # Footer
            paras_xml.append(_para(""))
            paras_xml.append(_para("Yours sincerely,", size=22, spacing_after=40))
            paras_xml.append(_para(""))
            paras_xml.append(_para(candidate, bold=True, size=22, spacing_after=20))
            paras_xml.append(_para(" | ".join(filter(None, [email, phone])), size=20, spacing_after=0))

            doc_xml = (
                "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
                "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
                "<w:body>"
                "<w:sectPr>"
                "<w:pgSz w:w='11906' w:h='16838'/>"
                "<w:pgMar w:top='1440' w:right='1440' w:bottom='1440' w:left='1440'/>"
                "</w:sectPr>"
                + "".join(paras_xml)
                + "</w:body></w:document>"
            )
            ct_xml = (
                "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
                "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
                "<Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>"
                "<Default Extension='xml' ContentType='application/xml'/>"
                "<Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>"
                "</Types>"
            )
            rels_xml = (
                "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
                "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
                "<Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/>"
                "</Relationships>"
            )
            with zipfile.ZipFile(docx_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("[Content_Types].xml", ct_xml)
                zf.writestr("_rels/.rels", rels_xml)
                zf.writestr("word/document.xml", doc_xml)

            return pdf_path
        except Exception as _e:
            import sys as _sys
            print(f"[LETTER] Failed to write motivation letter: {_e}", file=_sys.stderr)
            return None

    def _collect_skill_context_for_letter(self, requirements: str = "") -> dict[str, Any]:
        """Build matched/missing skill context for requirement-aware letters."""
        ctx: dict[str, Any] = {"job_skills": [], "matched": [], "missing": [], "match_percentage": 0}
        req_text = (requirements or "").strip()
        if not req_text:
            return ctx
        try:
            job_skills = extract_skills_from_text(req_text)
            user_skills = get_user_skills(self.config.profile, self.config.settings)
            analysis = compare_skills(job_skills, user_skills)
            ctx["job_skills"] = job_skills
            ctx["matched"] = analysis.get("matched", [])
            ctx["missing"] = analysis.get("missing", [])
            ctx["match_percentage"] = analysis.get("match_percentage", 0)
        except Exception:
            pass
        return ctx

    def _prepare_company_letters(self, *, title: str = "", company: str = "", requirements: str = "") -> None:
        """Generate per-company motivation letter (PDF+DOCX) and cover letter â€” once per run."""
        stem = self._letter_stem(title=title, company=company)
        if stem in self._letter_file_cache:
            return

        # Always regenerate for each new company/role pair â€” tailored to requirements.
        motivation = self._generate_motivation_letter(
            question="Please provide a motivation letter",
            job_title=title,
            company=company,
            requirements=requirements,
        )
        # Writes motivation_letter_<stem>.pdf and motivation_letter_<stem>.docx
        self._persist_company_motivation_letter(title=title, company=company, body=motivation)

        # Also generate a cover letter (same body, slightly different header).
        cover_pdf = self._build_cover_letter_pdf(title=title, company=company, requirements=requirements)
        cover_docx = self._build_cover_letter_docx(title=title, company=company, requirements=requirements)

        import sys as _sys
        print(f"[LETTER] Generated for '{company}' / '{title}' â†’ {stem}", file=_sys.stderr)

        self._letter_file_cache[stem] = {
            "cover_pdf": cover_pdf,
            "cover_docx": cover_docx,
        }

    def _generate_motivation_letter(self, question: str, job_title: str, company: str, requirements: str = "") -> str:
        """Generate a professional, requirement-aware motivation letter."""
        cache_key = "|".join(
            [
                (job_title or "").strip().lower(),
                (company or "").strip().lower(),
                (question or "").strip().lower(),
                (requirements or "")[:700].strip().lower(),
            ]
        )
        cached = self._motivation_cache.get(cache_key)
        if cached:
            self._persist_company_motivation_letter(title=job_title, company=company, body=cached)
            return cached

        skill_ctx = self._collect_skill_context_for_letter(requirements)
        matched_skills = skill_ctx.get("matched", [])[:8]
        missing_skills = skill_ctx.get("missing", [])[:4]
        job_skills = skill_ctx.get("job_skills", [])[:10]
        match_percentage = skill_ctx.get("match_percentage", 0)

        system = (
            "Write a polished and professional motivation letter tailored to role and company requirements. "
            "Use only facts from CV context and provided matched skills; do not fabricate experience. "
            "Structure with clear short paragraphs and strong business tone. "
            "Length target: 160-220 words."
        )
        user_msg = (
            f"Role: {job_title or 'Software Developer'}\n"
            f"Company: {company or 'Target company'}\n"
            f"Question/field: {question}\n\n"
            f"Job requirements/context:\n{requirements[:2000] or 'Not provided'}\n\n"
            f"Detected job skills: {', '.join(job_skills) if job_skills else 'N/A'}\n"
            f"Matched CV skills: {', '.join(matched_skills) if matched_skills else 'N/A'}\n"
            f"Skills still developing: {', '.join(missing_skills) if missing_skills else 'N/A'}\n"
            f"Approximate match percentage: {match_percentage}%\n\n"
            f"Candidate CV context:\n{self._cv_context}\n\n"
            "Output plain text only (no bullets, no markdown)."
        )

        letter = ""
        try:
            resp = _requests.post(
                self._OLLAMA_URL,
                json={
                    "model": self._OLLAMA_MODEL,
                    "prompt": f"<|system|>\n{system}\n<|user|>\n{user_msg}\n<|assistant|>",
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 420},
                },
                timeout=10,
            )
            resp.raise_for_status()
            letter = (resp.json().get("response") or "").strip()
            # Keep paragraph breaks while cleaning up excessive whitespace.
            letter = re.sub(r"[ \t]+", " ", letter).strip()
            letter = re.sub(r"\n{3,}", "\n\n", letter)
        except Exception:
            letter = ""

        if not letter:
            company_name = company or "your company"
            role_name = job_title or "Software Developer"
            matched_text = ", ".join(matched_skills[:5]) if matched_skills else "full-stack development, API integration, and software delivery"
            job_focus = ", ".join(job_skills[:4]) if job_skills else "modern software engineering"
            growth_text = ""
            if missing_skills:
                growth_text = (
                    f" I am also actively strengthening areas such as {', '.join(missing_skills[:2])} to align even faster with your stack."
                )
            letter = (
                f"Dear Hiring Manager,\n\n"
                f"I am excited to apply for the {role_name} position at {company_name}. "
                f"With {self.config.profile.total_experience_years} years of practical software engineering experience, "
                f"I have delivered production-ready solutions with a strong focus on quality, maintainability, and measurable business impact.\n\n"
                f"Based on your role requirements, I can contribute immediately in areas including {matched_text}. "
                f"I am especially motivated by your focus on {job_focus}, and I enjoy collaborating across product and engineering to ship reliable outcomes.{growth_text}\n\n"
                "I would value the opportunity to discuss how my background and execution style can support your team goals. "
                "Thank you for your time and consideration."
            )

        # LinkedIn text areas can be strict; keep safe length.
        if len(letter) > 1400:
            letter = letter[:1397] + "..."

        self._motivation_cache[cache_key] = letter
        self._persist_company_motivation_letter(title=job_title, company=company, body=letter)
        return letter

    # â”€â”€ Ollama AI: answer open-text job application questions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _OLLAMA_URL = "http://localhost:11434/api/generate"
    _OLLAMA_MODEL = "llama3"          # change to "mistral" or any installed model
    _OLLAMA_TIMEOUT = 8               # seconds â€“ kept short to avoid blocking the flow

    def _ai_pick_dropdown_option(
        self,
        question: str,
        options: list[tuple[str, str]],  # [(value, label), ...]
        job_title: str = "",
        company: str = "",
    ) -> str | None:
        """Ask Ollama to pick the best dropdown option for an unknown question.

        Returns the option *value* string to pass to select_option(), or None.
        """
        if not options:
            return None
        cache_key = f"dropdown::{question.strip().lower()}::{','.join(t for _, t in options)}"
        if cache_key in self._ai_cache:
            return self._ai_cache[cache_key]

        options_text = "\n".join(f"{i+1}. {label}" for i, (_, label) in enumerate(options))
        system = (
            "You are helping fill a job application form. "
            "Given a question and a numbered list of dropdown options, "
            "reply ONLY with the number (1, 2, 3 â€¦) of the best option for the candidate. "
            "No explanation. Just the number."
        )
        user_msg = (
            f"Role: {job_title or 'Software Developer'} at {company or 'a company'}\n"
            f"Candidate context:\n{self._cv_context}\n\n"
            f"Question: {question}\n\n"
            f"Options:\n{options_text}\n\n"
            "Reply with the option number only."
        )
        try:
            resp = _requests.post(
                self._OLLAMA_URL,
                json={
                    "model": self._OLLAMA_MODEL,
                    "prompt": f"<|system|>\n{system}\n<|user|>\n{user_msg}\n<|assistant|>",
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 8},
                },
                timeout=self._OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            raw = (resp.json().get("response") or "").strip()
            m = re.search(r"\d+", raw)
            if not m:
                self._ai_cache[cache_key] = None
                return None
            idx = int(m.group(0)) - 1
            if 0 <= idx < len(options):
                val = options[idx][0]
                self._ai_cache[cache_key] = val
                return val
        except Exception:
            pass
        self._ai_cache[cache_key] = None
        return None

    def _ai_answer(self, question: str, job_title: str = "", company: str = "") -> str | None:
        """Ask local Ollama for multilingual screening answers.

        Rules:
        - Answer in the same language as the question.
        - Use CV/profile facts when available.
        - If a fact is missing, use safe professional defaults (do not invent claims).
        """
        cache_key = question.strip().lower()
        if cache_key in self._ai_cache:
            return self._ai_cache[cache_key]
        system = (
            "You answer candidate screening questions for job applications. "
            "Respond in the SAME language as the question. "
            "Never invent concrete facts (years, skills, certifications) not in CV context. "
            "If information is missing, use safe professional defaults like 'Open to discussion'. "
            "Return strict JSON with keys: answer (string), confidence (0..1)."
        )
        user_msg = (
            f"Applying for: {job_title or 'Software Developer'} at {company or 'this company'}\n\n"
            f"CV context:\n{self._cv_context}\n\n"
            f"Question: {question}\n\n"
            "Output JSON only."
        )
        try:
            resp = _requests.post(
                self._OLLAMA_URL,
                json={
                    "model": self._OLLAMA_MODEL,
                    "prompt": f"<|system|>\n{system}\n<|user|>\n{user_msg}\n<|assistant|>",
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 160},
                },
                timeout=self._OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            raw = (resp.json().get("response") or "").strip()
            if not raw:
                return None

            # Extract first JSON object from model output.
            m = re.search(r"\{[\s\S]*\}", raw)
            if not m:
                return None
            data = json.loads(m.group(0))
            answer = str(data.get("answer") or "").strip()
            try:
                confidence = float(data.get("confidence", 0.0))
            except Exception:
                confidence = 0.0

            if not answer or confidence < 0.25:
                return None

            # Trim to ~450 chars (LinkedIn textarea limit is usually 500)
            if len(answer) > 450:
                answer = answer[:447] + "..."
            self._ai_cache[cache_key] = answer
            return answer
        except Exception:
            self._ai_cache[cache_key] = None
            return None

    def _collect_apply_actions(self, page) -> list[dict[str, Any]]:
        """Collect clickable action buttons in Easy Apply flow."""
        actions: list[dict[str, Any]] = []
        selectors = [
            ("submit", "button[aria-label*='Submit application'], button:has-text('Submit application'), button:has-text('Submit')"),
            ("review", "button[aria-label*='Review your application'], button:has-text('Review')"),
            ("continue", "button[aria-label='Continue to next step'], button[aria-label*='Continue'], button:has-text('Continue')"),
            ("next", "button:has-text('Next')"),
            ("apply", "button:has-text('Apply'), a:has-text('Apply'), a[href*='apply']"),
        ]

        for kind, selector in selectors:
            try:
                el = page.query_selector(selector)
            except Exception:
                el = None
            if not el:
                continue
            try:
                label = ((el.get_attribute("aria-label") or "") + " " + (el.inner_text() or "")).strip()
            except Exception:
                label = kind
            actions.append({"kind": kind, "label": label, "element": el})

        return actions

    def _ai_choose_apply_action(self, page, actions: list[dict[str, Any]], *, step: int, title: str = "", company: str = "") -> str | None:
        """Choose next Easy Apply action using deterministic priority (no AI â€” saves ~12 s/step)."""
        if not actions:
            return None

        # Deterministic fallback priority
        preferred_order = ["submit", "review", "continue", "next", "apply"]
        for key in preferred_order:
            if any(a.get("kind") == key for a in actions):
                return key
        return None

        fallback_choice = None  # unreachable â€” kept so diff is clean
        for key in preferred_order:
            if any(a.get("kind") == key for a in actions):
                fallback_choice = key
                break
        return fallback_choice

    def _try_message_poster(self, page, job_url: str, title: str, company: str) -> str:
        """After a successful Easy Apply, find the job poster and send a personalised connection request.

        Returns a short status string for logging/visibility.
        """
        try:
            # Go back to the job page to find the hiring team section
            page.goto(job_url, wait_until="domcontentloaded")
            self._human_pause()

            # Scroll down to reveal the hiring team card (it's below the fold)
            self._progressive_scroll(page, iterations=6)

            profile = self.config.profile

            # â”€â”€ Strategy 1: Message button directly on the job page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # LinkedIn shows "Meet the hiring team" / "People you can reach out to"
            # with a Message button right on the job page.
            poster_name_el = page.query_selector(
                # Current LinkedIn DOM (2025-2026): "People you can reach out to" section
                ".jobs-poster__name, "
                ".hirer-card__hirer-information a, "
                "[data-test-job-poster] a, "
                ".jobs-hiring-team__list a[href*='/in/'], "
                "section.jobs-hiring-team a[href*='/in/'], "
                ".job-details-hiring-team__recruiter-information a, "
                # Newer LinkedIn layout
                ".jobs-people-you-can-reach-out-to a[href*='/in/'], "
                ".job-details-people-you-can-reach a[href*='/in/'], "
                ".reach-out-to-people a[href*='/in/'], "
                "section[data-view-name*='hiring'] a[href*='/in/'], "
                "div[class*='hiring-team'] a[href*='/in/'], "
                "div[class*='people-you-can-reach'] a[href*='/in/'], "
                "h3 ~ div a[href*='/in/'], "
                # Broadest fallback: any profile link in the lower job page cards
                ".artdeco-card a[href*='/in/'][data-tracking-control-name*='poster']"
            )
            poster_name = ""
            if poster_name_el:
                poster_name = (poster_name_el.inner_text() or "").strip().split("\n")[0].strip()
            first_name = poster_name.split()[0] if poster_name else "there"

            note = (
                f"Hi {first_name}, I just applied for the {title} position at {company}. "
                f"I am very excited about this opportunity and it would be a pleasure to be part of "
                f"{company}'s team. Looking forward to connecting!"
            )
            if len(note) > 299:
                note = note[:296] + "..."

            # Look for the Message button in the hiring team card on the job page
            job_page_msg_btn = None
            for sel in [
                # Current LinkedIn layout (2025-2026): "People you can reach out to"
                "button[aria-label*='Message'][aria-label*='Woodhouse']",
                "section button[aria-label*='Message']",
                ".jobs-people-you-can-reach-out-to button[aria-label*='Message']",
                ".job-details-people-you-can-reach button[aria-label*='Message']",
                "div[class*='hiring-team'] button[aria-label*='Message']",
                "div[class*='people-you-can-reach'] button[aria-label*='Message']",
                # Older selectors
                "section.jobs-hiring-team button[aria-label*='Message']",
                ".jobs-hiring-team button[aria-label*='Message']",
                ".hirer-card button[aria-label*='Message']",
                "button[aria-label*='Message'][aria-label*='recruiter']",
                "button[aria-label*='Message'][aria-label*='hiring']",
            ]:
                try:
                    el = page.query_selector(sel)
                    if el:
                        job_page_msg_btn = el
                        break
                except Exception:
                    continue

            # If not found via specific selectors, find any Message button near the poster name
            if not job_page_msg_btn and poster_name_el:
                try:
                    # Walk up to the card container, then find Message inside it
                    card = page.evaluate_handle(
                        """el => {
                            let n = el;
                            for (let i = 0; i < 8; i++) {
                                if (!n.parentElement) break;
                                n = n.parentElement;
                                // Find button with "Message" text inside this ancestor
                                const btns = n.querySelectorAll('button');
                                for (const btn of btns) {
                                    if (btn.innerText.trim() === 'Message' || (btn.getAttribute('aria-label') || '').includes('Message')) return btn;
                                }
                            }
                            return null;
                        }""",
                        poster_name_el
                    )
                    btn_el = card.as_element()
                    if btn_el:
                        job_page_msg_btn = btn_el
                except Exception:
                    pass

            # Last resort: find any visible "Message" button on the whole page
            if not job_page_msg_btn:
                try:
                    all_btns = page.query_selector_all("button")
                    for btn in all_btns:
                        try:
                            aria = (btn.get_attribute("aria-label") or "").strip()
                            txt = (btn.inner_text() or "").strip()
                            if txt == "Message" or aria.startswith("Message"):
                                job_page_msg_btn = btn
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

            if job_page_msg_btn:
                try:
                    job_page_msg_btn.click()
                    self._human_pause()
                    msg_area = page.query_selector("div[contenteditable='true']")
                    if msg_area:
                        msg_area.click()
                        self._human_pause(0.2, 0.5)
                        msg_area.type(note, delay=30)
                        self._human_pause(0.3, 0.8)
                        send_btn = page.query_selector(
                            "button[type='submit'][aria-label*='Send'], "
                            "button.msg-form__send-button, "
                            "button[aria-label='Send']"
                        )
                        if send_btn:
                            send_btn.click()
                            self._human_pause()
                            return f"direct message sent to {poster_name or 'poster'}"
                        return "message typed but send button not found"
                    return "message overlay did not open"
                except Exception as e:
                    pass  # Fall through to profile-page strategy

            # â”€â”€ Strategy 2: Navigate to poster's LinkedIn profile â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            poster_link = poster_name_el
            if not poster_link:
                # Try broader selectors
                for sel in [
                    "a[href*='/in/'][aria-label*='recruiter']",
                    "a[href*='/in/'][aria-label*='hiring']",
                ]:
                    try:
                        el = page.query_selector(sel)
                        if el:
                            poster_link = el
                            break
                    except Exception:
                        continue

            if not poster_link:
                return "no hiring poster found"

            poster_href = poster_link.get_attribute("href") or ""
            if poster_href.startswith("/"):
                poster_href = "https://www.linkedin.com" + poster_href
            if not poster_href or "/in/" not in poster_href:
                return "poster profile link unavailable"

            page.goto(poster_href.split("?")[0], wait_until="domcontentloaded")
            self._human_pause()

            # --- Try Connect first ---
            connect_btn = None
            for sel in [
                "button[aria-label*='Connect']",
                "button:has-text('Connect')",
            ]:
                try:
                    el = page.query_selector(sel)
                    if el:
                        label = ((el.get_attribute("aria-label") or "") + " " + (el.inner_text() or "")).strip().lower()
                        if "connect" in label and "disconnect" not in label and "remove" not in label:
                            connect_btn = el
                            break
                except Exception:
                    continue

            if connect_btn:
                try:
                    connect_btn.click()
                    self._human_pause()
                except Exception:
                    return "connect button not clickable"

                add_note_btn = page.query_selector(
                    "button[aria-label*='Add a note'], button:has-text('Add a note')"
                )
                if add_note_btn:
                    add_note_btn.click()
                    self._human_pause()
                    note_area = page.query_selector("textarea[name='message'], textarea#custom-message")
                    if note_area:
                        note_area.fill(note)
                        self._human_pause(0.3, 0.7)

                send_btn = page.query_selector(
                    "button[aria-label*='Send invitation'], button[aria-label*='Send now'], "
                    "button:has-text('Send invitation'), button:has-text('Send')"
                )
                if send_btn:
                    send_btn.click()
                    self._human_pause()
                    return f"connection note sent to {first_name}"
                return "connect opened but send button not found"

            # --- Fallback: Message if already connected ---
            msg_btn = None
            for sel in [
                "button[aria-label*='Message']",
                "button:has-text('Message')",
            ]:
                try:
                    el = page.query_selector(sel)
                    if el:
                        msg_btn = el
                        break
                except Exception:
                    continue

            if msg_btn:
                msg_btn.click()
                self._human_pause()
                msg_area = page.query_selector("div[contenteditable='true']")
                if msg_area:
                    msg_area.click()
                    self._human_pause(0.2, 0.5)
                    msg_area.type(note, delay=30)
                    self._human_pause(0.3, 0.8)
                    send_btn = page.query_selector(
                        "button[type='submit'][aria-label*='Send'], "
                        "button.msg-form__send-button"
                    )
                    if send_btn:
                        send_btn.click()
                        self._human_pause()
                        return f"direct message sent to {first_name}"
                    return "message typed but send button not found"
                return "message box not found"

            return "not connected and connect not available"

        except Exception as exc:
            return f"messaging skipped: {type(exc).__name__}"

    def _build_cover_letter_lines(self, *, title: str = "", company: str = "", requirements: str = "") -> list[str]:
        body = self._generate_motivation_letter(
            question="Please provide a cover letter",
            job_title=title,
            company=company,
            requirements=requirements,
        )
        if not body:
            body = (
                f"Dear Hiring Team, I am applying for the {title or 'Software Developer'} role at {company or 'your company'}. "
                "I bring strong full-stack software development experience, ownership, and collaborative delivery. "
                "I would be glad to contribute to your team and discuss how my background matches your requirements."
            )

        skill_ctx = self._collect_skill_context_for_letter(requirements)
        matched_skills = skill_ctx.get("matched", [])[:6]
        match_line = ""
        if matched_skills:
            match_line = f"Relevant matched skills: {', '.join(matched_skills)}"

        today = datetime.now().strftime("%d %b %Y")
        header_lines = [
            self.config.profile.full_name or "Candidate",
            self.config.profile.email or "",
            self.config.profile.phone or "",
            self.config.profile.location or "",
            "",
            today,
            "",
            f"Role: {title or 'Software Engineer'}",
            f"Company: {company or 'N/A'}",
            "",
            "Dear Hiring Manager,",
            "",
        ]
        wrapped_body: list[str] = []
        for para in re.split(r"\n+", body):
            para = re.sub(r"\s+", " ", para).strip()
            if not para:
                wrapped_body.append("")
                continue
            wrapped_body.extend(textwrap.wrap(para, width=88) or [para])

        footer_lines = ["", "Kind regards,", self.config.profile.full_name or "Candidate"]
        if match_line:
            footer_lines = ["", match_line] + footer_lines

        return (header_lines + wrapped_body + footer_lines)[:95]

    def _build_cover_letter_pdf(self, *, title: str = "", company: str = "", requirements: str = "") -> Path | None:
        """Generate a professionally formatted PDF cover letter (A4, two-font layout)."""
        try:
            output_dir = self._letters_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)
            stem = self._letter_stem(title=title, company=company)
            out_path = output_dir / f"cover_letter_{stem}.pdf"

            # â”€â”€ Collect data â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            profile = self.config.profile
            candidate = (profile.full_name or "Candidate").strip()
            role      = (title   or "Software Developer").strip()
            comp      = (company or "Hiring Company").strip()
            email     = (profile.email    or "").strip()
            phone     = (profile.phone    or "").strip()
            location  = (profile.location or "").strip()
            today     = datetime.now().strftime("%d %B %Y")

            body_raw = self._generate_motivation_letter(
                question="Please provide a cover letter",
                job_title=title, company=company, requirements=requirements,
            )
            if not body_raw:
                body_raw = (
                    f"I am writing to express my strong interest in the {role} position at {comp}. "
                    "My background in full-stack software development, combined with hands-on experience "
                    "delivering scalable solutions, makes me a strong fit for your team. "
                    "I thrive in collaborative, agile environments and am driven by challenging technical problems."
                )

            skill_ctx = self._collect_skill_context_for_letter(requirements)
            matched   = skill_ctx.get("matched", [])[:6]

            body_paras: list[str] = []
            for para in re.split(r"\n+", body_raw.strip()):
                para = re.sub(r"\s+", " ", para).strip()
                if para:
                    body_paras.append(para)

            def _esc(s: str) -> str:
                return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

            # â”€â”€ Build PDF content stream â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # A4: 595 x 842 pt, margins: left=50, right=545, top starts at 800
            parts: list[str] = []

            # â€” Header block (name + title, contact right-aligned) â€”
            parts += ["BT", "/F2 18 Tf", "50 800 Td", f"({_esc(candidate)}) Tj", "ET"]
            parts += ["BT", "/F1 10 Tf", "50 783 Td", f"({_esc(role)}) Tj", "ET"]
            contact_items = [x for x in [phone, email, location] if x]
            contact_str   = "  |  ".join(contact_items)
            parts += ["BT", "/F1 9 Tf", "50 770 Td", f"({_esc(contact_str)}) Tj", "ET"]

            # â€” Horizontal rule â€”
            parts += ["0.4 w", "50 762 m", "545 762 l", "S"]

            # â€” Date â€”
            parts += ["BT", "/F1 10 Tf", "50 748 Td", f"({_esc(today)}) Tj", "ET"]

            # â€” Company / Re: line â€”
            parts += ["BT", "/F1 10 Tf", "50 732 Td", f"({_esc(comp)}) Tj", "ET"]
            parts += ["BT", "/F1 10 Tf", "50 718 Td", f"(Re: {_esc(role)} position) Tj", "ET"]

            # â€” Salutation â€”
            parts += ["BT", "/F1 11 Tf", "50 700 Td", "(Dear Hiring Manager,) Tj", "ET"]

            # â€” Body paragraphs â€”
            y = 682
            for para in body_paras:
                # Wrap at ~90 chars (approx. 6.8pt avg char width at 11pt = ~78 chars in 545-50=495pt)
                wrapped = textwrap.wrap(para, width=90) or [para]
                for line in wrapped:
                    if y < 80:
                        break
                    parts += ["BT", "/F1 11 Tf", f"50 {y} Td", f"({_esc(line)}) Tj", "ET"]
                    y -= 14
                y -= 6  # extra gap between paragraphs

            # â€” Matched skills note â€”
            if matched:
                y -= 4
                skills_line = f"Key matched skills: {', '.join(matched)}"
                parts += ["BT", "/F1 9 Tf", f"50 {y} Td", f"({_esc(skills_line)}) Tj", "ET"]
                y -= 16

            # â€” Footer / signature â€”
            y -= 6
            parts += ["BT", "/F1 11 Tf", f"50 {y} Td", "(Kind regards,) Tj", "ET"]
            y -= 28
            parts += ["BT", "/F2 11 Tf", f"50 {y} Td", f"({_esc(candidate)}) Tj", "ET"]
            if email or phone:
                y -= 14
                sig_contact = "  |  ".join([x for x in [email, phone] if x])
                parts += ["BT", "/F1 9 Tf", f"50 {y} Td", f"({_esc(sig_contact)}) Tj", "ET"]

            stream       = "\n".join(parts)
            stream_bytes = stream.encode("latin-1", errors="replace")

            # â”€â”€ Assemble PDF objects â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            objs = [
                "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
                "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
                (
                    "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                    "/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>\nendobj\n"
                ),
                f"4 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n{stream}\nendstream\nendobj\n",
                "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
                "6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n",
            ]

            hdr      = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
            offsets  = [0]
            payload  = bytearray(hdr)
            for obj in objs:
                offsets.append(len(payload))
                payload.extend(obj.encode("latin-1", errors="replace"))
            xref_start = len(payload)
            payload.extend(f"xref\n0 {len(objs)+1}\n".encode("ascii"))
            payload.extend(b"0000000000 65535 f \n")
            for off in offsets[1:]:
                payload.extend(f"{off:010d} 00000 n \n".encode("ascii"))
            payload.extend(f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\n".encode("ascii"))
            payload.extend(f"startxref\n{xref_start}\n%%EOF\n".encode("ascii"))
            out_path.write_bytes(bytes(payload))
            return out_path
        except Exception:
            return None

    def _build_cover_letter_docx(self, *, title: str = "", company: str = "", requirements: str = "") -> Path | None:
        """Generate a professionally styled DOCX cover letter matching the sample layout."""
        try:
            output_dir = self._letters_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)
            stem = self._letter_stem(title=title, company=company)
            out_path = output_dir / f"cover_letter_{stem}.docx"

            # â”€â”€ Collect data â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            profile   = self.config.profile
            candidate = (profile.full_name or "Candidate").strip()
            role      = (title   or "Software Developer").strip()
            comp      = (company or "Hiring Company").strip()
            email     = (profile.email    or "").strip()
            phone     = (profile.phone    or "").strip()
            location  = (profile.location or "").strip()
            today     = datetime.now().strftime("%d %B %Y")

            body_raw = self._generate_motivation_letter(
                question="Please provide a cover letter",
                job_title=title, company=company, requirements=requirements,
            )
            if not body_raw:
                body_raw = (
                    f"I am writing to express my strong interest in the {role} position at {comp}. "
                    "My background in full-stack software development, combined with hands-on experience "
                    "delivering scalable solutions, makes me a strong fit for your team. "
                    "I thrive in collaborative, agile environments and am driven by challenging technical problems."
                )

            skill_ctx = self._collect_skill_context_for_letter(requirements)
            matched   = skill_ctx.get("matched", [])[:6]

            body_paras: list[str] = []
            for para in re.split(r"\n+", body_raw.strip()):
                para = re.sub(r"\s+", " ", para).strip()
                if para:
                    body_paras.append(para)

            def _wx(s: str) -> str:
                return xml_escape((s or "").strip())

            def _p(text: str, bold: bool = False, size: int = 22,
                   align: str = "", after: int = 80, before: int = 0,
                   color: str = "", border_bottom: bool = False) -> str:
                rpr_parts = []
                if bold:
                    rpr_parts.append("<w:b/>")
                rpr_parts.append(f"<w:sz w:val='{size}'/><w:szCs w:val='{size}'/>")
                if color:
                    rpr_parts.append(f"<w:color w:val='{color}'/>")
                rpr = f"<w:rPr>{''.join(rpr_parts)}</w:rPr>"

                ppr_parts = [f"<w:spacing w:before='{before}' w:after='{after}'/>"]
                if align:
                    ppr_parts.append(f"<w:jc w:val='{align}'/>")
                if border_bottom:
                    ppr_parts.append(
                        "<w:pBdr><w:bottom w:val='single' w:sz='6' w:space='1' w:color='2C3E50'/></w:pBdr>"
                    )
                ppr = f"<w:pPr>{''.join(ppr_parts)}</w:pPr>"

                if not text.strip():
                    return f"<w:p>{ppr}</w:p>"
                return f"<w:p>{ppr}<w:r>{rpr}<w:t xml:space='preserve'>{_wx(text)}</w:t></w:r></w:p>"

            paras: list[str] = []

            # â€” Name (large, bold, navy-ish) â€”
            paras.append(_p(candidate, bold=True, size=36, after=0, color="1A252F"))
            # â€” Role subtitle â€”
            paras.append(_p(role, bold=False, size=20, after=20, color="5D6D7E"))
            # â€” Contact line right-aligned â€”
            contact_line = "  |  ".join(x for x in [phone, email, location] if x)
            if contact_line:
                paras.append(_p(contact_line, size=18, align="right", after=0, color="5D6D7E"))
            # â€” Horizontal divider (bottom border on empty para) â€”
            paras.append(_p("", after=120, border_bottom=True))

            # â€” Date â€”
            paras.append(_p(today, size=20, after=40))
            # â€” Company block â€”
            paras.append(_p(comp, bold=True, size=20, after=20))
            paras.append(_p(f"Re: {role} position", size=20, after=120))

            # â€” Salutation â€”
            paras.append(_p("Dear Hiring Manager,", size=22, after=80))

            # â€” Body paragraphs â€”
            for bp in body_paras:
                paras.append(_p(bp, size=22, after=100))

            # â€” Matched skills note (if any) â€”
            if matched:
                paras.append(_p(f"Key matched skills: {', '.join(matched)}", size=18, after=100, color="5D6D7E"))

            # â€” Footer / sign-off â€”
            paras.append(_p("", after=20))
            paras.append(_p("Kind regards,", size=22, after=40))
            paras.append(_p("", after=20))
            paras.append(_p(candidate, bold=True, size=22, after=20))
            sig_contact = "  |  ".join(x for x in [email, phone] if x)
            if sig_contact:
                paras.append(_p(sig_contact, size=18, after=0, color="5D6D7E"))

            document_xml = (
                "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
                "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
                "<w:body>"
                "<w:sectPr>"
                "<w:pgSz w:w='11906' w:h='16838'/>"
                "<w:pgMar w:top='1134' w:right='1134' w:bottom='1134' w:left='1134'/>"
                "</w:sectPr>"
                + "".join(paras)
                + "</w:body></w:document>"
            )
            ct_xml = (
                "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
                "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
                "<Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>"
                "<Default Extension='xml' ContentType='application/xml'/>"
                "<Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>"
                "</Types>"
            )
            rels_xml = (
                "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
                "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
                "<Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/>"
                "</Relationships>"
            )
            with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("[Content_Types].xml", ct_xml)
                zf.writestr("_rels/.rels", rels_xml)
                zf.writestr("word/document.xml", document_xml)
            return out_path
        except Exception:
            return None

    def _handle_file_inputs(self, page, *, title: str = "", company: str = "", requirements: str = "") -> None:
        """Handle resume and cover-letter upload fields in Easy Apply."""
        try:
            file_inputs = page.query_selector_all("input[type='file']")
        except Exception:
            return
        if not file_inputs:
            return

        cover_pdf_path = None
        cover_docx_path = None

        def _ensure_cover_docs() -> None:
            nonlocal cover_pdf_path, cover_docx_path
            # Generate lazily only when we actually find a cover-letter upload field.
            if (cover_pdf_path and cover_pdf_path.exists()) or (cover_docx_path and cover_docx_path.exists()):
                return
            self._prepare_company_letters(title=title, company=company, requirements=requirements)
            cover_pdf_path = self._build_cover_letter_pdf(title=title, company=company, requirements=requirements)
            cover_docx_path = self._build_cover_letter_docx(title=title, company=company, requirements=requirements)

        cover_kws = (
            "cover", "motivation", "letter", "lettera", "presentazione",
            "anschreiben", "lettre", "carta", "motivacion", "motivacao",
        )
        resume_kws = (
            "resume", "cv", "curriculum",
        )
        preferred_cv = self._resolve_latest_cv_path()

        placeholder_img_path = self.config.paths.base_dir / "generated_letters" / "upload_placeholder.png"
        if not placeholder_img_path.exists():
            try:
                placeholder_img_path.parent.mkdir(parents=True, exist_ok=True)
                # 1x1 transparent PNG.
                png_b64 = (
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
                    "/w8AAgMBgL9l7nQAAAAASUVORK5CYII="
                )
                placeholder_img_path.write_bytes(base64.b64decode(png_b64))
            except Exception:
                placeholder_img_path = None

        resume_uploaded = False
        cover_uploaded = False

        for file_input in file_inputs:
            meta_parts = []
            try:
                meta_parts.extend(
                    [
                        file_input.get_attribute("name") or "",
                        file_input.get_attribute("id") or "",
                        file_input.get_attribute("aria-label") or "",
                        file_input.get_attribute("accept") or "",
                    ]
                )
                container = file_input.query_selector("xpath=ancestor::*[self::fieldset or self::section or self::div][1]")
                if container:
                    meta_parts.append((container.inner_text() or "")[:700])
            except Exception:
                pass

            meta = " ".join(meta_parts).lower()
            accept_attr = (file_input.get_attribute("accept") or "").lower()

            accepts_image = any(tok in accept_attr for tok in ("image", ".png", ".jpg", ".jpeg", ".gif"))
            accepts_document = any(tok in accept_attr for tok in ("pdf", ".pdf", "doc", ".doc", ".docx"))
            image_only = accepts_image and not accepts_document

            is_cover = any(k in meta for k in cover_kws)
            if not is_cover and any(
                k in meta for k in (
                    "supporting", "additional", "attachment", "supplement",
                    "upload document", "attach document", "presentation",
                )
            ):
                is_cover = True
            # Ambiguous second document input is often the cover-letter slot.
            if not is_cover and not image_only and resume_uploaded and not cover_uploaded:
                is_cover = True

            is_resume = any(k in meta for k in resume_kws) or (not is_cover and not image_only and not resume_uploaded)

            try:
                if is_cover:
                    _ensure_cover_docs()
                    preferred_cover_path = None
                    wants_docx = any(k in (accept_attr + " " + meta) for k in ("docx", ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
                    wants_doc = any(k in (accept_attr + " " + meta) for k in (".doc", "application/msword"))

                    if wants_docx and cover_docx_path and cover_docx_path.exists():
                        preferred_cover_path = cover_docx_path
                    elif wants_doc and cover_docx_path and cover_docx_path.exists():
                        preferred_cover_path = cover_docx_path
                    elif cover_pdf_path and cover_pdf_path.exists():
                        preferred_cover_path = cover_pdf_path
                    elif cover_docx_path and cover_docx_path.exists():
                        preferred_cover_path = cover_docx_path

                    if preferred_cover_path:
                        file_input.set_input_files(str(preferred_cover_path))
                        self._human_pause(0.4, 0.8)
                        self._wait_for_upload_processing(page)
                        cover_uploaded = True
                        fname = preferred_cover_path.name
                        if fname not in self._current_report["uploaded_files"]:
                            self._current_report["uploaded_files"].append(f"Cover Letter: {fname}")
                    continue

                if is_resume:
                    if preferred_cv and preferred_cv.exists():
                        try:
                            file_input.set_input_files(str(preferred_cv))
                            self._human_pause(0.4, 0.8)
                            self._wait_for_upload_processing(page)
                            resume_uploaded = True
                            cv_fname = preferred_cv.name
                            if cv_fname not in self._current_report["uploaded_files"]:
                                self._current_report["uploaded_files"].append(f"CV/Resume: {cv_fname}")
                            continue
                        except Exception:
                            pass

                    resume_radios = page.query_selector_all(
                        ".jobs-document-upload-redesign-card__container input[type='radio'][name*='resume'], "
                        "input[type='radio'][name*='resume'], input[type='radio'][name*='cv']"
                    )
                    if resume_radios:
                        already_selected = any(r.is_checked() for r in resume_radios)
                        if not already_selected:
                            chosen_radio = self._pick_best_resume_radio(page, resume_radios, preferred_cv)
                            if chosen_radio:
                                chosen_radio.check(force=True)
                            self._human_pause(0.2, 0.5)
                        resume_uploaded = True
                        continue
                    if preferred_cv and preferred_cv.exists():
                        file_input.set_input_files(str(preferred_cv))
                        self._human_pause(0.4, 0.8)
                        self._wait_for_upload_processing(page)
                        resume_uploaded = True
                        cv_fname = preferred_cv.name
                        if cv_fname not in self._current_report["uploaded_files"]:
                            self._current_report["uploaded_files"].append(f"CV/Resume: {cv_fname}")
                elif image_only and placeholder_img_path and placeholder_img_path.exists():
                    file_input.set_input_files(str(placeholder_img_path))
                    self._human_pause(0.2, 0.5)
                    self._wait_for_upload_processing(page)
                    img_fname = placeholder_img_path.name
                    if img_fname not in self._current_report["uploaded_files"]:
                        self._current_report["uploaded_files"].append(f"Image: {img_fname}")
            except Exception:
                continue

    def _check_easy_apply_limit(self, page) -> bool:
        """Detect the 'You reached today\'s Easy Apply limit' dialog and dismiss it.
        Returns True if the limit dialog was found (caller should stop applying)."""
        try:
            # Look for the modal heading text
            heading = page.query_selector(
                "div[role='dialog'] h2, div[role='alertdialog'] h2, "
                ".artdeco-modal h2, .jobs-apply-modal h2"
            )
            if heading and "easy apply limit" in (heading.inner_text() or "").lower():
                print("[EASY_APPLY] Daily Easy Apply limit reached â€“ dismissing dialog and stopping.")
                for btn_sel in [
                    "button:has-text('Got it')",
                    "button[aria-label='Got it']",
                    "button:has-text('OK')",
                    ".artdeco-modal__confirm-dialog-btn",
                ]:
                    btn = page.query_selector(btn_sel)
                    if btn:
                        try:
                            btn.click(timeout=2000)
                        except Exception:
                            pass
                        break
                return True
        except Exception:
            pass
        return False

    def _dismiss_linkedin_toasts(self, page) -> None:
        """Dismiss any floating toast/snackbar notifications LinkedIn may show."""
        try:
            for sel in [
                "button.artdeco-toast-item__dismiss",
                "button[aria-label*='Dismiss'][aria-label*='notification']",
                "button[aria-label='Dismiss'][class*='toast']",
                ".artdeco-toast-item button",
                "li.artdeco-toast-item button",
            ]:
                btns = page.query_selector_all(sel)
                for btn in btns:
                    try:
                        btn.click(timeout=1500)
                    except Exception:
                        pass
        except Exception:
            pass

    def _wait_for_upload_processing(self, page, timeout_ms: int = 8000) -> None:
        """Wait until LinkedIn's file-upload processing spinner disappears."""
        try:
            # LinkedIn shows a progress/loading indicator while processing uploads.
            page.wait_for_selector(
                ".jobs-document-upload__loading-spinner, "
                ".artdeco-loader, "
                "[data-test-upload-in-progress]",
                timeout=2000,
            )
            # If found, wait for it to go away.
            page.wait_for_selector(
                ".jobs-document-upload__loading-spinner, "
                ".artdeco-loader, "
                "[data-test-upload-in-progress]",
                state="hidden",
                timeout=timeout_ms,
            )
        except Exception:
            pass  # No spinner found â€” that's fine

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
        report: dict | None = None,
        missing_skills: dict | None = None,
    ) -> dict[str, Any]:
        rec = {
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
        if report:
            rec["report"] = {
                "uploaded_files": report.get("uploaded_files", []),
                "qa_pairs": [{"q": q, "a": a} for q, a in report.get("qa_pairs", {}).items()],
                "external_ats": report.get("external_ats", {}),
            }
        if missing_skills:
            rec["missing_skills"] = missing_skills
        return rec

    def _extract_job_id(self, url: str) -> str:
        match = re.search(r"/jobs/view/(\d+)", url)
        return match.group(1) if match else url

    def _progressive_scroll(self, page, iterations: int = 8) -> None:
        # Use viewport-relative scrolling instead of fixed pixels so behavior is
        # stable on different devices, display scales, and window sizes.
        viewport_h = 900
        try:
            vp = page.viewport_size
            if vp and isinstance(vp, dict):
                viewport_h = int(vp.get("height") or viewport_h)
        except Exception:
            pass

        step_min = max(320, int(viewport_h * 0.50))
        step_max = max(step_min + 120, int(viewport_h * 0.90))
        stuck_count = 0

        for _ in range(iterations):
            before_y = 0
            after_y = 0
            at_bottom = False
            try:
                before_y = int(page.evaluate("() => Math.round(window.scrollY || 0)"))
            except Exception:
                before_y = 0

            moved = False
            try:
                page.mouse.wheel(0, random.randint(step_min, step_max))
                moved = True
            except Exception:
                pass

            if not moved:
                try:
                    page.keyboard.press("PageDown")
                except Exception:
                    pass

            self._human_pause(0.3, 0.8)

            try:
                after_y = int(page.evaluate("() => Math.round(window.scrollY || 0)"))
                at_bottom = bool(
                    page.evaluate(
                        "() => (window.innerHeight + window.scrollY) >= (document.body.scrollHeight - 4)"
                    )
                )
            except Exception:
                after_y = before_y
                at_bottom = False

            if at_bottom:
                break

            if after_y <= before_y + 2:
                stuck_count += 1
                if stuck_count >= 2:
                    break
            else:
                stuck_count = 0

    def _fill_location_typeahead(self, page, input_el, location_value: str) -> bool:
        value = (location_value or "").strip()
        if not value:
            return False

        city_token = value.split(",")[0].strip().lower()
        if not city_token:
            city_token = value.lower()

        try:
            input_el.click(timeout=2000)
        except Exception:
            pass

        try:
            input_el.fill("")
        except Exception:
            try:
                input_el.press("Control+a")
                input_el.press("Backspace")
            except Exception:
                pass

        try:
            input_el.type(value, delay=45)
        except Exception:
            return False

        self._human_pause(0.25, 0.5)

        option_selectors = [
            "li[role='option']",
            "div[role='option']",
            ".basic-typeahead__selectable",
            "ul[role='listbox'] li",
            ".jobs-search-box__typeahead li",
        ]

        options = []
        for selector in option_selectors:
            try:
                found = page.query_selector_all(selector)
            except Exception:
                found = []
            if found:
                options = found
                break

        if not options:
            try:
                page.keyboard.press("ArrowDown")
                self._human_pause(0.1, 0.2)
                page.keyboard.press("Enter")
                self._human_pause(0.2, 0.4)
                return True
            except Exception:
                return False

        best = None
        fallback = None
        for opt in options:
            try:
                if not opt.is_visible():
                    continue
                txt = (opt.inner_text() or "").strip().lower()
                if not txt:
                    continue
                if fallback is None:
                    fallback = opt
                if city_token in txt:
                    best = opt
                    break
            except Exception:
                continue

        chosen_option = best or fallback
        if not chosen_option:
            return False

        try:
            chosen_option.click(timeout=2500)
            self._human_pause(0.2, 0.4)
            return True
        except Exception:
            try:
                page.keyboard.press("ArrowDown")
                page.keyboard.press("Enter")
                self._human_pause(0.2, 0.4)
                return True
            except Exception:
                return False

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

    # â”€â”€ Networking campaign â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _get_networking_target_companies(self) -> list[str]:
        """Select companies based on the candidate's role focus."""
        title = ((getattr(self.config.profile, "current_job_title", "") or "").strip()).lower()
        keywords = [str(k).lower() for k in (getattr(self.config.settings, "keywords", []) or [])]
        role_context = " ".join([title] + keywords)

        software_role_tokens = [
            "software", "engineer", "developer", "backend", "frontend",
            "full stack", "fullstack", "web", "application",
        ]

        if any(token in role_context for token in software_role_tokens):
            return NETWORKING_SOFTWARE_ENGINEERING_COMPANIES

        return NETWORKING_TARGET_COMPANIES

    # â”€â”€ Direct external job boards campaign â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Sites below are accessible without login and don't aggressively block bots.
    # Indeed / Glassdoor are excluded â€” they CAPTCHA-block automated browsers.

    _DIRECT_EXTERNAL_SITES: list[dict] = [
        {
            "name": "WeWorkRemotely",
            "search_url": "https://weworkremotely.com/remote-jobs/search?term={keywords}",
            "card_selectors": ["section.jobs ul li:not(.view-all)", "article"],
            "card_selectors": ["a[href*='/remote-jobs/']", "section.jobs ul li:not(.view-all)", "article"],
            "apply_btn_selectors": [
                "a:has-text('Apply for this position')",
                "a:has-text('Apply')",
                ".apply-link",
            ],
            "next_page_selector": None,
        },
        {
            "name": "RemoteOK",
            "search_url": "https://remoteok.com/remote-{kw_slug}-jobs",
            "card_selectors": ["tr[data-id]", "tr.job"],
            "apply_btn_selectors": [
                "a.button:has-text('Apply')",
                "a[class*='apply']",
                "a:has-text('Apply')",
            ],
            "next_page_selector": None,
        },
        {
            "name": "EuropeRemoteJobs",
            "search_url": "https://europeremotejobs.com/remote-jobs/?s={keywords}",
            "card_selectors": [".job_listing", "li.job_listing", ".job-listing", "article", "h2 a[href]"],
            "apply_btn_selectors": [
                "a.apply_button",
                "a:has-text('Apply for job')",
                "a:has-text('Apply')",
                "a:has-text('Apply Now')",
                "a[href*='apply']",
            ],
            "next_page_selector": "a.next",
        },
        {
            "name": "Jobicy",
            "search_url": "https://jobicy.com/jobs/?s={keywords}",
            "card_selectors": ["article.job-post", ".job-post", "li[class*='job']", "a[href*='/jobs/']", "h2 a[href]"],
            "apply_btn_selectors": [
                "a.apply-btn",
                "a:has-text('Apply')",
                "a[href*='apply']",
                "a:has-text('Apply now')",
            ],
            "next_page_selector": "a.next",
        },
    ]

    def run_direct_external_campaign(self) -> dict[str, Any]:
        """Browse external job boards directly â€” no LinkedIn.
        Uses WeWorkRemotely, RemoteOK, and other bot-friendly remote job sites.
        """
        start = datetime.now(timezone.utc).isoformat()
        stats: dict[str, int] = {"scanned": 0, "submitted": 0, "skipped": 0, "failures": 0, "errors": 0}

        run_headless = self.config.settings.headless
        visible_args = [] if run_headless else [
            "--start-maximized", "--window-position=0,0",
            "--disable-blink-features=AutomationControlled",
        ]
        launch_kw: dict = {
            "headless": run_headless,
            "args": visible_args + [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
            ],
        }
        if not run_headless:
            launch_kw["slow_mo"] = 80

        with sync_playwright() as pw:
            browser = None
            for channel in ["chrome", "msedge"]:
                try:
                    browser = pw.chromium.launch(channel=channel, **launch_kw)
                    break
                except Exception:
                    continue
            if browser is None:
                browser = pw.chromium.launch(**launch_kw)
            self._active_browser = browser

            context = browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="Europe/Budapest",
            )
            self._active_context = context

            # Open the first job site immediately so the user sees a real page right away
            if not run_headless:
                first_url = (
                    self._DIRECT_EXTERNAL_SITES[0]["search_url"]
                    .replace("{keywords}", quote_plus((self.config.settings.keywords or ["Software Developer"])[0]))
                    .replace("{kw_slug}", (self.config.settings.keywords or ["Software Developer"])[0].lower().replace(" ", "-"))
                )
                splash = context.new_page()
                self._setup_page_as_human(splash)
                try:
                    splash.goto(first_url, wait_until="domcontentloaded", timeout=15000)
                    splash.bring_to_front()
                    self._human_reading_pause(0.5, 1.0)
                except Exception:
                    pass
                splash.close()

            try:
                for site in self._DIRECT_EXTERNAL_SITES:
                    if self.stop_requested:
                        break
                    try:
                       if site.get("name") == "RemoteOK":
                           self._direct_external_search_remoteok_api(context, site, stats)
                       else:
                           self._direct_external_search_site(context, site, stats)
                    except Exception as exc:
                        self._log(f"[DIRECT-EXT] Site {site['name']} error: {exc}")
                        stats["errors"] += 1
            finally:
                try:
                    context.close()
                except Exception:
                    pass
                try:
                    browser.close()
                except Exception:
                    pass
                self._active_context = None
                self._active_browser = None

        return {
            "started_at": start,
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "stats": stats,
            "job_events": self._job_events,
        }

    def _direct_external_search_site(self, context, site: dict, stats: dict) -> None:
        """Search one external job board and attempt to apply to found jobs."""
        p = self.config.profile
        s = self.config.settings

        profile_title = (getattr(p, "current_job_title", "") or "").strip()
        keywords = profile_title or "Software Engineer"
        location = getattr(s, "locations", [None])[0] or "Remote"
        kw_slug = keywords.lower().replace(" ", "-")

        search_url = (
            site["search_url"]
            .replace("{keywords}", quote_plus(keywords))
            .replace("{location}", quote_plus(location))
            .replace("{kw_slug}", kw_slug)
        )

        page = context.new_page()
        self._setup_page_as_human(page)
        try:
            self._log(f"[DIRECT-EXT] Opening {site['name']}: {search_url}")
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                # Wait for JS to render job listings
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                page.bring_to_front()
            except Exception as nav_exc:
                self._log(f"[DIRECT-EXT] {site['name']} navigation failed: {nav_exc}")
                stats["errors"] += 1
                return

            # Check for CAPTCHA or bot-detection wall immediately
            page_issue = self._detect_external_page_error(page, search_url)
            if page_issue:
                self._log(f"[DIRECT-EXT] {site['name']} error page: {page_issue}")
                stats["errors"] += 1
                return

            wall = self._detect_external_account_wall(page)
            if wall:
                self._log(f"[DIRECT-EXT] {site['name']} requires login: {wall}")
                stats["skipped"] += 1
                return

            self._human_reading_pause(1.0, 2.0)

            page_num = 0
            max_pages = 2
            applied_this_site = 0

            while page_num < max_pages and not self.stop_requested:
                page_num += 1

                # Scroll through the results page naturally
                self._direct_external_scroll_results(page)

                # Collect all visible job card links
                job_links = self._direct_external_collect_jobs(page, site)
                if not job_links and page_num == 1:
                    # Some boards ignore URL params; try in-page search
                    self._direct_external_try_inpage_search(page, keywords, location)
                    self._direct_external_scroll_results(page)
                    job_links = self._direct_external_collect_jobs(page, site)
                self._log(f"[DIRECT-EXT] {site['name']} page {page_num}: found {len(job_links)} jobs")

                for job_url in job_links:
                    if self.stop_requested:
                        break
                    if applied_this_site >= (self.limit or 10):
                        break
                    stats["scanned"] += 1
                    try:
                        ok = self._direct_external_apply_one(context, job_url, site, stats)
                        if ok:
                            applied_this_site += 1
                    except Exception as exc:
                        import traceback
                        self._log(f"[DIRECT-EXT] Apply error {job_url[:60]}: {exc}")
                        self._log(traceback.format_exc()[-1200:])
                        stats["failures"] += 1

                # Try to go to next page
                if not site.get("next_page_selector"):
                    break
                try:
                    next_btn = page.locator(site["next_page_selector"]).first
                    if not next_btn.is_visible(timeout=2000):
                        break
                    next_btn.click(timeout=3000)
                    self._human_reading_pause(1.5, 2.5)
                except Exception:
                    break
        finally:
            page.close()

    def _direct_external_search_remoteok_api(self, context, site: dict, stats: dict) -> None:
        """Use RemoteOK API to get direct apply/company URLs and skip dead aiok.co redirects."""
        p = self.config.profile
        profile_title = (getattr(p, "current_job_title", "") or "").strip().lower()
        keywords = [w for w in profile_title.split() if len(w) > 2] or ["software", "engineer"]

        page = context.new_page()
        self._setup_page_as_human(page)
        try:
            api_url = "https://remoteok.com/api"
            self._log(f"[DIRECT-EXT] Opening RemoteOK API: {api_url}")
            try:
                page.goto(api_url, wait_until="domcontentloaded", timeout=20000)
                body = page.locator("body").inner_text(timeout=6000)
                data = json.loads(body)
            except Exception as exc:
                self._log(f"[DIRECT-EXT] RemoteOK API failed: {exc}")
                stats["errors"] += 1
                return

            jobs = []
            for item in data if isinstance(data, list) else []:
                if not isinstance(item, dict):
                    continue
                position = (item.get("position") or "").lower()
                tags = " ".join(item.get("tags") or []).lower()
                hay = f"{position} {tags}"
                if keywords and not any(k in hay for k in keywords):
                    continue
                apply_url = (item.get("apply_url") or item.get("url") or "").strip()
                if not apply_url:
                    continue
                low = apply_url.lower()
                if "aiok.co" in low:
                    continue
                jobs.append(apply_url)
                if len(jobs) >= 20:
                    break

            self._log(f"[DIRECT-EXT] RemoteOK API: found {len(jobs)} direct apply URLs")

            applied_this_site = 0
            for job_url in jobs:
                if self.stop_requested:
                    break
                if applied_this_site >= (self.limit or 10):
                    break
                stats["scanned"] += 1
                try:
                    ok = self._direct_external_apply_one(context, job_url, site, stats)
                    if ok:
                        applied_this_site += 1
                except Exception as exc:
                    import traceback
                    self._log(f"[DIRECT-EXT] Apply error {job_url[:60]}: {exc}")
                    self._log(traceback.format_exc()[-1200:])
                    stats["failures"] += 1
        finally:
            page.close()

    def _direct_external_try_inpage_search(self, page, keywords: str, location: str) -> None:
        """Best-effort in-page search for sites that ignore query params and open a generic page."""
        search_selectors = [
            "input[type='search']",
            "input[name*='search' i]",
            "input[id*='search' i]",
            "input[placeholder*='search' i]",
            "input[placeholder*='job' i]",
        ]
        try:
            for sel in search_selectors:
                try:
                    inp = page.locator(sel).first
                    if inp.is_visible(timeout=1200):
                        self._human_move_mouse_to(page, inp)
                        self._human_pause(0.1, 0.25)
                        inp.click(timeout=2000)
                        self._human_pause(0.1, 0.2)
                        query = f"{keywords} {location}".strip()
                        for ch in query:
                            inp.type(ch, delay=random.randint(40, 120))
                        self._human_pause(0.15, 0.35)
                        inp.press("Enter")
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=12000)
                        except Exception:
                            pass
                        self._human_reading_pause(0.8, 1.5)
                        self._log(f"[DIRECT-EXT] In-page search executed: {query}")
                        return
                except Exception:
                    continue
        except Exception:
            pass

    def _direct_external_scroll_results(self, page) -> None:
        """Scroll down the results page naturally to load all job cards."""
        try:
            for _ in range(random.randint(3, 6)):
                page.mouse.wheel(0, random.randint(300, 600))
                time.sleep(random.uniform(0.3, 0.8))
            # Scroll back up a little, like a human re-checking
            page.mouse.wheel(0, -random.randint(100, 300))
            self._human_pause(0.3, 0.7)
        except Exception:
            pass

    def _direct_external_collect_jobs(self, page, site: dict) -> list[str]:
        """Return a de-duplicated list of job detail/apply URLs from the search page."""
        urls: list[str] = []
        seen: set[str] = set()

        def _is_probable_job_url(href: str) -> bool:
            low = (href or "").lower()
            if not low or low.startswith("javascript") or low.startswith("mailto:"):
                return False
            if site.get("name") == "WeWorkRemotely":
                return "/remote-jobs/" in low and "/company/" not in low and "/listing_ads/" not in low
            # RemoteOK frequently exposes company pages; keep only real job paths.
            if site.get("name") == "RemoteOK":
                return "/remote-jobs/" in low
            if site.get("name") == "Jobicy":
                # Keep only actual job detail URLs like /jobs/12345-slug (has digit after /jobs/)
                import re as _re
                return bool(_re.search(r"/jobs/\d", low))
            blocked = (
                "/company", "/companies", "/blog", "/about", "/privacy", "/terms",
                "linkedin.com", "twitter.com", "facebook.com", "instagram.com"
            )
            return not any(b in low for b in blocked)

        for selector in site["card_selectors"]:
            try:
                cards = page.query_selector_all(selector)
                for card in cards:
                    try:
                        hrefs: list[str] = []

                        # RemoteOK: prefer explicit job anchors first.
                        if site.get("name") == "RemoteOK":
                            try:
                                links = card.query_selector_all("a[href*='/remote-jobs/']")
                                for lk in links:
                                    hrefs.append(lk.get_attribute("href") or "")
                            except Exception:
                                pass

                        # Generic fallback: first anchor or card href.
                        if not hrefs:
                            link = card.query_selector("a[href]")
                            if link:
                                hrefs.append(link.get_attribute("href") or "")
                            else:
                                own_href = card.get_attribute("href") or ""
                                if own_href:
                                    hrefs.append(own_href)

                        for href in hrefs:
                            href = (href or "").strip()
                            if not href or not _is_probable_job_url(href):
                                continue
                            if href.startswith("/"):
                                base = page.url.split("/")[0] + "//" + page.url.split("/")[2]
                                href = base + href
                            if href in seen:
                                continue
                            seen.add(href)
                            urls.append(href)
                    except Exception:
                        continue
                if urls:
                    break
            except Exception:
                continue

        # WeWorkRemotely fallback: job links are often directly in anchors, not always in card wrappers.
        if not urls and site.get("name") == "WeWorkRemotely":
            try:
                links = page.query_selector_all("a[href*='/remote-jobs/']")
                for lk in links:
                    href = (lk.get_attribute("href") or "").strip()
                    if not href:
                        continue
                    if href.startswith("/"):
                        href = f"https://weworkremotely.com{href}"
                    low = href.lower()
                    if "/company/" in low or "/listing_ads/" in low:
                        continue
                    if href not in seen:
                        seen.add(href)
                        urls.append(href)
            except Exception:
                pass
        return urls[:20]  # cap per page

    def _find_best_apply_link(self, page, site: dict) -> tuple[Any | None, str]:
        """Find apply action using site selectors first, then robust generic fallbacks."""
        broken_domains = ("aiok.co", "remoteok.com/l/")

        def _is_broken_href(href: str) -> bool:
            low = (href or "").lower()
            if not low.startswith("http"):
                return False
            try:
                host = low.split("/")[2]
            except Exception:
                return False
            for d in broken_domains:
                if "/" in d:
                    if d in low:
                        return True
                else:
                    if host == d or host.endswith(f".{d}"):
                        return True
            return False

        # 1) Site-specific selectors
        for sel in site.get("apply_btn_selectors", []):
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1200):
                    href = (btn.get_attribute("href") or "").strip()
                    if _is_broken_href(href):
                        continue
                    return btn, href
            except Exception:
                continue

        # 2) Generic apply-like controls
        generic_selectors = [
            "a:has-text('Apply now')",
            "a:has-text('Apply for this job')",
            "a:has-text('Apply for this position')",
            "a:has-text('Apply')",
            "button:has-text('Apply now')",
            "button:has-text('Apply')",
            "a[href*='apply']",
            "a[href*='careers']",
            "a[href*='jobs']",
        ]
        for sel in generic_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=900):
                    href = (btn.get_attribute("href") or "").strip()
                    if _is_broken_href(href):
                        continue
                    return btn, href
            except Exception:
                continue

        # 3) RemoteOK and similar boards: pick likely external outbound link.
        try:
            anchors = page.query_selector_all("a[href]")
        except Exception:
            anchors = []

        blocked_domains = (
            "remoteok.com", "weworkremotely.com", "jobicy.com", "europeremotejobs.com",
            "linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com", "t.me"
        )
        for a in anchors[:150]:
            try:
                href = (a.get_attribute("href") or "").strip()
                txt = (a.inner_text() or "").strip().lower()
                if not href:
                    continue
                if href.startswith("/"):
                    continue
                hlow = href.lower()
                if not hlow.startswith("http"):
                    continue
                if any(d in hlow for d in blocked_domains):
                    continue
                if _is_broken_href(href):
                    continue
                # Prefer links with apply-related text first
                if any(k in txt for k in ("apply", "job", "position", "career", "open role")):
                    return None, href

                    # 4) Last resort: any external link (not internal navigation) on the page
                    for a in anchors[:150]:
                        try:
                            href = (a.get_attribute("href") or "").strip()
                            if not href or href.startswith("/"):
                                continue
                            hlow = href.lower()
                            if not hlow.startswith("http"):
                                continue
                            if any(d in hlow for d in blocked_domains):
                                continue
                            if _is_broken_href(href):
                                continue
                            return None, href
                        except Exception:
                            continue
            except Exception:
                continue

        return None, ""

    def _open_external_apply_target(self, context, page, apply_btn, btn_href: str, site: dict):
        """Open apply destination from button/href and return a target page when it becomes external.

        Returns:
            tuple[target_page_or_none, note]
        """
        target_page = None
        note = ""

        # Normalize relative href.
        normalized_href = (btn_href or "").strip()
        if normalized_href.startswith("/"):
            parts = page.url.split("/")
            if len(parts) >= 3:
                normalized_href = f"{parts[0]}//{parts[2]}{normalized_href}"

        current_host = ""
        try:
            current_host = page.url.split("/")[2].lower()
        except Exception:
            current_host = ""

        def _is_broken_host(href: str) -> bool:
            low = (href or "").lower()
            if not low.startswith("http"):
                return False
            try:
                host = low.split("/")[2]
            except Exception:
                return False
            return host == "aiok.co" or host.endswith(".aiok.co")

        def _is_externalish(href: str) -> bool:
            low = (href or "").lower()
            if not low:
                return False
            if "/l/" in low or "apply" in low:
                return True
            if low.startswith("http"):
                try:
                    host = low.split("/")[2]
                    return host != current_host
                except Exception:
                    return True
            return False

        # Avoid known dead redirect domains.
        if normalized_href and _is_broken_host(normalized_href):
            note = f"skipped broken redirect domain: {normalized_href[:80]}"
            normalized_href = ""

        # Prefer direct navigation when href likely points to outbound/apply route.
        if normalized_href and _is_externalish(normalized_href):
            try:
                target_page = context.new_page()
                self._setup_page_as_human(target_page)
                target_page.goto(normalized_href, wait_until="domcontentloaded", timeout=18000)
                self._human_reading_pause(0.8, 1.6)
                # Check if redirect landed on a dead domain
                final_url = target_page.url
                if _is_broken_host(final_url):
                    try:
                        target_page.close()
                    except Exception:
                        pass
                    note = f"redirect ended at dead domain: {final_url[:80]}"
                else:
                    return target_page, "opened apply href"
            except Exception as exc:
                note = f"open href failed: {exc}"

        # Try click path (popup or same-tab navigation).
        if apply_btn is not None:
            before_url = page.url
            try:
                with page.expect_popup(timeout=3500) as popup_info:
                    self._human_move_mouse_to(page, apply_btn)
                    self._human_pause(0.1, 0.25)
                    apply_btn.click(timeout=3500)
                target_page = popup_info.value
                self._setup_page_as_human(target_page)
                target_page.wait_for_load_state("domcontentloaded", timeout=15000)
                self._human_reading_pause(0.8, 1.6)
                return target_page, "opened popup from apply click"
            except Exception:
                try:
                    self._human_move_mouse_to(page, apply_btn)
                    self._human_pause(0.1, 0.2)
                    apply_btn.click(timeout=3000)
                except Exception:
                    pass

            try:
                page.wait_for_load_state("domcontentloaded", timeout=9000)
            except Exception:
                pass

            after_url = page.url
            if after_url != before_url:
                try:
                    after_host = after_url.split("/")[2].lower()
                except Exception:
                    after_host = ""
                if after_host and after_host != current_host:
                    return page, "navigated to external host after apply click"
                if _is_externalish(after_url):
                    return page, "navigated to external apply route after click"

        return None, note or "no external destination opened"

    def _direct_external_apply_one(self, context, job_url: str, site: dict, stats: dict) -> bool:
        """Open one job page and attempt to apply. Returns True if submitted."""
        page = context.new_page()
        self._setup_page_as_human(page)
        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=18000)
            # Wait for JS to render apply button
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            self._human_reading_pause(1.2, 2.8)

            # Check for page errors
            page_issue = self._detect_external_page_error(page, job_url)
            if page_issue:
                self._log(f"[DIRECT-EXT] Skipping â€” {page_issue}")
                stats["skipped"] += 1
                return False

            # Check for account walls
            wall = self._detect_external_account_wall(page)
            if wall:
                self._log(f"[DIRECT-EXT] Account wall on {job_url[:60]}: {wall}")
                login_ok, login_note = self._try_external_login(page)
                if login_ok:
                    self._log(f"[DIRECT-EXT] {login_note}")
                    self._human_reading_pause(0.6, 1.2)
                else:
                    self._log(f"[DIRECT-EXT] {login_note}")
                    stats["skipped"] += 1
                    return False

            # Extract basic job info for logging
            title = ""
            company = ""
            try:
                title = (page.locator("h1").first.inner_text(timeout=2000) or "").strip()[:80]
            except Exception:
                pass
            try:
                company = (page.locator("[class*='company']").first.inner_text(timeout=1500) or "").strip()[:50]
            except Exception:
                pass
            self._log(f"[DIRECT-EXT] Applying: {title} @ {company} | {job_url[:60]}")

            apply_btn, btn_href = self._find_best_apply_link(page, site)

            if not apply_btn and not btn_href:
                self._log(f"[DIRECT-EXT] No apply button found on {job_url[:60]}")
                stats["skipped"] += 1
                return False

            ext_page, ext_note = self._open_external_apply_target(context, page, apply_btn, btn_href, site)

            if ext_page is not None:
                # Opens an ATS site â€” use existing ATS fill helpers
                self._current_report = {"qa_pairs": {}, "uploaded_files": [], "external_ats": {}}
                self._log(f"[DIRECT-EXT] Apply route opened: {ext_note}")

                err = self._detect_external_page_error(ext_page, ext_page.url)
                if err:
                    self._log(f"[DIRECT-EXT] {err}")
                    stats["skipped"] += 1
                    return False

                wall2 = self._detect_external_account_wall(ext_page)
                if wall2:
                    self._log(f"[DIRECT-EXT] {wall2}")
                    login_ok, login_note = self._try_external_login(ext_page)
                    if login_ok:
                        self._log(f"[DIRECT-EXT] {login_note}")
                        self._human_reading_pause(0.6, 1.2)
                    else:
                        self._log(f"[DIRECT-EXT] {login_note}")
                        stats["skipped"] += 1
                        return False

                ats = self._detect_ats(ext_page.url)
                self._log(f"[DIRECT-EXT] ATS: {ats} | {ext_page.url[:70]}")
                try:
                    ok, note = self._fill_generic_external(ext_page)
                except Exception as fill_exc:
                    ok, note = False, f"ATS fill exception: {fill_exc}"
                if ok:
                    stats["submitted"] += 1
                    self._log(f"[DIRECT-EXT] âœ“ Submitted via {ats}: {note}")
                    return True
                else:
                    self._log(f"[DIRECT-EXT] âœ— Could not submit: {note}")
                    stats["failures"] += 1
                    return False
            else:
                # Inline form on the same page â€” click button and fill
                self._current_report = {"qa_pairs": {}, "uploaded_files": [], "external_ats": {}}
                if apply_btn is not None:
                    self._human_move_mouse_to(page, apply_btn)
                    self._human_pause(0.1, 0.25)
                    apply_btn.click(timeout=3000)
                self._human_reading_pause(0.8, 1.8)

                wall3 = self._detect_external_account_wall(page)
                if wall3:
                    self._log(f"[DIRECT-EXT] {wall3}")
                    login_ok, login_note = self._try_external_login(page)
                    if login_ok:
                        self._log(f"[DIRECT-EXT] {login_note}")
                        self._human_reading_pause(0.5, 1.0)
                    else:
                        self._log(f"[DIRECT-EXT] {login_note}")
                        stats["skipped"] += 1
                        return False

                try:
                    ok, note = self._fill_generic_external(page)
                except Exception as fill_exc:
                    ok, note = False, f"Inline fill exception: {fill_exc}"
                if ok:
                    stats["submitted"] += 1
                    self._log(f"[DIRECT-EXT] âœ“ Submitted inline: {note}")
                    return True
                else:
                    self._log(f"[DIRECT-EXT] âœ— Inline fill failed: {note}")
                    stats["failures"] += 1
                    return False
        finally:
            try:
                page.close()
            except Exception:
                pass

    def run_networking_campaign(self) -> dict[str, Any]:
        """Follow role-matched companies on LinkedIn.

        Returns a dict with stats: sent, skipped, failures.
        Uses the same Playwright session as the apply bot (reuses saved login state).
        """
        start = datetime.now(timezone.utc).isoformat()
        net_stats: dict[str, int] = {"sent": 0, "skipped": 0, "failures": 0}

        run_headless = self.config.settings.headless
        if not self.config.paths.browser_state_path.exists():
            run_headless = False

        with sync_playwright() as p:
            browser = None
            for channel in ["chrome", "msedge"]:
                try:
                    browser = p.chromium.launch(headless=run_headless, channel=channel)
                    break
                except Exception:
                    continue
            if browser is None:
                browser = p.chromium.launch(headless=run_headless)

            context = browser.new_context(
                storage_state=str(self.config.paths.browser_state_path)
                if self.config.paths.browser_state_path.exists()
                else None
            )
            page = context.new_page()
            try:
                self._login(page)
                self._do_networking(page, net_stats)
            finally:
                context.storage_state(path=str(self.config.paths.browser_state_path))
                context.close()
                browser.close()

        return {
            "started_at": start,
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "stats": net_stats,
        }

    def run_unfollow_companies_campaign(
        self,
        *,
        companies: list[str] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Unfollow previously tracked companies from network_sent.json."""
        start = datetime.now(timezone.utc).isoformat()
        stats: dict[str, int] = {"unfollowed": 0, "skipped": 0, "failures": 0}

        run_headless = self.config.settings.headless
        if not self.config.paths.browser_state_path.exists():
            run_headless = False

        with sync_playwright() as p:
            browser = None
            for channel in ["chrome", "msedge"]:
                try:
                    browser = p.chromium.launch(headless=run_headless, channel=channel)
                    break
                except Exception:
                    continue
            if browser is None:
                browser = p.chromium.launch(headless=run_headless)

            context = browser.new_context(
                storage_state=str(self.config.paths.browser_state_path)
                if self.config.paths.browser_state_path.exists()
                else None
            )
            page = context.new_page()
            try:
                self._login(page)
                self._do_unfollow_companies(page, stats, companies=companies, limit=limit)
            finally:
                context.storage_state(path=str(self.config.paths.browser_state_path))
                context.close()
                browser.close()

        return {
            "started_at": start,
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "stats": stats,
        }

    def _do_networking(self, page, stats: dict[str, int]) -> None:
        """Follow top international companies on LinkedIn to grow connections."""
        network_log_path = self.config.paths.base_dir / "network_sent.json"
        sent: dict[str, Any] = self._read_json(network_log_path, default={})
        target_companies = self._get_networking_target_companies()

        max_per_run: int = getattr(self.config.settings, "max_network_per_run", 20)
        count = 0

        print(
            f"[NETWORK] Title='{getattr(self.config.profile, 'current_job_title', '')}' "
            f"-> {len(target_companies)} role-matched companies"
        )

        for company in target_companies:
            if count >= max_per_run:
                break

            # â”€â”€ Follow the company page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            follow_key = f"__follow__{company.lower()}"
            if follow_key not in sent:
                try:
                    company_search_url = (
                        "https://www.linkedin.com/search/results/companies/"
                        f"?keywords={quote_plus(company)}"
                    )
                    page.goto(company_search_url, wait_until="domcontentloaded", timeout=60_000)
                    self._human_pause()
                    # Click the first company result
                    first_link = page.query_selector(
                        "a[href*='/company/'], "
                        ".entity-result__title-text a, "
                        "div[data-view-name='search-entity-result-universal-template'] a[href*='/company/']"
                    )
                    if first_link:
                        company_href = first_link.get_attribute("href") or ""
                        if company_href.startswith("/"):
                            company_href = "https://www.linkedin.com" + company_href
                        company_href = company_href.split("?")[0]
                        page.goto(company_href, wait_until="domcontentloaded", timeout=60_000)
                        self._human_pause()
                        # Find the Follow button on the company page
                        follow_btn = None
                        for sel in [
                            "button[aria-label*='Follow'][aria-label*='" + company + "']",
                            "button[aria-label='Follow']",
                            "button:has-text('Follow')",
                        ]:
                            try:
                                b = page.query_selector(sel)
                                if b:
                                    follow_btn = b
                                    break
                            except Exception:
                                pass
                        if follow_btn:
                            follow_btn.click(timeout=3000)
                            self._human_pause(0.5, 1.0)
                            sent[follow_key] = {
                                "company": company,
                                "company_url": company_href,
                                "followed_at": datetime.now(timezone.utc).isoformat(),
                            }
                            self._write_json(network_log_path, sent)
                            stats["sent"] += 1
                            count += 1
                except Exception:
                    pass

    def _do_unfollow_companies(
        self,
        page,
        stats: dict[str, int],
        *,
        companies: list[str] | None,
        limit: int,
    ) -> None:
        """Unfollow tracked companies and update network_sent.json accordingly."""
        network_log_path = self.config.paths.base_dir / "network_sent.json"
        sent: dict[str, Any] = self._read_json(network_log_path, default={})

        targets: list[tuple[str, dict[str, Any]]] = []
        requested_names = [c.strip() for c in (companies or []) if c and c.strip()]
        normalized_filter = {c.lower() for c in requested_names}
        for key, payload in sent.items():
            if not key.startswith("__follow__") or not isinstance(payload, dict):
                continue
            company_name = str(payload.get("company", "")).strip()
            if not company_name:
                continue
            if normalized_filter:
                company_name_l = company_name.lower()
                matches = any(
                    company_name_l == needle
                    or needle in company_name_l
                    or company_name_l in needle
                    for needle in normalized_filter
                )
                if not matches:
                    continue
            targets.append((key, payload))

        # If the requested company is not in tracking log, still try direct unfollow.
        if not targets and requested_names:
            for requested in requested_names:
                targets.append((f"__adhoc__{requested.lower()}", {"company": requested, "company_url": ""}))

        for idx, (follow_key, payload) in enumerate(targets):
            if idx >= limit:
                break

            company = str(payload.get("company", "")).strip()
            company_url = str(payload.get("company_url", "")).strip()
            if not company:
                stats["skipped"] += 1
                continue

            try:
                if company_url:
                    page.goto(company_url, wait_until="domcontentloaded", timeout=60_000)
                else:
                    search_url = (
                        "https://www.linkedin.com/search/results/companies/"
                        f"?keywords={quote_plus(company)}"
                    )
                    page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
                    self._human_pause(0.5, 1.0)
                    first_link = page.query_selector(
                        "a[href*='/company/'], "
                        ".entity-result__title-text a, "
                        "div[data-view-name='search-entity-result-universal-template'] a[href*='/company/']"
                    )
                    if not first_link:
                        stats["skipped"] += 1
                        continue
                    href = first_link.get_attribute("href") or ""
                    if href.startswith("/"):
                        href = "https://www.linkedin.com" + href
                    company_url = href.split("?")[0]
                    page.goto(company_url, wait_until="domcontentloaded", timeout=60_000)

                self._human_pause(0.5, 1.0)

                clicked = False
                for sel in [
                    "button:has-text('Following')",
                    "button[aria-label*='Following']",
                    "button[aria-label*='following']",
                    "button[aria-pressed='true'][aria-label*='Follow']",
                    "button[aria-pressed='true'][aria-label*='follow']",
                    "button[aria-label*='Unfollow']",
                    "button:has-text('Unfollow')",
                ]:
                    btn = page.query_selector(sel)
                    if btn:
                        try:
                            btn.click(timeout=3000)
                            clicked = True
                            break
                        except Exception:
                            pass

                if not clicked:
                    # Some company pages expose Unfollow via overflow menu.
                    try:
                        more_btn = page.query_selector(
                            "button[aria-label='More actions'], "
                            "button[aria-label*='More actions'], "
                            "button[aria-label*='more actions']"
                        )
                        if more_btn:
                            more_btn.click(timeout=3000)
                            self._human_pause(0.3, 0.6)
                            menu_unfollow = page.query_selector(
                                "div[role='menuitem']:has-text('Unfollow'), "
                                "span:has-text('Unfollow')"
                            )
                            if menu_unfollow:
                                menu_unfollow.click(timeout=3000)
                                clicked = True
                    except Exception:
                        pass

                if not clicked:
                    stats["skipped"] += 1
                    continue

                self._human_pause(0.4, 0.8)
                confirm_btn = page.query_selector(
                    "button:has-text('Unfollow'), "
                    "button[aria-label*='Unfollow']"
                )
                if confirm_btn:
                    try:
                        confirm_btn.click(timeout=3000)
                    except Exception:
                        pass

                stats["unfollowed"] += 1
                if follow_key.startswith("__follow__"):
                    sent.pop(follow_key, None)
                self._write_json(network_log_path, sent)
                self._human_pause(0.5, 1.0)
            except Exception:
                stats["failures"] += 1


    def _send_connection_request_on_card(self, page, card) -> bool | None:
        """Click Connect on a search-result card and confirm the modal.

        Returns:
            True  â€” invitation sent successfully
            False â€” an error occurred
            None  â€” not applicable (already connected, button absent, etc.)
        """
        try:
            # 1. Find the Connect button directly on the card
            connect_btn = None
            for sel in [
                "button[aria-label*='Invite'][aria-label*='connect']",
                "button[aria-label*='Connect']",
                "button[aria-label*='connect']",
            ]:
                try:
                    connect_btn = card.query_selector(sel)
                    if connect_btn:
                        break
                except Exception:
                    pass

            if not connect_btn:
                # Scan all buttons for text "Connect"
                for btn in (card.query_selector_all("button") or []):
                    try:
                        if (btn.inner_text() or "").strip().lower() == "connect":
                            connect_btn = btn
                            break
                    except Exception:
                        pass

            if not connect_btn:
                # Try "..." overflow menu
                more_btn = None
                for sel in [
                    "button[aria-label='More actions']",
                    "button[aria-label*='more actions']",
                    "button[aria-label*='More']",
                ]:
                    try:
                        more_btn = card.query_selector(sel)
                        if more_btn:
                            break
                    except Exception:
                        pass

                if not more_btn:
                    return None  # No way to connect from this card

                more_btn.click(timeout=3000)
                page.wait_for_timeout(700)
                for sel in [
                    "div[role='option']:has-text('Connect')",
                    "li[role='option']:has-text('Connect')",
                    "span:has-text('Connect')",
                ]:
                    try:
                        item = page.query_selector(sel)
                        if item:
                            item.click(timeout=3000)
                            connect_btn = True  # sentinel â€” modal will follow
                            break
                    except Exception:
                        pass

                if not connect_btn:
                    return None
            else:
                connect_btn.click(timeout=3000)

            page.wait_for_timeout(1200)

            # 2. Handle post-click modal
            # "Send now" / "Send without a note"
            for sel in [
                "button[aria-label='Send now']",
                "button[aria-label='Send without a note']",
                "button:has-text('Send now')",
                "button:has-text('Send without a note')",
            ]:
                try:
                    btn = page.query_selector(sel)
                    if btn:
                        btn.click(timeout=3000)
                        page.wait_for_timeout(800)
                        return True
                except Exception:
                    pass

            # "How do you know X?" â€” dismiss; we can't auto-categorize
            for sel in [
                "button[aria-label='Dismiss']",
                "button[aria-label='Close']",
                "button:has-text('Cancel')",
            ]:
                try:
                    btn = page.query_selector(sel)
                    if btn:
                        btn.click(timeout=2000)
                        return None
                except Exception:
                    pass

            # No modal visible â€” request likely sent inline (no extra step required)
            return True

        except Exception:
            return False

    # â”€â”€ State helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _write_state(self) -> None:
        self._write_json(self.config.paths.state_path, self.state)

    def _reached_limit(self) -> bool:
        # Count terminal outcomes so short test runs stop quickly.
        # "skipped" = already seen / redirected â†’ also doesn't count.
        processed = (
            self.stats["submitted"]
            + self.stats["dry_run"]
            + self.stats["manual_required"]
            + self.stats["failures"]
        )
        return processed >= self.limit

