LinkedIn Auto-Apply Bot (Local)

Quick start:
1) Create and activate your Python environment.
2) Install dependencies:
   pip install -r requirements.txt
   playwright install chromium
3) Create .env in this folder with:
   LINKEDIN_EMAIL=your_email
   LINKEDIN_PASSWORD=your_password
4) Validate local setup:
   python main.py --validate
5) Dry run (no submissions):
   python main.py --dry-run --limit 5
6) Live run:
   python main.py --limit 25
7) Resume interrupted run:
   python main.py --resume --limit 25

Windows Task Scheduler example (daily at 08:30, no user password prompt):
schtasks /Create /SC DAILY /TN "LinkedInAutoApply" /TR "cmd /c cd /d D:\cv_portofolio\linkedin_bot && D:\cv_portofolio\.venv\Scripts\python.exe main.py --headless --limit 25" /ST 08:30 /RU "SYSTEM" /RL HIGHEST /F

Notes:
- CAPTCHA/2FA cannot be bypassed automatically. Resolve challenge manually and rerun with --resume.
- External job applications are logged as manual_required in applied_jobs.json.
- The run limit caps processed jobs (submitted/manual/skipped/failed), not only successful submissions.
- Do not commit .env to source control.
- Priority queue is enabled by default: jobs discovered from LinkedIn notifications are processed before regular keyword/location search.
- To prioritize jobs from LinkedIn Gmail alerts, add full job URLs to priority_job_links.txt (one URL per line) in this folder.
