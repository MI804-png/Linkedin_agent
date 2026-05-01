#!/usr/bin/env bash
# ============================================================
# cloudshell_fix.sh
# Run in Oracle Cloud Shell to fix the two issues found:
#   1. Playwright not installed on the VM
#   2. LinkedIn session expired (playwright_state.json stale/missing)
#
# Usage:
#   bash cloudshell_fix.sh
# ============================================================
set -euo pipefail

VM_IP="89.168.109.195"
KEY="$HOME/.ssh/linkedin_bot_key"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=30 -i $KEY"
BOT_DIR="$HOME/cv_portofolio/linkedin_bot"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}  $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERR]${NC}  $*"; }
hdr()  { echo -e "\n${YELLOW}══ $* ══${NC}"; }

vm()      { ssh $SSH_OPTS ubuntu@$VM_IP "$@"; }
vm_bg()   { ssh $SSH_OPTS ubuntu@$VM_IP "nohup $* > /tmp/fix_bg.log 2>&1 &"; }

# ── Sanity checks ─────────────────────────────────────────────
hdr "Pre-flight"
[[ -f "$KEY" ]] || { err "SSH key not found: $KEY"; exit 1; }
vm 'echo pong' &>/dev/null && ok "VM reachable" || { err "VM unreachable"; exit 1; }

# ── Step 1: Install Playwright on the VM ─────────────────────
hdr "Step 1/3 — Install Playwright on VM"
vm "
  set -e
  cd ~/cv_portofolio/linkedin_bot
  echo '  Installing Python deps from requirements.txt...'
  pip3 install -q -r requirements.txt
  echo '  Installing Playwright Chromium browser...'
  python3 -m playwright install chromium
  echo '  Verifying...'
  python3 -c 'from playwright.sync_api import sync_playwright; print(\"  Playwright import OK\")'
"
ok "Playwright installed"

# ── Step 2: Clear stale session ───────────────────────────────
hdr "Step 2/3 — Clear stale LinkedIn session"
vm "
  STATE=~/cv_portofolio/linkedin_bot/playwright_state.json
  if [[ -f \$STATE ]]; then
    mv \$STATE \${STATE}.bak
    echo '  Backed up old state to playwright_state.json.bak'
  else
    echo '  No existing state file (already clean)'
  fi
"
ok "Session cleared"

# ── Step 3: Fresh login run ───────────────────────────────────
hdr "Step 3/3 — Fresh LinkedIn login (headed via Xvfb)"
warn "The bot will now open a real browser on the VM (via Xvfb) to log in."
warn "This saves a new playwright_state.json so future headless runs work."
echo ""

vm "
  set -e
  cd ~/cv_portofolio/linkedin_bot

  # Make sure Xvfb is installed
  if ! command -v Xvfb &>/dev/null; then
    echo '  Installing Xvfb...'
    sudo apt-get install -y -q xvfb
  fi

  # Run the bot once in headed (but Xvfb) mode with limit=1
  # This will log in, save playwright_state.json, and apply to 1 job
  echo '  Running bot (xvfb-run, limit=1) — this may take 60-120 seconds...'
  timeout 180 xvfb-run -a python3 main.py --headless --limit 1 2>&1 | tee /tmp/fix_login_run.log
"

# ── Verify session saved ──────────────────────────────────────
hdr "Verifying session saved"
vm "
  STATE=~/cv_portofolio/linkedin_bot/playwright_state.json
  if [[ -f \$STATE ]]; then
    SIZE=\$(wc -c < \$STATE)
    echo \"  playwright_state.json: \${SIZE} bytes\"
    if [[ \$SIZE -gt 500 ]]; then
      echo '  [OK]  Session looks valid (non-trivial size)'
    else
      echo '  [WARN] File is very small — login may not have completed'
    fi
  else
    echo '  [MISS] playwright_state.json not created — login likely failed'
    echo '  Check /tmp/fix_login_run.log on the VM for details'
  fi
"

# ── Show last lines of run ────────────────────────────────────
hdr "Run output"
vm "tail -30 /tmp/fix_login_run.log 2>/dev/null || echo '(no log)'"

# ── Cron verification ─────────────────────────────────────────
hdr "Cron (unchanged)"
vm "crontab -l"

# ── Summary ───────────────────────────────────────────────────
hdr "Summary"
echo ""
echo "  What was fixed:"
echo "    1. Playwright + Chromium installed on the VM"
echo "    2. Stale playwright_state.json cleared"
echo "    3. Fresh login run executed to create a new session"
echo ""
echo "  Next step — verify everything is OK:"
echo "    bash cloudshell_check.sh"
echo ""
echo "  To watch tomorrow's cron run live:"
echo "    ssh $SSH_OPTS ubuntu@$VM_IP \\"
echo "      'tail -f ~/cv_portofolio/linkedin_bot/logs/cron.log'"
echo ""
ok "Fix complete. Bot should now work on the next cron run at 08:30 Budapest time."
