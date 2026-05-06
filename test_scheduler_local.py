#!/usr/bin/env python3
"""
Test script: Verify scheduler is properly configured locally.
Run this before deploying to Render to ensure everything works.

Usage:
    python test_scheduler_local.py
"""
import sys
import os
from datetime import datetime, timedelta

# Add webapp to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))

def test_imports():
    """Test 1: Verify all imports work"""
    print("\n[TEST 1] Checking imports...")
    try:
        from app import app, db, UserProfile, BotRun, MissingSkillsReport
        print("  ✓ Flask app imports successful")
        print("  ✓ Database models found")
        return app, db, UserProfile, BotRun, MissingSkillsReport
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        sys.exit(1)

def test_database_connection(app, db):
    """Test 2: Verify database connection"""
    print("\n[TEST 2] Testing database connection...")
    try:
        with app.app_context():
            result = db.session.execute(db.text("SELECT 1"))
            result.fetchone()
            print("  ✓ Database connection successful")
            return True
    except Exception as e:
        print(f"  ✗ Database connection failed: {e}")
        return False

def test_schema(app, db, UserProfile):
    """Test 3: Verify scheduler columns exist"""
    print("\n[TEST 3] Checking scheduler database schema...")
    try:
        with app.app_context():
            # Create tables if they don't exist
            db.create_all()
            
            # Check columns
            inspector = db.inspect(db.engine)
            columns = {col['name'] for col in inspector.get_columns('user_profiles')}
            
            required_cols = {
                'scheduled_run_hour',
                'scheduled_run_minute', 
                'auto_apply_enabled',
                'last_scheduled_run',
                'send_missing_skills'
            }
            
            missing = required_cols - columns
            if missing:
                print(f"  ✗ Missing columns: {missing}")
                print("\n  Fix: Run migrations or check app.py ensure_schema_updates()")
                return False
            
            print(f"  ✓ All scheduler columns present: {required_cols}")
            return True
    except Exception as e:
        print(f"  ✗ Schema check failed: {e}")
        return False

def test_user_profiles(app, UserProfile):
    """Test 4: Check if users exist and are configured"""
    print("\n[TEST 4] Checking user profiles...")
    try:
        with app.app_context():
            profiles = UserProfile.query.all()
            if not profiles:
                print("  ⚠ No user profiles found (this is OK for fresh install)")
                return True
            
            enabled = UserProfile.query.filter_by(auto_apply_enabled=True).count()
            print(f"  ✓ Found {len(profiles)} total users")
            print(f"  ✓ {enabled} users have scheduler enabled")
            
            if enabled > 0:
                user = UserProfile.query.filter_by(auto_apply_enabled=True).first()
                print(f"\n  Sample scheduled user:")
                print(f"    - User ID: {user.user_id}")
                print(f"    - Run Time: {user.scheduled_run_hour:02d}:{user.scheduled_run_minute:02d} UTC")
                print(f"    - Last Run: {user.last_scheduled_run}")
            
            return True
    except Exception as e:
        print(f"  ✗ User profile check failed: {e}")
        return False

def test_cron_endpoint(app):
    """Test 5: Test the cron endpoint locally"""
    print("\n[TEST 5] Testing cron endpoint...")
    try:
        with app.app_context():
            # Test without auth (should fail)
            client = app.test_client()
            response = client.post('/api/cron/check_scheduled_jobs')
            
            if response.status_code == 401:
                print("  ✓ Endpoint correctly requires authentication")
            else:
                print(f"  ⚠ Expected 401 Unauthorized, got {response.status_code}")
            
            # Test with default key (should work in dev)
            response = client.post(
                '/api/cron/check_scheduled_jobs',
                headers={'Authorization': 'Bearer default-insecure-key-change-me'}
            )
            
            if response.status_code == 200:
                data = response.get_json()
                print(f"  ✓ Endpoint works (triggered {data.get('triggered_runs', 0)} runs)")
                return True
            else:
                print(f"  ✗ Endpoint returned {response.status_code}: {response.data}")
                return False
    except Exception as e:
        print(f"  ✗ Cron endpoint test failed: {e}")
        return False

def test_time_matching(app, db, UserProfile):
    """Test 6: Simulate time-based matching"""
    print("\n[TEST 6] Testing scheduler time matching logic...")
    try:
        with app.app_context():
            now = datetime.utcnow()
            print(f"  Current UTC time: {now.hour:02d}:{now.minute:02d}")
            
            # Check if any users match current time
            profiles = UserProfile.query.filter_by(auto_apply_enabled=True).all()
            
            if not profiles:
                print("  ⚠ No enabled users (create one to test)")
                return True
            
            matches = [
                p for p in profiles 
                if p.scheduled_run_hour == now.hour and 
                   p.scheduled_run_minute == now.minute
            ]
            
            if matches:
                print(f"  ✓ Found {len(matches)} user(s) matching current time!")
                print(f"  ✓ These would trigger NOW if running via cron")
            else:
                next_user = profiles[0]
                time_str = f"{next_user.scheduled_run_hour:02d}:{next_user.scheduled_run_minute:02d}"
                print(f"  ℹ No users match current time")
                print(f"    Next scheduled run: {time_str} UTC for user_id={next_user.user_id}")
                print(f"    To test now, update: scheduled_run_hour={now.hour}, scheduled_run_minute={now.minute}")
            
            return True
    except Exception as e:
        print(f"  ✗ Time matching test failed: {e}")
        return False

def test_bot_runner(app):
    """Test 7: Verify bot_runner is available"""
    print("\n[TEST 7] Checking bot_runner integration...")
    try:
        with app.app_context():
            from bot_runner import run_for_user_async
            print("  ✓ bot_runner.run_for_user_async() is available")
            print("  ✓ Cron endpoint can trigger bot runs")
            return True
    except Exception as e:
        print(f"  ✗ bot_runner test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("SCHEDULER LOCAL TEST")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Imports
    app, db, UserProfile, BotRun, MissingSkillsReport = test_imports()
    
    # Test 2: Database connection
    results['db_connection'] = test_database_connection(app, db)
    
    # Test 3: Schema
    results['schema'] = test_schema(app, db, UserProfile)
    
    # Test 4: User profiles
    results['users'] = test_user_profiles(app, UserProfile)
    
    # Test 5: Cron endpoint
    results['cron_endpoint'] = test_cron_endpoint(app)
    
    # Test 6: Time matching
    results['time_matching'] = test_time_matching(app, db, UserProfile)
    
    # Test 7: Bot runner
    results['bot_runner'] = test_bot_runner(app)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {test}")
    
    print("=" * 60)
    print(f"Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Ready to deploy to Render.\n")
        print("Next steps:")
        print("1. Generate CRON_SECRET_KEY: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
        print("2. Add to Render environment variables")
        print("3. Create Render Cron Job to call /api/cron/check_scheduled_jobs")
        print("4. Configure user schedule in database")
        print("\nSee SCHEDULER_QUICK_START.md for details")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Fix issues before deploying.\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
