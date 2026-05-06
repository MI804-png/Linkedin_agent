# Daily Scheduler Setup - COMPLETE ✅

Your LinkedIn bot is now ready to run automatically every day on Render.

## What's Ready

| Component | Status | Details |
|-----------|--------|---------|
| **Cron Endpoint** | ✅ Complete | `/api/cron/check_scheduled_jobs` with Bearer token auth |
| **Database Schema** | ✅ Complete | Scheduler columns added to user_profiles |
| **Time Matching** | ✅ Complete | Checks current UTC hour:minute |
| **Job Triggering** | ✅ Complete | Calls bot_runner.run_for_user_async() |
| **Debouncing** | ✅ Complete | Prevents duplicate runs within 1 hour |
| **Skill Tracking** | ✅ Complete | Stores missing skills for each application |
| **Local Testing** | ✅ Complete | All 6 tests pass |

## How It Works

```
Every Minute:
  Render Cron Job
    ↓
  Calls /api/cron/check_scheduled_jobs
    ↓
  Checks ALL users' scheduled times
    ↓
  If user's time matches NOW (UTC):
    - Verify last run was >1 hour ago
    - Trigger bot_runner.run_for_user_async()
    - Store last_scheduled_run timestamp
    ↓
  Bot runs in background:
    - Logs in to LinkedIn
    - Applies to jobs
    - Extracts missing skills
    - Stores skill reports
```

## Deploy in 5 Steps

### 1️⃣ Generate Secret Key
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2️⃣ Add to Render Service Environment
- Render Dashboard → Service → Environment
- Add: `CRON_SECRET_KEY=YOUR_KEY_HERE`
- Save & redeploy

### 3️⃣ Create Render Cron Job
- **Name**: `job-bot-scheduler`
- **Runtime**: Node
- **Schedule**: `*/1 * * * *` (every minute)
- **Start Command**:
  ```
  curl -X POST https://YOUR_RENDER_URL/api/cron/check_scheduled_jobs \
    -H "Authorization: Bearer $CRON_SECRET_KEY"
  ```
- Add same `CRON_SECRET_KEY` to cron environment

### 4️⃣ Configure Your Schedule (Database)
```sql
UPDATE user_profiles 
SET auto_apply_enabled = true,
    scheduled_run_hour = 8,           -- Your preferred hour (UTC)
    scheduled_run_minute = 30,        -- Your preferred minute
    send_missing_skills = true
WHERE user_id = 1;
```

### 5️⃣ Test It
```bash
# Check logs
curl -X POST https://YOUR_RENDER_URL/api/cron/check_scheduled_jobs \
  -H "Authorization: Bearer YOUR_SECRET_KEY"

# Should return: {"status": "ok", "triggered_runs": 0}
```

## Files Created/Modified

### Documentation
- `RENDER_DEPLOYMENT.md` - Complete deployment guide with troubleshooting
- `SCHEDULER_QUICK_START.md` - Quick reference card (2 minutes)
- `SCHEDULER_SETUP_RENDER.md` - Detailed technical setup (30 minutes)
- `SKILLS_INTEGRATION.md` - Skills tracking feature documentation

### Code Changes
- `webapp/app.py`
  - Added `/api/cron/check_scheduled_jobs` endpoint
  - Added MissingSkillsReport model
  - Added scheduler columns to UserProfile
  - Added schema migration logic
  
- `linkedin_bot/bot.py`
  - Integrated skill extraction
  - Tracks missing skills per application
  
- `linkedin_bot/skill_extractor.py`
  - 100+ skill recognition database
  - Skill gap analysis
  
- `webapp/bot_runner.py`
  - Stores missing skills in database after each run

### Testing
- `test_scheduler_local.py` - Validates all components locally

## Database Schema

**UserProfile** additions:
```sql
scheduled_run_hour INTEGER DEFAULT 8        -- Hour (0-23) UTC
scheduled_run_minute INTEGER DEFAULT 0      -- Minute (0-59)
auto_apply_enabled BOOLEAN DEFAULT FALSE    -- Enable scheduler
last_scheduled_run DATETIME                 -- Last run timestamp (prevents duplicates)
send_missing_skills BOOLEAN DEFAULT FALSE   -- Email reports
```

**New Table**: MissingSkillsReport
```sql
- id (PK)
- user_id (FK)
- job_id
- job_title
- company_name
- job_url
- missing_skills (JSON array)
- confidence_score (0.0-1.0)
- created_at (timestamp)
```

## Key Features

✅ **Daily Scheduling**: Run jobs at same time every day
✅ **Per-User Schedules**: Each user has own preferred time
✅ **UTC-Based**: Platform-independent time handling
✅ **Secure**: Bearer token authentication
✅ **Debounced**: No duplicate runs within 1 hour
✅ **Monitored**: Complete logging and tracking
✅ **Scalable**: Works with any number of users
✅ **Skill Tracking**: Automatically detects missing skills
✅ **Background Job**: Doesn't block web requests

## Monitoring Commands

### Check Scheduled Users
```sql
SELECT user_id, scheduled_run_hour, scheduled_run_minute, 
       auto_apply_enabled, last_scheduled_run
FROM user_profiles
WHERE auto_apply_enabled = true;
```

### View Recent Runs
```sql
SELECT user_id, status, submitted, skipped, failures, created_at 
FROM bot_runs
WHERE created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC
LIMIT 10;
```

### Check Missing Skills
```sql
SELECT job_title, company_name, 
       json_array_length(missing_skills::json) as num_missing,
       confidence_score
FROM missing_skills_reports
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

## Testing Locally

All components tested locally with `test_scheduler_local.py`:

```
✓ PASS   db_connection
✓ PASS   schema
✓ PASS   users
✓ PASS   cron_endpoint
✓ PASS   time_matching
✓ PASS   bot_runner
```

Run locally to verify: `.venv\Scripts\python.exe test_scheduler_local.py`

## UTC Time Reference

| Your Local | UTC Hour |
|-----------|----------|
| 8 AM CET  | 7        |
| 9 AM CET  | 8        |
| 10 AM CET | 9        |
| 6 PM CET  | 17       |

Find your timezone: https://www.timeanddate.com/worldclock/timezone/utc

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Unauthorized" | Verify `CRON_SECRET_KEY` in both service and cron environment |
| Jobs not running | Check `auto_apply_enabled = true` and time matches UTC |
| Too many runs | Ensure minute is specific (not *), debounce handles rest |
| LinkedIn errors | Verify credentials valid, check 2FA not blocking |
| Missing skills not stored | Check bot runs completed successfully |

## Next Steps

1. **Deploy to Render** using RENDER_DEPLOYMENT.md (5 minutes)
2. **Monitor first run** - wait for scheduled time, check logs
3. **Verify success** - check BotRun and MissingSkillsReport tables
4. **Fine-tune** - adjust run time or job search keywords as needed
5. **Add notifications** (future) - email missing skills reports

## Security

- ✅ Secret key is random (32+ characters)
- ✅ Stored in Render environment (not in code)
- ✅ Bearer token authentication required
- ✅ All triggers logged for auditing
- ✅ Different key per environment

## Support Resources

- **Quick Start**: See `SCHEDULER_QUICK_START.md` (2 min read)
- **Full Setup**: See `SCHEDULER_SETUP_RENDER.md` (30 min read)
- **Deployment**: See `RENDER_DEPLOYMENT.md` (step-by-step)
- **Test Locally**: Run `test_scheduler_local.py`

## Ready to Deploy?

✅ All components tested and working
✅ Documentation complete
✅ Security configured
✅ Monitoring tools ready

**Next:** Follow RENDER_DEPLOYMENT.md to deploy in 5 steps!

---

**Status**: Production Ready 🚀
**Last Updated**: May 4, 2026
**Test Results**: 6/6 PASS
