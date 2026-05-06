# Scheduler Architecture

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      RENDER INFRASTRUCTURE                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────┐        ┌──────────────────────┐           │
│  │  Render Cron Job     │        │  Flask Web Service   │           │
│  │  (every minute)      │        │  (Always running)    │           │
│  └──────────────┬───────┘        └──────────────────────┘           │
│                 │                                                   │
│                 │ Call with                                        │
│                 │ CRON_SECRET_KEY                                  │
│                 │                                                   │
│                 │ GET/POST                                          │
│                 │ /api/cron/                                        │
│                 │ check_scheduled_jobs                              │
│                 │                                                   │
│                 └──────────────────────┬──────────────────────────► │
│                                        │                            │
│                      ┌─────────────────▼────────────┐               │
│                      │  Endpoint Handler            │               │
│                      ├──────────────────────────────┤               │
│                      │ 1. Check Bearer Token        │               │
│                      │ 2. Get current UTC time      │               │
│                      │ 3. Query UserProfiles        │               │
│                      │ 4. Match scheduled time      │               │
│                      │ 5. Check 1-hour debounce     │               │
│                      │ 6. Trigger bot run if match  │               │
│                      └─────────────────┬────────────┘               │
│                                        │                            │
│                      ┌─────────────────▼────────────┐               │
│                      │  bot_runner.run_for_user_async()            │
│                      ├──────────────────────────────┤               │
│                      │ - Create BotRun record       │               │
│                      │ - Start background thread    │               │
│                      │ - Initialize LinkedIn bot    │               │
│                      │ - Apply to jobs              │               │
│                      │ - Extract missing skills     │               │
│                      │ - Store results              │               │
│                      └─────────────────┬────────────┘               │
│                                        │                            │
│        ┌───────────────────────────────┼───────────────────────┐   │
│        │                               │                       │   │
│        ▼                               ▼                       ▼   │
│    ┌────────────┐             ┌──────────────────┐     ┌────────────┐
│    │  BotRun    │             │  Missing         │     │  LinkedIn  │
│    │  Table     │             │  SkillsReport    │     │  Sessions  │
│    │            │             │  Table           │     │            │
│    │ - status   │             │                  │     │ - Auth     │
│    │ - logs     │             │ - job_skills     │     │ - Apply    │
│    │ - stats    │             │ - missing_skills │     │ - Track    │
│    └────────────┘             │ - confidence     │     └────────────┘
│                               │ - company        │
│                               └──────────────────┘
│                                                                      │
│  ┌──────────────────────────────────────────────────────┐           │
│  │  PostgreSQL Database                                │           │
│  │  - user_profiles (scheduler config)                 │           │
│  │  - bot_runs (execution history)                     │           │
│  │  - missing_skills_reports (skill gaps)              │           │
│  └──────────────────────────────────────────────────────┘           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Timeline: What Happens at Scheduled Time

```
User sets: scheduled_run_hour=8, scheduled_run_minute=30

Day 1, 08:29 UTC:
  └─ Cron calls endpoint
     └─ No match yet (hour=8 but minute=29)
     └─ Response: {"triggered": 0}

Day 1, 08:30 UTC:  ✓ MATCH
  └─ Cron calls endpoint
     └─ Finds user with hour=8, minute=30
     └─ Checks last_scheduled_run
        └─ Empty or >1 hour ago: PROCEED
     └─ Calls bot_runner.run_for_user_async()
        ├─ Creates BotRun record
        ├─ Sets status = "running"
        ├─ Starts background thread
        └─ Returns run_id
     └─ Updates user.last_scheduled_run = NOW()
     └─ Response: {"triggered": 1, "run_id": 12345}

Day 1, 08:31-08:59 UTC:
  └─ Cron calls endpoint
     └─ Found match (hour=8, minute=...) but minute != 30
     └─ Response: {"triggered": 0}

Day 1, 09:30 UTC:  ✓ 1 HOUR LATER
  └─ Cron calls endpoint
     └─ Found match (if minute was also set to 30, or within retry window)
     └─ Checks: last_scheduled_run (09:30) - (08:30) = 1 hour
        └─ Time check: is_set() = True, so SKIP
     └─ Response: {"triggered": 0}

Day 2, 08:30 UTC:  ✓ NEXT DAY
  └─ Cron calls endpoint
     └─ Found match (hour=8, minute=30)
     └─ Checks: (08:30 next day) - (08:30 prev day) = >24 hours
        └─ Time check: is_set() = True, but >1 hour, so PROCEED
     └─ Trigger bot again
     └─ Update last_scheduled_run
```

## Data Flow: Skill Extraction

```
Job Posting
    │
    ▼
bot.py:_process_single_job()
    │
    ├─ Extract requirements text
    │
    ▼
skill_extractor.extract_skills_from_text()
    │
    ├─ Parse text for recognized skills
    ├─ Match against 100+ skill database
    ├─ Return sorted list
    │
    ▼
skill_extractor.get_user_skills()
    │
    ├─ Extract from: keywords, languages, job title, field of study
    ├─ Return user's skill set
    │
    ▼
skill_extractor.compare_skills()
    │
    ├─ Find missing = job_skills - user_skills
    ├─ Find matched = job_skills ∩ user_skills
    ├─ Calculate match_percentage
    │
    ▼
missing_skills_data dict
    │
    ├─ Store in job_record
    │
    ▼
bot_runner._on_job_result()
    │
    ├─ If status == "submitted"
    │
    ▼
MissingSkillsReport.create()
    │
    ├─ Store in database:
    │   - user_id
    │   - job_id, title, company
    │   - missing_skills (JSON)
    │   - confidence_score
    │   - created_at
    │
    ▼
PostgreSQL: missing_skills_reports table
    │
    ▼
Available for:
    ├─ Dashboard display
    ├─ Email notifications
    ├─ Skill trend analysis
    └─ Personalized recommendations
```

## State Machine: BotRun Status

```
                    ┌─────────────────┐
                    │   Created       │
                    │ (Just inserted) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   Running       │
                    │ (Bot started)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌─────────┐    ┌─────────┐    ┌──────────┐
        │ Done    │    │ Stopped │    │ Error    │
        │ (Normal)│    │ (User   │    │ (Crashed)│
        │ exit)   │    │ clicked)│    │          │
        └─────────┘    └─────────┘    └──────────┘
```

## Authentication Flow

```
Render Cron Job
    │
    ├─ Reads CRON_SECRET_KEY from environment
    │   └─ Example: "3X_k9F2w5q8r1t4y7u0i9o2p5a8s1d4f"
    │
    ├─ Builds Authorization header
    │   └─ "Authorization: Bearer 3X_k9F2w5q8r1t4y7u0i9o2p5a8s1d4f"
    │
    ├─ Calls endpoint with header
    │   └─ POST /api/cron/check_scheduled_jobs
    │
    ▼
Flask endpoint handler
    │
    ├─ Reads Authorization header
    ├─ Extracts Bearer token
    ├─ Compares to environment CRON_SECRET_KEY
    │
    ├─ If match:
    │   └─ Continue ✓
    │
    ├─ If no match:
    │   └─ Return 401 Unauthorized ✗
    │
    ▼
Proceed with job triggering
```

## Configuration Levels

```
Environment (Render Dashboard)
    ├─ CRON_SECRET_KEY
    ├─ DATABASE_URL
    ├─ LINKEDIN_EMAIL
    └─ LINKEDIN_PASSWORD

Database (Per-User)
    ├─ auto_apply_enabled (BOOL)
    ├─ scheduled_run_hour (INT 0-23)
    ├─ scheduled_run_minute (INT 0-59)
    ├─ send_missing_skills (BOOL)
    └─ last_scheduled_run (DATETIME)

Bot Config (Per-Run)
    ├─ keywords (list of search terms)
    ├─ locations (list of cities)
    ├─ max_applications_per_run
    ├─ headless mode
    └─ LinkedIn credentials
```

## Failure Scenarios & Recovery

```
Scenario 1: Cron job fails to call endpoint
    └─ Render Cron health check would alert
    └─ Restart cron job
    └─ Next minute, tries again

Scenario 2: Endpoint auth fails
    └─ Returns 401 Unauthorized
    └─ Cron job retries next minute (expected behavior)
    └─ Check: Environment variables match

Scenario 3: Bot crashes mid-run
    └─ BotRun.status set to "error" (at finally block)
    └─ Logged for debugging
    └─ Next scheduled run can proceed (debounce check)

Scenario 4: Database not available
    └─ ConnectionError caught
    └─ Endpoint returns 500
    └─ BotRun not updated
    └─ Retries next minute

Scenario 5: LinkedIn credentials invalid
    └─ Bot fails to login
    └─ Sets BotRun.status = "error"
    └─ Logs error message
    └─ Won't retry until next scheduled time

Scenario 6: Too many applications per day
    └─ Bot honors max_applications_per_run limit
    └─ Remaining jobs queued for next run
    └─ Status = "done" even if didn't apply to all
```

## Performance Metrics

```
Cron Overhead:
    ├─ Call frequency: Every 1 minute
    ├─ Per-call execution: <1 second
    ├─ Daily calls: ~1440
    ├─ CPU impact: Negligible
    └─ Cost: ~0.001 compute hours/day

Bot Execution (when triggered):
    ├─ LinkedIn login: ~10 seconds
    ├─ Per application: ~20-40 seconds (depends on form complexity)
    ├─ Skill extraction: <1 second per job
    ├─ Database writes: <100ms per job
    └─ Total for 25 jobs: ~10-20 minutes

Database:
    ├─ New records/day: ~25 (jobs)
    ├─ Scaling: Millions of records supported
    └─ Indexing: user_id, created_at for queries

Storage:
    ├─ BotRun per day: ~1KB
    ├─ MissingSkillsReport per job: ~2KB
    ├─ 30 days storage: ~1-2MB
    └─ Annual storage: ~15-20MB
```

---

**Ready to deploy?** Follow **RENDER_DEPLOYMENT.md** for step-by-step instructions.
