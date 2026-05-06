import sys, os
sys.path.insert(0, r"D:\cv_portofolio\webapp")
os.chdir(r"D:\cv_portofolio\webapp")

from app import app, ensure_schema_updates

with app.app_context():
    ensure_schema_updates()

app.run(host="0.0.0.0", port=5001, debug=False)
