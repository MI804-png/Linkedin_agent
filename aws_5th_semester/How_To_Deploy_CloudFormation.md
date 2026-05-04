# How to Deploy Everything Automatically with CloudFormation

## What is CloudFormation?
CloudFormation is AWS's infrastructure-as-code service. You upload a template file, and it automatically creates all resources for you!

---

## PREREQUISITES (Do These First!)

### 1. EC2 Key Pair - ✅ YOU ALREADY HAVE THIS!
**Your existing key pair:**
```
Key Name: key-0e7e39471a6f908f1
Type: RSA
Fingerprint: 31:9c:6d:f0:c3:31:61:6d:72:59:62:0a:c6:d0:dd:f3:74:6f:d1:25
Created: 2025/10/01 15:34 GMT+3
```

✅ **You can skip creating a new key pair!** You'll use: `key-0e7e39471a6f908f1`

**Make sure you have the .pem file saved on your computer!**

### 2. Find Your IP Address (for SSH access)
1. Go to: https://whatismyipaddress.com/
2. Copy your IPv4 address (e.g., 123.45.67.89)
3. Add `/32` at the end (e.g., 123.45.67.89/32)
4. Save this for later

---

## STEP-BY-STEP DEPLOYMENT

### Step 1: Open CloudFormation Console
1. Go to AWS Console: https://console.aws.amazon.com/cloudformation
2. **Make sure you're in EU-West-1 (Ireland) region** (check top-right corner)
3. Click **"Create stack"** → **"With new resources (standard)"**

### Step 2: Upload Template
1. **Choose "Upload a template file"**
2. Click **"Choose file"**
3. Select the file: `cloudformation-template.yaml` (from your aws folder)
4. Click **"Next"**

### Step 3: Configure Stack Details

**Stack name:**
```
MyAWSProject
```

**Parameters:**
- **KeyPairName**: Select `key-0e7e39471a6f908f1` (your existing key)
- **DBPassword**: Enter a strong password (min 8 characters, letters and numbers only)
  - Example: `MyPassword123`
  - **⚠️ WRITE THIS DOWN! You'll need it later!**
- **YourIPAddress**: Enter your IP with /32 (e.g., `123.45.67.89/32`)
  - Or use `0.0.0.0/0` to allow SSH from anywhere (less secure)

Click **"Next"**

### Step 4: Configure Stack Options
- Leave everything as default
- Scroll to bottom
- Click **"Next"**

### Step 5: Review and Create
1. Scroll to bottom
2. ✅ Check the box: **"I acknowledge that AWS CloudFormation might create IAM resources"**
3. Click **"Submit"**

---

## WAIT FOR COMPLETION

### What Happens Now?
CloudFormation will create everything automatically! This takes about **10-15 minutes**.

**Watch the progress:**
- Status shows: `CREATE_IN_PROGRESS`
- Click refresh button to update
- You can click on **"Events"** tab to see what's being created in real-time

**Resources being created:**
1. ✅ VPC and Subnets (1 min)
2. ✅ Internet Gateway and Route Tables (1 min)
3. ✅ Security Groups (1 min)
4. ✅ S3 Bucket (1 min)
5. ✅ RDS Database (5-7 minutes) ⏱️
6. ✅ EC2 Instances (3-4 minutes)
7. ✅ Load Balancer and Target Groups (3-4 minutes)

**When complete:**
- Status changes to: `CREATE_COMPLETE` ✅
- You'll see a green checkmark

---

## GETTING YOUR URLS

### Step 1: View Outputs
1. Click on your stack name: **MyAWSProject**
2. Click the **"Outputs"** tab
3. You'll see all important information:

```
LoadBalancerDNS: MyProject-ALB-xxxxxxxxx.eu-west-1.elb.amazonaws.com
WebUIURL: http://MyProject-ALB-xxxxxxxxx.eu-west-1.elb.amazonaws.com
APIURL: http://xx.xx.xx.xx:3000
RDSEndpoint: myproject-db.xxxxxxxxx.eu-west-1.rds.amazonaws.com
S3BucketName: myproject-storage-xxxxxxxxxxxx
WebUIInstanceIP: xx.xx.xx.xx
APIInstanceIP: xx.xx.xx.xx
```

### Step 2: Test Your Application

**Test Web UI:**
1. Copy the **WebUIURL** from Outputs
2. Paste in browser
3. Wait 2-3 minutes for Docker to finish setup
4. Refresh if needed
5. You should see: "Welcome to My AWS Project!"

**Test API:**
1. Copy the **APIURL** from Outputs
2. Paste in browser
3. You should see JSON response with database endpoint

**Test S3:**
1. Go to S3 Console
2. Find bucket: `myproject-storage-xxxxxxxxxxxx`
3. Upload a test file
4. Click on file → Copy URL → Open in browser

---

## VERIFY EVERYTHING WORKS

### Check EC2 Instances
1. Go to **EC2** → **Instances**
2. You should see:
   - ✅ MyProject-Web-UI (running)
   - ✅ MyProject-API (running)

### Check Load Balancer
1. Go to **EC2** → **Load Balancers**
2. You should see:
   - ✅ MyProject-ALB (active)

### Check RDS Database
1. Go to **RDS** → **Databases**
2. You should see:
   - ✅ myproject-db (available)

### Check S3 Bucket
1. Go to **S3**
2. You should see:
   - ✅ myproject-storage-xxxxxxxxxxxx

### Check VPC
1. Go to **VPC** → **Your VPCs**
2. You should see:
   - ✅ MyProject-VPC

---

## CONNECT TO EC2 INSTANCES (SSH)

### For Mac/Linux:
```bash
# Change permission of key file
chmod 400 key-0e7e39471a6f908f1.pem

# SSH to Web UI instance
ssh -i key-0e7e39471a6f908f1.pem ubuntu@[WebUIInstanceIP]

# Check Docker is running
docker ps

# View container logs
docker logs webapp
```

### For Windows (using PuTTY):
1. Convert .ppk key using PuTTYgen if needed
2. Open PuTTY
3. Enter IP address from Outputs
4. Connection → SSH → Auth → Browse to your key file
5. Click Open

---

## CONNECT TO RDS DATABASE

### From EC2 Instance:
```bash
# SSH into Web UI instance first
ssh -i key-0e7e39471a6f908f1.pem ubuntu@[WebUIInstanceIP]

# Install MySQL client
sudo apt update
sudo apt install mysql-client -y

# Connect to RDS
mysql -h [RDSEndpoint] -u admin -p
# Enter your DBPassword when prompted

# Test database
SHOW DATABASES;
USE myprojectdb;
CREATE TABLE test (id INT, name VARCHAR(50));
INSERT INTO test VALUES (1, 'Hello from RDS!');
SELECT * FROM test;
```

---

## TROUBLESHOOTING

### If Web UI doesn't load:
1. Wait 5 minutes (Docker needs time to build and start)
2. Check CloudFormation Events tab for errors
3. SSH into instance and check:
```bash
docker ps
docker logs webapp
cat /var/log/cloud-init-output.log
```

### If Stack Creation Fails:
1. Click on the failed stack
2. Go to "Events" tab
3. Look for red "CREATE_FAILED" entries
4. Common issues:
   - ❌ **Key pair doesn't exist**: Create the key pair first!
   - ❌ **Password too weak**: Use 8+ alphanumeric characters
   - ❌ **IP format wrong**: Use format x.x.x.x/32
   - ❌ **Resource limits**: Check you haven't reached AWS limits

### If Target Groups Show Unhealthy:
1. Wait 3-5 minutes for health checks
2. Go to **EC2** → **Target Groups**
3. Click on target group
4. Check "Targets" tab for health status
5. If still unhealthy, SSH into instance and check Docker

---

## COST ESTIMATE

**Monthly costs (approximate):**
- 2 × t2.micro EC2: ~$17/month
- db.t3.micro RDS: ~$12/month
- Application Load Balancer: ~$16/month
- S3 storage: First 5GB free
- Data transfer: First 1GB free

**Total: ~$45-50/month**

**With AWS Free Tier (first 12 months):**
- 750 hours/month t2.micro EC2: FREE
- 750 hours/month RDS: FREE
- Result: ~$16/month (just ALB)

---

## DELETE EVERYTHING (CLEANUP)

### Option 1: Delete the Entire Stack (EASIEST)
1. Go to **CloudFormation**
2. Select your stack: **MyAWSProject**
3. Click **"Delete"**
4. Click **"Delete stack"** to confirm
5. Wait 10-15 minutes
6. Everything is deleted automatically! ✅

### Option 2: Delete S3 Bucket First (if stack deletion fails)
Sometimes S3 bucket prevents stack deletion:
1. Go to **S3**
2. Select your bucket
3. Click **"Empty"** → Type "permanently delete" → Confirm
4. Now try deleting the CloudFormation stack again

---

## TAKING SCREENSHOTS FOR DOCUMENTATION

Take screenshots of:
1. ✅ CloudFormation stack in CREATE_COMPLETE status
2. ✅ CloudFormation Outputs tab
3. ✅ VPC Dashboard showing your VPC
4. ✅ EC2 Instances running
5. ✅ Load Balancer showing healthy targets
6. ✅ RDS Database in available state
7. ✅ S3 Bucket with uploaded files
8. ✅ Web UI in browser (showing the page)
9. ✅ API response in browser (JSON output)
10. ✅ Security Groups configuration

---

## DOCUMENTATION CHECKLIST

For your 10+ page report, you now have:

✅ **Architecture**: Automatically created by CloudFormation
✅ **VPC**: Complete network with public/private subnets
✅ **EC2**: 2 instances with Docker
✅ **S3**: Storage bucket with public access
✅ **RDS**: MySQL database
✅ **Load Balancer**: Traffic distribution
✅ **Infrastructure as Code**: Complete CloudFormation template
✅ **Screenshots**: All resources created
✅ **Testing**: URLs and connection details

---

## NEXT STEPS

1. ✅ Upload CloudFormation template
2. ✅ Wait for completion (10-15 min)
3. ✅ Test all URLs from Outputs
4. ✅ Take screenshots
5. ✅ Upload files to S3
6. ✅ Test database connection
7. ✅ Write documentation
8. ✅ **DELETE STACK when done!**

---

## QUICK REFERENCE

**What was created automatically:**
- 1 VPC with 4 subnets (2 public, 2 private)
- 1 Internet Gateway
- 1 Route Table
- 3 Security Groups
- 1 S3 Bucket
- 1 RDS MySQL Database
- 2 EC2 Instances (with Docker pre-installed)
- 1 Application Load Balancer
- 2 Target Groups

**Total time:** 10-15 minutes
**Total clicks:** ~10 clicks (vs. 100+ clicks manually!)
**Total resources:** 20+ AWS resources

**This is the EASIEST way to deploy your AWS project!** 🚀
