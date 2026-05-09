import sys, os
sys.path.insert(0, r'd:\cv_portofolio\webapp')
os.chdir(r'd:\cv_portofolio\webapp')

from app import app, db
from models import User, UserProfile

with app.app_context():
    user = User.query.filter_by(email='mikhael@autoapply.com').first()
    if not user:
        print('User not found')
        sys.exit(1)
    
    p = UserProfile.query.filter_by(user_id=user.id).first()
    if not p:
        print('Profile not found, creating...')
        p = UserProfile(user_id=user.id)
        db.session.add(p)
    
    print(f'Before: cv_filename={p.cv_filename!r}, li_email={p.linkedin_email!r}')
    
    if not p.full_name:
        p.full_name = 'Mikhael Nabil Salama Rezk'
    if not p.linkedin_email:
        p.linkedin_email = 'mikhael@autoapply.com'
    if not p.linkedin_password_enc:
        p.set_linkedin_password('Thesis2026!')
    if not p.cv_filename:
        p.cv_filename = 'placeholder_cv.pdf'
    
    db.session.commit()
    print('Profile updated OK')
    print(f'After: cv_filename={p.cv_filename!r}, li_email={p.linkedin_email!r}')
