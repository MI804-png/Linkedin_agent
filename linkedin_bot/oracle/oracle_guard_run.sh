#!/usr/bin/env bash
set -euo pipefail

BOT_DIR="$HOME/cv_portofolio/linkedin_bot"
PYTHON_BIN="$BOT_DIR/.venv/bin/python"
RUN_HISTORY="$BOT_DIR/run_history.json"
LOG_FILE="$BOT_DIR/scheduler_output.log"

mkdir -p "$BOT_DIR"
cd "$BOT_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[$(date -Is)] ERROR: Python virtualenv not found at $PYTHON_BIN" >> "$LOG_FILE"
  exit 1
fi

if [[ ! -f "$HOME/cv_portofolio/Mikhael_CV.pdf" ]]; then
  echo "[$(date -Is)] ERROR: CV not found at $HOME/cv_portofolio/Mikhael_CV.pdf" >> "$LOG_FILE"
  exit 1
fi

LAST_RUN_DATE="$($PYTHON_BIN - <<'PY'
import json
from pathlib import Path
from datetime import datetime

path = Path("run_history.json")
if not path.exists() or path.stat().st_size == 0:
    print("")
    raise SystemExit

try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("")
    raise SystemExit

if not isinstance(data, list) or not data:
    print("")
    raise SystemExit

last = data[-1].get("started_at", "")
if not last:
    print("")
    raise SystemExit

try:
    dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    print(dt.astimezone().date().isoformat())
except Exception:
    print("")
PY
)"

TODAY="$(date +%F)"
if [[ -n "$LAST_RUN_DATE" && "$LAST_RUN_DATE" == "$TODAY" ]]; then
  echo "[$(date -Is)] Skipped: already ran today." >> "$LOG_FILE"
  exit 0
fi

echo "[$(date -Is)] Starting daily run." >> "$LOG_FILE"

set +e
xvfb-run -a "$PYTHON_BIN" main.py --headless --limit 25 >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
set -e

echo "[$(date -Is)] Finished with exit code: $EXIT_CODE" >> "$LOG_FILE"
exit $EXIT_CODE
