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
from datetime import datetime
from pathlib import Path

# Add the linkedin_bot directory to path so we can import bot & config
BOT_DIR = Path(__file__).resolve().parent.parent / "linkedin_bot"
sys.path.insert(0, str(BOT_DIR))

from config import (
    CandidateProfile, BotSettings, RuntimeConfig, RuntimePaths
)
from bot import LinkedInAutoApplyBot


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
    from app import db, UserProfile, User, UPLOAD_FOLDER

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
    with app.app_context():
        from app import db, BotRun

        bot_run = db.session.get(BotRun, run_id)

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

            bot = LinkedInAutoApplyBot(config, dry_run=False, resume=False)
            bot.run()

            stats = bot.stats
            bot_run.submitted = stats.get("submitted", 0)
            bot_run.skipped = stats.get("skipped", 0)
            bot_run.failures = stats.get("failures", 0)
            _log(f"Done. submitted={bot_run.submitted} skipped={bot_run.skipped} failures={bot_run.failures}")
            bot_run.status = "done"

        except Exception as exc:
            _log(f"ERROR: {exc}")
            bot_run.status = "error"

        finally:
            bot_run.finished_at = datetime.utcnow()
            bot_run.log_snippet = "\n".join(log_lines)
            db.session.commit()


def run_for_user_async(user_id: int) -> int:
    """
    Creates a BotRun record and starts the bot in a background thread.
    Returns the run_id.
    """
    from flask import current_app
    from app import db, BotRun

    run = BotRun(user_id=user_id, status="running")
    db.session.add(run)
    db.session.commit()
    run_id = run.id

    t = threading.Thread(
        target=_do_run,
        args=(current_app._get_current_object(), user_id, run_id),
        daemon=True,
    )
    t.start()
    return run_id
