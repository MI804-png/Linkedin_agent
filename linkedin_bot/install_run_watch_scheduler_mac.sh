#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BOT_DIR="$ROOT_DIR/linkedin_bot"
CONFIG_FILE="$BOT_DIR/.scheduler.env"
CONFIG_EXAMPLE="$BOT_DIR/.scheduler.env.example"
PLIST_PATH="$HOME/Library/LaunchAgents/com.autoapply.runwatch.scheduler.plist"

PYTHON_EXE="$ROOT_DIR/.venv/bin/python3"
if [[ ! -x "$PYTHON_EXE" ]]; then
  PYTHON_EXE="$ROOT_DIR/.venv/bin/python"
fi
if [[ ! -x "$PYTHON_EXE" ]]; then
  PYTHON_EXE="$(command -v python3)"
fi

if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "Could not find python3. Install Python or create .venv first." >&2
  exit 1
fi

if [[ ! -f "$CONFIG_FILE" && -f "$CONFIG_EXAMPLE" ]]; then
  cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
  echo "Created $CONFIG_FILE from template. Fill in your dashboard email/password before relying on automatic runs."
fi

mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.autoapply.runwatch.scheduler</string>
    <key>ProgramArguments</key>
    <array>
      <string>$PYTHON_EXE</string>
      <string>$BOT_DIR/run_watch_scheduler.py</string>
      <string>--daemon</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>$ROOT_DIR</string>
    <key>StandardOutPath</key>
    <string>$BOT_DIR/run_watch_scheduler.launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>$BOT_DIR/run_watch_scheduler.launchd.err.log</string>
  </dict>
</plist>
PLIST

launchctl bootout "gui/$UID" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST_PATH"
launchctl enable "gui/$UID/com.autoapply.runwatch.scheduler" >/dev/null 2>&1 || true
launchctl kickstart -k "gui/$UID/com.autoapply.runwatch.scheduler" >/dev/null 2>&1 || true

echo "Installed macOS LaunchAgent: $PLIST_PATH"
echo "The scheduler will start when you log in and will check your local dashboard schedule every minute."
echo "Config file: $CONFIG_FILE"
