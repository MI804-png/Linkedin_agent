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

Automatic Run and Watch scheduler (desktop-only):
1) Copy .scheduler.env.example to .scheduler.env and set:
   AUTOAPPLY_ACCOUNT_EMAIL=your local dashboard account email
   AUTOAPPLY_ACCOUNT_PASSWORD=your local dashboard account password
   Optional: AUTOAPPLY_ACCOUNT_USER_ID=1 if you prefer selecting the local user by id
   Optional: AUTOAPPLY_RUN_MODE=external_watch if you want the direct external-sites runner instead of LinkedIn Run and Watch
2) Keep auto-apply enabled in the local dashboard profile and set the scheduled UTC time there.
3) Validate the scheduler without triggering a run:
   python run_watch_scheduler.py --check
4) Windows install:
   powershell -ExecutionPolicy Bypass -File .\install_run_watch_scheduler_windows.ps1
5) macOS install:
   bash ./install_run_watch_scheduler_mac.sh

How it behaves:
- The scheduler starts when you log in on Windows or macOS.
- It checks the local dashboard schedule every minute.
- When the scheduled UTC minute matches, it logs into the local dashboard and triggers either Run and Watch or External Websites Watch, depending on AUTOAPPLY_RUN_MODE.
- The actual search filter "within this many days" comes from the selected dashboard profile (posted_days_ago).
- Optional immediate login-time run: set AUTOAPPLY_RUN_ON_LOGIN=1 in .scheduler.env.
- Important: profile apply_type=external_only still means LinkedIn jobs that leave LinkedIn for the company site. It is not the same as External Websites Watch, which starts from WeWorkRemotely, RemoteOK, EuropeRemoteJobs, and Jobicy.
