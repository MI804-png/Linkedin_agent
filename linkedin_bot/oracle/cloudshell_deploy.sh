#!/usr/bin/env bash
# ============================================================
#  LinkedIn Auto-Apply Bot — Oracle Cloud Shell Deploy Script
#  Upload this file to Cloud Shell, then run:
#    bash cloudshell_deploy.sh
# ============================================================
set -euo pipefail

# -------- FILL IN YOUR PASSWORD BEFORE RUNNING --------
LINKEDIN_EMAIL="Mikhael.Nabil.Salama.Rezk@gmail.com"
LINKEDIN_PASSWORD="mikha@2001"
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
# Cloud Shell authenticates via delegation token; tenancy OCID is in OCI_CLI_TENANCY
TENANCY_ID="${OCI_CLI_TENANCY:-}"
[[ -z "$TENANCY_ID" ]] && TENANCY_ID="${OCI_RESOURCE_PRINCIPAL_TENANCY_ID:-}"
[[ -z "$TENANCY_ID" ]] && TENANCY_ID="${OCI_TENANCY:-}"
if [[ -z "$TENANCY_ID" ]]; then
  TOKEN_FILE="${OCI_CLI_SECURITY_TOKEN_FILE:-}"
  if [[ -z "$TOKEN_FILE" && -f "$HOME/.oci/config" ]]; then
    TOKEN_FILE=$(grep '^security_token_file=' "$HOME/.oci/config" | head -1 | cut -d= -f2 | tr -d '[:space:]')
  fi
  if [[ -n "$TOKEN_FILE" && -f "$TOKEN_FILE" ]]; then
    TENANCY_ID=$(python3 - "$TOKEN_FILE" <<'PY'
import base64
import json
import sys

path = sys.argv[1]
token = open(path, 'r', encoding='utf-8').read().strip()
if token.lower().startswith('bearer '):
    token = token.split(None, 1)[1].strip()
parts = token.split('.')
if len(parts) < 2:
    print("")
    raise SystemExit(0)
payload = parts[1] + '=' * (-len(parts[1]) % 4)
data = json.loads(base64.urlsafe_b64decode(payload.encode('ascii')).decode('utf-8'))
for key in ("res_tenant", "tenant", "tenancyId", "tenancy_id"):
    v = data.get(key)
    if isinstance(v, str) and v:
        print(v)
        break
else:
    print("")
PY
)
  fi
fi
TENANCY_ID="$(echo "$TENANCY_ID" | tr -d '\r\n[:space:]')"
if [[ "$TENANCY_ID" == ocid1.compartment.* ]]; then
  CURRENT_COMPARTMENT="$TENANCY_ID"
  for _ in 1 2 3 4 5 6; do
    PARENT_ID=$(oci iam compartment get \
      --compartment-id "$CURRENT_COMPARTMENT" \
      --query "data.\"compartment-id\"" --raw-output 2>/dev/null || true)
    PARENT_ID="$(echo "$PARENT_ID" | tr -d '\r\n[:space:]')"
    [[ -z "$PARENT_ID" ]] && break
    if [[ "$PARENT_ID" == ocid1.tenancy.* ]]; then
      TENANCY_ID="$PARENT_ID"
      break
    fi
    CURRENT_COMPARTMENT="$PARENT_ID"
  done
fi
if [[ -z "$TENANCY_ID" ]]; then
  echo "ERROR: Cannot determine tenancy OCID from env vars or token."
  echo "Set TENANCY_ID manually at the top of this script and retry."
  exit 1
fi
if [[ "$TENANCY_ID" != ocid1.tenancy.* ]]; then
  echo "ERROR: Invalid tenancy OCID resolved: $TENANCY_ID"
  echo "Set TENANCY_ID manually at the top of the script and retry."
  exit 1
fi
# Use tenancy root as compartment (works for free-tier accounts with no sub-compartments)
COMPARTMENT_ID=$(oci iam compartment list --all \
  --query "data[?name!='ManagedCompartmentForPaaS'] | [0].id" \
  --raw-output 2>/dev/null)
[[ -z "$COMPARTMENT_ID" || "$COMPARTMENT_ID" == "None" ]] && COMPARTMENT_ID="$TENANCY_ID"
AD_LIST=$(oci iam availability-domain list \
  --compartment-id "$TENANCY_ID" \
  --output json 2>/dev/null | python3 -c "import json,sys
try:
    obj=json.load(sys.stdin)
    items=obj.get('data', []) if isinstance(obj, dict) else []
    names=[x.get('name','').strip() for x in items if isinstance(x, dict)]
    print('\\n'.join([n for n in names if n]))
except Exception:
    print('')")
AD_LIST="$(echo "$AD_LIST" | tr -d '\r' | sed '/^$/d')"
if [[ -z "$AD_LIST" ]]; then
  echo "ERROR: Could not list availability domains for tenancy $TENANCY_ID"
  exit 1
fi
echo "  Tenancy   : $TENANCY_ID"
echo "  Compartment: $COMPARTMENT_ID"
echo "  ADs:"
while read -r AD_NAME; do
  [[ -n "$AD_NAME" ]] && echo "    - $AD_NAME"
done <<< "$AD_LIST"

# ---- 3. Image ----
echo "[3/7] Finding Ubuntu images for fallback shapes..."
IMAGE_ID_A1=$(oci compute image list \
  --compartment-id "$TENANCY_ID" \
  --operating-system "Canonical Ubuntu" \
  --operating-system-version "22.04" \
  --shape "VM.Standard.A1.Flex" \
  --sort-by TIMECREATED --sort-order DESC \
  --query "data[0].id" --raw-output 2>/dev/null || true)

IMAGE_ID_E2=$(oci compute image list \
  --compartment-id "$TENANCY_ID" \
  --operating-system "Canonical Ubuntu" \
  --operating-system-version "22.04" \
  --shape "VM.Standard.E2.1.Micro" \
  --sort-by TIMECREATED --sort-order DESC \
  --query "data[0].id" --raw-output 2>/dev/null || true)

echo "  A1 image: $IMAGE_ID_A1"
echo "  E2 image: $IMAGE_ID_E2"

# ---- 4. Subnet ----
echo "[4/7] Finding default subnet..."
VCN_ID=$(oci network vcn list --all \
  --compartment-id "$COMPARTMENT_ID" \
  --lifecycle-state AVAILABLE \
  --query "data[0].id" --raw-output 2>/dev/null || true)

if [[ -z "$VCN_ID" || "$VCN_ID" == "None" ]]; then
  echo "  No VCN found. Creating one..."
  VCN_JSON=$(oci network vcn create \
    --compartment-id "$COMPARTMENT_ID" \
    --cidr-block "10.0.0.0/16" \
    --display-name "${VM_DISPLAY_NAME}-vcn" \
    --dns-label "lnkbotvcn" \
    --wait-for-state AVAILABLE \
    --max-wait-seconds 180)
  VCN_ID=$(echo "$VCN_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

  RT_ID=$(echo "$VCN_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['default-route-table-id'])")
  SEC_LIST_ID=$(echo "$VCN_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['default-security-list-id'])")

  IGW_ID=$(oci network internet-gateway create \
    --compartment-id "$COMPARTMENT_ID" \
    --vcn-id "$VCN_ID" \
    --display-name "${VM_DISPLAY_NAME}-igw" \
    --is-enabled true \
    --wait-for-state AVAILABLE \
    --max-wait-seconds 120 \
    --query "data.id" --raw-output)

  oci network route-table update \
    --rt-id "$RT_ID" \
    --route-rules "[{\"cidrBlock\":\"0.0.0.0/0\",\"networkEntityId\":\"$IGW_ID\"}]" \
    --force >/dev/null

  SUBNET_ID=$(oci network subnet create \
    --compartment-id "$COMPARTMENT_ID" \
    --vcn-id "$VCN_ID" \
    --cidr-block "10.0.1.0/24" \
    --display-name "${VM_DISPLAY_NAME}-subnet" \
    --dns-label "lnkbotsn" \
    --prohibit-public-ip-on-vnic false \
    --security-list-ids "[\"$SEC_LIST_ID\"]" \
    --route-table-id "$RT_ID" \
    --wait-for-state AVAILABLE \
    --max-wait-seconds 180 \
    --query "data.id" --raw-output)
else
  SUBNET_ID=$(oci network subnet list --all \
    --compartment-id "$COMPARTMENT_ID" \
    --vcn-id "$VCN_ID" \
    --lifecycle-state AVAILABLE \
    --query "data[0].id" --raw-output 2>/dev/null || true)

  if [[ -z "$SUBNET_ID" || "$SUBNET_ID" == "None" ]]; then
    echo "  VCN found but no subnet. Creating subnet..."
    RT_ID=$(oci network vcn get --vcn-id "$VCN_ID" --query "data.\"default-route-table-id\"" --raw-output)
    SEC_LIST_ID=$(oci network vcn get --vcn-id "$VCN_ID" --query "data.\"default-security-list-id\"" --raw-output)
    SUBNET_ID=$(oci network subnet create \
      --compartment-id "$COMPARTMENT_ID" \
      --vcn-id "$VCN_ID" \
      --cidr-block "10.0.1.0/24" \
      --display-name "${VM_DISPLAY_NAME}-subnet" \
      --dns-label "lnkbotsn" \
      --prohibit-public-ip-on-vnic false \
      --security-list-ids "[\"$SEC_LIST_ID\"]" \
      --route-table-id "$RT_ID" \
      --wait-for-state AVAILABLE \
      --max-wait-seconds 180 \
      --query "data.id" --raw-output)
  fi
fi

if [[ -z "$SUBNET_ID" || "$SUBNET_ID" == "None" ]]; then
  echo "ERROR: Failed to resolve or create subnet."
  exit 1
fi

SEC_LIST_ID=$(oci network subnet get --subnet-id "$SUBNET_ID" \
  --query "data.\"security-list-ids\"[0]" --raw-output 2>/dev/null || true)
[[ -z "$SEC_LIST_ID" || "$SEC_LIST_ID" == "None" ]] && \
  SEC_LIST_ID=$(oci network vcn get --vcn-id "$VCN_ID" --query "data.\"default-security-list-id\"" --raw-output)

echo "  VCN: $VCN_ID"
echo "  Subnet: $SUBNET_ID"

# ---- 5. Launch VM ----
echo "[5/7] Creating VM instance (~2 min)..."
INSTANCE_JSON=""
INSTANCE_ID=""
SELECTED_AD=""
SELECTED_CFG=""
SELECTED_SHAPE=""

# Try requested A1 first, then E2 micro early (often available), then smaller A1 sizes.
declare -a LAUNCH_CANDIDATES=()
if [[ -n "$IMAGE_ID_A1" && "$IMAGE_ID_A1" != "None" ]]; then
  LAUNCH_CANDIDATES+=("VM.Standard.A1.Flex|${OCPUS}|${MEMORY_GB}|$IMAGE_ID_A1|with-shape-config")
fi
if [[ -n "$IMAGE_ID_E2" && "$IMAGE_ID_E2" != "None" ]]; then
  LAUNCH_CANDIDATES+=("VM.Standard.E2.1.Micro|0|0|$IMAGE_ID_E2|no-shape-config")
fi
if [[ -n "$IMAGE_ID_A1" && "$IMAGE_ID_A1" != "None" ]]; then
  [[ "${OCPUS}:${MEMORY_GB}" != "1:4" ]] && LAUNCH_CANDIDATES+=("VM.Standard.A1.Flex|1|4|$IMAGE_ID_A1|with-shape-config")
  [[ "${OCPUS}:${MEMORY_GB}" != "1:2" ]] && LAUNCH_CANDIDATES+=("VM.Standard.A1.Flex|1|2|$IMAGE_ID_A1|with-shape-config")
fi

if [[ ${#LAUNCH_CANDIDATES[@]} -eq 0 ]]; then
  echo "ERROR: No compatible Ubuntu images found for A1 or E2 shapes."
  exit 1
fi

for CAND in "${LAUNCH_CANDIDATES[@]}"; do
  C_SHAPE="$(echo "$CAND" | cut -d'|' -f1)"
  C_OCPUS="$(echo "$CAND" | cut -d'|' -f2)"
  C_MEM="$(echo "$CAND" | cut -d'|' -f3)"
  C_IMAGE="$(echo "$CAND" | cut -d'|' -f4)"
  C_MODE="$(echo "$CAND" | cut -d'|' -f5)"

  while read -r TRY_AD; do
    [[ -z "$TRY_AD" ]] && continue
    if [[ "$C_MODE" == "with-shape-config" ]]; then
      echo "  Trying AD=$TRY_AD, shape=$C_SHAPE, ocpus=$C_OCPUS, mem=${C_MEM}GB..."
    else
      echo "  Trying AD=$TRY_AD, shape=$C_SHAPE..."
    fi

    set +e
    if [[ "$C_MODE" == "with-shape-config" ]]; then
      LAUNCH_OUTPUT=$(oci compute instance launch \
        --availability-domain "$TRY_AD" \
        --compartment-id "$COMPARTMENT_ID" \
        --display-name "$VM_DISPLAY_NAME" \
        --image-id "$C_IMAGE" \
        --shape "$C_SHAPE" \
        --shape-config "{\"ocpus\":$C_OCPUS,\"memoryInGBs\":$C_MEM}" \
        --subnet-id "$SUBNET_ID" \
        --assign-public-ip true \
        --ssh-authorized-keys-file "${KEY_PATH}.pub" \
        --wait-for-state RUNNING \
        --max-wait-seconds 420 \
        --query "data.id" --raw-output 2>&1)
    else
      LAUNCH_OUTPUT=$(oci compute instance launch \
        --availability-domain "$TRY_AD" \
        --compartment-id "$COMPARTMENT_ID" \
        --display-name "$VM_DISPLAY_NAME" \
        --image-id "$C_IMAGE" \
        --shape "$C_SHAPE" \
        --subnet-id "$SUBNET_ID" \
        --assign-public-ip true \
        --ssh-authorized-keys-file "${KEY_PATH}.pub" \
        --wait-for-state RUNNING \
        --max-wait-seconds 420 \
        --query "data.id" --raw-output 2>&1)
    fi
    LAUNCH_RC=$?
    set -e

    if [[ $LAUNCH_RC -eq 0 ]]; then
      INSTANCE_JSON="$LAUNCH_OUTPUT"
      INSTANCE_ID=$(echo "$LAUNCH_OUTPUT" | grep -o 'ocid1.instance[^"[:space:]]*' | head -1)
      INSTANCE_ID="$(echo "$INSTANCE_ID" | tr -d '\r\n[:space:]')"
      if [[ -z "$INSTANCE_ID" || "$INSTANCE_ID" != ocid1.instance.* ]]; then
        echo "$LAUNCH_OUTPUT"
        echo "ERROR: VM created but could not parse instance OCID from launch output."
        exit 1
      fi
      SELECTED_AD="$TRY_AD"
      SELECTED_SHAPE="$C_SHAPE"
      if [[ "$C_MODE" == "with-shape-config" ]]; then
        SELECTED_CFG="${C_OCPUS} OCPU / ${C_MEM}GB"
      else
        SELECTED_CFG="default"
      fi
      break 2
    fi

    if echo "$LAUNCH_OUTPUT" | grep -qi "Out of host capacity"; then
      if [[ "$C_MODE" == "with-shape-config" ]]; then
        echo "    Capacity unavailable in AD=$TRY_AD for $C_SHAPE ${C_OCPUS}/${C_MEM}. Trying next option..."
      else
        echo "    Capacity unavailable in AD=$TRY_AD for $C_SHAPE. Trying next option..."
      fi
      continue
    fi

    echo "$LAUNCH_OUTPUT"
    echo "ERROR: VM launch failed with non-capacity error."
    exit 1
  done <<< "$AD_LIST"
done

if [[ -z "$INSTANCE_JSON" ]]; then
  echo "ERROR: No host capacity found in any AD for A1 or E2 fallback shapes."
  echo "Tried candidates: ${LAUNCH_CANDIDATES[*]}"
  echo "Re-run later, or change region (e.g., eu-milan-1 / eu-amsterdam-1)."
  exit 1
fi

echo "  Selected AD/shape/config: $SELECTED_AD / $SELECTED_SHAPE / $SELECTED_CFG"
PUBLIC_IP=$(oci compute instance list-vnics \
  --instance-id "$INSTANCE_ID" \
  --query "data[0].\"public-ip\"" --raw-output)
echo "  VM IP: $PUBLIC_IP"

# ---- 6. Open SSH port ----
echo "[6/7] Ensuring port 22 open..."
oci network security-list update \
  --security-list-id "$SEC_LIST_ID" \
  --ingress-security-rules '[{"source":"0.0.0.0/0","protocol":"6","isStateless":false,"tcpOptions":{"destinationPortRange":{"min":22,"max":22}}}]' \
  --force 2>/dev/null || true
echo "Waiting 60s for SSH..."
sleep 60

# ---- 7. Install bot ----
echo "[7/7] Installing bot on VM..."
SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=30 -i $KEY_PATH ubuntu@$PUBLIC_IP"

$SSH "mkdir -p ~/cv_portofolio/linkedin_bot/oracle ~/cv_portofolio/linkedin_bot/logs"

echo '  Uploading files...'
printf '%s' 'ZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucw0KDQpmcm9tIGRhdGFjbGFzc2VzIGltcG9ydCBhc2RpY3QNCmZyb20gZGF0ZXRpbWUgaW1wb3J0IGRhdGV0aW1lLCB0aW1lem9uZQ0KaW1wb3J0IGpzb24NCmZyb20gcGF0aGxpYiBpbXBvcnQgUGF0aA0KaW1wb3J0IHJhbmRvbQ0KaW1wb3J0IHJlDQppbXBvcnQgdGltZQ0KZnJvbSB0eXBpbmcgaW1wb3J0IEFueQ0KZnJvbSB1cmxsaWIucGFyc2UgaW1wb3J0IHF1b3RlX3BsdXMNCg0KZnJvbSBwbGF5d3JpZ2h0LnN5bmNfYXBpIGltcG9ydCBzeW5jX3BsYXl3cmlnaHQsIFRpbWVvdXRFcnJvciBhcyBQbGF5d3JpZ2h0VGltZW91dEVycm9yDQoNCmZyb20gY29uZmlnIGltcG9ydCBSdW50aW1lQ29uZmlnDQoNCg0KY2xhc3MgTGlua2VkSW5BdXRvQXBwbHlCb3Q6DQogICAgZGVmIF9faW5pdF9fKHNlbGYsIGNvbmZpZzogUnVudGltZUNvbmZpZywgKiwgZHJ5X3J1bjogYm9vbCA9IEZhbHNlLCByZXN1bWU6IGJvb2wgPSBGYWxzZSwgbGltaXQ6IGludCB8IE5vbmUgPSBOb25lKToNCiAgICAgICAgc2VsZi5jb25maWcgPSBjb25maWcNCiAgICAgICAgc2VsZi5kcnlfcnVuID0gZHJ5X3J1bg0KICAgICAgICBzZWxmLnJlc3VtZSA9IHJlc3VtZQ0KICAgICAgICBzZWxmLmxpbWl0ID0gbGltaXQgb3IgY29uZmlnLnNldHRpbmdzLm1heF9hcHBsaWNhdGlvbnNfcGVyX3J1bg0KDQogICAgICAgIHNlbGYuYXBwbGllZF9qb2JzID0gc2VsZi5fcmVhZF9qc29uKGNvbmZpZy5wYXRocy5hcHBsaWVkX2xvZywgZGVmYXVsdD1bXSkNCiAgICAgICAgc2VsZi5zdGF0ZSA9IHNlbGYuX3JlYWRfanNvbihjb25maWcucGF0aHMuc3RhdGVfcGF0aCwgZGVmYXVsdD17ImNvbWJvX2luZGV4IjogMCwgImpvYl9vZmZzZXQiOiAwfSkNCg0KICAgICAgICBzZWxmLnN0YXRzOiBkaWN0W3N0ciwgaW50XSA9IHsNCiAgICAgICAgICAgICJzY2FubmVkIjogMCwNCiAgICAgICAgICAgICJzdWJtaXR0ZWQiOiAwLA0KICAgICAgICAgICAgInNraXBwZWQiOiAwLA0KICAgICAgICAgICAgImRyeV9ydW4iOiAwLA0KICAgICAgICAgICAgIm1hbnVhbF9yZXF1aXJlZCI6IDAsDQogICAgICAgICAgICAiZmFpbHVyZXMiOiAwLA0KICAgICAgICB9DQoNCiAgICBkZWYgcnVuKHNlbGYpIC0+IGRpY3Rbc3RyLCBBbnldOg0KICAgICAgICBzdGFydCA9IGRhdGV0aW1lLm5vdyh0aW1lem9uZS51dGMpLmlzb2Zvcm1hdCgpDQoNCiAgICAgICAgIyBGaXJzdCBydW46IGlmIG5vIHNhdmVkIHNlc3Npb24sIGZvcmNlIGEgdmlzaWJsZSBicm93c2VyIGxvZ2luIHNvIExpbmtlZEluDQogICAgICAgICMgcmVuZGVycyB0aGUgcmVhbCBmb3JtIChoZWFkbGVzcyBpcyBkZXRlY3RlZCBhbmQgYmxvY2tlZCBieSBMaW5rZWRJbikuDQogICAgICAgIHJ1bl9oZWFkbGVzcyA9IHNlbGYuY29uZmlnLnNldHRpbmdzLmhlYWRsZXNzDQogICAgICAgIGlmIG5vdCBzZWxmLmNvbmZpZy5wYXRocy5icm93c2VyX3N0YXRlX3BhdGguZXhpc3RzKCk6DQogICAgICAgICAgICBydW5faGVhZGxlc3MgPSBGYWxzZSAgIyBNdXN0IHNob3cgYnJvd3NlciB0byBwYXNzIExpbmtlZEluIGFudGktYm90IG9uIGZpcnN0IGxvZ2luDQoNCiAgICAgICAgd2l0aCBzeW5jX3BsYXl3cmlnaHQoKSBhcyBwOg0KICAgICAgICAgICAgYnJvd3NlciA9IHAuY2hyb21pdW0ubGF1bmNoKGhlYWRsZXNzPXJ1bl9oZWFkbGVzcykNCiAgICAgICAgICAgIGNvbnRleHQgPSBicm93c2VyLm5ld19jb250ZXh0KA0KICAgICAgICAgICAgICAgIHN0b3JhZ2Vfc3RhdGU9c3RyKHNlbGYuY29uZmlnLnBhdGhzLmJyb3dzZXJfc3RhdGVfcGF0aCkNCiAgICAgICAgICAgICAgICBpZiBzZWxmLmNvbmZpZy5wYXRocy5icm93c2VyX3N0YXRlX3BhdGguZXhpc3RzKCkNCiAgICAgICAgICAgICAgICBlbHNlIE5vbmUNCiAgICAgICAgICAgICkNCiAgICAgICAgICAgIHBhZ2UgPSBjb250ZXh0Lm5ld19wYWdlKCkNCg0KICAgICAgICAgICAgdHJ5Og0KICAgICAgICAgICAgICAgIHNlbGYuX2xvZ2luKHBhZ2UpDQogICAgICAgICAgICAgICAgIyBSZXNldCBkYWlseSBzdGF0ZSBjdXJzb3IgdW5sZXNzIHJlc3VtaW5nDQogICAgICAgICAgICAgICAgaWYgbm90IHNlbGYucmVzdW1lOg0KICAgICAgICAgICAgICAgICAgICBzZWxmLnN0YXRlID0geyJjb21ib19pbmRleCI6IDAsICJqb2Jfb2Zmc2V0IjogMH0NCiAgICAgICAgICAgICAgICBzZWxmLl9wcm9jZXNzX3NlYXJjaF9jb21iaW5hdGlvbnMocGFnZSkNCiAgICAgICAgICAgIGZpbmFsbHk6DQogICAgICAgICAgICAgICAgY29udGV4dC5zdG9yYWdlX3N0YXRlKHBhdGg9c3RyKHNlbGYuY29uZmlnLnBhdGhzLmJyb3dzZXJfc3RhdGVfcGF0aCkpDQogICAgICAgICAgICAgICAgY29udGV4dC5jbG9zZSgpDQogICAgICAgICAgICAgICAgYnJvd3Nlci5jbG9zZSgpDQoNCiAgICAgICAgZW5kID0gZGF0ZXRpbWUubm93KHRpbWV6b25lLnV0YykuaXNvZm9ybWF0KCkNCg0KICAgICAgICBydW5fcmVzdWx0ID0gew0KICAgICAgICAgICAgInN0YXJ0ZWRfYXQiOiBzdGFydCwNCiAgICAgICAgICAgICJlbmRlZF9hdCI6IGVuZCwNCiAgICAgICAgICAgICJkcnlfcnVuIjogc2VsZi5kcnlfcnVuLA0KICAgICAgICAgICAgInJlc3VtZSI6IHNlbGYucmVzdW1lLA0KICAgICAgICAgICAgImxpbWl0Ijogc2VsZi5saW1pdCwNCiAgICAgICAgICAgICJzdGF0cyI6IHNlbGYuc3RhdHMsDQogICAgICAgIH0NCiAgICAgICAgc2VsZi5fYXBwZW5kX3J1bl9oaXN0b3J5KHJ1bl9yZXN1bHQpDQogICAgICAgIHJldHVybiBydW5fcmVzdWx0DQoNCiAgICBkZWYgX2xvZ2luKHNlbGYsIHBhZ2UpIC0+IE5vbmU6DQogICAgICAgIHBhZ2UuZ290bygiaHR0cHM6Ly93d3cubGlua2VkaW4uY29tL2ZlZWQvIiwgd2FpdF91bnRpbD0iZG9tY29udGVudGxvYWRlZCIpDQogICAgICAgIHBhZ2Uud2FpdF9mb3JfdGltZW91dCgyMDAwKQ0KICAgICAgICAjIEFscmVhZHkgbG9nZ2VkIGluIGlmIGFueSBhdXRoZW50aWNhdGVkIExpbmtlZEluIHBhZ2UgaXMgc2hvd24NCiAgICAgICAgaWYgc2VsZi5faXNfYXV0aGVudGljYXRlZChwYWdlKToNCiAgICAgICAgICAgIHJldHVybg0KDQogICAgICAgICMgU2Vzc2lvbiBleHBpcmVkIOKAlCBkZWxldGUgc3RhbGUgc3RhdGUgZmlsZSBzbyBuZXh0IG1hbnVhbCBydW4gcmVidWlsZHMgaXQNCiAgICAgICAgaWYgc2VsZi5jb25maWcucGF0aHMuYnJvd3Nlcl9zdGF0ZV9wYXRoLmV4aXN0cygpOg0KICAgICAgICAgICAgc2VsZi5jb25maWcucGF0aHMuYnJvd3Nlcl9zdGF0ZV9wYXRoLnVubGluaygpDQogICAgICAgICAgICByYWlzZSBSdW50aW1lRXJyb3IoDQogICAgICAgICAgICAgICAgIkxpbmtlZEluIHNlc3Npb24gZXhwaXJlZC4gUnVuIG9uY2UgbWFudWFsbHkgKHdpdGhvdXQgLS1oZWFkbGVzcykgdG8gbG9nIGluIGFnYWluOlxuIg0KICAgICAgICAgICAgICAgICIgIGQ6XFxjdl9wb3J0b2ZvbGlvXFwudmVudlxcU2NyaXB0c1xccHl0aG9uLmV4ZSBtYWluLnB5IC0tbGltaXQgMVxuIg0KICAgICAgICAgICAgICAgICJUaGVuIHRoZSBzY2hlZHVsZWQgdGFzayB3aWxsIHJlc3VtZSBhdXRvbWF0aWNhbGx5LiINCiAgICAgICAgICAgICkNCg0KDQogICAgICAgICMgQWNjZXB0IGNvb2tpZSBjb25zZW50IGlmIHByZXNlbnQgKGl0IGJsb2NrcyBmb3JtIHJlbmRlcmluZykNCiAgICAgICAgdHJ5Og0KICAgICAgICAgICAgY29uc2VudF9idG4gPSBwYWdlLmxvY2F0b3IoImJ1dHRvblthY3Rpb24tdHlwZT0nQUNDRVBUJ10iKQ0KICAgICAgICAgICAgaWYgY29uc2VudF9idG4uY291bnQoKSA+IDA6DQogICAgICAgICAgICAgICAgY29uc2VudF9idG4uZmlyc3QuY2xpY2sodGltZW91dD01MDAwKQ0KICAgICAgICAgICAgICAgIHBhZ2Uud2FpdF9mb3JfdGltZW91dCgxMDAwKQ0KICAgICAgICBleGNlcHQgRXhjZXB0aW9uOg0KICAgICAgICAgICAgcGFzcw0KDQogICAgICAgICMgTmF2aWdhdGUgZGlyZWN0bHkgdG8gL2xvZ2luDQogICAgICAgIHBhZ2UuZ290bygiaHR0cHM6Ly93d3cubGlua2VkaW4uY29tL2xvZ2luIiwgd2FpdF91bnRpbD0iZG9tY29udGVudGxvYWRlZCIpDQogICAgICAgIHBhZ2Uud2FpdF9mb3JfdGltZW91dCgyMDAwKQ0KDQogICAgICAgICMgQWNjZXB0IGNvb2tpZSBjb25zZW50IG9uIGxvZ2luIHBhZ2UgaWYgc2hvd24NCiAgICAgICAgdHJ5Og0KICAgICAgICAgICAgY29uc2VudF9idG4gPSBwYWdlLmxvY2F0b3IoImJ1dHRvblthY3Rpb24tdHlwZT0nQUNDRVBUJ10iKQ0KICAgICAgICAgICAgaWYgY29uc2VudF9idG4uY291bnQoKSA+IDA6DQogICAgICAgICAgICAgICAgY29uc2VudF9idG4uZmlyc3QuY2xpY2sodGltZW91dD01MDAwKQ0KICAgICAgICAgICAgICAgIHBhZ2Uud2FpdF9mb3JfdGltZW91dCgxMDAwKQ0KICAgICAgICBleGNlcHQgRXhjZXB0aW9uOg0KICAgICAgICAgICAgcGFzcw0KDQogICAgICAgIHBhZ2Uud2FpdF9mb3JfdGltZW91dCgyMDAwKQ0KDQogICAgICAgIGVtYWlsX29rID0gc2VsZi5faHVtYW5fdHlwZV9maXJzdCgNCiAgICAgICAgICAgIHBhZ2UsDQogICAgICAgICAgICBbIiN1c2VybmFtZSIsICJpbnB1dFtuYW1lPSdzZXNzaW9uX2tleSddW3R5cGU9J3RleHQnXSIsICJpbnB1dFthdXRvY29tcGxldGU9J3VzZXJuYW1lJ10iLCAiaW5wdXRbdHlwZT0nZW1haWwnXSJdLA0KICAgICAgICAgICAgc2VsZi5jb25maWcuZW1haWwsDQogICAgICAgICkNCiAgICAgICAgcGFzc3dvcmRfb2sgPSBzZWxmLl9odW1hbl90eXBlX2ZpcnN0KA0KICAgICAgICAgICAgcGFnZSwNCiAgICAgICAgICAgIFsiI3Bhc3N3b3JkIiwgImlucHV0W25hbWU9J3Nlc3Npb25fcGFzc3dvcmQnXSIsICJpbnB1dFt0eXBlPSdwYXNzd29yZCddIl0sDQogICAgICAgICAgICBzZWxmLmNvbmZpZy5wYXNzd29yZCwNCiAgICAgICAgKQ0KDQogICAgICAgIGlmIG5vdCBlbWFpbF9vayBvciBub3QgcGFzc3dvcmRfb2s6DQogICAgICAgICAgICBpZiBzZWxmLl9pc19zZWN1cml0eV9jaGFsbGVuZ2UocGFnZSk6DQogICAgICAgICAgICAgICAgc2VsZi5fd3JpdGVfc3RhdGUoKQ0KICAgICAgICAgICAgICAgIHJhaXNlIFJ1bnRpbWVFcnJvcigNCiAgICAgICAgICAgICAgICAgICAgZiJMaW5rZWRJbiBzZWN1cml0eSBjaGFsbGVuZ2UgKDJGQS9DQVBUQ0hBKSBkZXRlY3RlZCBhdCB7cGFnZS51cmx9LiBSZXNvbHZlIG1hbnVhbGx5IGFuZCByZXJ1biB3aXRoIC0tcmVzdW1lLiINCiAgICAgICAgICAgICAgICApDQogICAgICAgICAgICBkZWJ1Z19wYXRoID0gc2VsZi5fc2F2ZV9kZWJ1Z19hcnRpZmFjdHMocGFnZSwgImxvZ2luX2Zvcm1fbWlzc2luZyIpDQogICAgICAgICAgICByYWlzZSBSdW50aW1lRXJyb3IoDQogICAgICAgICAgICAgICAgZiJDb3VsZCBub3QgbG9jYXRlIExpbmtlZEluIGxvZ2luIGZvcm0gZmllbGRzLiBQYWdlOiB7cGFnZS51cmx9LiBEZWJ1ZyBzYXZlZCBhdCB7ZGVidWdfcGF0aH0uIg0KICAgICAgICAgICAgKQ0KDQogICAgICAgIHBhZ2UuY2xpY2soImJ1dHRvblt0eXBlPSdzdWJtaXQnXSIpDQogICAgICAgIHBhZ2Uud2FpdF9mb3JfdGltZW91dCgzMDAwKQ0KDQogICAgICAgIGlmIHNlbGYuX2lzX3NlY3VyaXR5X2NoYWxsZW5nZShwYWdlKToNCiAgICAgICAgICAgIHNlbGYuX3dyaXRlX3N0YXRlKCkNCiAgICAgICAgICAgIHJhaXNlIFJ1bnRpbWVFcnJvcigNCiAgICAgICAgICAgICAgICAiTGlua2VkSW4gc2VjdXJpdHkgY2hhbGxlbmdlICgyRkEvQ0FQVENIQSkgZGV0ZWN0ZWQuIFJlc29sdmUgbWFudWFsbHkgYW5kIHJlcnVuIHdpdGggLS1yZXN1bWUuIg0KICAgICAgICAgICAgKQ0KDQogICAgZGVmIF9maW5kX2FwcGx5X2J1dHRvbihzZWxmLCBwYWdlKToNCiAgICAgICAgIiIiRmluZCBhcHBseS9lYXN5IGFwcGx5IGVsZW1lbnQgKGJ1dHRvbiBvciBhbmNob3IgbGluaykgdXNpbmcgdGV4dCBhbmQgYXJpYSBhdHRyaWJ1dGVzLiIiIg0KICAgICAgICAjIExpbmtlZEluJ3MgRWFzeSBBcHBseSBpcyByZW5kZXJlZCBhcyBhbiA8YT4gdGFnIHdpdGggYXJpYS1sYWJlbA0KICAgICAgICBmb3Igc2VsZWN0b3IgaW4gWw0KICAgICAgICAgICAgImFbYXJpYS1sYWJlbCo9J0Vhc3kgQXBwbHknXSIsDQogICAgICAgICAgICAiYTpoYXMtdGV4dCgnRWFzeSBBcHBseScpIiwNCiAgICAgICAgICAgICJhW2FyaWEtbGFiZWwqPSdlYXN5IGFwcGx5J10iLA0KICAgICAgICAgICAgImJ1dHRvbjpoYXMtdGV4dCgnRWFzeSBBcHBseScpIiwNCiAgICAgICAgICAgICJidXR0b25bYXJpYS1sYWJlbCo9J0Vhc3kgQXBwbHknXSIsDQogICAgICAgICAgICAiYnV0dG9uOmhhcy10ZXh0KCdBcHBseScpIiwNCiAgICAgICAgICAgICJidXR0b25bYXJpYS1sYWJlbCo9J0FwcGx5J10iLA0KICAgICAgICAgICAgImFbaHJlZio9J29wZW5TRFVJQXBwbHlGbG93J10iLA0KICAgICAgICBdOg0KICAgICAgICAgICAgdHJ5Og0KICAgICAgICAgICAgICAgIGVsID0gcGFnZS5xdWVyeV9zZWxlY3RvcihzZWxlY3RvcikNCiAgICAgICAgICAgICAgICBpZiBlbDoNCiAgICAgICAgICAgICAgICAgICAgcmV0dXJuIGVsDQogICAgICAgICAgICBleGNlcHQgRXhjZXB0aW9uOg0KICAgICAgICAgICAgICAgIGNvbnRpbnVlDQoNCiAgICAgICAgIyBGYWxsYmFjazogc2NhbiBidXR0b25zIGFuZCBhbmNob3JzIGZvciBhcHBseSB0ZXh0DQogICAgICAgIGZvciBlbCBpbiBwYWdlLnF1ZXJ5X3NlbGVjdG9yX2FsbCgiYnV0dG9uLCBhIik6DQogICAgICAgICAgICB0cnk6DQogICAgICAgICAgICAgICAgdHh0ID0gKGVsLmlubmVyX3RleHQoKSBvciAiIikuc3RyaXAoKS5sb3dlcigpDQogICAgICAgICAgICAgICAgYXJpYSA9IChlbC5nZXRfYXR0cmlidXRlKCJhcmlhLWxhYmVsIikgb3IgIiIpLmxvd2VyKCkNCiAgICAgICAgICAgICAgICBpZiAiYXBwbHkiIGluIHR4dCBvciAiYXBwbHkiIGluIGFyaWE6DQogICAgICAgICAgICAgICAgICAgIHJldHVybiBlbA0KICAgICAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjoNCiAgICAgICAgICAgICAgICBjb250aW51ZQ0KDQogICAgICAgIHJldHVybiBOb25lDQoNCiAgICBkZWYgX2dldF9lYXN5X2FwcGx5X3VybChzZWxmLCBwYWdlKSAtPiBzdHIgfCBOb25lOg0KICAgICAgICAiIiJHZXQgdGhlIEVhc3kgQXBwbHkgZmxvdyBVUkwgZGlyZWN0bHkgZnJvbSB0aGUgcGFnZSBhbmNob3IgaHJlZi4iIiINCiAgICAgICAgZm9yIHNlbGVjdG9yIGluIFsNCiAgICAgICAgICAgICJhW2FyaWEtbGFiZWwqPSdFYXN5IEFwcGx5J10iLA0KICAgICAgICAgICAgImFbaHJlZio9J29wZW5TRFVJQXBwbHlGbG93J10iLA0KICAgICAgICAgICAgImE6aGFzLXRleHQoJ0Vhc3kgQXBwbHknKSIsDQogICAgICAgIF06DQogICAgICAgICAgICB0cnk6DQogICAgICAgICAgICAgICAgZWwgPSBwYWdlLnF1ZXJ5X3NlbGVjdG9yKHNlbGVjdG9yKQ0KICAgICAgICAgICAgICAgIGlmIGVsOg0KICAgICAgICAgICAgICAgICAgICBocmVmID0gZWwuZ2V0X2F0dHJpYnV0ZSgiaHJlZiIpIG9yICIiDQogICAgICAgICAgICAgICAgICAgIGlmIGhyZWYuc3RhcnRzd2l0aCgiLyIpOg0KICAgICAgICAgICAgICAgICAgICAgICAgaHJlZiA9ICJodHRwczovL3d3dy5saW5rZWRpbi5jb20iICsgaHJlZg0KICAgICAgICAgICAgICAgICAgICByZXR1cm4gaHJlZiBvciBOb25lDQogICAgICAgICAgICBleGNlcHQgRXhjZXB0aW9uOg0KICAgICAgICAgICAgICAgIGNvbnRpbnVlDQogICAgICAgIHJldHVybiBOb25lDQoNCiAgICBkZWYgX2lzX2F1dGhlbnRpY2F0ZWQoc2VsZiwgcGFnZSkgLT4gYm9vbDoNCiAgICAgICAgdXJsID0gcGFnZS51cmwubG93ZXIoKQ0KICAgICAgICBhdXRoZW50aWNhdGVkX2luZGljYXRvcnMgPSBbDQogICAgICAgICAgICAibGlua2VkaW4uY29tL2ZlZWQiLA0KICAgICAgICAgICAgImxpbmtlZGluLmNvbS9qb2JzIiwNCiAgICAgICAgICAgICJsaW5rZWRpbi5jb20vbXluZXR3b3JrIiwNCiAgICAgICAgICAgICJsaW5rZWRpbi5jb20vbWVzc2FnaW5nIiwNCiAgICAgICAgICAgICJsaW5rZWRpbi5jb20vbm90aWZpY2F0aW9ucyIsDQogICAgICAgICAgICAibGlua2VkaW4uY29tL2luLyIsDQogICAgICAgIF0NCiAgICAgICAgaWYgYW55KHRva2VuIGluIHVybCBmb3IgdG9rZW4gaW4gYXV0aGVudGljYXRlZF9pbmRpY2F0b3JzKToNCiAgICAgICAgICAgICMgQWRkaXRpb25hbCBjaGVjazogbG9naW4gcGFnZXMgc2hvdWxkIG5vdCBjb250YWluIHRoZXNlDQogICAgICAgICAgICBpZiAibGlua2VkaW4uY29tL2xvZ2luIiBub3QgaW4gdXJsIGFuZCAibGlua2VkaW4uY29tL2F1dGh3YWxsIiBub3QgaW4gdXJsOg0KICAgICAgICAgICAgICAgIHJldHVybiBUcnVlDQogICAgICAgIHJldHVybiBGYWxzZQ0KDQoNCiAgICBkZWYgX2lzX3NlY3VyaXR5X2NoYWxsZW5nZShzZWxmLCBwYWdlKSAtPiBib29sOg0KICAgICAgICB1cmwgPSBwYWdlLnVybC5sb3dlcigpDQogICAgICAgIGlmIGFueSh0b2tlbiBpbiB1cmwgZm9yIHRva2VuIGluIFsiY2hlY2twb2ludCIsICJjaGFsbGVuZ2UiLCAiY2FwdGNoYSIsICJ2ZXJpZnkiLCAic2VjdXJpdHkiXSk6DQogICAgICAgICAgICByZXR1cm4gVHJ1ZQ0KDQogICAgICAgIHRyeToNCiAgICAgICAgICAgIGJvZHlfdGV4dCA9IChwYWdlLmlubmVyX3RleHQoImJvZHkiKSBvciAiIikubG93ZXIoKQ0KICAgICAgICBleGNlcHQgRXhjZXB0aW9uOg0KICAgICAgICAgICAgYm9keV90ZXh0ID0gIiINCg0KICAgICAgICBjaGFsbGVuZ2VfbWFya2VycyA9IFsNCiAgICAgICAgICAgICJzZWN1cml0eSBjaGVjayIsDQogICAgICAgICAgICAidmVyaWZ5IGl0J3MgeW91IiwNCiAgICAgICAgICAgICJ2ZXJpZnkgaXQgaXMgeW91IiwNCiAgICAgICAgICAgICJjYXB0Y2hhIiwNCiAgICAgICAgICAgICJ1bnVzdWFsIGFjdGl2aXR5IiwNCiAgICAgICAgICAgICJhcmUgeW91IGEgcm9ib3QiLA0KICAgICAgICAgICAgImNoYWxsZW5nZSIsDQogICAgICAgIF0NCiAgICAgICAgcmV0dXJuIGFueShtYXJrZXIgaW4gYm9keV90ZXh0IGZvciBtYXJrZXIgaW4gY2hhbGxlbmdlX21hcmtlcnMpDQoNCiAgICBkZWYgX3Byb2Nlc3Nfc2VhcmNoX2NvbWJpbmF0aW9ucyhzZWxmLCBwYWdlKSAtPiBOb25lOg0KICAgICAgICBjb21ib3MgPSBbKGssIGwpIGZvciBrIGluIHNlbGYuY29uZmlnLnNldHRpbmdzLmtleXdvcmRzIGZvciBsIGluIHNlbGYuY29uZmlnLnNldHRpbmdzLmxvY2F0aW9uc10NCiAgICAgICAgc3RhcnRfY29tYm8gPSBzZWxmLnN0YXRlLmdldCgiY29tYm9faW5kZXgiLCAwKSBpZiBzZWxmLnJlc3VtZSBlbHNlIDANCg0KICAgICAgICBmb3IgY29tYm9faW5kZXgsIChrZXl3b3JkLCBsb2NhdGlvbikgaW4gZW51bWVyYXRlKGNvbWJvc1tzdGFydF9jb21ibzpdLCBzdGFydD1zdGFydF9jb21ibyk6DQogICAgICAgICAgICBpZiBzZWxmLl9yZWFjaGVkX2xpbWl0KCk6DQogICAgICAgICAgICAgICAgYnJlYWsNCg0KICAgICAgICAgICAgam9iX3VybHMgPSBzZWxmLl9jb2xsZWN0X2pvYl91cmxzKHBhZ2UsIGtleXdvcmQsIGxvY2F0aW9uKQ0KICAgICAgICAgICAgaWYgbm90IGpvYl91cmxzOg0KICAgICAgICAgICAgICAgIGNvbnRpbnVlDQoNCiAgICAgICAgICAgIHN0YXJ0X29mZnNldCA9IHNlbGYuc3RhdGUuZ2V0KCJqb2Jfb2Zmc2V0IiwgMCkgaWYgKHNlbGYucmVzdW1lIGFuZCBjb21ib19pbmRleCA9PSBzdGFydF9jb21ibykgZWxzZSAwDQogICAgICAgICAgICBmb3Igam9iX29mZnNldCwgam9iX3VybCBpbiBlbnVtZXJhdGUoam9iX3VybHNbc3RhcnRfb2Zmc2V0Ol0sIHN0YXJ0PXN0YXJ0X29mZnNldCk6DQogICAgICAgICAgICAgICAgaWYgc2VsZi5fcmVhY2hlZF9saW1pdCgpOg0KICAgICAgICAgICAgICAgICAgICBzZWxmLnN0YXRlWyJjb21ib19pbmRleCJdID0gY29tYm9faW5kZXgNCiAgICAgICAgICAgICAgICAgICAgc2VsZi5zdGF0ZVsiam9iX29mZnNldCJdID0gam9iX29mZnNldA0KICAgICAgICAgICAgICAgICAgICBzZWxmLl93cml0ZV9zdGF0ZSgpDQogICAgICAgICAgICAgICAgICAgIHJldHVybg0KDQogICAgICAgICAgICAgICAgc2VsZi5zdGF0c1sic2Nhbm5lZCJdICs9IDENCiAgICAgICAgICAgICAgICBzZWxmLnN0YXRlWyJjb21ib19pbmRleCJdID0gY29tYm9faW5kZXgNCiAgICAgICAgICAgICAgICBzZWxmLnN0YXRlWyJqb2Jfb2Zmc2V0Il0gPSBqb2Jfb2Zmc2V0DQogICAgICAgICAgICAgICAgc2VsZi5fd3JpdGVfc3RhdGUoKQ0KDQogICAgICAgICAgICAgICAgam9iX2lkID0gc2VsZi5fZXh0cmFjdF9qb2JfaWQoam9iX3VybCkNCiAgICAgICAgICAgICAgICBpZiBzZWxmLl9hbHJlYWR5X3NlZW4oam9iX2lkKToNCiAgICAgICAgICAgICAgICAgICAgc2VsZi5zdGF0c1sic2tpcHBlZCJdICs9IDENCiAgICAgICAgICAgICAgICAgICAgY29udGludWUNCg0KICAgICAgICAgICAgICAgIHJlc3VsdCA9IHNlbGYuX3Byb2Nlc3Nfc2luZ2xlX2pvYihwYWdlLCBqb2JfdXJsLCBqb2JfaWQsIGxvY2F0aW9uKQ0KICAgICAgICAgICAgICAgIHNlbGYuX3JlY29yZF9qb2IocmVzdWx0KQ0KDQogICAgICAgIHNlbGYuc3RhdGVbImNvbWJvX2luZGV4Il0gPSAwDQogICAgICAgIHNlbGYuc3RhdGVbImpvYl9vZmZzZXQiXSA9IDANCiAgICAgICAgc2VsZi5fd3JpdGVfc3RhdGUoKQ0KDQogICAgZGVmIF9jb2xsZWN0X2pvYl91cmxzKHNlbGYsIHBhZ2UsIGtleXdvcmQ6IHN0ciwgbG9jYXRpb246IHN0cikgLT4gbGlzdFtzdHJdOg0KICAgICAgICBlbmNvZGVkX2tleXdvcmQgPSBxdW90ZV9wbHVzKGtleXdvcmQpDQogICAgICAgIGVuY29kZWRfbG9jYXRpb24gPSBxdW90ZV9wbHVzKGxvY2F0aW9uKQ0KICAgICAgICAjIGZfTEY9Zl9BTCBmaWx0ZXJzIGZvciBFYXN5IEFwcGx5IG9ubHkgdG8gbWF4aW1pc2UgYXV0by1zdWJtaXQgcmF0ZQ0KICAgICAgICBzZWFyY2hfdXJsID0gKA0KICAgICAgICAgICAgImh0dHBzOi8vd3d3LmxpbmtlZGluLmNvbS9qb2JzL3NlYXJjaC8iDQogICAgICAgICAgICBmIj9rZXl3b3Jkcz17ZW5jb2RlZF9rZXl3b3JkfSZsb2NhdGlvbj17ZW5jb2RlZF9sb2NhdGlvbn0iDQogICAgICAgICAgICBmIiZmX0xGPWZfQUwmZl9UUFI9cntzZWxmLmNvbmZpZy5zZXR0aW5ncy5wb3N0ZWRfZGF5c19hZ28gKiA4NjQwMH0iDQogICAgICAgICkNCg0KICAgICAgICBwYWdlLmdvdG8oc2VhcmNoX3VybCwgd2FpdF91bnRpbD0iZG9tY29udGVudGxvYWRlZCIpDQogICAgICAgIHNlbGYuX2h1bWFuX3BhdXNlKCkNCiAgICAgICAgc2VsZi5fcHJvZ3Jlc3NpdmVfc2Nyb2xsKHBhZ2UpDQoNCiAgICAgICAgIyBCcm9hZCBhbmNob3IgbWF0Y2gg4oCUIGpvYiBjYXJkcyB1c2UgbXVsdGlwbGUgbGluayBwYXR0ZXJucyBhY3Jvc3MgTGlua2VkSW4gdmVyc2lvbnMNCiAgICAgICAgYW5jaG9ycyA9IHBhZ2UucXVlcnlfc2VsZWN0b3JfYWxsKCJhIikNCiAgICAgICAgdXJsczogbGlzdFtzdHJdID0gW10NCiAgICAgICAgZm9yIGFuY2hvciBpbiBhbmNob3JzOg0KICAgICAgICAgICAgaHJlZiA9IGFuY2hvci5nZXRfYXR0cmlidXRlKCJocmVmIikNCiAgICAgICAgICAgIGlmIG5vdCBocmVmOg0KICAgICAgICAgICAgICAgIGNvbnRpbnVlDQogICAgICAgICAgICBpZiBocmVmLnN0YXJ0c3dpdGgoIi8iKToNCiAgICAgICAgICAgICAgICBocmVmID0gZiJodHRwczovL3d3dy5saW5rZWRpbi5jb217aHJlZn0iDQogICAgICAgICAgICBpZiAiL2pvYnMvdmlldy8iIGluIGhyZWY6DQogICAgICAgICAgICAgICAgY2xlYW4gPSBocmVmLnNwbGl0KCI/IilbMF0NCiAgICAgICAgICAgICAgICBpZiBjbGVhbiBub3QgaW4gdXJsczoNCiAgICAgICAgICAgICAgICAgICAgdXJscy5hcHBlbmQoY2xlYW4pDQoNCiAgICAgICAgcmV0dXJuIHVybHMNCg0KICAgIGRlZiBfcHJvY2Vzc19zaW5nbGVfam9iKHNlbGYsIHBhZ2UsIGpvYl91cmw6IHN0ciwgam9iX2lkOiBzdHIsIGxvY2F0aW9uOiBzdHIpIC0+IGRpY3Rbc3RyLCBBbnldOg0KICAgICAgICBmb3IgYXR0ZW1wdCBpbiByYW5nZShzZWxmLmNvbmZpZy5zZXR0aW5ncy5yZXRyaWVzX3Blcl9qb2IgKyAxKToNCiAgICAgICAgICAgIHRyeToNCiAgICAgICAgICAgICAgICBwYWdlLmdvdG8oam9iX3VybCwgd2FpdF91bnRpbD0iZG9tY29udGVudGxvYWRlZCIpDQogICAgICAgICAgICAgICAgc2VsZi5faHVtYW5fcGF1c2UoKQ0KDQogICAgICAgICAgICAgICAgdGl0bGUgPSBzZWxmLl90ZXh0X29yX2VtcHR5KHBhZ2UsICJoMSIpDQogICAgICAgICAgICAgICAgY29tcGFueSA9IChzZWxmLl90ZXh0X29yX2VtcHR5KHBhZ2UsICIuam9icy11bmlmaWVkLXRvcC1jYXJkX19jb21wYW55LW5hbWUiKQ0KICAgICAgICAgICAgICAgICAgICAgICAgICAgb3Igc2VsZi5fdGV4dF9vcl9lbXB0eShwYWdlLCAiYVtkYXRhLXRyYWNraW5nLWNvbnRyb2wtbmFtZSo9J2NvbXBhbnknXSIpDQogICAgICAgICAgICAgICAgICAgICAgICAgICBvciBzZWxmLl90ZXh0X29yX2VtcHR5KHBhZ2UsICIuam9iLWRldGFpbHMtam9icy11bmlmaWVkLXRvcC1jYXJkX19jb21wYW55LW5hbWUiKSkNCiAgICAgICAgICAgICAgICBwbGFjZSA9IChzZWxmLl90ZXh0X29yX2VtcHR5KHBhZ2UsICIuam9icy11bmlmaWVkLXRvcC1jYXJkX19idWxsZXQiKQ0KICAgICAgICAgICAgICAgICAgICAgICAgIG9yIHNlbGYuX3RleHRfb3JfZW1wdHkocGFnZSwgIi5qb2ItZGV0YWlscy1qb2JzLXVuaWZpZWQtdG9wLWNhcmRfX3RlcnRpYXJ5LWRlc2NyaXB0aW9uIikNCiAgICAgICAgICAgICAgICAgICAgICAgICBvciBzZWxmLl90ZXh0X29yX2VtcHR5KHBhZ2UsICJzcGFuW2NsYXNzKj0nd29ya3BsYWNlLXR5cGUnXSIpKQ0KDQogICAgICAgICAgICAgICAgYXBwbHlfZWxlbWVudCA9IHNlbGYuX2ZpbmRfYXBwbHlfYnV0dG9uKHBhZ2UpDQogICAgICAgICAgICAgICAgaWYgbm90IGFwcGx5X2VsZW1lbnQ6DQogICAgICAgICAgICAgICAgICAgIHNlbGYuc3RhdHNbInNraXBwZWQiXSArPSAxDQogICAgICAgICAgICAgICAgICAgIHJldHVybiBzZWxmLl9qb2JfcmVjb3JkKGpvYl9pZCwgam9iX3VybCwgdGl0bGUsIGNvbXBhbnksIHBsYWNlLCAic2tpcHBlZCIsICJObyBhcHBseSBidXR0b24iKQ0KDQogICAgICAgICAgICAgICAgIyBEZXRlY3QgRWFzeSBBcHBseSBieSBocmVmIG9yIHRleHQNCiAgICAgICAgICAgICAgICBocmVmID0gKGFwcGx5X2VsZW1lbnQuZ2V0X2F0dHJpYnV0ZSgiaHJlZiIpIG9yICIiKS5sb3dlcigpDQogICAgICAgICAgICAgICAgYnV0dG9uX3RleHQgPSAoYXBwbHlfZWxlbWVudC5pbm5lcl90ZXh0KCkgb3IgIiIpLnN0cmlwKCkubG93ZXIoKQ0KICAgICAgICAgICAgICAgIGFyaWEgPSAoYXBwbHlfZWxlbWVudC5nZXRfYXR0cmlidXRlKCJhcmlhLWxhYmVsIikgb3IgIiIpLmxvd2VyKCkNCiAgICAgICAgICAgICAgICBpc19lYXN5X2FwcGx5ID0gIm9wZW5zZHVpIiBpbiBocmVmIG9yICJlYXN5IGFwcGx5IiBpbiBidXR0b25fdGV4dCBvciAiZWFzeSBhcHBseSIgaW4gYXJpYQ0KDQogICAgICAgICAgICAgICAgaWYgaXNfZWFzeV9hcHBseToNCiAgICAgICAgICAgICAgICAgICAgaWYgc2VsZi5kcnlfcnVuOg0KICAgICAgICAgICAgICAgICAgICAgICAgc2VsZi5zdGF0c1siZHJ5X3J1biJdICs9IDENCiAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiBzZWxmLl9qb2JfcmVjb3JkKGpvYl9pZCwgam9iX3VybCwgdGl0bGUsIGNvbXBhbnksIHBsYWNlLCAiZHJ5X3J1biIsICJFYXN5IEFwcGx5IGZvdW5kIikNCg0KICAgICAgICAgICAgICAgICAgICBpZiBzZWxmLl9ydW5fZWFzeV9hcHBseShwYWdlLCBsb2NhdGlvbik6DQogICAgICAgICAgICAgICAgICAgICAgICBzZWxmLnN0YXRzWyJzdWJtaXR0ZWQiXSArPSAxDQogICAgICAgICAgICAgICAgICAgICAgICByZXR1cm4gc2VsZi5fam9iX3JlY29yZChqb2JfaWQsIGpvYl91cmwsIHRpdGxlLCBjb21wYW55LCBwbGFjZSwgInN1Ym1pdHRlZCIsICJFYXN5IEFwcGx5IHN1Ym1pdHRlZCIpDQoNCiAgICAgICAgICAgICAgICAgICAgc2VsZi5zdGF0c1siZmFpbHVyZXMiXSArPSAxDQogICAgICAgICAgICAgICAgICAgIHJldHVybiBzZWxmLl9qb2JfcmVjb3JkKGpvYl9pZCwgam9iX3VybCwgdGl0bGUsIGNvbXBhbnksIHBsYWNlLCAiZmFpbGVkIiwgIkVhc3kgQXBwbHkgZmxvdyBmYWlsZWQiKQ0KDQogICAgICAgICAgICAgICAgZXh0ZXJuYWxfdXJsID0gc2VsZi5faGFuZGxlX2V4dGVybmFsX2FwcGx5KHBhZ2UpDQogICAgICAgICAgICAgICAgc2VsZi5zdGF0c1sibWFudWFsX3JlcXVpcmVkIl0gKz0gMQ0KICAgICAgICAgICAgICAgIHJldHVybiBzZWxmLl9qb2JfcmVjb3JkKA0KICAgICAgICAgICAgICAgICAgICBqb2JfaWQsDQogICAgICAgICAgICAgICAgICAgIGpvYl91cmwsDQogICAgICAgICAgICAgICAgICAgIHRpdGxlLA0KICAgICAgICAgICAgICAgICAgICBjb21wYW55LA0KICAgICAgICAgICAgICAgICAgICBwbGFjZSwNCiAgICAgICAgICAgICAgICAgICAgIm1hbnVhbF9yZXF1aXJlZCIsDQogICAgICAgICAgICAgICAgICAgIGYiRXh0ZXJuYWwgYXBwbHk6IHtleHRlcm5hbF91cmwgb3IgJ29wZW5lZCd9IiwNCiAgICAgICAgICAgICAgICApDQoNCiAgICAgICAgICAgIGV4Y2VwdCBQbGF5d3JpZ2h0VGltZW91dEVycm9yOg0KICAgICAgICAgICAgICAgIGlmIGF0dGVtcHQgPj0gc2VsZi5jb25maWcuc2V0dGluZ3MucmV0cmllc19wZXJfam9iOg0KICAgICAgICAgICAgICAgICAgICBzZWxmLnN0YXRzWyJmYWlsdXJlcyJdICs9IDENCiAgICAgICAgICAgICAgICAgICAgcmV0dXJuIHNlbGYuX2pvYl9yZWNvcmQoam9iX2lkLCBqb2JfdXJsLCAiIiwgIiIsICIiLCAiZmFpbGVkIiwgIlRpbWVvdXQiKQ0KICAgICAgICAgICAgICAgIHNlbGYuX2h1bWFuX3BhdXNlKCkNCiAgICAgICAgICAgIGV4Y2VwdCBFeGNlcHRpb24gYXMgZXhjOg0KICAgICAgICAgICAgICAgIGlmIGF0dGVtcHQgPj0gc2VsZi5jb25maWcuc2V0dGluZ3MucmV0cmllc19wZXJfam9iOg0KICAgICAgICAgICAgICAgICAgICBzZWxmLnN0YXRzWyJmYWlsdXJlcyJdICs9IDENCiAgICAgICAgICAgICAgICAgICAgcmV0dXJuIHNlbGYuX2pvYl9yZWNvcmQoam9iX2lkLCBqb2JfdXJsLCAiIiwgIiIsICIiLCAiZmFpbGVkIiwgZiJVbmhhbmRsZWQgZXJyb3I6IHtleGN9IikNCiAgICAgICAgICAgICAgICBzZWxmLl9odW1hbl9wYXVzZSgpDQoNCiAgICAgICAgc2VsZi5zdGF0c1siZmFpbHVyZXMiXSArPSAxDQogICAgICAgIHJldHVybiBzZWxmLl9qb2JfcmVjb3JkKGpvYl9pZCwgam9iX3VybCwgIiIsICIiLCAiIiwgImZhaWxlZCIsICJVbmtub3duIGZhaWx1cmUiKQ0KDQogICAgZGVmIF9ydW5fZWFzeV9hcHBseShzZWxmLCBwYWdlLCBsb2NhdGlvbjogc3RyKSAtPiBib29sOg0KICAgICAgICAjIFRyeSB0byBnZXQgdGhlIGRpcmVjdCBVUkwgZm9yIHRoZSBFYXN5IEFwcGx5IGZsb3cNCiAgICAgICAgYXBwbHlfdXJsID0gc2VsZi5fZ2V0X2Vhc3lfYXBwbHlfdXJsKHBhZ2UpDQogICAgICAgIGlmIGFwcGx5X3VybDoNCiAgICAgICAgICAgIHBhZ2UuZ290byhhcHBseV91cmwsIHdhaXRfdW50aWw9ImRvbWNvbnRlbnRsb2FkZWQiKQ0KICAgICAgICAgICAgc2VsZi5faHVtYW5fcGF1c2UoKQ0KICAgICAgICBlbHNlOg0KICAgICAgICAgICAgYXBwbHlfYnRuID0gc2VsZi5fZmluZF9hcHBseV9idXR0b24ocGFnZSkNCiAgICAgICAgICAgIGlmIG5vdCBhcHBseV9idG46DQogICAgICAgICAgICAgICAgcmV0dXJuIEZhbHNlDQogICAgICAgICAgICBhcHBseV9idG4uY2xpY2soKQ0KICAgICAgICAgICAgc2VsZi5faHVtYW5fcGF1c2UoKQ0KDQogICAgICAgIGZpbGVfaW5wdXQgPSBwYWdlLnF1ZXJ5X3NlbGVjdG9yKCJpbnB1dFt0eXBlPSdmaWxlJ10iKQ0KICAgICAgICBpZiBmaWxlX2lucHV0IGFuZCBzZWxmLmNvbmZpZy5wYXRocy5jdl9wYXRoLmV4aXN0cygpOg0KICAgICAgICAgICAgZmlsZV9pbnB1dC5zZXRfaW5wdXRfZmlsZXMoc3RyKHNlbGYuY29uZmlnLnBhdGhzLmN2X3BhdGgpKQ0KICAgICAgICAgICAgc2VsZi5faHVtYW5fcGF1c2UoKQ0KDQogICAgICAgIGZvciBfIGluIHJhbmdlKDEwKToNCiAgICAgICAgICAgIHNlbGYuX2F1dG9maWxsX3Zpc2libGVfZmllbGRzKHBhZ2UsIGxvY2F0aW9uKQ0KDQogICAgICAgICAgICBzdWJtaXRfYnRuID0gcGFnZS5xdWVyeV9zZWxlY3RvcigiYnV0dG9uW2FyaWEtbGFiZWwqPSdTdWJtaXQgYXBwbGljYXRpb24nXSwgYnV0dG9uOmhhcy10ZXh0KCdTdWJtaXQgYXBwbGljYXRpb24nKSIpDQogICAgICAgICAgICBpZiBzdWJtaXRfYnRuOg0KICAgICAgICAgICAgICAgIHN1Ym1pdF9idG4uY2xpY2soKQ0KICAgICAgICAgICAgICAgIHNlbGYuX2h1bWFuX3BhdXNlKCkNCiAgICAgICAgICAgICAgICBzZWxmLl9jbG9zZV9hcHBseV9tb2RhbChwYWdlKQ0KICAgICAgICAgICAgICAgIHJldHVybiBUcnVlDQoNCiAgICAgICAgICAgIG5leHRfYnRuID0gcGFnZS5xdWVyeV9zZWxlY3RvcigiYnV0dG9uW2FyaWEtbGFiZWw9J0NvbnRpbnVlIHRvIG5leHQgc3RlcCddLCBidXR0b246aGFzLXRleHQoJ05leHQnKSwgYnV0dG9uOmhhcy10ZXh0KCdSZXZpZXcnKSIpDQogICAgICAgICAgICBpZiBub3QgbmV4dF9idG46DQogICAgICAgICAgICAgICAgYnJlYWsNCiAgICAgICAgICAgIG5leHRfYnRuLmNsaWNrKCkNCiAgICAgICAgICAgIHNlbGYuX2h1bWFuX3BhdXNlKCkNCg0KICAgICAgICBzZWxmLl9kaXNtaXNzX2FwcGx5X2Zsb3cocGFnZSkNCiAgICAgICAgcmV0dXJuIEZhbHNlDQoNCiAgICBkZWYgX2F1dG9maWxsX3Zpc2libGVfZmllbGRzKHNlbGYsIHBhZ2UsIGxvY2F0aW9uOiBzdHIpIC0+IE5vbmU6DQogICAgICAgIHByb2ZpbGUgPSBzZWxmLmNvbmZpZy5wcm9maWxlDQoNCiAgICAgICAgZmlsbF9tYXAgPSB7DQogICAgICAgICAgICAiZmlyc3QgbmFtZSI6IHByb2ZpbGUuZnVsbF9uYW1lLnNwbGl0KCIgIilbMF0sDQogICAgICAgICAgICAibGFzdCBuYW1lIjogcHJvZmlsZS5mdWxsX25hbWUuc3BsaXQoIiAiKVstMV0sDQogICAgICAgICAgICAiZnVsbCBuYW1lIjogcHJvZmlsZS5mdWxsX25hbWUsDQogICAgICAgICAgICAibmFtZSI6IHByb2ZpbGUuZnVsbF9uYW1lLA0KICAgICAgICAgICAgImVtYWlsIjogcHJvZmlsZS5lbWFpbCwNCiAgICAgICAgICAgICJwaG9uZSI6IHByb2ZpbGUucGhvbmUsDQogICAgICAgICAgICAiY2l0eSI6IHByb2ZpbGUubG9jYXRpb24sDQogICAgICAgICAgICAibG9jYXRpb24iOiBwcm9maWxlLmxvY2F0aW9uLA0KICAgICAgICAgICAgImV4cGVyaWVuY2UiOiBwcm9maWxlLnRvdGFsX2V4cGVyaWVuY2VfeWVhcnMsDQogICAgICAgICAgICAic2FsYXJ5IjogcHJvZmlsZS5zYWxhcnlfaHVuZ2FyeSBpZiAiaHVuZ2FyeSIgaW4gbG9jYXRpb24ubG93ZXIoKSBlbHNlIHByb2ZpbGUuc2FsYXJ5X2l0YWx5LA0KICAgICAgICAgICAgImF1dGhvcml6YXRpb24iOiBwcm9maWxlLndvcmtfYXV0aG9yaXphdGlvbl9odW5nYXJ5IGlmICJodW5nYXJ5IiBpbiBsb2NhdGlvbi5sb3dlcigpIGVsc2UgcHJvZmlsZS53b3JrX2F1dGhvcml6YXRpb25faXRhbHksDQogICAgICAgICAgICAid29yayBwZXJtaXQiOiBwcm9maWxlLndvcmtfYXV0aG9yaXphdGlvbl9odW5nYXJ5IGlmICJodW5nYXJ5IiBpbiBsb2NhdGlvbi5sb3dlcigpIGVsc2UgcHJvZmlsZS53b3JrX2F1dGhvcml6YXRpb25faXRhbHksDQogICAgICAgICAgICAiZ3JhZHVhdGlvbiI6IHByb2ZpbGUuZ3JhZHVhdGlvbl95ZWFyLA0KICAgICAgICB9DQoNCiAgICAgICAgaW5wdXRzID0gcGFnZS5xdWVyeV9zZWxlY3Rvcl9hbGwoImlucHV0LCB0ZXh0YXJlYSIpDQogICAgICAgIGZvciBpbnB1dF9lbCBpbiBpbnB1dHM6DQogICAgICAgICAgICBpbnB1dF90eXBlID0gKGlucHV0X2VsLmdldF9hdHRyaWJ1dGUoInR5cGUiKSBvciAidGV4dCIpLmxvd2VyKCkNCiAgICAgICAgICAgIGlmIGlucHV0X3R5cGUgaW4geyJoaWRkZW4iLCAic3VibWl0IiwgImJ1dHRvbiIsICJjaGVja2JveCIsICJyYWRpbyIsICJmaWxlIn06DQogICAgICAgICAgICAgICAgY29udGludWUNCg0KICAgICAgICAgICAgdmFsdWUgPSAoaW5wdXRfZWwuaW5wdXRfdmFsdWUoKSBvciAiIikuc3RyaXAoKQ0KICAgICAgICAgICAgaWYgdmFsdWU6DQogICAgICAgICAgICAgICAgY29udGludWUNCg0KICAgICAgICAgICAgbWV0YWRhdGEgPSAiICIuam9pbigNCiAgICAgICAgICAgICAgICBmaWx0ZXIoDQogICAgICAgICAgICAgICAgICAgIE5vbmUsDQogICAgICAgICAgICAgICAgICAgIFsNCiAgICAgICAgICAgICAgICAgICAgICAgIGlucHV0X2VsLmdldF9hdHRyaWJ1dGUoIm5hbWUiKSwNCiAgICAgICAgICAgICAgICAgICAgICAgIGlucHV0X2VsLmdldF9hdHRyaWJ1dGUoImlkIiksDQogICAgICAgICAgICAgICAgICAgICAgICBpbnB1dF9lbC5nZXRfYXR0cmlidXRlKCJwbGFjZWhvbGRlciIpLA0KICAgICAgICAgICAgICAgICAgICAgICAgaW5wdXRfZWwuZ2V0X2F0dHJpYnV0ZSgiYXJpYS1sYWJlbCIpLA0KICAgICAgICAgICAgICAgICAgICBdLA0KICAgICAgICAgICAgICAgICkNCiAgICAgICAgICAgICkubG93ZXIoKQ0KDQogICAgICAgICAgICBjaG9zZW4gPSBOb25lDQogICAgICAgICAgICBmb3Iga2V5LCBtYXBwZWQgaW4gZmlsbF9tYXAuaXRlbXMoKToNCiAgICAgICAgICAgICAgICBpZiBrZXkgaW4gbWV0YWRhdGE6DQogICAgICAgICAgICAgICAgICAgIGNob3NlbiA9IG1hcHBlZA0KICAgICAgICAgICAgICAgICAgICBicmVhaw0KDQogICAgICAgICAgICBpZiBjaG9zZW46DQogICAgICAgICAgICAgICAgdHJ5Og0KICAgICAgICAgICAgICAgICAgICBpbnB1dF9lbC5maWxsKGNob3NlbikNCiAgICAgICAgICAgICAgICAgICAgc2VsZi5faHVtYW5fcGF1c2UoMC4yLCAwLjYpDQogICAgICAgICAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjoNCiAgICAgICAgICAgICAgICAgICAgY29udGludWUNCg0KICAgIGRlZiBfaGFuZGxlX2V4dGVybmFsX2FwcGx5KHNlbGYsIHBhZ2UpIC0+IHN0ciB8IE5vbmU6DQogICAgICAgIGJ0biA9IHNlbGYuX2ZpbmRfYXBwbHlfYnV0dG9uKHBhZ2UpDQogICAgICAgIGlmIG5vdCBidG46DQogICAgICAgICAgICByZXR1cm4gTm9uZQ0KDQogICAgICAgIGV4dGVybmFsX3VybCA9IE5vbmUNCiAgICAgICAgdHJ5Og0KICAgICAgICAgICAgd2l0aCBwYWdlLmV4cGVjdF9wb3B1cCh0aW1lb3V0PTMwMDApIGFzIHBvcHVwX2luZm86DQogICAgICAgICAgICAgICAgYnRuLmNsaWNrKCkNCiAgICAgICAgICAgIHBvcHVwID0gcG9wdXBfaW5mby52YWx1ZQ0KICAgICAgICAgICAgcG9wdXAud2FpdF9mb3JfbG9hZF9zdGF0ZSgiZG9tY29udGVudGxvYWRlZCIsIHRpbWVvdXQ9NTAwMCkNCiAgICAgICAgICAgIGV4dGVybmFsX3VybCA9IHBvcHVwLnVybA0KICAgICAgICAgICAgcG9wdXAuY2xvc2UoKQ0KICAgICAgICBleGNlcHQgRXhjZXB0aW9uOg0KICAgICAgICAgICAgdHJ5Og0KICAgICAgICAgICAgICAgIGJ0bi5jbGljaygpDQogICAgICAgICAgICAgICAgc2VsZi5faHVtYW5fcGF1c2UoKQ0KICAgICAgICAgICAgICAgIGV4dGVybmFsX3VybCA9IHBhZ2UudXJsDQogICAgICAgICAgICBleGNlcHQgRXhjZXB0aW9uOg0KICAgICAgICAgICAgICAgIHJldHVybiBOb25lDQoNCiAgICAgICAgcmV0dXJuIGV4dGVybmFsX3VybA0KDQogICAgZGVmIF9kaXNtaXNzX2FwcGx5X2Zsb3coc2VsZiwgcGFnZSkgLT4gTm9uZToNCiAgICAgICAgZGlzY2FyZCA9IHBhZ2UucXVlcnlfc2VsZWN0b3IoImJ1dHRvbjpoYXMtdGV4dCgnRGlzY2FyZCcpIikNCiAgICAgICAgY2xvc2UgPSBwYWdlLnF1ZXJ5X3NlbGVjdG9yKCJidXR0b25bYXJpYS1sYWJlbD0nRGlzbWlzcyddIikNCiAgICAgICAgaWYgY2xvc2U6DQogICAgICAgICAgICBjbG9zZS5jbGljaygpDQogICAgICAgICAgICBzZWxmLl9odW1hbl9wYXVzZSgwLjIsIDAuOCkNCiAgICAgICAgaWYgZGlzY2FyZDoNCiAgICAgICAgICAgIGRpc2NhcmQuY2xpY2soKQ0KICAgICAgICAgICAgc2VsZi5faHVtYW5fcGF1c2UoMC4yLCAwLjgpDQoNCiAgICBkZWYgX2Nsb3NlX2FwcGx5X21vZGFsKHNlbGYsIHBhZ2UpIC0+IE5vbmU6DQogICAgICAgIGRvbmUgPSBwYWdlLnF1ZXJ5X3NlbGVjdG9yKCJidXR0b246aGFzLXRleHQoJ0RvbmUnKSIpDQogICAgICAgIGlmIGRvbmU6DQogICAgICAgICAgICBkb25lLmNsaWNrKCkNCiAgICAgICAgICAgIHNlbGYuX2h1bWFuX3BhdXNlKDAuMiwgMC44KQ0KDQogICAgZGVmIF9hbHJlYWR5X3NlZW4oc2VsZiwgam9iX2lkOiBzdHIpIC0+IGJvb2w6DQogICAgICAgIHJldHVybiBhbnkoZW50cnkuZ2V0KCJqb2JfaWQiKSA9PSBqb2JfaWQgZm9yIGVudHJ5IGluIHNlbGYuYXBwbGllZF9qb2JzKQ0KDQogICAgZGVmIF9yZWNvcmRfam9iKHNlbGYsIGpvYjogZGljdFtzdHIsIEFueV0pIC0+IE5vbmU6DQogICAgICAgICMgT25seSBwZXJzaXN0IHRydWUgYXBwbGllZCBvdXRjb21lcyB0byBkZWR1cGUgZnV0dXJlIHJ1bnMuDQogICAgICAgIGlmIGpvYi5nZXQoInN0YXR1cyIpIG5vdCBpbiB7InN1Ym1pdHRlZCIsICJtYW51YWxfcmVxdWlyZWQifToNCiAgICAgICAgICAgIHJldHVybg0KICAgICAgICBzZWxmLmFwcGxpZWRfam9icy5hcHBlbmQoam9iKQ0KICAgICAgICBzZWxmLl93cml0ZV9qc29uKHNlbGYuY29uZmlnLnBhdGhzLmFwcGxpZWRfbG9nLCBzZWxmLmFwcGxpZWRfam9icykNCg0KICAgIGRlZiBfYXBwZW5kX3J1bl9oaXN0b3J5KHNlbGYsIHJlc3VsdDogZGljdFtzdHIsIEFueV0pIC0+IE5vbmU6DQogICAgICAgIGhpc3RvcnkgPSBzZWxmLl9yZWFkX2pzb24oc2VsZi5jb25maWcucGF0aHMucnVuX2hpc3RvcnlfbG9nLCBkZWZhdWx0PVtdKQ0KICAgICAgICBoaXN0b3J5LmFwcGVuZChyZXN1bHQpDQogICAgICAgIHNlbGYuX3dyaXRlX2pzb24oc2VsZi5jb25maWcucGF0aHMucnVuX2hpc3RvcnlfbG9nLCBoaXN0b3J5KQ0KDQogICAgZGVmIF9qb2JfcmVjb3JkKA0KICAgICAgICBzZWxmLA0KICAgICAgICBqb2JfaWQ6IHN0ciwNCiAgICAgICAgam9iX3VybDogc3RyLA0KICAgICAgICB0aXRsZTogc3RyLA0KICAgICAgICBjb21wYW55OiBzdHIsDQogICAgICAgIGxvY2F0aW9uOiBzdHIsDQogICAgICAgIHN0YXR1czogc3RyLA0KICAgICAgICBub3RlOiBzdHIsDQogICAgKSAtPiBkaWN0W3N0ciwgQW55XToNCiAgICAgICAgcmV0dXJuIHsNCiAgICAgICAgICAgICJ0aW1lc3RhbXAiOiBkYXRldGltZS5ub3codGltZXpvbmUudXRjKS5pc29mb3JtYXQoKSwNCiAgICAgICAgICAgICJqb2JfaWQiOiBqb2JfaWQsDQogICAgICAgICAgICAiam9iX3VybCI6IGpvYl91cmwsDQogICAgICAgICAgICAidGl0bGUiOiB0aXRsZS5zdHJpcCgpLA0KICAgICAgICAgICAgImNvbXBhbnkiOiBjb21wYW55LnN0cmlwKCksDQogICAgICAgICAgICAibG9jYXRpb24iOiBsb2NhdGlvbi5zdHJpcCgpLA0KICAgICAgICAgICAgInN0YXR1cyI6IHN0YXR1cywNCiAgICAgICAgICAgICJub3RlIjogbm90ZSwNCiAgICAgICAgICAgICJwcm9maWxlX3NuYXBzaG90IjogYXNkaWN0KHNlbGYuY29uZmlnLnByb2ZpbGUpLA0KICAgICAgICB9DQoNCiAgICBkZWYgX2V4dHJhY3Rfam9iX2lkKHNlbGYsIHVybDogc3RyKSAtPiBzdHI6DQogICAgICAgIG1hdGNoID0gcmUuc2VhcmNoKHIiL2pvYnMvdmlldy8oXGQrKSIsIHVybCkNCiAgICAgICAgcmV0dXJuIG1hdGNoLmdyb3VwKDEpIGlmIG1hdGNoIGVsc2UgdXJsDQoNCiAgICBkZWYgX3Byb2dyZXNzaXZlX3Njcm9sbChzZWxmLCBwYWdlKSAtPiBOb25lOg0KICAgICAgICBmb3IgXyBpbiByYW5nZSgzKToNCiAgICAgICAgICAgIHBhZ2UubW91c2Uud2hlZWwoMCwgcmFuZG9tLnJhbmRpbnQoNTAwLCAxMDAwKSkNCiAgICAgICAgICAgIHNlbGYuX2h1bWFuX3BhdXNlKDAuNCwgMS4xKQ0KDQogICAgZGVmIF9odW1hbl9wYXVzZShzZWxmLCBtaW5fc2Vjb25kczogZmxvYXQgfCBOb25lID0gTm9uZSwgbWF4X3NlY29uZHM6IGZsb2F0IHwgTm9uZSA9IE5vbmUpIC0+IE5vbmU6DQogICAgICAgIG1pbl93YWl0ID0gbWluX3NlY29uZHMgaWYgbWluX3NlY29uZHMgaXMgbm90IE5vbmUgZWxzZSBzZWxmLmNvbmZpZy5zZXR0aW5ncy5yYW5kb21fd2FpdF9taW5fc2Vjb25kcw0KICAgICAgICBtYXhfd2FpdCA9IG1heF9zZWNvbmRzIGlmIG1heF9zZWNvbmRzIGlzIG5vdCBOb25lIGVsc2Ugc2VsZi5jb25maWcuc2V0dGluZ3MucmFuZG9tX3dhaXRfbWF4X3NlY29uZHMNCiAgICAgICAgdGltZS5zbGVlcChyYW5kb20udW5pZm9ybShtaW5fd2FpdCwgbWF4X3dhaXQpKQ0KDQogICAgZGVmIF9odW1hbl90eXBlX2ZpcnN0KHNlbGYsIHBhZ2UsIHNlbGVjdG9yczogbGlzdFtzdHJdLCB0ZXh0OiBzdHIpIC0+IGJvb2w6DQogICAgICAgIGZvciBzZWxlY3RvciBpbiBzZWxlY3RvcnM6DQogICAgICAgICAgICB0cnk6DQogICAgICAgICAgICAgICAgc2VsZi5faHVtYW5fdHlwZShwYWdlLCBzZWxlY3RvciwgdGV4dCkNCiAgICAgICAgICAgICAgICByZXR1cm4gVHJ1ZQ0KICAgICAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjoNCiAgICAgICAgICAgICAgICBjb250aW51ZQ0KICAgICAgICByZXR1cm4gRmFsc2UNCg0KICAgIGRlZiBfaHVtYW5fdHlwZShzZWxmLCBwYWdlLCBzZWxlY3Rvcjogc3RyLCB0ZXh0OiBzdHIpIC0+IE5vbmU6DQogICAgICAgIGxvY2F0b3IgPSBwYWdlLmxvY2F0b3Ioc2VsZWN0b3IpDQogICAgICAgIGxvY2F0b3Iud2FpdF9mb3Ioc3RhdGU9ImF0dGFjaGVkIiwgdGltZW91dD0xMDAwMCkNCg0KICAgICAgICAjIFRyeSBkaXJlY3QgZmlsbCBmaXJzdCBiZWNhdXNlIGxvZ2luIHBhZ2VzIGNhbiBzaG93IG92ZXJsYXlzIHRoYXQgYmxvY2sgY2xpY2suDQogICAgICAgIHRyeToNCiAgICAgICAgICAgIGxvY2F0b3IuZmlsbCgiIikNCiAgICAgICAgICAgIGZvciBjaCBpbiB0ZXh0Og0KICAgICAgICAgICAgICAgIGxvY2F0b3IudHlwZShjaCwgZGVsYXk9cmFuZG9tLnVuaWZvcm0oMzAsIDkwKSkNCiAgICAgICAgICAgIHJldHVybg0KICAgICAgICBleGNlcHQgRXhjZXB0aW9uOg0KICAgICAgICAgICAgcGFzcw0KDQogICAgICAgIHBhZ2UuY2xpY2soc2VsZWN0b3IsIHRpbWVvdXQ9MTAwMDApDQogICAgICAgIGZvciBjaCBpbiB0ZXh0Og0KICAgICAgICAgICAgcGFnZS5rZXlib2FyZC50eXBlKGNoKQ0KICAgICAgICAgICAgdGltZS5zbGVlcChyYW5kb20udW5pZm9ybSgwLjAzLCAwLjA5KSkNCg0KICAgIGRlZiBfdGV4dF9vcl9lbXB0eShzZWxmLCBwYWdlLCBzZWxlY3Rvcjogc3RyKSAtPiBzdHI6DQogICAgICAgIGVsID0gcGFnZS5xdWVyeV9zZWxlY3RvcihzZWxlY3RvcikNCiAgICAgICAgcmV0dXJuIChlbC5pbm5lcl90ZXh0KCkgaWYgZWwgZWxzZSAiIikgb3IgIiINCg0KICAgIGRlZiBfc2F2ZV9kZWJ1Z19hcnRpZmFjdHMoc2VsZiwgcGFnZSwgcHJlZml4OiBzdHIpIC0+IHN0cjoNCiAgICAgICAgbG9nc19kaXIgPSBzZWxmLmNvbmZpZy5wYXRocy5iYXNlX2RpciAvICJsb2dzIg0KICAgICAgICBsb2dzX2Rpci5ta2RpcihwYXJlbnRzPVRydWUsIGV4aXN0X29rPVRydWUpDQogICAgICAgIHRzID0gZGF0ZXRpbWUubm93KHRpbWV6b25lLnV0Yykuc3RyZnRpbWUoIiVZJW0lZFQlSCVNJVNaIikNCg0KICAgICAgICBodG1sX3BhdGggPSBsb2dzX2RpciAvIGYie3ByZWZpeH1fe3RzfS5odG1sIg0KICAgICAgICBwbmdfcGF0aCA9IGxvZ3NfZGlyIC8gZiJ7cHJlZml4fV97dHN9LnBuZyINCg0KICAgICAgICB0cnk6DQogICAgICAgICAgICBodG1sX3BhdGgud3JpdGVfdGV4dChwYWdlLmNvbnRlbnQoKSwgZW5jb2Rpbmc9InV0Zi04IikNCiAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjoNCiAgICAgICAgICAgIHBhc3MNCg0KICAgICAgICB0cnk6DQogICAgICAgICAgICBwYWdlLnNjcmVlbnNob3QocGF0aD1zdHIocG5nX3BhdGgpLCBmdWxsX3BhZ2U9VHJ1ZSkNCiAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjoNCiAgICAgICAgICAgIHBhc3MNCg0KICAgICAgICByZXR1cm4gc3RyKGxvZ3NfZGlyKQ0KDQogICAgZGVmIF9yZWFkX2pzb24oc2VsZiwgcGF0aDogUGF0aCwgKiwgZGVmYXVsdDogQW55KSAtPiBBbnk6DQogICAgICAgIGlmIG5vdCBwYXRoLmV4aXN0cygpOg0KICAgICAgICAgICAgcmV0dXJuIGRlZmF1bHQNCiAgICAgICAgdHJ5Og0KICAgICAgICAgICAgd2l0aCBwYXRoLm9wZW4oInIiLCBlbmNvZGluZz0idXRmLTgiKSBhcyBmOg0KICAgICAgICAgICAgICAgIHJldHVybiBqc29uLmxvYWQoZikNCiAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjoNCiAgICAgICAgICAgIHJldHVybiBkZWZhdWx0DQoNCiAgICBkZWYgX3dyaXRlX2pzb24oc2VsZiwgcGF0aDogUGF0aCwgY29udGVudDogQW55KSAtPiBOb25lOg0KICAgICAgICBwYXRoLnBhcmVudC5ta2RpcihwYXJlbnRzPVRydWUsIGV4aXN0X29rPVRydWUpDQogICAgICAgIHdpdGggcGF0aC5vcGVuKCJ3IiwgZW5jb2Rpbmc9InV0Zi04IikgYXMgZjoNCiAgICAgICAgICAgIGpzb24uZHVtcChjb250ZW50LCBmLCBpbmRlbnQ9MiwgZW5zdXJlX2FzY2lpPVRydWUpDQoNCiAgICBkZWYgX3dyaXRlX3N0YXRlKHNlbGYpIC0+IE5vbmU6DQogICAgICAgIHNlbGYuX3dyaXRlX2pzb24oc2VsZi5jb25maWcucGF0aHMuc3RhdGVfcGF0aCwgc2VsZi5zdGF0ZSkNCg0KICAgIGRlZiBfcmVhY2hlZF9saW1pdChzZWxmKSAtPiBib29sOg0KICAgICAgICAjIExpbWl0IGJ5IHByb2Nlc3NlZCBqb2JzIHNvIGRyeS1ydW5zIGFuZCBtaXhlZCBmbG93cyB0ZXJtaW5hdGUgcHJlZGljdGFibHkuDQogICAgICAgIHByb2Nlc3NlZCA9ICgNCiAgICAgICAgICAgIHNlbGYuc3RhdHNbInN1Ym1pdHRlZCJdDQogICAgICAgICAgICArIHNlbGYuc3RhdHNbImRyeV9ydW4iXQ0KICAgICAgICAgICAgKyBzZWxmLnN0YXRzWyJtYW51YWxfcmVxdWlyZWQiXQ0KICAgICAgICAgICAgKyBzZWxmLnN0YXRzWyJza2lwcGVkIl0NCiAgICAgICAgICAgICsgc2VsZi5zdGF0c1siZmFpbHVyZXMiXQ0KICAgICAgICApDQogICAgICAgIHJldHVybiBwcm9jZXNzZWQgPj0gc2VsZi5saW1pdA0K' | $SSH 'base64 -d > ~/cv_portofolio/linkedin_bot/bot.py'
printf '%s' 'ZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucw0KDQpmcm9tIGRhdGFjbGFzc2VzIGltcG9ydCBkYXRhY2xhc3MsIGZpZWxkDQpmcm9tIHBhdGhsaWIgaW1wb3J0IFBhdGgNCmltcG9ydCBvcw0KZnJvbSBkb3RlbnYgaW1wb3J0IGxvYWRfZG90ZW52DQoNCg0KQkFTRV9ESVIgPSBQYXRoKF9fZmlsZV9fKS5yZXNvbHZlKCkucGFyZW50DQoNCg0KQGRhdGFjbGFzcw0KY2xhc3MgQ2FuZGlkYXRlUHJvZmlsZToNCiAgICBmdWxsX25hbWU6IHN0ciA9ICJNaWtoYWVsIE5hYmlsIFNhbGFtYSBSZXprIg0KICAgIGVtYWlsOiBzdHIgPSAiTWlraGFlbC5OYWJpbC5TYWxhbWEuUmV6a0BnbWFpbC5jb20iDQogICAgcGhvbmU6IHN0ciA9ICIrMzYgNzAgNjM1IDU3NjUiDQogICAgbG9jYXRpb246IHN0ciA9ICJLZWNza2VtZXQsIEh1bmdhcnkiDQogICAgZ3JhZHVhdGlvbl95ZWFyOiBzdHIgPSAiMjAyNyINCiAgICB0b3RhbF9leHBlcmllbmNlX3llYXJzOiBzdHIgPSAiNSINCiAgICB3b3JrX2F1dGhvcml6YXRpb25faHVuZ2FyeTogc3RyID0gIlllcywgSSBoYXZlIGEgdmFsaWQgSHVuZ2FyaWFuIHN0dWRlbnQgcmVzaWRlbmNlIHBlcm1pdC4iDQogICAgd29ya19hdXRob3JpemF0aW9uX2l0YWx5OiBzdHIgPSAiSSBtYXkgcmVxdWlyZSBzcG9uc29yc2hpcDsgb3BlbiB0byBkaXNjdXNzaW9uLiINCiAgICBzYWxhcnlfaHVuZ2FyeTogc3RyID0gIjEwMDAwMDAgSFVGL21vbnRoIg0KICAgIHNhbGFyeV9pdGFseTogc3RyID0gIk5lZ290aWFibGUiDQoNCg0KQGRhdGFjbGFzcw0KY2xhc3MgQm90U2V0dGluZ3M6DQogICAga2V5d29yZHM6IGxpc3Rbc3RyXSA9IGZpZWxkKA0KICAgICAgICBkZWZhdWx0X2ZhY3Rvcnk9bGFtYmRhOiBbDQogICAgICAgICAgICAiRnVsbCBTdGFjayBEZXZlbG9wZXIiLA0KICAgICAgICAgICAgIkZyb250ZW5kIERldmVsb3BlciIsDQogICAgICAgICAgICAiQmFja2VuZCBEZXZlbG9wZXIiLA0KICAgICAgICAgICAgIldlYiBEZXZlbG9wZXIiLA0KICAgICAgICAgICAgIlNvZnR3YXJlIERldmVsb3BlciIsDQogICAgICAgIF0NCiAgICApDQogICAgbG9jYXRpb25zOiBsaXN0W3N0cl0gPSBmaWVsZCgNCiAgICAgICAgZGVmYXVsdF9mYWN0b3J5PWxhbWJkYTogWyJIdW5nYXJ5IiwgIkJ1ZGFwZXN0IiwgIkl0YWx5IiwgIk1pbGFuIiwgIlJvbWUiXQ0KICAgICkNCiAgICBtYXhfYXBwbGljYXRpb25zX3Blcl9ydW46IGludCA9IDI1DQogICAgcmV0cmllc19wZXJfam9iOiBpbnQgPSAyDQogICAgcG9zdGVkX2RheXNfYWdvOiBpbnQgPSA3DQogICAgaGVhZGxlc3M6IGJvb2wgPSBGYWxzZQ0KICAgIHJhbmRvbV93YWl0X21pbl9zZWNvbmRzOiBmbG9hdCA9IDEuNQ0KICAgIHJhbmRvbV93YWl0X21heF9zZWNvbmRzOiBmbG9hdCA9IDMuOA0KDQoNCkBkYXRhY2xhc3MNCmNsYXNzIFJ1bnRpbWVQYXRoczoNCiAgICBiYXNlX2RpcjogUGF0aCA9IEJBU0VfRElSDQogICAgY3ZfcGF0aDogUGF0aCA9IEJBU0VfRElSLnBhcmVudCAvICJNaWtoYWVsX0NWLnBkZiINCiAgICBhcHBsaWVkX2xvZzogUGF0aCA9IEJBU0VfRElSIC8gImFwcGxpZWRfam9icy5qc29uIg0KICAgIHJ1bl9oaXN0b3J5X2xvZzogUGF0aCA9IEJBU0VfRElSIC8gInJ1bl9oaXN0b3J5Lmpzb24iDQogICAgc3RhdGVfcGF0aDogUGF0aCA9IEJBU0VfRElSIC8gInN0YXRlLmpzb24iDQogICAgYnJvd3Nlcl9zdGF0ZV9wYXRoOiBQYXRoID0gQkFTRV9ESVIgLyAicGxheXdyaWdodF9zdGF0ZS5qc29uIg0KDQoNCkBkYXRhY2xhc3MNCmNsYXNzIFJ1bnRpbWVDb25maWc6DQogICAgZW1haWw6IHN0cg0KICAgIHBhc3N3b3JkOiBzdHINCiAgICBwcm9maWxlOiBDYW5kaWRhdGVQcm9maWxlDQogICAgc2V0dGluZ3M6IEJvdFNldHRpbmdzDQogICAgcGF0aHM6IFJ1bnRpbWVQYXRocw0KDQoNCmNsYXNzIE1pc3NpbmdDcmVkZW50aWFsRXJyb3IoUnVudGltZUVycm9yKToNCiAgICBwYXNzDQoNCg0KZGVmIGxvYWRfcnVudGltZV9jb25maWcoKiwgaGVhZGxlc3M6IGJvb2wgfCBOb25lID0gTm9uZSkgLT4gUnVudGltZUNvbmZpZzoNCiAgICBsb2FkX2RvdGVudihCQVNFX0RJUiAvICIuZW52IikNCg0KICAgIGVtYWlsID0gb3MuZ2V0ZW52KCJMSU5LRURJTl9FTUFJTCIsICIiKS5zdHJpcCgpDQogICAgcGFzc3dvcmQgPSBvcy5nZXRlbnYoIkxJTktFRElOX1BBU1NXT1JEIiwgIiIpLnN0cmlwKCkNCiAgICBpZiBub3QgZW1haWwgb3Igbm90IHBhc3N3b3JkOg0KICAgICAgICByYWlzZSBNaXNzaW5nQ3JlZGVudGlhbEVycm9yKA0KICAgICAgICAgICAgIk1pc3NpbmcgTElOS0VESU5fRU1BSUwgYW5kL29yIExJTktFRElOX1BBU1NXT1JEIGluIGxpbmtlZGluX2JvdC8uZW52Ig0KICAgICAgICApDQoNCiAgICBzZXR0aW5ncyA9IEJvdFNldHRpbmdzKCkNCiAgICBpZiBoZWFkbGVzcyBpcyBub3QgTm9uZToNCiAgICAgICAgc2V0dGluZ3MuaGVhZGxlc3MgPSBoZWFkbGVzcw0KDQogICAgcmV0dXJuIFJ1bnRpbWVDb25maWcoDQogICAgICAgIGVtYWlsPWVtYWlsLA0KICAgICAgICBwYXNzd29yZD1wYXNzd29yZCwNCiAgICAgICAgcHJvZmlsZT1DYW5kaWRhdGVQcm9maWxlKCksDQogICAgICAgIHNldHRpbmdzPXNldHRpbmdzLA0KICAgICAgICBwYXRocz1SdW50aW1lUGF0aHMoKSwNCiAgICApDQoNCg0KZGVmIHZhbGlkYXRlX2xvY2FsX2ZpbGVzKHBhdGhzOiBSdW50aW1lUGF0aHMpIC0+IGxpc3Rbc3RyXToNCiAgICBwcm9ibGVtczogbGlzdFtzdHJdID0gW10NCg0KICAgIGlmIG5vdCBwYXRocy5jdl9wYXRoLmV4aXN0cygpOg0KICAgICAgICBwcm9ibGVtcy5hcHBlbmQoZiJDViBmaWxlIG5vdCBmb3VuZDoge3BhdGhzLmN2X3BhdGh9IikNCg0KICAgIGZvciBwIGluIFtwYXRocy5hcHBsaWVkX2xvZywgcGF0aHMucnVuX2hpc3RvcnlfbG9nLCBwYXRocy5zdGF0ZV9wYXRoXToNCiAgICAgICAgaWYgbm90IHAuZXhpc3RzKCk6DQogICAgICAgICAgICBwcm9ibGVtcy5hcHBlbmQoZiJTdGF0ZS9sb2cgZmlsZSBtaXNzaW5nOiB7cH0iKQ0KDQogICAgcmV0dXJuIHByb2JsZW1zDQo=' | $SSH 'base64 -d > ~/cv_portofolio/linkedin_bot/config.py'
printf '%s' 'ZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucw0KDQppbXBvcnQgYXJncGFyc2UNCmltcG9ydCBqc29uDQpmcm9tIHBhdGhsaWIgaW1wb3J0IFBhdGgNCmltcG9ydCBzeXMNCg0KZnJvbSBib3QgaW1wb3J0IExpbmtlZEluQXV0b0FwcGx5Qm90DQpmcm9tIGNvbmZpZyBpbXBvcnQgTWlzc2luZ0NyZWRlbnRpYWxFcnJvciwgUnVudGltZVBhdGhzLCBsb2FkX3J1bnRpbWVfY29uZmlnLCB2YWxpZGF0ZV9sb2NhbF9maWxlcw0KDQoNCmRlZiBwYXJzZV9hcmdzKCkgLT4gYXJncGFyc2UuTmFtZXNwYWNlOg0KICAgIHBhcnNlciA9IGFyZ3BhcnNlLkFyZ3VtZW50UGFyc2VyKGRlc2NyaXB0aW9uPSJMaW5rZWRJbiBBdXRvLUFwcGx5IEJvdCIpDQogICAgcGFyc2VyLmFkZF9hcmd1bWVudCgiLS1kcnktcnVuIiwgYWN0aW9uPSJzdG9yZV90cnVlIiwgaGVscD0iU2VhcmNoIGFuZCBpbnNwZWN0IG9ubHksIG5vIHN1Ym1pc3Npb25zLiIpDQogICAgcGFyc2VyLmFkZF9hcmd1bWVudCgiLS1yZXN1bWUiLCBhY3Rpb249InN0b3JlX3RydWUiLCBoZWxwPSJSZXN1bWUgZnJvbSBzYXZlZCBjdXJzb3IgaW4gc3RhdGUuanNvbi4iKQ0KICAgIHBhcnNlci5hZGRfYXJndW1lbnQoIi0taGVhZGxlc3MiLCBhY3Rpb249InN0b3JlX3RydWUiLCBoZWxwPSJSdW4gYnJvd3NlciBpbiBoZWFkbGVzcyBtb2RlLiIpDQogICAgcGFyc2VyLmFkZF9hcmd1bWVudCgiLS1saW1pdCIsIHR5cGU9aW50LCBkZWZhdWx0PU5vbmUsIGhlbHA9Ik1heCBwcm9jZXNzZWQgam9icyBpbiB0aGlzIHJ1bi4iKQ0KICAgIHBhcnNlci5hZGRfYXJndW1lbnQoIi0tdmFsaWRhdGUiLCBhY3Rpb249InN0b3JlX3RydWUiLCBoZWxwPSJWYWxpZGF0ZSBsb2NhbCBzZXR1cCB3aXRob3V0IG9wZW5pbmcgYnJvd3Nlci4iKQ0KICAgIHJldHVybiBwYXJzZXIucGFyc2VfYXJncygpDQoNCg0KZGVmIHJ1bl92YWxpZGF0aW9uKCkgLT4gaW50Og0KICAgIHBhdGhzID0gUnVudGltZVBhdGhzKCkNCiAgICBwcm9ibGVtcyA9IHZhbGlkYXRlX2xvY2FsX2ZpbGVzKHBhdGhzKQ0KDQogICAgZW52X3BhdGggPSBwYXRocy5iYXNlX2RpciAvICIuZW52Ig0KICAgIGlmIG5vdCBlbnZfcGF0aC5leGlzdHMoKToNCiAgICAgICAgcHJvYmxlbXMuYXBwZW5kKGYiTWlzc2luZyAuZW52IGZpbGU6IHtlbnZfcGF0aH0iKQ0KDQogICAgcmVwb3J0ID0gew0KICAgICAgICAib2siOiBsZW4ocHJvYmxlbXMpID09IDAsDQogICAgICAgICJwcm9ibGVtcyI6IHByb2JsZW1zLA0KICAgICAgICAiY2hlY2tlZF9wYXRocyI6IHsNCiAgICAgICAgICAgICJjdiI6IHN0cihwYXRocy5jdl9wYXRoKSwNCiAgICAgICAgICAgICJhcHBsaWVkX2xvZyI6IHN0cihwYXRocy5hcHBsaWVkX2xvZyksDQogICAgICAgICAgICAicnVuX2hpc3RvcnlfbG9nIjogc3RyKHBhdGhzLnJ1bl9oaXN0b3J5X2xvZyksDQogICAgICAgICAgICAic3RhdGVfcGF0aCI6IHN0cihwYXRocy5zdGF0ZV9wYXRoKSwNCiAgICAgICAgICAgICJlbnZfcGF0aCI6IHN0cihlbnZfcGF0aCksDQogICAgICAgIH0sDQogICAgfQ0KICAgIHByaW50KGpzb24uZHVtcHMocmVwb3J0LCBpbmRlbnQ9MikpDQogICAgcmV0dXJuIDAgaWYgcmVwb3J0WyJvayJdIGVsc2UgMg0KDQoNCmRlZiBtYWluKCkgLT4gaW50Og0KICAgIGFyZ3MgPSBwYXJzZV9hcmdzKCkNCg0KICAgIGlmIGFyZ3MudmFsaWRhdGU6DQogICAgICAgIHJldHVybiBydW5fdmFsaWRhdGlvbigpDQoNCiAgICB0cnk6DQogICAgICAgIGNvbmZpZyA9IGxvYWRfcnVudGltZV9jb25maWcoaGVhZGxlc3M9YXJncy5oZWFkbGVzcykNCiAgICBleGNlcHQgTWlzc2luZ0NyZWRlbnRpYWxFcnJvciBhcyBleGM6DQogICAgICAgIHByaW50KHN0cihleGMpKQ0KICAgICAgICByZXR1cm4gMg0KDQogICAgYm90ID0gTGlua2VkSW5BdXRvQXBwbHlCb3QoDQogICAgICAgIGNvbmZpZywNCiAgICAgICAgZHJ5X3J1bj1hcmdzLmRyeV9ydW4sDQogICAgICAgIHJlc3VtZT1hcmdzLnJlc3VtZSwNCiAgICAgICAgbGltaXQ9YXJncy5saW1pdCwNCiAgICApDQoNCiAgICB0cnk6DQogICAgICAgIHJlc3VsdCA9IGJvdC5ydW4oKQ0KICAgIGV4Y2VwdCBFeGNlcHRpb24gYXMgZXhjOg0KICAgICAgICBwcmludChmIlJ1biBmYWlsZWQ6IHtleGN9IikNCiAgICAgICAgcmV0dXJuIDENCg0KICAgIHByaW50KCJSdW4gY29tcGxldGVkIikNCiAgICBwcmludChqc29uLmR1bXBzKHJlc3VsdCwgaW5kZW50PTIpKQ0KICAgIHJldHVybiAwDQoNCg0KaWYgX19uYW1lX18gPT0gIl9fbWFpbl9fIjoNCiAgICBzeXMuZXhpdChtYWluKCkpDQo=' | $SSH 'base64 -d > ~/cv_portofolio/linkedin_bot/main.py'
printf '%s' 'IyEvdXNyL2Jpbi9lbnYgYmFzaApzZXQgLWV1byBwaXBlZmFpbAoKQk9UX0RJUj0iJEhPTUUvY3ZfcG9ydG9mb2xpby9saW5rZWRpbl9ib3QiClBZVEhPTl9CSU49IiRCT1RfRElSLy52ZW52L2Jpbi9weXRob24iClJVTl9ISVNUT1JZPSIkQk9UX0RJUi9ydW5faGlzdG9yeS5qc29uIgpMT0dfRklMRT0iJEJPVF9ESVIvc2NoZWR1bGVyX291dHB1dC5sb2ciCgpta2RpciAtcCAiJEJPVF9ESVIiCmNkICIkQk9UX0RJUiIKCmlmIFtbICEgLXggIiRQWVRIT05fQklOIiBdXTsgdGhlbgogIGVjaG8gIlskKGRhdGUgLUlzKV0gRVJST1I6IFB5dGhvbiB2aXJ0dWFsZW52IG5vdCBmb3VuZCBhdCAkUFlUSE9OX0JJTiIgPj4gIiRMT0dfRklMRSIKICBleGl0IDEKZmkKCmlmIFtbICEgLWYgIiRIT01FL2N2X3BvcnRvZm9saW8vTWlraGFlbF9DVi5wZGYiIF1dOyB0aGVuCiAgZWNobyAiWyQoZGF0ZSAtSXMpXSBFUlJPUjogQ1Ygbm90IGZvdW5kIGF0ICRIT01FL2N2X3BvcnRvZm9saW8vTWlraGFlbF9DVi5wZGYiID4+ICIkTE9HX0ZJTEUiCiAgZXhpdCAxCmZpCgpMQVNUX1JVTl9EQVRFPSIkKCRQWVRIT05fQklOIC0gPDwnUFknCmltcG9ydCBqc29uCmZyb20gcGF0aGxpYiBpbXBvcnQgUGF0aApmcm9tIGRhdGV0aW1lIGltcG9ydCBkYXRldGltZQoKcGF0aCA9IFBhdGgoInJ1bl9oaXN0b3J5Lmpzb24iKQppZiBub3QgcGF0aC5leGlzdHMoKSBvciBwYXRoLnN0YXQoKS5zdF9zaXplID09IDA6CiAgICBwcmludCgiIikKICAgIHJhaXNlIFN5c3RlbUV4aXQKCnRyeToKICAgIGRhdGEgPSBqc29uLmxvYWRzKHBhdGgucmVhZF90ZXh0KGVuY29kaW5nPSJ1dGYtOCIpKQpleGNlcHQgRXhjZXB0aW9uOgogICAgcHJpbnQoIiIpCiAgICByYWlzZSBTeXN0ZW1FeGl0CgppZiBub3QgaXNpbnN0YW5jZShkYXRhLCBsaXN0KSBvciBub3QgZGF0YToKICAgIHByaW50KCIiKQogICAgcmFpc2UgU3lzdGVtRXhpdAoKbGFzdCA9IGRhdGFbLTFdLmdldCgic3RhcnRlZF9hdCIsICIiKQppZiBub3QgbGFzdDoKICAgIHByaW50KCIiKQogICAgcmFpc2UgU3lzdGVtRXhpdAoKdHJ5OgogICAgZHQgPSBkYXRldGltZS5mcm9taXNvZm9ybWF0KGxhc3QucmVwbGFjZSgiWiIsICIrMDA6MDAiKSkKICAgIHByaW50KGR0LmFzdGltZXpvbmUoKS5kYXRlKCkuaXNvZm9ybWF0KCkpCmV4Y2VwdCBFeGNlcHRpb246CiAgICBwcmludCgiIikKUFkKKSIKClRPREFZPSIkKGRhdGUgKyVGKSIKaWYgW1sgLW4gIiRMQVNUX1JVTl9EQVRFIiAmJiAiJExBU1RfUlVOX0RBVEUiID09ICIkVE9EQVkiIF1dOyB0aGVuCiAgZWNobyAiWyQoZGF0ZSAtSXMpXSBTa2lwcGVkOiBhbHJlYWR5IHJhbiB0b2RheS4iID4+ICIkTE9HX0ZJTEUiCiAgZXhpdCAwCmZpCgplY2hvICJbJChkYXRlIC1JcyldIFN0YXJ0aW5nIGRhaWx5IHJ1bi4iID4+ICIkTE9HX0ZJTEUiCgpzZXQgK2UKeHZmYi1ydW4gLWEgIiRQWVRIT05fQklOIiBtYWluLnB5IC0taGVhZGxlc3MgLS1saW1pdCAyNSA+PiAiJExPR19GSUxFIiAyPiYxCkVYSVRfQ09ERT0kPwpzZXQgLWUKCmVjaG8gIlskKGRhdGUgLUlzKV0gRmluaXNoZWQgd2l0aCBleGl0IGNvZGU6ICRFWElUX0NPREUiID4+ICIkTE9HX0ZJTEUiCmV4aXQgJEVYSVRfQ09ERQo=' | $SSH 'base64 -d > ~/cv_portofolio/linkedin_bot/oracle/oracle_guard_run.sh'
printf '%s' 'JVBERi0xLjQKJZOMi54gUmVwb3J0TGFiIEdlbmVyYXRlZCBQREYgZG9jdW1lbnQgKG9wZW5zb3VyY2UpCjEgMCBvYmoKPDwKL0YxIDIgMCBSIC9GMiAzIDAgUiAvRjMgNCAwIFIKPj4KZW5kb2JqCjIgMCBvYmoKPDwKL0Jhc2VGb250IC9IZWx2ZXRpY2EgL0VuY29kaW5nIC9XaW5BbnNpRW5jb2RpbmcgL05hbWUgL0YxIC9TdWJ0eXBlIC9UeXBlMSAvVHlwZSAvRm9udAo+PgplbmRvYmoKMyAwIG9iago8PAovQmFzZUZvbnQgL0hlbHZldGljYS1Cb2xkIC9FbmNvZGluZyAvV2luQW5zaUVuY29kaW5nIC9OYW1lIC9GMiAvU3VidHlwZSAvVHlwZTEgL1R5cGUgL0ZvbnQKPj4KZW5kb2JqCjQgMCBvYmoKPDwKL0Jhc2VGb250IC9aYXBmRGluZ2JhdHMgL05hbWUgL0YzIC9TdWJ0eXBlIC9UeXBlMSAvVHlwZSAvRm9udAo+PgplbmRvYmoKNSAwIG9iago8PAovQ29udGVudHMgMTAgMCBSIC9NZWRpYUJveCBbIDAgMCA2MTIgNzkyIF0gL1BhcmVudCA5IDAgUiAvUmVzb3VyY2VzIDw8Ci9Gb250IDEgMCBSIC9Qcm9jU2V0IFsgL1BERiAvVGV4dCAvSW1hZ2VCIC9JbWFnZUMgL0ltYWdlSSBdCj4+IC9Sb3RhdGUgMCAvVHJhbnMgPDwKCj4+IAogIC9UeXBlIC9QYWdlCj4+CmVuZG9iago2IDAgb2JqCjw8Ci9Db250ZW50cyAxMSAwIFIgL01lZGlhQm94IFsgMCAwIDYxMiA3OTIgXSAvUGFyZW50IDkgMCBSIC9SZXNvdXJjZXMgPDwKL0ZvbnQgMSAwIFIgL1Byb2NTZXQgWyAvUERGIC9UZXh0IC9JbWFnZUIgL0ltYWdlQyAvSW1hZ2VJIF0KPj4gL1JvdGF0ZSAwIC9UcmFucyA8PAoKPj4gCiAgL1R5cGUgL1BhZ2UKPj4KZW5kb2JqCjcgMCBvYmoKPDwKL1BhZ2VNb2RlIC9Vc2VOb25lIC9QYWdlcyA5IDAgUiAvVHlwZSAvQ2F0YWxvZwo+PgplbmRvYmoKOCAwIG9iago8PAovQXV0aG9yIChcKGFub255bW91c1wpKSAvQ3JlYXRpb25EYXRlIChEOjIwMjUxMjI0MDE0MDU2KzAyJzAwJykgL0NyZWF0b3IgKFwodW5zcGVjaWZpZWRcKSkgL0tleXdvcmRzICgpIC9Nb2REYXRlIChEOjIwMjUxMjI0MDE0MDU2KzAyJzAwJykgL1Byb2R1Y2VyIChSZXBvcnRMYWIgUERGIExpYnJhcnkgLSBcKG9wZW5zb3VyY2VcKSkgCiAgL1N1YmplY3QgKFwodW5zcGVjaWZpZWRcKSkgL1RpdGxlIChcKGFub255bW91c1wpKSAvVHJhcHBlZCAvRmFsc2UKPj4KZW5kb2JqCjkgMCBvYmoKPDwKL0NvdW50IDIgL0tpZHMgWyA1IDAgUiA2IDAgUiBdIC9UeXBlIC9QYWdlcwo+PgplbmRvYmoKMTAgMCBvYmoKPDwKL0ZpbHRlciBbIC9BU0NJSTg1RGVjb2RlIC9GbGF0ZURlY29kZSBdIC9MZW5ndGggMjk4Nwo+PgpzdHJlYW0KR2IhI11EMCtccicpaykwVTh0Ry9NbiZsLzBBKyhxUVFzR2owRz4nN1BNTmpRSGtBZ0svW2pgSmpmaVJHTzIkdXReYSg2SkM4ZmplVV09VyllNSpoQWgoOVM9ai5ESF5xQjxaOSdKP050ME1JaXRKXk4nJjBZSVg2cVgwRGc3UFdBLENMLS8yOWNXXmtdV1czYWQ7b19AcSZNLUZpRjlmRUk5XDU+WzdyP2RDMk1GIS5pWGVSUj4tRjVkbEI2U19sb14wbU9kNWUwOEkkcG9sJ2AmNSJzYmheNChVc21rRlxmWmp1NW49P2tqJzlAOnVPPGpbTVgvW2A/JSlrKDI+Ry5yS2hhZTguc1BYcTZXbGIyX0VZQlUnV08pY1JWXDUlWVY0QSNHYz5nWzEmTGtzKD8nKz1yKWM9K2VkQFpuZWxvam8lP0U7PioqOSZtVkcjPE8iQF1xW1NuLTJbIU9fXy1bP2o0LzBOXnRoPCJPblJMdGhUWjU2XEAwTyklQSFuJkBYXEVuO0VuPTNuQm5OTmZuQFsjP11dTDdoazZBOD8jK2hwKjljVkUrRWtCV2ZJJmpHQF1MZktKVGFPcS9DNktsT0g9LGhxVWIjaU1pY2o7P1xDS11RZ2MibVlcc0VMKCtpZ3VdMDYkOjRsLm1nM0x0U01WM0ZqSmwvSDBnaj4qOFRpQGRbPFkyNCViSHVZbGlEQWNnL3EyayVdPypEamBPUE9KMT5GUCk/ME5WVj4vK3A8NTlSWCNbZV5yNGlIZmlQMj9LWWRxXkI4I3MpS147NlZSSiddZUVPPnVUYjhmQUF1Qk0rRzhpM18yTm8pLUIpUmBXWDApQTw+SzlpJypQZEwkWjUmRWBwc0xrQU5fT1BrbD1OWCs6W1lEbGNQdGB1b29WSFs3XGZ0RF5LWWVNbjYiNzpCS1s7WlxXYVNxIUNQMkExOiIjLzFlQGU7WyxzKWlWUyY/OmVuQVdOQFxHLXE1T2piRSNtSj1XOWtRMCtWaExARkFHSSp1WVFHQUwhb1w0YSV0UTlOYzUmbUVvVUxZX0tuQT11NysrKlIoTig8bj9jNyJqNSFacW5MNDZPQE1lKjk/SWhIYGxcNS5aRDs4QFEnKSpTRks4TDFNbycsMFRZJ0QhKydyV1pzUiJQYmQqcFknTk5FQGdaaFdCYyxHOj8qPVBWI0hPODVWKmFIUlhqRVROYWReLWA7WXFZa1QzTlsxXl0lPGlacV1lR3ReYG9SKzpXJWdWcU9zayYsaEtNJG50NWRGYiMkR0N1VVRdYWAhTG1OayY9WXEuYUlhaUglMjlKYDJeN3NBOWZYK1lSZnBgYC85ODNaRk4rYi1Fa1Q7U0dnXSpTU2NaXlVCOzQ7NiYlPWJKQ2NyXUpKRWk4P2loRVstcCZqNnIkTkNTWi5HQzhtM2RXRkIzSDhTMDZBJCJoRlRvTXMmc1k1cmw0QSpEPlhJQ0JPV2tnOUUyXCFldWBIbSxYRlJrU1xqZi5OQ2BEVyFRJiteTCJOIlR0SEdDcUJxLDdgI29KaThpajNrSj9tMCMuYFhDSjhUU1ZBPyo6J3BkcWEtSThqWFlyaVtBKjJWYGw6S087YE8tOzpTVC03SVhBRFw2ZEJdNlg9KVRFSF9Qb29VaExYaG4xS0JZSCNZRWxeLFpuRkpjYEcrKUxwKiMiL3BjYDclbEEqcVI0KD9XLkE2N1ReLCdHc0clb0ZEZEpvWlExI0FhOT9cPi42TztAN2kyLXJdYDAkcWsoLFQpJ1coakRhUzhgNDBSYksuQmZsMHAtckIiazclI2FEMkpMUG5pZSJWUFhlKjBURSwnQnJjXjEnJWMtMENXTElhTDFmNTpSUW1TWFxGQDojZS5gbStfRjM4TUJHLERGInI7KClLM2ReJiptJiNyZFM0OCheaSdpSTRRYVFcKTxAMUkzJzomOCpbS01HP3ErKkpgS05LXS1HV3JzZEJzSF1UUm9sSWBvKFxtXzBAb2NuaiNtbHIrTGlcMVJbRiZNITExJDYlT3BRQV5zISpLaElVQFViZi4rbjwnXk4mTyUjND4jKEMwaGk5Rj5QZEMkKzU9V24zay4lazxeIlRVRjc4b2kwQyxRXnQsLGFmWVQ2MDlsPUBbLWIpTjFjSSNaaGk1PEJ0YTgmQ18wXFNCZD9oUGxmQE1KZVxVLSRvaSMpRWw1N0FGWEtPK1g7SVQ7L2dDZz5zbktjTHEmSVg5MWlcLWlZSk88TWc1PDNdVE5jbWw6akVZLEwxVikiVmpZRTMnUEtdZG1ZY0I7ZyNdTkMwKDxRVklFVlVrWC9IaDhOX21kSGFmSFFqN1VYNT5DSCVFU28zMzAsUkZfOiVyOEpXMFBEWy08ZDlYYHFpKlJPVjYsK20kcVNJQktnVidzcz5QQHRzUDtzUUgvcmFnNj1AZCQ8JkNqV2YrO105Mz5xNiptdVFecXVGPFBHOihqJUlPW0NEZU0wUUs9SlsxIWVmXz5CZHM/LD1PckZSKCNHNl4tUHQhLzVFIysjU0xcOC9TUTZpJzlKQzdXYEFBcGYwXElYKlMyN0AicmZUcGRbNl1aQ3FHbSxNVSMxLjFeQGlyY2tMX1VhV3M1cmZJOjZ1b1dOLFRLc01kYiQ7PyJeNSsyNF05TSpTXGRvY2NXMG0pUV5oTEs1JGJRYzplZ2hfJUEpKGtTW2M5dE11UlVDWGdAYGZMQFBaXkBlXk9IODNEYFguTSZyJyFSSFU+bF4yN3BHclpoLyxpb1YzUlA3cUw2YkdRZmBvUS9lUk9ZaSpHSiZrYF9cSyM4VSdkMF5qN1xDKnBCTVUkLVotXz09c1I0I3E/ZnM9PWxUOzwkQkBaKiZxKGdPIiVSJEBmZUpAMjVjNE1WLlBuSER0Tz07c2V1VS02a0BdMF1tcU9iWWVsJUE5a0g8Xjc8WjpdNklTRjBYa3FwU2NHKVQ5O2pLW2hkWSIkMVQ7W0BwOSJmSmhual07W2ZLL006NiY7OXBYRiNQZmdCWSs/RFsxV05IXChdMz5eQkQybEI+Z1JnWidnYWcvTWlKVGRiZXNtYkprJEkkczo8VSdEST5xSGZrc2RgSS5STjVzcWonW2VnUDYuNU5hOVBfPzFJIUlnUSZOXF9idS9fQU4pW1BmZmlYIj1MTWV1UzctM1lNRzJoaVJ1MkE3a25QSSgva0U5TzVHYk5rOnQ4bEQpTERGIVpIU1E4XztJMnNRO2s1JmouKEMxaSM+dG5EIis+Sj1kPUUxXk1jUUAncCwlPFEmZmdzPls3aWhxLi1kbyt0RT1CXE9XSFAsLG5Ob0VWXSFQTVhaOEkpUjJCK2QzJytFKFRQMGktQzkudVc6XlY7bV8sVGlRRUZZIWVNX2IuPyhbb0EwLW1nQDcnXVFxJi5pczwtV1tuUEgpNzsnTTQ8XDcncEdiTU9yMUFsV3FrVGZEVWk7NiMnW1E6ZWgjLmFgSlRAdWAiUCQ5cVVeZXQwR3JxVmluaGxpcCcmIjBgLEIvbjxlbkRWImFsOE1Jb0VCZz5PLDZpXFY8LXRIPEtAJGIqOSpvMElPXCIuM0BZTUJYaCtTS0RvdDtKI0QvMlxXYzpJSEMvJ2s6bzlyVDdLOmJjXDNxaVVmYylGXEdaaV5kU2A6Ny0rJmQ7dTtWWD5IKjY3QiktOTEsOVFjRmpYQjlYS15ncipgcCpnQlM0WEBmIm9aNUVKKCxGRDkoNVNhT1UsOlQhSXJmaiQ4cVdiInQ4Y3NzJShvRFwtM2AtQGAkNSRWUDxMTz5BLCsxaGYrWUJNKy03Yzk3Y01gKiYxUyZpK1UlMWUrbysnODNRdSwpZyoqMFhRLCknYiUmTUAndEtvYScjS0Z1cExnbixSUmJsWDA6ZV8rZCdjLUpdNVFLTmRobk8+b0woblxHUUBNLXVIWGA4J2ApbGNpLF1aOCUpWlhRNF5XK3FAX2cuS0RqWztQTmcodUczJVItUnJMfj5lbmRzdHJlYW0KZW5kb2JqCjExIDAgb2JqCjw8Ci9GaWx0ZXIgWyAvQVNDSUk4NURlY29kZSAvRmxhdGVEZWNvZGUgXSAvTGVuZ3RoIDE0MzcKPj4Kc3RyZWFtCkdhdWBSZ0pbJmsmOk5ebFxuXDpTX04lNFNgNDdSP05fLiRtJVlXS1lsaVNudVVHcy8rYjlQLTVXUzNFalFDU0RGNV4kbkBnJmJfLVxeZm04bCYtT2NuXSooQ1A5aUlZTDtxUkBWWztsNSo0UD8mKjVXZ15xL1BEcWhlXWpyKmQkM0pEQyVxXFk8MDE2aEpvNEZDaitWbTUkZSkkcEwmI3UtO1EhLFNAUmRraDZ0XypmYD1ZZjNrN1tIRlFJPlBHOUM0RGRrZmkhX3JmXFE+PVpqTkNAVCpTXGRqKkBLXXBgKSRtWU5mIyhNVTtQO25AJlZcIj81cF5gI1NbV00wVEhhQz8jclg9RC1gWGRePGZqXzA5JGx1Zm1HUDdVNF9iYzRhZHFmNClvVD0wVjA1NzpKUWQzYmtRTSoyR01GViswIV5EUUcoNDc5ZCxZQj8qWzA6dCVbKmssdSgvMVtMN0FlXV5gTnA3TzFDSFpdYXVETycxOSEqVEdxSzdsKC5YYFBtMTNbVy1jczgnQGNPTS83MHEkNkIjL19nKEJUMGJUMD1FbDVucVdRJWMwMEEoNDtsVUxvPl0zI3VzSkRmVz5bWTBMMD5fL3QmRmZQW21AWEtSP1ZuLGVSZXFeRTE+TyRWO3A4LEduTyhLRCJnIVd0MWRxKC8zMUYoTTpZTFBbbEd1P3FgRCdiYDM4JG9eIkxCMkxoJU8ianBqUU9DLEBtUlAjLDRNZi1FZm1TbUEvLD4jYk89WWRPUVY7ZTRmNiR1Xl5oayUySDUoQFRzIUIzJCg2bzMnMTlqZm0vQzphSio9THJvcDZAJkFbaVRsLFZLVkpFRytvWlIzSG5MOW9bWF1LaTk3ZiQkUGBkIl9xY2EzdFs9UjVCaTlUI2NgIyJPPlZDb09uVVl1cWs1YTJpKlpMbiwxX11sO2xVXytQQSp0I1AwZmliTWshODB0Tm8+UVkwK2wuMCdNUjQwQml0Nkc8UTtJbzpPVyEwOGs8KjQxJ00/UywtP0lKQmNrLEdOYFdRb01mRTlUOGdtRFJMUCYqVGFgVHB0bj9LJE1aM0UuYVo9XiRuJG8zMlBRP1xMXERLXDtPXjsiMGBaYHRJOUw1KU9TOSJCVT0+YEp1X2Y+Ym08ImFTbmkwKXUrVlc5TXNMWFJqZzY+SmdFSCpTNkxgbkdIPiRYQCMiI0FMSTdjJzhkIz4iQV8uSydfJjJqS1dBXjFEOV1LczdkXD1uXCxGbi1yKlRuMCNoVjJmPmc/WWtKKG5rallhOTBuNjJjbSU/Pjc4LjFiPCwwNSZBOmw2aDpXcyJFR0Q9U289c1QsQklrYHVtNDc5Wz1IdDtVUzBcU3RcM0dbc0AvXE85PmpVVyZCNTRcaWdpJnAsQChRPCJjNTZuOWQramdxYiolMGc5UU4iNFVSVnN1b2NvVDRUQF5dR19mRTIzbGBMM1M3V11OZD0qSydETXQsJTsqbztSZGJuMmtaJWU/Z2Y9cXFwYHMnLXRMS2o9IyNIKGZBYDR1WEIvZHUuWz06VzBPbiRAOS4tUT1vRl9bRGtQdVxfcC9LV3Jucj1UVSE5OUBPJ2RfXkUzT09ndG1lJC9pUio8Oj1Za1hJXUdBLG8vTUxIYmMwaWhGOVskQDksLTtxTGlHMmgzQGNqZUxaSmdDIWxFLEBlSilVPi44NydOTnROYEdSOERcMUA8XVFtJSFcN0RBLjMpXlcxNTFDLyMmSzhva2peYEZeazJkM0c1ZmhpTWQudVcuZklnRTBgI0lKKV5PTEg6bVs/b3RXT2dRJkBNJzBUdVYtRzZYJiw6cy5UT0ZCL25AcU46UkdFMSIwQCRjOzloZjM+KnBoVERBa00+JlJQQUlAIThGQUFaQG5OPUdmaV5DOkAkRUVfS04sXD5AZ2dqQi5+PmVuZHN0cmVhbQplbmRvYmoKeHJlZgowIDEyCjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDA2MSAwMDAwMCBuIAowMDAwMDAwMTEyIDAwMDAwIG4gCjAwMDAwMDAyMTkgMDAwMDAgbiAKMDAwMDAwMDMzMSAwMDAwMCBuIAowMDAwMDAwNDE0IDAwMDAwIG4gCjAwMDAwMDA2MDggMDAwMDAgbiAKMDAwMDAwMDgwMiAwMDAwMCBuIAowMDAwMDAwODcwIDAwMDAwIG4gCjAwMDAwMDExNTAgMDAwMDAgbiAKMDAwMDAwMTIxNSAwMDAwMCBuIAowMDAwMDA0Mjk0IDAwMDAwIG4gCnRyYWlsZXIKPDwKL0lEIApbPGJkMGEyMGEzMjAxMjViZTE2ZWYzODI1ZDA3NWZjYWRmPjxiZDBhMjBhMzIwMTI1YmUxNmVmMzgyNWQwNzVmY2FkZj5dCiUgUmVwb3J0TGFiIGdlbmVyYXRlZCBQREYgZG9jdW1lbnQgLS0gZGlnZXN0IChvcGVuc291cmNlKQoKL0luZm8gOCAwIFIKL1Jvb3QgNyAwIFIKL1NpemUgMTIKPj4Kc3RhcnR4cmVmCjU4MjMKJSVFT0YK' | $SSH 'base64 -d > ~/cv_portofolio/Mikhael_CV.pdf'

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
