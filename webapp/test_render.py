import sys, traceback
sys.stderr = sys.stdout

from app import app, db, User, UserProfile, BotRun, MissingSkillsReport
from app import ensure_api_token, _load_recent_job_events, _load_generated_letters

with app.app_context():
    u = db.session.get(User, 1)
    p = UserProfile.query.filter_by(user_id=1).first()
    print(f"User: {u.email}, Profile CV: {p.cv_filename}, LI: {p.linkedin_email}")
    try:
        runs = BotRun.query.filter_by(user_id=u.id).order_by(BotRun.started_at.desc()).limit(20).all()
        failed_runs = BotRun.query.filter(BotRun.user_id==u.id, BotRun.failures>0).order_by(BotRun.started_at.desc()).limit(15).all()
        total = db.session.query(db.func.sum(BotRun.submitted)).filter_by(user_id=u.id).scalar() or 0
        total_failed = db.session.query(db.func.sum(BotRun.failures)).filter_by(user_id=u.id).scalar() or 0
        total_attempted = int(total) + int(total_failed)
        success_probability = round((float(total) / float(total_attempted)) * 100.0, 1) if total_attempted else 0.0
        failure_probability = round(100.0 - success_probability, 1) if total_attempted else 0.0
        recent_for_chart = list(reversed(runs[:10]))
        application_stats = {
            'attempted': total_attempted,
            'submitted': int(total),
            'failed': int(total_failed),
            'success_probability': success_probability,
            'failure_probability': failure_probability,
            'labels': [f"Run {r.id}" for r in recent_for_chart],
            'submitted_series': [int(r.submitted or 0) for r in recent_for_chart],
            'failed_series': [int(r.failures or 0) for r in recent_for_chart],
        }
        api_token = ensure_api_token(u)
        submitted_jobs, failed_jobs = _load_recent_job_events(u.id, limit=25)
        generated_letters = _load_generated_letters(u.id, limit=40)
        missing_skills_reports = MissingSkillsReport.query.filter_by(user_profile_id=p.id).order_by(MissingSkillsReport.applied_at.desc()).limit(20).all()
        print(f"Data loaded: runs={len(runs)}, submitted={len(submitted_jobs)}, failed={len(failed_jobs)}, letters={len(generated_letters)}, reports={len(missing_skills_reports)}")

        with app.test_request_context('/dashboard'):
            from flask import render_template, session
            session['user_id'] = 1
            html = render_template(
                'dashboard.html',
                user=u, p=p, runs=runs, total_submitted=total,
                api_token=api_token, submitted_jobs=submitted_jobs,
                failed_jobs=failed_jobs, failed_runs=failed_runs,
                generated_letters=generated_letters,
                missing_skills_reports=missing_skills_reports,
                active_run_ids=set(),
                network_follow={'total': 0, 'items': []},
                networking_status={'running': False, 'action': '', 'started_at': ''},
                application_stats=application_stats,
                is_render=False,
            )
            print(f"RENDER OK, length={len(html)}")
    except Exception as e:
        print("RENDER FAILED:")
        traceback.print_exc()
