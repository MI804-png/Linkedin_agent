#!/usr/bin/env python
"""Diagnose profile issue."""
import sys
sys.path.insert(0, 'webapp')

from app import app, db, User, UserProfile

with app.app_context():
    users = User.query.all()
    
    if not users:
        print("ERROR: No users in database")
        sys.exit(1)
    
    user = users[0]
    print("User: {}".format(user.email))
    print("User ID: {}".format(user.id))
    
    p = UserProfile.query.filter_by(user_id=user.id).first()
    
    if not p:
        print("\nERROR: No profile found! Creating one...")
        p = UserProfile(user_id=user.id)
        db.session.add(p)
        db.session.commit()
        print("Profile created.")
    
    print("\n=== Profile Data ===")
    print("Profile ID: {}".format(p.id))
    print("CV filename: {}".format(p.cv_filename if p.cv_filename else "MISSING"))
    print("LinkedIn email: {}".format(p.linkedin_email if p.linkedin_email else "MISSING"))
    print("LinkedIn password: {}".format("SET" if p.linkedin_password_enc else "MISSING"))
    
    # Check what's missing
    print("\n=== Check ===")
    if not p.cv_filename:
        print("[!] MISSING: CV file upload")
    if not p.linkedin_email or not p.linkedin_password_enc:
        print("[!] MISSING: LinkedIn credentials")
    
    if p.cv_filename and p.linkedin_email and p.linkedin_password_enc:
        print("[OK] All required fields present!")
    
    # Show what needs to be fixed
    if not p.cv_filename or not p.linkedin_email or not p.linkedin_password_enc:
        print("\n=== To Fix ===")
        print("1. Open http://localhost:5000/profile")
        print("2. Upload your CV file")
        print("3. Enter your LinkedIn email and password")
        print("4. Click Save")
        print("5. Then try Dashboard again")
