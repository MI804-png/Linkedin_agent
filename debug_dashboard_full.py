#!/usr/bin/env python
"""Debug dashboard route errors in detail."""
import sys
import traceback
sys.path.insert(0, 'webapp')

from app import app, db, User, UserProfile, BotRun, MissingSkillsReport

with app.app_context():
    users = User.query.all()
    if not users:
        print("ERROR: No users found")
        sys.exit(1)
    
    user = users[0]
    print("Testing dashboard route for user: {}".format(user.email))
    print()
    
    # Manually run through dashboard route logic
    try:
        print("Step 1: get_current_user()...")
        print("  OK - user_id={}".format(user.id))
        
        print("\nStep 2: ensure_user_profile(user)...")
        from app import ensure_user_profile
        p = ensure_user_profile(user)
        print("  OK - profile_id={}".format(p.id))
        
        print("\nStep 3: Validate profile data...")
        if not p.cv_filename:
            print("  ERROR: Missing CV")
            sys.exit(1)
        if not p.linkedin_email or not p.linkedin_password_enc:
            print("  ERROR: Missing LinkedIn credentials")
            sys.exit(1)
        print("  OK - All required fields present")
        
        print("\nStep 4: Query BotRun (last 20)...")
        runs = BotRun.query.filter_by(user_id=user.id).order_by(BotRun.started_at.desc()).limit(20).all()
        print("  OK - {} runs".format(len(runs)))
        
        print("\nStep 5: Query failed runs...")
        failed_runs = (
            BotRun.query
            .filter(BotRun.user_id == user.id, BotRun.failures > 0)
            .order_by(BotRun.started_at.desc())
            .limit(15)
            .all()
        )
        print("  OK - {} failed runs".format(len(failed_runs)))
        
        print("\nStep 6: Sum submitted jobs...")
        total_submitted = db.session.query(db.func.sum(BotRun.submitted)).filter_by(user_id=user.id).scalar() or 0
        print("  OK - total_submitted={}".format(total_submitted))
        
        print("\nStep 7: ensure_api_token(user)...")
        from app import ensure_api_token
        api_token = ensure_api_token(user)
        print("  OK - token={}...".format(api_token[:20]))
        
        print("\nStep 8: _load_recent_job_events(user.id)...")
        from app import _load_recent_job_events
        submitted_jobs, failed_jobs = _load_recent_job_events(user.id, limit=25)
        print("  OK - {} submitted, {} failed".format(len(submitted_jobs), len(failed_jobs)))
        
        print("\nStep 9: _load_generated_letters(user.id)...")
        from app import _load_generated_letters
        generated_letters = _load_generated_letters(user.id, limit=40)
        print("  OK - {} letters".format(len(generated_letters)))
        
        print("\nStep 10: Load missing skills reports...")
        try:
            missing_skills_reports = (
                MissingSkillsReport.query
                .filter_by(user_profile_id=p.id)
                .order_by(MissingSkillsReport.applied_at.desc())
                .limit(20)
                .all()
            )
            print("  OK - {} missing skill reports".format(len(missing_skills_reports)))
        except Exception as e:
            print("  ERROR: {}".format(str(e)))
            traceback.print_exc()
        
        print("\nStep 11: Render template...")
        from flask import render_template
        html = render_template(
            "dashboard.html",
            user=user,
            p=p,
            runs=runs,
            total_submitted=total_submitted,
            api_token=api_token,
            submitted_jobs=submitted_jobs,
            failed_jobs=failed_jobs,
            failed_runs=failed_runs,
            generated_letters=generated_letters,
            missing_skills_reports=missing_skills_reports,
        )
        print("  OK - Template rendered ({} bytes)".format(len(html)))
        
        print("\n[SUCCESS] All dashboard components work!")
        
    except Exception as e:
        print("\n[ERROR] {}".format(str(e)))
        traceback.print_exc()
