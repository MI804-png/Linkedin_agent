# Daily Job Application Scheduler for Render

This guide walks you through setting up automated daily job applications on Render with a secure scheduler.

## Overview

The system works by:
1. **Cron Endpoint** (`/api/cron/check_scheduled_jobs`): Checks which users have scheduled runs at current time
2. **Render Cron Job**: Calls the endpoint every minute
3. **Per-User Schedule**: Each user sets their preferred run time (e.g., 8:00 AM daily)
4. **Debouncing**: Prevents duplicate runs within 1 hour of last execution

## Prerequisites

- ✅ Flask webapp deployed to Render
- ✅ PostgreSQL database on Render
- ✅ User profiles in database with `auto_apply_enabled = True`

## Step 1: Set Environment Variables on Render

1. Go to your Render service dashboard
2. Click **Environment** in the sidebar
3. Add these environment variables:

```
CRON_SECRET_KEY=your-super-secret-cron-key-12345
```

**Important**: Use a strong, random key. Example:
```bash
# Generate on your local machine
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Output: Example output might be: Tn_eK9-1q5w8r2t3y4u5i6o7p8a9s0d1
```

4. Click **Save** and wait for deployment

## Step 2: Create a Render Cron Job

### Option A: Using Render's Built-in Cron (Recommended)

1. In Render dashboard, go to **Create** → **Cron Job**
2. Fill in:
   - **Name**: `job-bot-scheduler`
   - **Runtime**: `Node`
   - **Build Command**: (leave empty)
   - **Start Command**: `curl -X POST https://your-service.onrender.com/api/cron/check_scheduled_jobs -H "Authorization: Bearer $CRON_SECRET_KEY"`
   - **Schedule**: `*/1 * * * *` (every minute)

3. Add environment variable:
   - **CRON_SECRET_KEY**: (copy from your service's environment)

4. Click **Create Cron Job**

### Option B: Using External Service (Alternative)

If Render Cron isn't available, use **EasyCron**:

1. Go to https://www.easycron.com
2. Create new cron job:
   - **URL**: `https://your-service.onrender.com/api/cron/check_scheduled_jobs`
   - **HTTP Method**: `POST`
   - **Authentication**: Add custom header:
     - Header: `Authorization`
     - Value: `Bearer YOUR_CRON_SECRET_KEY`
   - **Schedule**: Every minute (`*/1 * * * *`)

## Step 3: Configure User Schedule

Users set their preferred run time through the webapp dashboard:

### Via Dashboard UI (Coming Soon)
```
Profile → Bot Settings → Schedule
- Enabled: ✓
- Run Time: 08:00 (8 AM UTC)
- Send Missing Skills Reports: ✓
```

### Via Database (Manual Setup)

Connect to your PostgreSQL database:

```sql
UPDATE user_profiles 
SET auto_apply_enabled = true,
    scheduled_run_hour = 8,           -- 8 AM UTC
    scheduled_run_minute = 0,
    send_missing_skills = true
WHERE user_id = YOUR_USER_ID;
```

**Time Reference** (UTC):
- `0` = Midnight UTC
- `8` = 8 AM UTC  
- `12` = Noon UTC
- `18` = 6 PM UTC

To find your local UTC offset, use: https://www.timeanddate.com/worldclock/timezone/utc

## Step 4: Test the Scheduler Locally

### Test 1: Verify Endpoint Works

```bash
# Test with invalid auth (should fail)
curl -X POST http://localhost:5000/api/cron/check_scheduled_jobs

# Test with valid auth (should work)
curl -X POST http://localhost:5000/api/cron/check_scheduled_jobs \
  -H "Authorization: Bearer default-insecure-key-change-me"
```

### Test 2: Simulate Scheduled Time

```bash
# Set test time to 8:05 AM UTC for user_id=1
python << 'EOF'
from datetime import datetime, timedelta
from app import app, db, UserProfile

with app.app_context():
    profile = UserProfile.query.get(1)
    # Set schedule for exactly 5 minutes from now
    now = datetime.utcnow()
    profile.scheduled_run_hour = now.hour
    profile.scheduled_run_minute = now.minute + 5
    profile.auto_apply_enabled = True
    db.session.commit()
    print(f"Schedule set for {now.hour}:{now.minute + 5:02d} UTC")
EOF

# Wait for the scheduled time, then trigger:
curl -X POST http://localhost:5000/api/cron/check_scheduled_jobs \
  -H "Authorization: Bearer default-insecure-key-change-me"

# Check logs for: "Cron: Triggered bot run for user_id=1"
```

### Test 3: Monitor via Logs

```bash
# On Render: Logs tab shows cron activity
# Look for messages like:
# "Cron: Triggered bot run for user_id=1, run_id=12345"
# "Cron job failed: ..."
```

## Step 5: Verify It's Working

1. **Check Render logs**:
   - Dashboard → Your Service → Logs
   - Look for entries like: `Cron: Triggered bot run for user_id=1, run_id=12345`

2. **Check BotRun records**:
   ```sql
   SELECT * FROM bot_runs 
   ORDER BY created_at DESC 
   LIMIT 5;
   ```

3. **Verify schedule is active**:
   ```sql
   SELECT user_id, scheduled_run_hour, scheduled_run_minute, 
          auto_apply_enabled, last_scheduled_run
   FROM user_profiles
   WHERE auto_apply_enabled = true;
   ```

## How It Works

### Timeline Example (User set to 8:00 AM UTC)

```
07:59:00 UTC - Cron job calls endpoint
             - Endpoint checks all users
             - No matches yet

08:00:00 UTC - Cron job calls endpoint  ✓
             - Endpoint finds user with 08:00 schedule
             - Triggers bot_run for that user
             - Sets last_scheduled_run = now
             - Logs: "Cron: Triggered bot run for user_id=1"

08:01:00 UTC - Cron job calls endpoint
             - Endpoint checks user
             - Match found BUT last run < 1 hour ago
             - Skips (prevents duplicate)

09:00:00 UTC - Cron job calls endpoint
             - Endpoint checks user
             - Match found AND > 1 hour since last run
             - Could trigger again (if minute = 0)
```

## Troubleshooting

### "Unauthorized" Error
- ✅ Check `CRON_SECRET_KEY` is set on Render service
- ✅ Verify cron job has same key in environment
- ✅ Restart both service and cron job

### No Jobs Triggered
- Check user's `auto_apply_enabled = true`
- Verify `scheduled_run_hour` and `scheduled_run_minute` match current UTC time
- Check time zone (scheduler uses UTC)
- Look for "Cron: Triggered..." in logs

### Too Many Runs
- The 1-hour debounce may not work if:
  - `last_scheduled_run` is NULL (first run)
  - Service was restarted (timer reset)
- Manually set `last_scheduled_run` if needed:
  ```sql
  UPDATE user_profiles 
  SET last_scheduled_run = NOW()
  WHERE user_id = YOUR_USER_ID;
  ```

### Jobs Not Applying
- Check bot has valid LinkedIn credentials
- Check database migration ran (scheduler fields exist)
- Check logs for bot errors in `BotRun.log_snippet`

## Advanced Configuration

### Change Schedule After Deploy

```bash
# SSH into Render or use database:
curl https://your-service.onrender.com/admin/change-schedule \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "hour": 18,
    "minute": 30
  }'
```

### Disable Scheduler

```sql
UPDATE user_profiles 
SET auto_apply_enabled = false
WHERE user_id = YOUR_USER_ID;
```

### Run Now (Manual Trigger)

```bash
curl https://your-service.onrender.com/run_now \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

## Security Notes

- ✅ Cron endpoint requires Bearer token authentication
- ✅ Token stored as environment variable (not in code)
- ✅ Uses different key per deployment
- ✅ Endpoint logs all triggers for auditing

**Never commit `CRON_SECRET_KEY` to git.**

## Monitoring

### Set Up Alerts (Optional)

1. Go to Render Dashboard
2. Click **Alerts** (bottom sidebar)
3. Create alert for:
   - CPU > 80%
   - Memory > 90%
   - Service crashed

### View Cron History

```sql
SELECT 
  user_id,
  status,
  submitted,
  skipped,
  failures,
  created_at
FROM bot_runs
WHERE created_at > NOW() - INTERVAL 7 DAY
ORDER BY created_at DESC;
```

## Next Steps

1. ✅ Set `CRON_SECRET_KEY` on Render
2. ✅ Create Render Cron Job (or use EasyCron)
3. ✅ Configure user schedule in database
4. ✅ Wait for next scheduled time or trigger manually
5. ✅ Check logs to confirm it's running

## Dashboard UI (Future)

Soon you'll be able to configure schedules directly in the webapp:
- Navigate to Settings → Scheduler
- Select preferred run time
- Enable/disable auto-apply
- View run history and logs

## Example: Daily 9 AM Applications

```sql
-- Set all users to 9 AM UTC daily
UPDATE user_profiles 
SET auto_apply_enabled = true,
    scheduled_run_hour = 9,
    scheduled_run_minute = 0
WHERE profile_id > 0;

-- Verify
SELECT user_id, scheduled_run_hour, auto_apply_enabled 
FROM user_profiles;
```

---

**Questions?** Check the logs on Render or run a manual test to see what's happening!
