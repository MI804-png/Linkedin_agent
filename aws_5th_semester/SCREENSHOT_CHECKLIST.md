# Screenshot Checklist for Project Documentation

## Screenshots to Take for Complete Documentation

### 1. Website - Home Page
**URL:** `http://MyProject-ALB-1911809755.eu-west-1.elb.amazonaws.com`
- ✅ Full page screenshot showing:
  - Header with logo
  - Hero section ("Transform Your Business")
  - Services section (6 cards)
  - Scroll down to show stats section

### 2. Website - Contact Form (Before Submission)
**URL:** Same Load Balancer URL, scroll to bottom
- ✅ Contact form with filled fields:
  - Name: Mikhael Nabil Salama Rezk
  - Email: mikhael@example.com
  - Company: Demo Company
  - Service: Cloud Migration
  - Message: Testing the AWS cloud infrastructure project

### 3. Website - Contact Form (Success Message)
- ✅ After clicking "Send Message"
- ✅ Show green success message: "Thank you! Your message has been sent successfully."

### 4. CloudFormation Stack
**Console:** CloudFormation → Stacks
- ✅ Stack list showing "MyAWSProject" with status "CREATE_COMPLETE"
- ✅ Click on stack → Resources tab (show all resources)
- ✅ Click on stack → Outputs tab (show RDS endpoint, Load Balancer DNS, S3 bucket)

### 5. EC2 Instances
**Console:** EC2 → Instances
- ✅ Both instances running:
  - MyProject-Web-UI (with public IP)
  - MyProject-API
- ✅ Show instance state: "Running"
- ✅ Show instance types: t3.micro

### 6. Load Balancer
**Console:** EC2 → Load Balancers
- ✅ MyProject-ALB details
- ✅ State: "Active"
- ✅ DNS name visible
- ✅ Click on "Listeners and rules" tab → show the 2 rules

### 7. Target Groups
**Console:** EC2 → Target Groups
- ✅ MyProject-Web-TG showing:
  - 1 Total target
  - 1 Healthy
  - 0 Unhealthy
- ✅ Click on "Targets" tab to show registered instance

### 8. RDS Database
**Console:** RDS → Databases
- ✅ myproject-db details
- ✅ Status: "Available"
- ✅ Engine: MySQL 8.0
- ✅ Instance class: db.t3.micro
- ✅ Endpoint visible

### 9. Database Data - EC2 Terminal
**In EC2 Instance Connect terminal:**

Run this command and take screenshot:
```bash
mysql -h myproject-db.c900uesmqwtf.eu-west-1.rds.amazonaws.com -u admin -pMyPassword123 -D myprojectdb -e "SELECT * FROM contacts;"
```
- ✅ Show the query results with your submitted contact data
- ✅ Show all columns: id, name, email, company, service, message, timestamp, created_at

### 10. Database Data - Contact Count
**In EC2 Instance Connect terminal:**
```bash
mysql -h myproject-db.c900uesmqwtf.eu-west-1.rds.amazonaws.com -u admin -pMyPassword123 -D myprojectdb -e "SELECT COUNT(*) as total_contacts FROM contacts;"
```
- ✅ Show the count of contacts

### 11. Docker Container Status
**In EC2 Instance Connect terminal:**
```bash
sudo docker ps
```
- ✅ Show container "webapp" running
- ✅ Show port mapping: 0.0.0.0:80->3000/tcp
- ✅ Show status: "Up"

### 12. Docker Container Logs
**In EC2 Instance Connect terminal:**
```bash
sudo docker logs webapp --tail 30
```
- ✅ Show "Server running" message
- ✅ Show "Database initialized"
- ✅ Show any API request logs

### 13. VPC Configuration
**Console:** VPC → Your VPCs
- ✅ Show VPC with CIDR 10.0.0.0/16
- ✅ Show 2 subnets in different AZs

### 14. S3 Bucket
**Console:** S3 → Buckets
- ✅ Show myproject-storage-674182808760 bucket
- ✅ Show cloudtech-app.tar.gz file if present

### 15. Security Groups
**Console:** EC2 → Security Groups
- ✅ Show MyProject-LB-SG (Load Balancer security group)
- ✅ Show MyProject-EC2-SG (EC2 security group)
- ✅ Show MyProject-RDS-SG (Database security group)
- ✅ Click on one to show inbound/outbound rules

### 16. API Health Check
**In browser or terminal:**
```
http://MyProject-ALB-1911809755.eu-west-1.elb.amazonaws.com/health
```
- ✅ Show JSON response: {"status":"ok"}

### 17. API Endpoint
**In browser or terminal:**
```
http://MyProject-ALB-1911809755.eu-west-1.elb.amazonaws.com/api
```
- ✅ Show JSON response: {"message":"API is running"}

---

## Optional Advanced Screenshots

### 18. CloudFormation Template
**Console:** CloudFormation → MyAWSProject → Template tab
- ✅ Show the YAML template code

### 19. EC2 Instance Connect
**Console:** EC2 → Connect → EC2 Instance Connect
- ✅ Show the browser-based terminal interface

### 20. Target Group Health Check Configuration
**Console:** EC2 → Target Groups → MyProject-Web-TG → Health checks tab
- ✅ Show health check settings (port, path, interval)

---

## Screenshot Organization

**Recommended naming:**
```
01_website_homepage.png
02_website_contact_form.png
03_website_success_message.png
04_cloudformation_stack.png
05_cloudformation_resources.png
06_ec2_instances.png
07_load_balancer.png
08_target_groups_healthy.png
09_rds_database.png
10_database_contacts_table.png
11_docker_container_status.png
12_docker_logs.png
13_vpc_configuration.png
14_s3_bucket.png
15_security_groups.png
16_api_health_check.png
```

---

## How to Take Screenshots

**Windows:**
- **Full screen:** Press `Win + Shift + S` → Select area
- **Active window:** Press `Alt + Print Screen`
- Screenshots save to clipboard → Paste in Paint/Word/PowerPoint

**Save screenshots to:**
`C:\aws\screenshots\`

---

## For PDF/PowerPoint Presentation

**Suggested slide order:**
1. Title slide (Your name, Neptun code)
2. Architecture diagram (all AWS resources)
3. CloudFormation stack (CREATE_COMPLETE)
4. Website homepage
5. Contact form submission
6. Database data verification
7. EC2 instances running
8. Load Balancer active
9. RDS database available
10. Docker container running
11. Security configuration
12. Cost optimization summary
13. Conclusion

---

## Quick Commands for Terminal Screenshots

Copy these commands to run in EC2 terminal:

```bash
# Database query
mysql -h myproject-db.c900uesmqwtf.eu-west-1.rds.amazonaws.com -u admin -pMyPassword123 -D myprojectdb -e "SELECT * FROM contacts;"

# Contact count
mysql -h myproject-db.c900uesmqwtf.eu-west-1.rds.amazonaws.com -u admin -pMyPassword123 -D myprojectdb -e "SELECT COUNT(*) FROM contacts;"

# Docker status
sudo docker ps

# Docker logs
sudo docker logs webapp --tail 30

# Test health endpoint locally
curl http://localhost:80/health

# Test API locally
curl http://localhost:80/api
```

---

**Take all screenshots now while resources are running!**
**After screenshots, you can safely delete the CloudFormation stack.**
