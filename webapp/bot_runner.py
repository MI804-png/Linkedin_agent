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
import threading
import importlib
from datetime import datetime, timedelta
from pathlib import Path

# Add the linkedin_bot directory to path so we can import bot & config
BOT_DIR = Path(__file__).resolve().parent.parent / "linkedin_bot"
sys.path.insert(0, str(BOT_DIR))

from config import (
    CandidateProfile, BotSettings, RuntimeConfig, RuntimePaths
)
from bot import LinkedInAutoApplyBot

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


def _do_run_watch_subprocess(app, user_id: int, run_id: int) -> None:
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
        _do_run_watch_subprocess(app, user_id, run_id)
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
                _active_bots[run_id] = bot
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
                config = build_config_for_user(user_id, watch_browser=watch_browser)
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

                result = bot.run_direct_external_campaign()
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

