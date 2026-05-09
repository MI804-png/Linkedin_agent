import sqlite3
db = "d:/cv_portofolio/webapp/app.db"
conn = sqlite3.connect(db)
cols_info = conn.execute("PRAGMA table_info(bot_runs)").fetchall()
print("Columns:", cols_info)
rows = conn.execute("SELECT * FROM bot_runs ORDER BY rowid DESC LIMIT 2").fetchall()
for r in rows:
    print(r)
conn.close()

