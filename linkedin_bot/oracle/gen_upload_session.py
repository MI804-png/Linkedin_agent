"""
Generate cloudshell_upload_session.sh — embeds the local playwright_state.json
as base64 and produces a shell script you paste into Oracle Cloud Shell
to transfer the working LinkedIn session to the VM.
"""
import base64
import pathlib
import textwrap

BASE = pathlib.Path(__file__).resolve().parent.parent
STATE_FILE = BASE / "playwright_state.json"
OUT = pathlib.Path(__file__).resolve().parent / "cloudshell_upload_session.sh"

if not STATE_FILE.exists():
    raise SystemExit(f"ERROR: {STATE_FILE} not found. Run the bot locally once to create it.")

raw   = STATE_FILE.read_bytes()
b64   = base64.b64encode(raw).decode()
chunks = textwrap.wrap(b64, 3000)

KEY  = "/home/mikhael_na/.ssh/linkedin_bot_key"
IP   = "89.168.109.195"
DEST = "~/cv_portofolio/linkedin_bot/playwright_state.json"

lines = [
    "#!/usr/bin/env bash",
    "# ─────────────────────────────────────────────────────────",
    "# cloudshell_upload_session.sh",
    "# Uploads your local LinkedIn session to the Oracle VM.",
    "# Run this in Oracle Cloud Shell.",
    "# ─────────────────────────────────────────────────────────",
    "set -euo pipefail",
    "",
    f'KEY="{KEY}"',
    f'IP="{IP}"',
    'OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=20 -i $KEY"',
    "",
    "echo 'Uploading playwright_state.json to VM...'",
    "",
    "# Rebuild the base64 string in chunks to avoid shell line-length limits",
    "B64=''",
]

for chunk in chunks:
    lines.append(f"B64=\"${{B64}}{chunk}\"")

lines += [
    "",
    "# Decode and write on the VM",
    f'ssh $OPTS ubuntu@$IP "printf \'%s\' \'$B64\' | base64 -d > {DEST}"',
    "",
    "# Verify",
    f'SIZE=$(ssh $OPTS ubuntu@$IP "wc -c < {DEST}")',
    'echo "Uploaded $SIZE bytes"',
    f'ssh $OPTS ubuntu@$IP "python3 -c \\"import json; d=json.load(open(\\\"cv_portofolio/linkedin_bot/playwright_state.json\\\")); print(\'Cookies:\', len(d.get(\'cookies\',[])), \'Origins:\', len(d.get(\'origins\',[])))\\""',
    "",
    "echo ''",
    "echo 'Session uploaded! Now run a test:'",
    "echo '  bash cloudshell_check.sh --run'",
]

script = "\n".join(lines) + "\n"
OUT.write_bytes(script.encode("utf-8"))
print(f"Written: {OUT}")
print(f"  State file: {len(raw)} bytes  /  {len(chunks)} base64 chunks")
