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


def build_config_for_user(user_id: int) -> RuntimeConfig:
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
    )

    settings = BotSettings(
        keywords=p.keywords_list or ["Software Developer"],
        locations=p.locations_list or ["Hungary"],
        max_applications_per_run=p.max_applications,
        posted_days_ago=p.posted_days_ago,
        headless=True,
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


def _do_run(app, user_id: int, run_id: int) -> None:
    """
    Actually runs the bot in a background thread, inside the Flask app context.
    Updates the BotRun record when done.
    """
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
                config = build_config_for_user(user_id)
                _log(f"Starting bot for user {user_id} ({config.email})")
                bot_run.log_snippet = "\n".join(log_lines)
                db.session.commit()

                bot = LinkedInAutoApplyBot(config, dry_run=False, resume=False)

                # Wire per-job callback so individual results appear in the log.
                def _on_job_result(result: dict) -> None:
                    status = result.get("status", "?")
                    title = (result.get("title") or "")[:60]
                    company = (result.get("company") or "")[:40]
                    note = result.get("note") or ""
                    _log(f"[{status.upper()}] {title} @ {company} — {note}")
                    bot_run.log_snippet = "\n".join(log_lines)
                    db.session.commit()

                bot._on_job_result = _on_job_result

                bot.run()

                stats = bot.stats
                bot_run.submitted = stats.get("submitted", 0)
                bot_run.skipped = stats.get("skipped", 0)
                bot_run.failures = stats.get("failures", 0)
                _log(f"Done. submitted={bot_run.submitted} skipped={bot_run.skipped} failures={bot_run.failures}")
                bot_run.status = "done"

            except Exception as exc:
                _log(f"ERROR: {exc}")
                import traceback
                _log(traceback.format_exc())
                bot_run.status = "error"

            finally:
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


def run_for_user_async(user_id: int) -> int:
    """
    Creates a BotRun record and starts the bot in a background thread.
    Returns the run_id.
    """
    # Bot cannot run on cloud servers (no persistent browser state, blocked IPs,
    # insufficient memory). Only works on the local Windows machine.
    if os.environ.get("RENDER") or os.environ.get("BOT_DISABLED"):
        app_mod = _resolve_app_module()
        db = app_mod.db
        BotRun = app_mod.BotRun
        run = BotRun(
            user_id=user_id,
            status="error",
            finished_at=datetime.utcnow(),
            log_snippet="Bot cannot run on Render. The bot must run on your local PC via Windows Task Scheduler (set for 08:30 daily).",
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
    existing = (
        BotRun.query
        .filter_by(user_id=user_id, status="running")
        .order_by(BotRun.started_at.desc())
        .first()
    )
    if existing:
        age = datetime.utcnow() - existing.started_at
        if age < timedelta(minutes=20):
            return existing.id
        existing.status = "error"
        existing.finished_at = datetime.utcnow()
        note = "Run marked stale after server restart/interruption."
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
            _do_run(app, user_id, run_id)
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
        max_duration_seconds = 15 * 60  # 15 minutes
        check_interval = 30  # Check every 30 seconds
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


