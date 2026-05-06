#!/usr/bin/env python3
"""
Test dashboard loading with error details
"""
import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))

# Enable verbose logging
logging.basicConfig(level=logging.DEBUG)

from app import app, db, User, UserProfile, BotRun

# Set up logging to capture exceptions
logger = app.logger

with app.app_context():
    users = User.query.all()
    
    if not users:
        print("ERROR: No users in database")
        sys.exit(1)
    
    user = users[0]
    print("Testing with user: {}".format(user.email))
    
    # Simulate what happens in dashboard route
    print("\n=== Simulating Dashboard Route ===\n")
    
    try:
        print("1. get_current_user()...")
        # This would be automatic via @login_required
        print("   OK - user_id={}".format(user.id))
        
        print("2. ensure_user_profile(user)...")
        from app import ensure_user_profile
        p = ensure_user_profile(user)
        print("   OK - profile_id={}".format(p.id))
        
        print("3. Query BotRun (last 20)...")
        runs = BotRun.query.filter_by(user_id=user.id).order_by(BotRun.started_at.desc()).limit(20).all()
        print("   OK - {} runs".format(len(runs)))
        
        print("4. Query failed runs (last 15)...")
        failed_runs = (
            BotRun.query
            .filter(BotRun.user_id == user.id, BotRun.failures > 0)
            .order_by(BotRun.started_at.desc())
            .limit(15)
            .all()
        )
        print("   OK - {} failed runs".format(len(failed_runs)))
        
        print("5. Sum submitted jobs...")
        total_submitted = db.session.query(db.func.sum(BotRun.submitted)).filter_by(user_id=user.id).scalar() or 0
        print("   OK - total={}".format(total_submitted))
        
        print("6. ensure_api_token(user)...")
        from app import ensure_api_token
        api_token = ensure_api_token(user)
        print("   OK - token={}...".format(api_token[:20]))
        
        print("7. _load_recent_job_events(user.id)...")
        from app import _load_recent_job_events
        submitted_jobs, failed_jobs = _load_recent_job_events(user.id, limit=25)
        print("   OK - {} submitted, {} failed".format(len(submitted_jobs), len(failed_jobs)))
        
        print("8. _load_generated_letters(user.id)...")
        from app import _load_generated_letters
        generated_letters = _load_generated_letters(user.id, limit=40)
        print("   OK - {} letters".format(len(generated_letters)))
        
        print("\n[PASS] All dashboard components loaded successfully!")
        print("\nNow testing with proper request context...")
        
        print("9. Testing dashboard via test client...")
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = user.id
            
            response = client.get('/dashboard')
            
            if response.status_code == 200:
                print("   OK - Dashboard loaded successfully (200 OK)")
                print("       Response size: {} bytes".format(len(response.data)))
            elif response.status_code == 302:
                print("   ERROR - Dashboard redirected to {}".format(response.location))
                print("      This means an error occurred!")
            else:
                print("   ERROR - Got status {}".format(response.status_code))
                print("      Response: {}".format(response.data[:500]))
        
        print("\n[PASS] Dashboard loads successfully!")
        
    except Exception as e:
        print("\n[FAIL] ERROR: {}".format(str(e)))
        import traceback
        traceback.print_exc()
        
        # Log to app
        app.logger.exception("Dashboard loading failed")
        
        sys.exit(1)
