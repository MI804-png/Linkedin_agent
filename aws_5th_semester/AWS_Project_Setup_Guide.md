# AWS Project Setup Guide - Step by Step
**Region: EU-West-1 (Ireland)**

## Project Overview
This guide will help you create:
- VPC with public/private subnets
- 2 EC2 instances (Web UI + API with Docker)
- S3 bucket for static files
- RDS MySQL database
- Application Load Balancer

---

## STEP 1: Create VPC (Virtual Private Cloud)

### 1.1 Go to VPC Dashboard
- Search for "VPC" in AWS Console
- Click "Create VPC"

### 1.2 VPC Configuration
```
Name: MyProject-VPC
IPv4 CIDR: 10.0.0.0/16
Tenancy: Default
```
Click **Create VPC**

### 1.3 Create Subnets
Create 2 public subnets (for EC2 and Load Balancer):

**Public Subnet 1:**
```
Name: MyProject-Public-1a
VPC: MyProject-VPC
Availability Zone: eu-west-1a
IPv4 CIDR: 10.0.1.0/24
```

**Public Subnet 2:**
```
Name: MyProject-Public-1b
VPC: MyProject-VPC
Availability Zone: eu-west-1b
IPv4 CIDR: 10.0.2.0/24
```

Create 2 private subnets (for RDS):

**Private Subnet 1:**
```
Name: MyProject-Private-1a
VPC: MyProject-VPC
Availability Zone: eu-west-1a
IPv4 CIDR: 10.0.3.0/24
```

**Private Subnet 2:**
```
Name: MyProject-Private-1b
VPC: MyProject-VPC
Availability Zone: eu-west-1b
IPv4 CIDR: 10.0.4.0/24
```

### 1.4 Create Internet Gateway
```
Name: MyProject-IGW
```
- After creation, click "Actions" → "Attach to VPC"
- Select MyProject-VPC

### 1.5 Create Route Table
```
Name: MyProject-Public-RT
VPC: MyProject-VPC
```
- Click "Edit routes" → "Add route"
- Destination: 0.0.0.0/0
- Target: Select your Internet Gateway (MyProject-IGW)
- Save

**Associate subnets:**
- Go to "Subnet Associations" tab
- Click "Edit subnet associations"
- Select both PUBLIC subnets (MyProject-Public-1a and MyProject-Public-1b)
- Save

---

## STEP 2: Create Security Groups

### 2.1 Load Balancer Security Group
```
Name: MyProject-LB-SG
Description: Security group for Load Balancer
VPC: MyProject-VPC

Inbound Rules:
- Type: HTTP, Port: 80, Source: 0.0.0.0/0
- Type: HTTPS, Port: 443, Source: 0.0.0.0/0

Outbound Rules:
- All traffic (default)
```

### 2.2 EC2 Security Group
```
Name: MyProject-EC2-SG
Description: Security group for EC2 instances
VPC: MyProject-VPC

Inbound Rules:
- Type: HTTP, Port: 80, Source: MyProject-LB-SG
- Type: Custom TCP, Port: 3000, Source: MyProject-LB-SG (for API)
- Type: SSH, Port: 22, Source: Your IP address

Outbound Rules:
- All traffic (default)
```

### 2.3 RDS Security Group
```
Name: MyProject-RDS-SG
Description: Security group for RDS
VPC: MyProject-VPC

Inbound Rules:
- Type: MySQL/Aurora, Port: 3306, Source: MyProject-EC2-SG

Outbound Rules:
- All traffic (default)
```

---

## STEP 3: Create S3 Bucket

### 3.1 Go to S3 Dashboard
- Click "Create bucket"

### 3.2 Bucket Configuration
```
Bucket name: myproject-storage-[your-unique-id]
Region: EU (Ireland) eu-west-1
Block all public access: Uncheck (for public website hosting)
Bucket Versioning: Enable
```
Click **Create bucket**

### 3.3 Upload Test File
- Click on your bucket
- Click "Upload"
- Add a test file (e.g., logo.png or test.txt)
- Click "Upload"

### 3.4 Make Bucket Public (Optional)
- Go to "Permissions" tab
- Edit "Bucket policy"
- Add this policy (replace YOUR-BUCKET-NAME):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
        }
    ]
}
```

---

## STEP 4: Create RDS Database

### 4.1 Go to RDS Dashboard
- Click "Create database"

### 4.2 Database Configuration
```
Engine: MySQL
Version: MySQL 8.0 (latest)
Template: Free tier

Settings:
DB instance identifier: myproject-db
Master username: admin
Master password: [Create a strong password - SAVE THIS!]

Instance configuration:
DB instance class: db.t3.micro (or db.t2.micro for free tier)

Storage:
Storage type: General Purpose SSD (gp2)
Allocated storage: 20 GB

Connectivity:
VPC: MyProject-VPC
Subnet group: Create new DB subnet group
Public access: No
VPC security group: MyProject-RDS-SG
Availability Zone: eu-west-1a

Database authentication: Password authentication

Additional configuration:
Initial database name: myprojectdb
Backup retention: 7 days
```
Click **Create database**

⏱️ **Wait 5-10 minutes for database to be created**

---

## STEP 5: Create EC2 Instances

### 5.1 Launch First EC2 Instance (Web UI)

Go to EC2 Dashboard → Click "Launch Instance"

**Instance 1 - Web UI:**
```
Name: MyProject-Web-UI
AMI: Ubuntu Server 22.04 LTS
Instance type: t2.micro
Key pair: Create new key pair (download and save it!)
  Name: myproject-key
  Type: RSA
  Format: .pem

Network settings:
VPC: MyProject-VPC
Subnet: MyProject-Public-1a
Auto-assign public IP: Enable
Security group: MyProject-EC2-SG

Storage: 8 GB gp2

Advanced details - User data (paste this):
```

```bash
#!/bin/bash
apt update
apt upgrade -y
apt install docker.io -y
systemctl start docker
systemctl enable docker
usermod -aG docker ubuntu

# Create simple web page
mkdir -p /home/ubuntu/webapp
cat > /home/ubuntu/webapp/index.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>My AWS Project - Web UI</title>
    <style>
        body { font-family: Arial; text-align: center; padding: 50px; background: #f0f0f0; }
        h1 { color: #FF9900; }
        .container { background: white; padding: 30px; border-radius: 10px; max-width: 600px; margin: 0 auto; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Welcome to My AWS Project!</h1>
        <h2>Web UI Server</h2>
        <p>This is running on EC2 with Docker</p>
        <p>Instance: Web-UI</p>
    </div>
</body>
</html>
EOF

cat > /home/ubuntu/webapp/Dockerfile << 'EOF'
FROM ubuntu:22.04
RUN apt update && apt upgrade -y && apt install apache2 -y
COPY index.html /var/www/html/index.html
EXPOSE 80
CMD ["apachectl", "-D", "FOREGROUND"]
EOF

# Build and run Docker container
cd /home/ubuntu/webapp
docker build -t webapp .
docker run -d -p 80:80 --name webapp --restart always webapp
```

Click **Launch instance**

### 5.2 Launch Second EC2 Instance (API Server)

Click "Launch Instance" again

**Instance 2 - API Server:**
```
Name: MyProject-API
AMI: Ubuntu Server 22.04 LTS
Instance type: t2.micro
Key pair: Use existing (myproject-key)

Network settings:
VPC: MyProject-VPC
Subnet: MyProject-Public-1b
Auto-assign public IP: Enable
Security group: MyProject-EC2-SG

Storage: 8 GB gp2

Advanced details - User data (paste this):
```

```bash
#!/bin/bash
apt update
apt upgrade -y
apt install docker.io -y
systemctl start docker
systemctl enable docker
usermod -aG docker ubuntu

# Create simple API
mkdir -p /home/ubuntu/api
cat > /home/ubuntu/api/server.js << 'EOF'
const http = require('http');
const hostname = '0.0.0.0';
const port = 3000;

const server = http.createServer((req, res) => {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'application/json');
  res.end(JSON.stringify({
    message: 'Hello from API Server!',
    status: 'running',
    instance: 'API',
    timestamp: new Date().toISOString()
  }));
});

server.listen(port, hostname, () => {
  console.log(`API Server running at http://${hostname}:${port}/`);
});
EOF

cat > /home/ubuntu/api/Dockerfile << 'EOF'
FROM node:18-alpine
WORKDIR /app
COPY server.js .
EXPOSE 3000
CMD ["node", "server.js"]
EOF

# Build and run Docker container
cd /home/ubuntu/api
docker build -t api .
docker run -d -p 3000:3000 --name api --restart always api
```

Click **Launch instance**

⏱️ **Wait 2-3 minutes for instances to launch and run user data scripts**

---

## STEP 6: Create Application Load Balancer

### 6.1 Go to EC2 → Load Balancers
- Click "Create Load Balancer"
- Select "Application Load Balancer"

### 6.2 Configure Load Balancer
```
Name: MyProject-ALB
Scheme: Internet-facing
IP address type: IPv4

Network mapping:
VPC: MyProject-VPC
Availability Zones:
  ✓ eu-west-1a (MyProject-Public-1a)
  ✓ eu-west-1b (MyProject-Public-1b)

Security groups: MyProject-LB-SG
```

### 6.3 Configure Target Groups

**Create Target Group 1 (Web UI):**
- Click "Create target group"
```
Target type: Instances
Name: MyProject-Web-TG
Protocol: HTTP
Port: 80
VPC: MyProject-VPC

Health checks:
Path: /
```
- Click "Next"
- Select "MyProject-Web-UI" instance
- Click "Include as pending below"
- Click "Create target group"

**Create Target Group 2 (API):**
- Click "Create target group"
```
Target type: Instances
Name: MyProject-API-TG
Protocol: HTTP
Port: 3000
VPC: MyProject-VPC

Health checks:
Path: /
```
- Click "Next"
- Select "MyProject-API" instance
- Click "Include as pending below"
- Click "Create target group"

### 6.4 Configure Listeners
Back in Load Balancer creation:

```
Listeners:
Protocol: HTTP
Port: 80
Default action: Forward to MyProject-Web-TG
```

Click "Add listener" for API:
```
Protocol: HTTP
Port: 3000
Default action: Forward to MyProject-API-TG
```

Click **Create load balancer**

⏱️ **Wait 3-5 minutes for load balancer to become active**

---

## STEP 7: Test Your Setup

### 7.1 Get Load Balancer DNS
- Go to EC2 → Load Balancers
- Select MyProject-ALB
- Copy the "DNS name" (e.g., MyProject-ALB-123456789.eu-west-1.elb.amazonaws.com)

### 7.2 Test Web UI
Open browser:
```
http://[YOUR-ALB-DNS-NAME]
```
You should see the Web UI page

### 7.3 Test API
Open browser:
```
http://[YOUR-ALB-DNS-NAME]:3000
```
You should see JSON response from API

### 7.4 Test S3
- Go to S3 → Your bucket
- Click on uploaded file
- Copy "Object URL" and open in browser

### 7.5 Test RDS Connection
SSH into Web-UI instance:
```bash
ssh -i myproject-key.pem ubuntu@[EC2-PUBLIC-IP]

# Install MySQL client
sudo apt install mysql-client -y

# Connect to RDS (use your RDS endpoint from RDS console)
mysql -h [RDS-ENDPOINT] -u admin -p
# Enter password when prompted

# Test database
SHOW DATABASES;
USE myprojectdb;
```

---

## STEP 8: Clean Up (When Done)

**Important:** To avoid charges, delete resources in this order:

1. Load Balancer
2. Target Groups
3. EC2 Instances
4. RDS Database
5. S3 Bucket (empty it first)
6. Internet Gateway (detach first)
7. Subnets
8. Route Tables
9. Security Groups
10. VPC

---

## Documentation Checklist

For your 10+ page report, include:

✓ Architecture diagram
✓ VPC configuration (CIDR blocks, subnets)
✓ Security group rules
✓ EC2 instance details (AMI, instance type, user data scripts)
✓ Dockerfile content and Docker commands
✓ RDS configuration and connection details
✓ S3 bucket policy and usage
✓ Load Balancer configuration
✓ Screenshots of working application
✓ Challenges faced and solutions
✓ Cost analysis
✓ References

---

## Quick Reference

**5 Components Used:**
1. ✅ VPC - Network infrastructure
2. ✅ 2 EC2 Services - Web UI + API
3. ✅ S3 - File storage
4. ✅ RDS - MySQL database
5. ✅ Load Balancer - Traffic distribution

**Bonus:** Docker is used on both EC2 instances!

---

## Troubleshooting

**If Web UI doesn't load:**
- Check EC2 instance is running
- Check security group allows port 80
- SSH into instance and run: `docker ps` to see if container is running
- Check user data logs: `cat /var/log/cloud-init-output.log`

**If API doesn't respond:**
- Check security group allows port 3000
- SSH into API instance and check: `docker logs api`

**If can't connect to RDS:**
- Verify RDS security group allows traffic from EC2 security group
- Check RDS endpoint is correct
- Verify database is in "Available" state

**If Load Balancer shows unhealthy targets:**
- Wait 2-3 minutes for health checks to pass
- Verify target group health check path is correct
- Check instances are running and Docker containers are up

---

## Cost Estimate (Approximate)

- VPC: Free
- 2 × t2.micro EC2: ~$0.0116/hour × 2 = ~$17/month
- db.t3.micro RDS: ~$0.017/hour = ~$12/month
- ALB: ~$0.0225/hour = ~$16/month
- S3: First 5GB free, then ~$0.023/GB

**Total: ~$45-50/month** (with free tier: ~$20-25/month)

**Remember to SHUT DOWN when not using to minimize costs!**
