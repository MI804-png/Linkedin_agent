#!/usr/bin/env python3
"""Debug dashboard loading issue"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))

from app import app, db, User, UserProfile
from flask import session

# Create app context
with app.app_context():
    # Check if user exists
    users = User.query.all()
    print(f"Total users in DB: {len(users)}")
    
    if users:
        user = users[0]
        print(f"\nUser: {user.email}")
        print(f"User ID: {user.id}")
        
        # Check if profile exists
        try:
            profile = user.profile
            if profile:
                print(f"Profile exists: {profile.id}")
                print(f"  - Full name: {profile.full_name}")
                print(f"  - LinkedIn email: {profile.linkedin_email}")
                print(f"  - CV uploaded: {bool(profile.cv_filename)}")
            else:
                print("Profile: None")
        except Exception as e:
            print(f"Error accessing profile: {e}")
        
        # Try to replicate dashboard loading
        print("\n--- Testing dashboard load ---")
        try:
            from bot_runner import build_config_for_user
            config = build_config_for_user(user.id)
            print(f"✓ Config built successfully")
        except Exception as e:
            print(f"✗ Config build failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test loading BotRun
        print("\n--- Testing BotRun query ---")
        try:
            from app import BotRun
            runs = BotRun.query.filter_by(user_id=user.id).order_by(BotRun.started_at.desc()).limit(20).all()
            print(f"✓ BotRun query successful: {len(runs)} runs")
        except Exception as e:
            print(f"✗ BotRun query failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test loading job events
        print("\n--- Testing job events load ---")
        try:
            from app import _load_recent_job_events
            submitted, failed = _load_recent_job_events(user.id, limit=25)
            print(f"✓ Job events loaded: {len(submitted)} submitted, {len(failed)} failed")
        except Exception as e:
            print(f"✗ Job events load failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test loading generated letters
        print("\n--- Testing generated letters load ---")
        try:
            from app import _load_generated_letters
            letters = _load_generated_letters(user.id, limit=40)
            print(f"✓ Generated letters loaded: {len(letters)} letters")
        except Exception as e:
            print(f"✗ Generated letters load failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test ensure_api_token
        print("\n--- Testing API token ---")
        try:
            from app import ensure_api_token
            token = ensure_api_token(user)
            print(f"✓ API token generated: {token[:20]}...")
        except Exception as e:
            print(f"✗ API token failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test rendering dashboard
        print("\n--- Testing dashboard render ---")
        try:
            with app.test_client() as client:
                # Login
                with client.session_transaction() as sess:
                    sess['user_id'] = user.id
                
                # Try dashboard
                response = client.get('/dashboard')
                if response.status_code == 200:
                    print(f"✓ Dashboard loaded successfully")
                elif response.status_code == 302:
                    print(f"✗ Dashboard redirected (likely to /profile)")
                    print(f"  Location: {response.location}")
                else:
                    print(f"✗ Dashboard returned {response.status_code}")
                    print(f"  Response: {response.data[:200]}")
        except Exception as e:
            print(f"✗ Dashboard render failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("No users in database. Create a user first via signup.")
