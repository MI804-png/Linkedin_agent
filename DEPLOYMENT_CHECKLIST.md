# Daily Scheduler Deployment Checklist ✅

Use this checklist to deploy the daily job scheduler to Render.

---

## ✅ Pre-Deployment (Local)

- [ ] Run local tests: `.venv\Scripts\python.exe test_scheduler_local.py`
- [ ] Verify all 6 tests pass
- [ ] Check database has scheduler columns (test should verify)
- [ ] Verify LinkedIn credentials are correct
- [ ] Backup current Render database (optional but recommended)

**Expected Result:**
```
✓ PASS   db_connection
✓ PASS   schema
✓ PASS   users
✓ PASS   cron_endpoint
✓ PASS   time_matching
✓ PASS   bot_runner
Result: 6/6 tests passed
```

---

## ✅ Generate Secret Key

- [ ] Run: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] Copy the output (e.g., `3X_k9F2w5q8r1t4y7u0i9o2p5a8s1d4f`)
- [ ] Save it somewhere safe (you'll need it 3 times)

**Do NOT:** Commit to git, share publicly, or store in code

---

## ✅ Step 1: Update Render Service Environment

- [ ] Log in to Render Dashboard
- [ ] Go to your Flask service
- [ ] Click **Environment** in sidebar
- [ ] Click **Add Environment Variable**
- [ ] **Name**: `CRON_SECRET_KEY`
- [ ] **Value**: Paste your secret key
- [ ] Click **Save**
- [ ] Wait for auto-deployment (check **Logs** tab)
- [ ] Verify deployment says "Deploy successful"

**Time**: ~2 minutes

---

## ✅ Step 2: Create Render Cron Job

- [ ] Click **Create** button (top right)
- [ ] Select **Cron Job**

### Fill in these fields:

- [ ] **Name**: `job-bot-scheduler`
- [ ] **Runtime**: Select `Node` from dropdown
- [ ] **Build Command**: Leave blank
- [ ] **Start Command**: 
  
  ```
  curl -X POST https://YOUR_RENDER_URL/api/cron/check_scheduled_jobs \
    -H "Authorization: Bearer $CRON_SECRET_KEY"
  ```
  
  (Replace `YOUR_RENDER_URL` with your actual URL, e.g., `https://my-job-bot.onrender.com`)

- [ ] **Schedule**: `*/1 * * * *` (every minute)

### Add Environment:

- [ ] Click **Environment** section
- [ ] Click **Add Variable**
- [ ] **Name**: `CRON_SECRET_KEY`
- [ ] **Value**: Paste your secret key (same as before)

### Create it:

- [ ] Click **Create Cron Job**
- [ ] Wait for creation (should be instant)
- [ ] See it listed in Render dashboard

**Time**: ~3 minutes

---

## ✅ Step 3: Configure User Schedule

### Option A: Via Database (Recommended)

- [ ] Connect to your Render PostgreSQL database
- [ ] Run this SQL query:

  ```sql
  UPDATE user_profiles 
  SET auto_apply_enabled = true,
      scheduled_run_hour = 8,           -- Change to your preferred hour (UTC)
      scheduled_run_minute = 30,        -- Change to your preferred minute
      send_missing_skills = true
  WHERE user_id = 1;                    -- Change user_id if needed
  ```

- [ ] Verify it worked:
  ```sql
  SELECT user_id, scheduled_run_hour, scheduled_run_minute, 
         auto_apply_enabled, last_scheduled_run
  FROM user_profiles
  WHERE user_id = 1;
  ```

### Find your UTC time:

- [ ] Visit https://www.timeanddate.com/worldclock/timezone/utc
- [ ] Find your local timezone
- [ ] Calculate UTC hour:
  - 8 AM CET = 7 UTC
  - 9 AM CET = 8 UTC
  - 10 AM CET = 9 UTC
  - 6 PM CET = 17 UTC

**Time**: ~5 minutes

---

## ✅ Step 4: Test the Cron Endpoint

### Test with cURL:

- [ ] Open terminal/PowerShell
- [ ] Run:
  
  ```bash
  curl -X POST https://YOUR_RENDER_URL/api/cron/check_scheduled_jobs \
    -H "Authorization: Bearer YOUR_SECRET_KEY"
  ```

- [ ] Verify response is:
  ```json
  {"status": "ok", "triggered_runs": 0}
  ```

### If you get "Unauthorized":

- [ ] Check `CRON_SECRET_KEY` is set in service environment
- [ ] Check cron job has same key in environment
- [ ] Restart both (service and cron job)
- [ ] Try again

**Time**: ~2 minutes

---

## ✅ Step 5: Monitor First Run

### Option A: Wait for Scheduled Time

- [ ] Note when your scheduled time is (e.g., 08:30 UTC)
- [ ] Wait until that time
- [ ] Check Render Logs:
  - Go to Cron Job → **Logs**
  - Look for execution around your scheduled time
  - Should see success message

- [ ] Check service logs:
  - Go to Service → **Logs**
  - Search for "Cron: Triggered" or "Starting bot"
  - Should see bot initialization

- [ ] Check database:
  ```sql
  SELECT * FROM bot_runs 
  ORDER BY created_at DESC 
  LIMIT 1;
  ```
  Should show new run with your user_id

**Time**: Depends on your scheduled time (wait until it runs)

### Option B: Manually Trigger Now (Testing)

- [ ] Update your schedule to current UTC time:
  ```sql
  SELECT NOW() AT TIME ZONE 'UTC';
  -- Example output: 2026-05-04 19:05:00+00
  -- So use hour=19, minute=5
  
  UPDATE user_profiles 
  SET scheduled_run_hour = 19,
      scheduled_run_minute = 5
  WHERE user_id = 1;
  ```

- [ ] Call endpoint:
  ```bash
  curl -X POST https://YOUR_RENDER_URL/api/cron/check_scheduled_jobs \
    -H "Authorization: Bearer YOUR_SECRET_KEY"
  ```

- [ ] Check response: `{"triggered_runs": 1}`

- [ ] Watch service logs for bot startup

**Time**: ~5 minutes (to see results)

---

## ✅ Verify Everything Works

After your first scheduled run:

- [ ] Check **Render Logs** → Cron Job
  - Should see execution entry
  - Status: success or error

- [ ] Check **Render Logs** → Service
  - Search for "Cron: Triggered bot run"
  - Should see bot initialization messages

- [ ] Check **BotRun table**
  ```sql
  SELECT user_id, status, submitted, skipped, failures, created_at 
  FROM bot_runs
  WHERE created_at > NOW() - INTERVAL '24 hours'
  ORDER BY created_at DESC
  LIMIT 1;
  ```
  Should show your recent run with status "done" or "running"

- [ ] Check **MissingSkillsReport table**
  ```sql
  SELECT job_title, company_name, 
         json_array_length(missing_skills::json) as num_missing
  FROM missing_skills_reports
  WHERE created_at > NOW() - INTERVAL '24 hours'
  LIMIT 5;
  ```
  Should show missing skills for applied jobs

- [ ] LinkedIn bot should have applied to jobs
  - Check LinkedIn applications in profile

**Result**: ✅ Daily scheduler is working!

---

## ✅ Post-Deployment

- [ ] Document your scheduled time (for reference)
- [ ] Set up monitoring/alerts (optional)
- [ ] Share status with team if applicable
- [ ] Plan for skill report notifications (future enhancement)

---

## 🔄 Troubleshooting

### Problem: "Unauthorized" error

- [ ] Verify `CRON_SECRET_KEY` is in service environment
- [ ] Verify `CRON_SECRET_KEY` is in cron job environment
- [ ] Check they're both the same value
- [ ] Restart service and cron job
- [ ] Try curl command again

### Problem: Cron job shows error in logs

- [ ] Check curl command syntax (no typos)
- [ ] Check URL is correct for your service
- [ ] Check Bearer token format: `Bearer YOUR_KEY` (not just `YOUR_KEY`)
- [ ] Try simpler test:
  ```bash
  curl https://YOUR_RENDER_URL/health
  ```
  Should return 200 OK

### Problem: No bot run created

- [ ] Check `auto_apply_enabled = true` in database
- [ ] Check scheduled time matches current UTC time
- [ ] Verify time zone is UTC (not your local time)
- [ ] Check logs for errors

### Problem: Bot runs but doesn't apply

- [ ] Check LinkedIn credentials are correct
- [ ] Check LinkedIn 2FA isn't blocking (disable temporarily to test)
- [ ] Check job search keywords are valid
- [ ] Check bot logs in service output

### Problem: Runs at wrong time

- [ ] Time is always UTC, not your local timezone
- [ ] Calculate correct UTC hour: use https://www.timeanddate.com/worldclock/timezone/utc
- [ ] Update database:
  ```sql
  UPDATE user_profiles 
  SET scheduled_run_hour = YOUR_UTC_HOUR
  WHERE user_id = 1;
  ```

---

## ✅ Final Verification Checklist

- [ ] Cron job exists in Render dashboard
- [ ] Cron job has `CRON_SECRET_KEY` in environment
- [ ] Service has `CRON_SECRET_KEY` in environment
- [ ] User profile has `auto_apply_enabled = true`
- [ ] User profile has valid `scheduled_run_hour` and `scheduled_run_minute`
- [ ] Curl test returns `{"status": "ok"}`
- [ ] Logs show bot ran (or waiting for scheduled time)
- [ ] BotRun record created in database
- [ ] LinkedIn applications visible in profile

**If all ✅**: You're done! Your daily scheduler is live! 🎉

---

## 📊 Monitoring Going Forward

### Daily Check:

```sql
SELECT DATE(created_at) as date, COUNT(*) as runs, 
       SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as successful
FROM bot_runs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

### Weekly Report:

```sql
SELECT user_id, COUNT(*) as runs, 
       SUM(submitted) as total_applied,
       SUM(skipped) as total_skipped,
       SUM(failures) as total_failed
FROM bot_runs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY user_id;
```

---

## 📝 Documentation

For detailed information, see:

- **RENDER_DEPLOYMENT.md** - Step-by-step with details
- **SCHEDULER_QUICK_START.md** - Quick reference
- **SCHEDULER_SETUP_RENDER.md** - Full technical guide
- **SCHEDULER_ARCHITECTURE.md** - How it works
- **test_scheduler_local.py** - Validation script

---

**Status**: Ready for deployment ✅

**Questions?** Check the docs or run `test_scheduler_local.py` to diagnose issues.

**Deployed?** Congratulations! 🚀 Your bot runs automatically every day!
