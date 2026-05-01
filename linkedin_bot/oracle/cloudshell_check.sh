#!/usr/bin/env bash
# ============================================================
# cloudshell_check.sh
# Run this in Oracle Cloud Shell to verify the LinkedIn bot
# is installed and working on the VM at 89.168.109.195
#
# Usage:
#   bash cloudshell_check.sh           # full check
#   bash cloudshell_check.sh --run     # check + trigger a live bot run
# ============================================================
set -euo pipefail

VM_IP="89.168.109.195"
KEY="$HOME/.ssh/linkedin_bot_key"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=20 -i $KEY"
BOT_DIR="~/cv_portofolio/linkedin_bot"
RUN_MODE="${1:-}"

# ── colours ──────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}  $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERR]${NC}  $*"; }
hdr()  { echo -e "\n${YELLOW}══ $* ══${NC}"; }

# ── SSH key check ─────────────────────────────────────────────
hdr "SSH Key"
if [[ -f "$KEY" ]]; then
  ok "Key found: $KEY"
else
  err "Key NOT found at $KEY"
  echo "    Re-run cloudshell_deploy.sh to regenerate it, or:"
  echo "    ssh-keygen -t rsa -b 4096 -f $KEY -N '' && echo 'Then add pub key to VM authorized_keys'"
  exit 1
fi

# ── Connectivity ──────────────────────────────────────────────
hdr "VM Connectivity  ($VM_IP)"
if ssh $SSH_OPTS ubuntu@$VM_IP 'echo pong' &>/dev/null; then
  ok "VM is reachable"
else
  err "Cannot reach $VM_IP — VM may be stopped"
  exit 1
fi

# ── Helper: run command on VM ─────────────────────────────────
vm() { ssh $SSH_OPTS ubuntu@$VM_IP "$@"; }

# ── System info ───────────────────────────────────────────────
hdr "VM System Info"
vm 'echo "Uptime:  $(uptime -p)" ; echo "OS:      $(lsb_release -ds 2>/dev/null || cat /etc/os-release | grep PRETTY | cut -d= -f2)" ; echo "Python:  $(python3 --version 2>&1)" ; echo "Disk:    $(df -h ~ | tail -1 | awk '"'"'{print $3"/"$2" used ("$5")"}'"'"')"'

# ── Bot files ─────────────────────────────────────────────────
hdr "Bot Installation"
vm "
  FILES=(
    '$BOT_DIR/bot.py'
    '$BOT_DIR/config.py'
    '$BOT_DIR/main.py'
    '$BOT_DIR/requirements.txt'
    '$BOT_DIR/oracle/oracle_guard_run.sh'
    '~/cv_portofolio/Mikhael_CV.pdf'
  )
  all_ok=true
  for f in \"\${FILES[@]}\"; do
    expanded=\$(eval echo \$f)
    if [[ -f \$expanded ]]; then
      echo '  [OK]  '\$expanded
    else
      echo '  [MISS] '\$expanded
      all_ok=false
    fi
  done
  \$all_ok && echo 'All bot files present.' || echo 'Some files missing!'
"

# ── Playwright ────────────────────────────────────────────────
hdr "Playwright / Chromium"
vm "python3 -c \"from playwright.sync_api import sync_playwright; print('Playwright import OK')\" 2>&1 || echo 'Playwright NOT installed'"
vm "chromium-browser --version 2>/dev/null || chromium --version 2>/dev/null || echo 'Chromium not in PATH (OK if using playwright install)'"
vm "python3 -m playwright install --list 2>/dev/null | grep -i chromium || echo 'Chromium browser: (check below)'"
vm "ls ~/.cache/ms-playwright/ 2>/dev/null | head -5 || echo 'playwright cache not found'"

# ── .env credentials ──────────────────────────────────────────
hdr "LinkedIn Credentials (.env)"
vm "
  ENV_FILE=$BOT_DIR/.env
  if [[ -f \$ENV_FILE ]]; then
    HAS_EMAIL=\$(grep -c 'LINKEDIN_EMAIL=' \$ENV_FILE || true)
    HAS_PASS=\$(grep -c 'LINKEDIN_PASSWORD=' \$ENV_FILE || true)
    [[ \$HAS_EMAIL -gt 0 ]] && echo '  [OK]  LINKEDIN_EMAIL is set' || echo '  [MISS] LINKEDIN_EMAIL missing'
    [[ \$HAS_PASS -gt 0 ]]  && echo '  [OK]  LINKEDIN_PASSWORD is set' || echo '  [MISS] LINKEDIN_PASSWORD missing'
  else
    echo '  [MISS] .env file not found at '\$ENV_FILE
  fi
"

# ── Cron ──────────────────────────────────────────────────────
hdr "Cron Schedule"
vm "crontab -l 2>/dev/null || echo '(no crontab)'"

# ── Run history ───────────────────────────────────────────────
hdr "Run History"
vm "
  RH=$BOT_DIR/run_history.json
  if [[ -f \$RH ]]; then
    python3 -c \"
import json, sys
d = json.load(open('\$RH'))
runs = d if isinstance(d, list) else [d]
print(f'  Total recorded runs: {len(runs)}')
for r in runs[-5:]:
    ts  = r.get('date') or r.get('timestamp','?')
    sub = r.get('submitted', r.get('stats',{}).get('submitted','?'))
    skp = r.get('skipped',  r.get('stats',{}).get('skipped','?'))
    print(f'    {ts}  submitted={sub}  skipped={skp}')
\"
  else
    echo '  (no run_history.json yet — bot has not run)'
  fi
"

# ── Applied jobs ──────────────────────────────────────────────
hdr "Applied Jobs"
vm "
  AJ=$BOT_DIR/applied_jobs.json
  if [[ -f \$AJ ]]; then
    python3 -c \"
import json
d = json.load(open('\$AJ'))
jobs = list(d.items()) if isinstance(d, dict) else d
print(f'  Total jobs applied: {len(jobs)}')
for jid, info in (list(d.items())[-5:] if isinstance(d,dict) else [(j.get('id','?'), j) for j in jobs[-5:]]):
    title = info.get('title','?') if isinstance(info,dict) else '?'
    ts    = info.get('applied_at','') if isinstance(info,dict) else ''
    print(f'    [{ts[:10]}] {title} (id={jid})')
\"
  else
    echo '  (no applied_jobs.json yet)'
  fi
"

# ── Cron output log ───────────────────────────────────────────
hdr "Last Cron Output (scheduler_output.log)"
vm "
  LOG=$BOT_DIR/scheduler_output.log
  if [[ -f \$LOG ]]; then
    echo '  Last 30 lines:'
    tail -30 \$LOG | sed 's/^/  /'
  else
    echo '  (no scheduler_output.log yet)'
  fi
"

# ── Bot logs folder ───────────────────────────────────────────
hdr "Bot Log Files"
vm "ls -lh $BOT_DIR/logs/ 2>/dev/null || echo '  (logs/ folder empty or missing)'"
vm "
  LATEST=\$(ls -t $BOT_DIR/logs/*.log 2>/dev/null | head -1)
  if [[ -n \$LATEST ]]; then
    echo 'Latest log: '\$LATEST
    tail -30 \$LATEST | sed 's/^/  /'
  fi
"

# ── Optional: trigger a live run ──────────────────────────────
if [[ "$RUN_MODE" == "--run" ]]; then
  hdr "Triggering Live Bot Run (--run flag)"
  warn "This will run the bot NOW in headless mode (limit 5 jobs)."
  read -p "  Continue? [y/N] " CONFIRM
  if [[ "${CONFIRM,,}" == "y" ]]; then
    vm "cd ~/cv_portofolio/linkedin_bot && nohup xvfb-run -a python3 main.py --headless --limit 5 > /tmp/bot_live_run.log 2>&1 &"
    echo ""
    ok "Bot started in background. Tailing output (Ctrl+C to stop):"
    sleep 3
    vm "tail -f /tmp/bot_live_run.log" || true
  else
    echo "  Skipped."
  fi
fi

# ── Summary ───────────────────────────────────────────────────
hdr "Summary"
echo ""
echo "  VM IP    : $VM_IP"
echo "  Bot dir  : $BOT_DIR"
echo "  To SSH manually:"
echo "    ssh $SSH_OPTS ubuntu@$VM_IP"
echo ""
echo "  To tail cron log live:"
echo "    ssh $SSH_OPTS ubuntu@$VM_IP 'tail -f ~/cv_portofolio/linkedin_bot/scheduler_output.log'"
echo ""
echo "  To trigger a test run now:"
echo "    bash cloudshell_check.sh --run"
echo ""
ok "Check complete."
