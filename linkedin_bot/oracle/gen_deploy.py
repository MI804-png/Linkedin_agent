"""
Generates cloudshell_deploy.sh — the all-in-one Oracle Cloud Shell script.
Run: python gen_deploy.py
"""
import pathlib, base64, textwrap

HERE  = pathlib.Path(__file__).parent
ROOT  = HERE.parent          # linkedin_bot/
PROJ  = ROOT.parent          # cv_portofolio/

cv_b64     = base64.b64encode((PROJ / "Mikhael_CV.pdf").read_bytes()).decode()
bot_b64    = base64.b64encode((ROOT / "bot.py").read_bytes()).decode()
config_b64 = base64.b64encode((ROOT / "config.py").read_bytes()).decode()
main_b64   = base64.b64encode((ROOT / "main.py").read_bytes()).decode()
guard_b64  = base64.b64encode((HERE / "oracle_guard_run.sh").read_bytes()).decode()

HEADER = """\
#!/usr/bin/env bash
# ============================================================
#  LinkedIn Auto-Apply Bot — Oracle Cloud Shell Deploy Script
#  Upload this file to Cloud Shell, then run:
#    bash cloudshell_deploy.sh
# ============================================================
set -euo pipefail

# -------- FILL IN YOUR PASSWORD BEFORE RUNNING --------
LINKEDIN_EMAIL="Mikhael.Nabil.Salama.Rezk@gmail.com"
LINKEDIN_PASSWORD=""   # <-- put your LinkedIn password here
# -------------------------------------------------------

SCHEDULE_HOUR=8
SCHEDULE_MINUTE=30
TZ_CRON="Europe/Budapest"
VM_DISPLAY_NAME="linkedin-bot"
VM_SHAPE="VM.Standard.A1.Flex"
OCPUS=1
MEMORY_GB=6
KEY_PATH="$HOME/.ssh/linkedin_bot_key"

if [[ -z "$LINKEDIN_PASSWORD" ]]; then
  echo "ERROR: Set LINKEDIN_PASSWORD at the top of this script first."
  exit 1
fi

# ---- 1. SSH key ----
echo "[1/7] Generating SSH key pair..."
mkdir -p "$HOME/.ssh"
[[ ! -f "$KEY_PATH" ]] && ssh-keygen -t rsa -b 4096 -f "$KEY_PATH" -N "" -q

# ---- 2. OCI params ----
echo "[2/7] Discovering OCI tenancy parameters..."
TENANCY_ID=$(oci iam compartment list --all \\
  --query "data[0].\\"compartment-id\\"" --raw-output)
COMPARTMENT_ID=$(oci iam compartment list --all \\
  --query "data[?name!='ManagedCompartmentForPaaS'] | [0].id" \\
  --raw-output 2>/dev/null || echo "$TENANCY_ID")
AD=$(oci iam availability-domain list \\
  --compartment-id "$TENANCY_ID" \\
  --query "data[0].name" --raw-output)
echo "  Compartment: $COMPARTMENT_ID  AD: $AD"

# ---- 3. Image ----
echo "[3/7] Finding Ubuntu 22.04 ARM image..."
IMAGE_ID=$(oci compute image list \\
  --compartment-id "$TENANCY_ID" \\
  --operating-system "Canonical Ubuntu" \\
  --operating-system-version "22.04" \\
  --shape "$VM_SHAPE" \\
  --sort-by TIMECREATED --sort-order DESC \\
  --query "data[0].id" --raw-output)
echo "  Image: $IMAGE_ID"

# ---- 4. Subnet ----
echo "[4/7] Finding default subnet..."
VCN_ID=$(oci network vcn list \\
  --compartment-id "$COMPARTMENT_ID" \\
  --query "data[0].id" --raw-output)
SUBNET_ID=$(oci network subnet list \\
  --compartment-id "$COMPARTMENT_ID" \\
  --vcn-id "$VCN_ID" \\
  --query "data[0].id" --raw-output)
echo "  Subnet: $SUBNET_ID"

# ---- 5. Launch VM ----
echo "[5/7] Creating VM instance (~2 min)..."
INSTANCE_JSON=$(oci compute instance launch \\
  --availability-domain "$AD" \\
  --compartment-id "$COMPARTMENT_ID" \\
  --display-name "$VM_DISPLAY_NAME" \\
  --image-id "$IMAGE_ID" \\
  --shape "$VM_SHAPE" \\
  --shape-config '{"ocpus":'"$OCPUS"',"memoryInGBs":'"$MEMORY_GB"'}' \\
  --subnet-id "$SUBNET_ID" \\
  --assign-public-ip true \\
  --ssh-authorized-keys-file "${KEY_PATH}.pub" \\
  --wait-for-state RUNNING \\
  --max-wait-seconds 300)

INSTANCE_ID=$(echo "$INSTANCE_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
PUBLIC_IP=$(oci compute instance list-vnics \\
  --instance-id "$INSTANCE_ID" \\
  --query "data[0].\\"public-ip\\"" --raw-output)
echo "  VM IP: $PUBLIC_IP"

# ---- 6. Open SSH port ----
echo "[6/7] Ensuring port 22 open..."
SEC_LIST_ID=$(oci network security-list list \\
  --compartment-id "$COMPARTMENT_ID" \\
  --vcn-id "$VCN_ID" \\
  --query "data[0].id" --raw-output)
oci network security-list update \\
  --security-list-id "$SEC_LIST_ID" \\
  --ingress-security-rules '[{"source":"0.0.0.0/0","protocol":"6","isStateless":false,"tcpOptions":{"destinationPortRange":{"min":22,"max":22}}}]' \\
  --force 2>/dev/null || true
echo "Waiting 60s for SSH..."
sleep 60

# ---- 7. Install bot ----
echo "[7/7] Installing bot on VM..."
SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=30 -i $KEY_PATH ubuntu@$PUBLIC_IP"

$SSH "mkdir -p ~/cv_portofolio/linkedin_bot/oracle ~/cv_portofolio/linkedin_bot/logs"

"""

# Helper: emit transfer_b64 calls (avoids giant single-argument command lines)
def transfer_line(remote_path, b64_data):
    # Split into chunks to keep line length manageable for bash heredoc
    return (
        f"printf '%s' '{b64_data}' | $SSH 'base64 -d > {remote_path}'\n"
    )

TRANSFERS = (
    "echo '  Uploading files...'\n"
    + transfer_line("~/cv_portofolio/linkedin_bot/bot.py",    bot_b64)
    + transfer_line("~/cv_portofolio/linkedin_bot/config.py", config_b64)
    + transfer_line("~/cv_portofolio/linkedin_bot/main.py",   main_b64)
    + transfer_line("~/cv_portofolio/linkedin_bot/oracle/oracle_guard_run.sh", guard_b64)
    + transfer_line("~/cv_portofolio/Mikhael_CV.pdf",         cv_b64)
)

FOOTER = """\

echo "  Writing .env and requirements.txt..."
$SSH bash <<ENDSSH
set -euo pipefail
cat > ~/cv_portofolio/linkedin_bot/.env <<'EOF'
LINKEDIN_EMAIL=$LINKEDIN_EMAIL
LINKEDIN_PASSWORD=$LINKEDIN_PASSWORD
EOF

cat > ~/cv_portofolio/linkedin_bot/requirements.txt <<'EOF'
playwright==1.53.0
python-dotenv==1.0.1
EOF

echo "[]" > ~/cv_portofolio/linkedin_bot/applied_jobs.json
echo "[]" > ~/cv_portofolio/linkedin_bot/run_history.json
echo "{}" > ~/cv_portofolio/linkedin_bot/state.json
chmod +x ~/cv_portofolio/linkedin_bot/oracle/oracle_guard_run.sh
ENDSSH

echo "  Installing Python + Playwright (~5 min)..."
$SSH bash <<'ENDSSH'
set -euo pipefail
sudo apt-get update -y -q
sudo apt-get install -y -q python3 python3-venv python3-pip xvfb
cd ~/cv_portofolio/linkedin_bot
python3 -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
.venv/bin/python -m playwright install --with-deps chromium
echo "Playwright OK"
ENDSSH

echo "  Setting up daily cron..."
$SSH bash <<ENDSSH
(
  crontab -l 2>/dev/null | sed '/# BEGIN LINKEDIN_AUTO_APPLY/,/# END LINKEDIN_AUTO_APPLY/d'
  echo "# BEGIN LINKEDIN_AUTO_APPLY"
  echo "CRON_TZ=$TZ_CRON"
  echo "$SCHEDULE_MINUTE $SCHEDULE_HOUR * * * /bin/bash ~/cv_portofolio/linkedin_bot/oracle/oracle_guard_run.sh >> ~/cv_portofolio/linkedin_bot/logs/cron.log 2>&1"
  echo "@reboot sleep 180 && /bin/bash ~/cv_portofolio/linkedin_bot/oracle/oracle_guard_run.sh >> ~/cv_portofolio/linkedin_bot/logs/cron.log 2>&1"
  echo "# END LINKEDIN_AUTO_APPLY"
) | crontab -
echo "Cron installed:"
crontab -l
ENDSSH

echo ""
echo "===================================================="
echo " DEPLOYMENT COMPLETE"
echo "===================================================="
echo " VM IP   : $PUBLIC_IP"
echo " SSH key : $KEY_PATH"
echo " Runs    : daily at ${SCHEDULE_HOUR}:$(printf %02d $SCHEDULE_MINUTE) Budapest time"
echo ""
echo " Run now :"
echo "   $SSH 'bash ~/cv_portofolio/linkedin_bot/oracle/oracle_guard_run.sh'"
echo ""
echo " Live log:"
echo "   $SSH 'tail -f ~/cv_portofolio/linkedin_bot/logs/cron.log'"
echo "===================================================="
"""

script = HEADER + TRANSFERS + FOOTER
out = HERE / "cloudshell_deploy.sh"
out.write_text(script, encoding="utf-8")
print(f"Done. {out}  ({len(script):,} bytes)")
