import sqlite3

db = sqlite3.connect("d:/cv_portofolio/webapp/app.db")
cur = db.cursor()
existing = {row[1] for row in cur.execute("PRAGMA table_info(user_profiles)")}

new_cols = [
    ("nationality", "TEXT DEFAULT ''"),
    ("is_eu_citizen", "INTEGER DEFAULT 0"),
    ("willing_to_relocate", "INTEGER DEFAULT 0"),
    ("willing_to_work_onsite", "INTEGER DEFAULT 0"),
    ("willing_to_work_remote", "INTEGER DEFAULT 1"),
    ("current_job_title", "TEXT DEFAULT ''"),
    ("years_management_experience", "TEXT DEFAULT '0'"),
    ("highest_education", "TEXT DEFAULT ''"),
    ("field_of_study", "TEXT DEFAULT ''"),
    ("english_proficiency", "TEXT DEFAULT 'Professional'"),
    ("languages_spoken", "TEXT DEFAULT ''"),
    ("has_drivers_license", "INTEGER DEFAULT 0"),
    ("drivers_license_category", "TEXT DEFAULT ''"),
    ("linkedin_url", "TEXT DEFAULT ''"),
    ("github_url", "TEXT DEFAULT ''"),
    ("portfolio_url", "TEXT DEFAULT ''"),
    ("gender", "TEXT DEFAULT ''"),
    ("has_disability", "INTEGER DEFAULT 0"),
    ("veteran_status", "TEXT DEFAULT 'No'"),
]

added = []
for col, typedef in new_cols:
    if col not in existing:
        cur.execute(f"ALTER TABLE user_profiles ADD COLUMN {col} {typedef}")
        added.append(col)

db.commit()
db.close()
print("Added:", added if added else "nothing new (all columns already exist)")
