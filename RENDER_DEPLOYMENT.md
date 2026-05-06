# Deploy Daily Job Scheduler to Render - Step by Step

**Status**: ✅ All tests pass locally. Ready to deploy to Render.

## What You're Deploying

A **daily job application bot** that automatically runs on a schedule you define. 

- Runs at your chosen time (e.g., 8:30 AM UTC daily)
- Automatically applies to jobs on LinkedIn
- Tracks missing skills for each application
- Securely authenticated with Render Cron Job

---

## Deployment Steps

### Step 1: Generate Secret Key (5 seconds)

Run this to create a secure random key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Copy the output**, for example:
```
3X_k9F2w5q8r1t4y7u0i9o2p5a8s1d4f
```

---

### Step 2: Add Environment Variable to Render (2 minutes)

1. Go to **Render Dashboard** → Your service → **Environment**
2. Click **Add Environment Variable**
3. **Name**: `CRON_SECRET_KEY`
4. **Value**: Paste the key from Step 1
5. Click **Save** and wait for auto-deploy (watch the logs)

Expected log when done:
```
Deploy successful. Your service is live.
```

---

### Step 3: Create Render Cron Job (3 minutes)

1. In Render dashboard, click **Create** (top button)
2. Click **Cron Job**
3. Fill in:

   | Field | Value |
   |-------|-------|
   | **Name** | `job-bot-scheduler` |
   | **Runtime** | `Node` |
   | **Build Command** | (leave blank) |
   | **Start Command** | See below ⬇️ |
   | **Schedule** | `*/1 * * * *` |

4. **Start Command** - Replace `YOUR_RENDER_URL` with your actual URL:
   ```
   curl -X POST https://YOUR_RENDER_URL/api/cron/check_scheduled_jobs -H "Authorization: Bearer $CRON_SECRET_KEY"
   ```
   
   **Example**:
   ```
   curl -X POST https://my-job-bot-app.onrender.com/api/cron/check_scheduled_jobs -H "Authorization: Bearer $CRON_SECRET_KEY"
   ```

5. Click **Environment** → **Add Environment Variable**
   - **Name**: `CRON_SECRET_KEY`
   - **Value**: Paste the same key from Step 1

6. Click **Create Cron Job** ✓

---

### Step 4: Configure Your Schedule (2 minutes)

Connect to your Render PostgreSQL database and set your run time:

```sql
UPDATE user_profiles 
SET auto_apply_enabled = true,
    scheduled_run_hour = 8,           -- 8 AM UTC
    scheduled_run_minute = 30,        -- 30 minutes
    send_missing_skills = true
WHERE user_id = 1;
```

**Find your UTC time**:
- 8 AM CET = UTC 7
- 9 AM CET = UTC 8  
- 10 AM CET = UTC 9
- 6 PM CET = UTC 17

Check: https://www.timeanddate.com/worldclock/timezone/utc

---

### Step 5: Test It (5 minutes)

#### Test 1: Check Render Logs

1. Go to Render → Your Cron Job → **Logs**
2. Should see activity like:
   ```
   Starting Cron Job...
   (either "success" or auth error)
   ```

#### Test 2: Trigger Manually

```bash
curl -X POST https://YOUR_RENDER_URL/api/cron/check_scheduled_jobs \
  -H "Authorization: Bearer YOUR_SECRET_KEY"
```

You should get:
```json
{"status": "ok", "triggered_runs": 0}
```

#### Test 3: Wait for Scheduled Time

If you set run time to 8:30 AM UTC, wait until then. Check:
- Render Logs for: `Cron: Triggered bot run for user_id=1`
- Database for new BotRun entries:
  ```sql
  SELECT * FROM bot_runs ORDER BY created_at DESC LIMIT 1;
  ```

---

## Troubleshooting

### Problem: "Unauthorized" Error

**Cause**: Cron job doesn't have the secret key

**Fix**:
```bash
# 1. Check service environment variable is set:
curl https://YOUR_RENDER_URL/health

# 2. Check cron job environment:
# Go to Cron Job → Environment → Verify CRON_SECRET_KEY is there

# 3. Restart both:
# - Service: Click "Restart" in dashboard
# - Cron Job: Just toggle it off/on
```

### Problem: Jobs Not Triggering

**Check 1**: Is scheduler enabled?
```sql
SELECT auto_apply_enabled, scheduled_run_hour 
FROM user_profiles WHERE user_id = 1;
```
Should show `auto_apply_enabled = true`

**Check 2**: Is time in UTC?
```sql
-- If you want 9 AM CET (your local), use 8 (UTC)
UPDATE user_profiles 
SET scheduled_run_hour = 8 
WHERE user_id = 1;
```

**Check 3**: Is cron job running?
- Go to Cron Job → Logs
- Should see execution every minute

### Problem: Too Many Runs

**Cause**: Minute matches multiple times per day

**Fix**: Use a specific minute that won't repeat:
```sql
UPDATE user_profiles 
SET scheduled_run_hour = 8,
    scheduled_run_minute = 17      -- Use an odd minute
WHERE user_id = 1;
```

The system includes a 1-hour debounce to prevent duplicate runs even if called multiple times.

---

## Monitor Your Scheduler

### View Recent Runs

```sql
SELECT user_id, status, submitted, skipped, failures, created_at 
FROM bot_runs
WHERE created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC
LIMIT 10;
```

### Check Scheduled Users

```sql
SELECT user_id, 
       auto_apply_enabled,
       scheduled_run_hour::text || ':' || 
       LPAD(scheduled_run_minute::text, 2, '0') as "Scheduled Time",
       last_scheduled_run
FROM user_profiles
WHERE auto_apply_enabled = true;
```

### View Cron Logs (Render)

1. Dashboard → Your Cron Job → **Logs**
2. Look for:
   - `SUCCESS` = Endpoint called successfully
   - `ERROR` = Auth failed or timeout
   - `Cron: Triggered...` = Job was triggered

---

## Advanced: Multiple Users

If you have multiple users, each can have their own schedule:

```sql
-- User 1: 8:30 AM UTC
UPDATE user_profiles 
SET auto_apply_enabled = true,
    scheduled_run_hour = 8,
    scheduled_run_minute = 30
WHERE user_id = 1;

-- User 2: 3 PM UTC
UPDATE user_profiles 
SET auto_apply_enabled = true,
    scheduled_run_hour = 15,
    scheduled_run_minute = 0
WHERE user_id = 2;
```

The cron job checks all users every minute and triggers whoever matches.

---

## Performance Notes

- Cron job calls endpoint every minute → ~1440 calls/day
- Each call takes <1 second
- Minimal CPU/memory impact
- Safe to run continuously

---

## Security Checklist

- ✅ Secret key is random (32+ characters)
- ✅ Secret key stored in Render environment (not in code)
- ✅ Cron endpoint requires Bearer token authentication
- ✅ Endpoint logs all triggers for auditing
- ✅ Different key per deployment

---

## Next Steps After Deployment

1. **Wait for first scheduled run** and verify it works
2. **Check logs** to confirm bot ran successfully  
3. **Add missing skills notifications** (optional dashboard feature)
4. **Set up Render alerts** for failures

---

## Quick Reference

| Task | Command/Location |
|------|-----------------|
| Generate key | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| Set schedule | `UPDATE user_profiles SET scheduled_run_hour=8, ...` |
| Test endpoint | `curl -X POST https://YOUR_URL/api/cron/check_scheduled_jobs ...` |
| View logs | Render → Cron Job → Logs |
| Check runs | `SELECT * FROM bot_runs ORDER BY created_at DESC;` |
| Disable scheduler | `UPDATE user_profiles SET auto_apply_enabled = false;` |

---

## Support

**Issue**: Check [SCHEDULER_SETUP_RENDER.md](SCHEDULER_SETUP_RENDER.md) for detailed troubleshooting

**Quick test locally**: `.venv\Scripts\python.exe test_scheduler_local.py`

**All tests passed?** ✅ You're ready to deploy!

---

**Deployed and working?** 🎉 

Your LinkedIn bot will now automatically apply to jobs every day at your scheduled time!
