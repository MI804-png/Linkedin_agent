# Quick Start: Daily Scheduler on Render

## ⚡ 5-Minute Setup

### 1. Generate Secret Key
```bash
python -c "import secrets; print('CRON_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

### 2. Add to Render Environment
- Dashboard → Your Service → Environment
- Add: `CRON_SECRET_KEY=your-key-from-step-1`
- Click Save and redeploy

### 3. Create Render Cron Job
- Click **Create** → **Cron Job**
- **Name**: `job-bot-scheduler`
- **Start Command**: 
  ```
  curl -X POST https://YOUR_RENDER_URL/api/cron/check_scheduled_jobs \
    -H "Authorization: Bearer $CRON_SECRET_KEY"
  ```
- **Schedule**: `*/1 * * * *` (every minute)
- Add same `CRON_SECRET_KEY` to cron job's environment

### 4. Configure User Schedule (Database)
```sql
UPDATE user_profiles 
SET auto_apply_enabled = true,
    scheduled_run_hour = 8,          -- 8 AM UTC
    scheduled_run_minute = 0,
    send_missing_skills = true
WHERE user_id = YOUR_USER_ID;
```

### 5. Test It
```sql
-- Check if configured
SELECT user_id, scheduled_run_hour, auto_apply_enabled 
FROM user_profiles;

-- Check recent runs
SELECT user_id, status, created_at 
FROM bot_runs 
ORDER BY created_at DESC LIMIT 5;
```

## UTC Time Conversion

| Local Time | UTC Hour | UTC Time |
|-----------|----------|----------|
| 8 AM CET  | 7        | 07:00    |
| 9 AM CET  | 8        | 08:00    |
| 10 AM CET | 9        | 09:00    |
| 6 PM CET  | 17       | 17:00    |

**Find your offset**: https://www.timeanddate.com/worldclock/timezone/utc

## How to Monitor

**Via Render Logs**:
```
Dashboard → Logs → Search for "Cron:"
```

Look for:
```
Cron: Triggered bot run for user_id=1, run_id=123
```

**Via Database**:
```sql
SELECT * FROM bot_runs 
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

## Common Issues

| Issue | Solution |
|-------|----------|
| "Unauthorized" | Check `CRON_SECRET_KEY` is set in both service AND cron job environment |
| Jobs not running | Verify `auto_apply_enabled = true` and time matches current UTC |
| Too many runs | Don't set `scheduled_run_minute` to current minute (use a different minute) |
| LinkedIn errors | Check credentials are valid and 2FA isn't blocking |

## Disable Scheduler

```sql
UPDATE user_profiles 
SET auto_apply_enabled = false
WHERE user_id = YOUR_USER_ID;
```

## Full Guide

See **SCHEDULER_SETUP_RENDER.md** for detailed troubleshooting and advanced options.
