"""
scheduler.py – daily cron-like scheduler using APScheduler.
At 08:30 UTC every day, runs the bot for every user who has
auto_apply_enabled=True and valid LinkedIn credentials + CV.
"""
from __future__ import annotations

from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


def _run_all_users(app) -> None:
    with app.app_context():
        from app import db, User, UserProfile, BotRun
        from bot_runner import run_for_user_async

        profiles = UserProfile.query.filter_by(auto_apply_enabled=True).all()
        print(f"[Scheduler] {datetime.utcnow()} – running for {len(profiles)} user(s)")

        for p in profiles:
            if not p.linkedin_email or not p.linkedin_password_enc or not p.cv_filename:
                print(f"[Scheduler] User {p.user_id}: skipping – incomplete profile")
                continue
            try:
                run_id = run_for_user_async(p.user_id)
                print(f"[Scheduler] User {p.user_id}: started run #{run_id}")
            except Exception as exc:
                print(f"[Scheduler] User {p.user_id}: error – {exc}")


def start_scheduler(app) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    # Run daily at 08:30 UTC
    scheduler.add_job(
        func=lambda: _run_all_users(app),
        trigger=CronTrigger(hour=8, minute=30, timezone="UTC"),
        id="daily_apply",
        name="Daily LinkedIn Apply",
        replace_existing=True,
    )
    scheduler.start()
    print("[Scheduler] Started – will run daily at 08:30 UTC")
    return scheduler
