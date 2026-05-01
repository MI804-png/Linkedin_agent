#!/usr/bin/env bash
set -euo pipefail

SCHEDULE_HOUR="${1:-8}"
SCHEDULE_MINUTE="${2:-30}"
SCHEDULE_TZ="${3:-Europe/Budapest}"

BASE_DIR="$HOME/cv_portofolio"
BOT_DIR="$BASE_DIR/linkedin_bot"
GUARD_SCRIPT="$BOT_DIR/oracle/oracle_guard_run.sh"
VENV_DIR="$BOT_DIR/.venv"

if [[ ! -d "$BOT_DIR" ]]; then
  echo "ERROR: Bot directory not found: $BOT_DIR"
  exit 1
fi

sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip xvfb curl ca-certificates

cd "$BOT_DIR"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r requirements.txt
"$VENV_DIR/bin/python" -m playwright install --with-deps chromium

chmod +x "$GUARD_SCRIPT"

CRON_BLOCK=$(cat <<EOF
# BEGIN LINKEDIN_AUTO_APPLY
CRON_TZ=$SCHEDULE_TZ
$SCHEDULE_MINUTE $SCHEDULE_HOUR * * * /bin/bash $GUARD_SCRIPT
@reboot sleep 180 && /bin/bash $GUARD_SCRIPT
# END LINKEDIN_AUTO_APPLY
EOF
)

(
  crontab -l 2>/dev/null | sed '/# BEGIN LINKEDIN_AUTO_APPLY/,/# END LINKEDIN_AUTO_APPLY/d'
  echo "$CRON_BLOCK"
) | crontab -

mkdir -p "$BOT_DIR/logs"
touch "$BOT_DIR/scheduler_output.log"

echo "Oracle setup complete."
echo "Daily run time: $SCHEDULE_HOUR:$SCHEDULE_MINUTE ($SCHEDULE_TZ)"
echo "Log file: $BOT_DIR/scheduler_output.log"
