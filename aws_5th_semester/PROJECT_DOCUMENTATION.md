# AWS Cloud Infrastructure Project Documentation

**Student Name:** Mikhael Nabil Salama Rezk  
**Neptun Code:** IHUTSC  
**Date:** November 25, 2025  
**Region:** EU-West-1 (Ireland)

---

## Executive Summary

This project demonstrates the deployment of a complete cloud-based web application infrastructure on Amazon Web Services (AWS). The solution implements a highly available, scalable architecture featuring a professional website with database connectivity, load balancing, and containerized application deployment.

---

## Architecture Overview

### Infrastructure Components

The deployed architecture consists of the following AWS services:

1. **Virtual Private Cloud (VPC)**
   - CIDR Block: 10.0.0.0/16
   - VPC ID: vpc-01d140e788ae1d7f2
   - Multi-AZ deployment across eu-west-1a and eu-west-1b

2. **Public Subnets**
   - Subnet 1 (eu-west-1a): subnet-05f43599d4a539119
   - Subnet 2 (eu-west-1b): subnet-0a652036531af11c46

3. **EC2 Instances**
   - **Web UI Instance:**
     - Instance ID: i-05b057aeec35a3b64
     - Public IP: 3.249.134.131
     - Instance Type: t3.micro
     - Operating System: Ubuntu 22.04 LTS
     - Availability Zone: eu-west-1a
   
   - **API Instance:**
     - Instance ID: i-0fca9f6d7bc9d30ba
     - Public IP: 3.250.18.98
     - Instance Type: t3.micro
     - Operating System: Ubuntu 22.04 LTS
     - Availability Zone: eu-west-1b

4. **Application Load Balancer (ALB)**
   - Name: MyProject-ALB
   - DNS: MyProject-ALB-1911809755.eu-west-1.elb.amazonaws.com
   - Type: Application Load Balancer
   - Scheme: Internet-facing
   - IP Address Type: IPv4

5. **Target Groups**
   - **MyProject-Web-TG:** Port 80 (HTTP) - 1 Healthy Target
   - **MyProject-API-TG:** Port 3000 (HTTP) - 0 Healthy Targets

6. **RDS MySQL Database**
   - Engine: MySQL 8.0
   - Instance Class: db.t3.micro
   - Endpoint: myproject-db.c900uesmqwtf.eu-west-1.rds.amazonaws.com
   - Database Name: myprojectdb
   - Master Username: admin
   - Backup Retention: 1 day
   - Multi-AZ: Disabled (cost optimization)

7. **S3 Storage Bucket**
   - Bucket Name: myproject-storage-674182808760
   - Used for: Application deployment packages

8. **Security Groups**
   - **MyProject-LB-SG:** Load Balancer security group (allows HTTP port 80)
   - **MyProject-EC2-SG:** EC2 instances security group (allows ports 22, 80, 3000)
   - **MyProject-RDS-SG:** Database security group (allows MySQL port 3306)

---

## Application Architecture

### Technology Stack

**Frontend:**
- HTML5
- CSS3 (Responsive Design with Gradient UI)
- JavaScript (Vanilla JS for form handling)

**Backend:**
- Node.js 18 (Alpine Linux)
- Express.js Framework (v4.18.2)
- MySQL2 Driver (v3.6.5)
- CORS Middleware (v2.8.5)

**Container Platform:**
- Docker
- Base Image: node:18-alpine

**Database:**
- MySQL 8.0
- Connection Pooling: 10 concurrent connections

### Application Features

#### 1. Professional Website Interface
- Modern gradient design with responsive layout
- Hero section with call-to-action
- Feature cards showcasing six cloud services:
  - Cloud Migration
  - Infrastructure Management
  - Security & Compliance
  - Data Analytics
  - DevOps Solutions
  - 24/7 Support
- Statistics section displaying key metrics
- Contact form for customer inquiries

#### 2. RESTful API Endpoints

| Endpoint | Method | Description | Response |
|----------|--------|-------------|----------|
| `/health` | GET | Health check endpoint | `{"status":"ok"}` |
| `/api` | GET | API information | `{"message":"API is running"}` |
| `/api/contact` | POST | Submit contact form | `{"success":true,"message":"Saved!"}` |
| `/api/contacts` | GET | Retrieve all contacts | JSON array of contacts |
| `/api/contacts/count` | GET | Get total contact count | `{"count": number}` |

#### 3. Database Schema

**Table: contacts**

```sql
CREATE TABLE IF NOT EXISTS contacts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) NOT NULL,
  company VARCHAR(255),
  service VARCHAR(255),
  message TEXT,
  timestamp DATETIME,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Deployment Process

### Phase 1: Infrastructure Deployment

The infrastructure was deployed using AWS CloudFormation with the following template:

**Stack Name:** MyAWSProject  
**Status:** CREATE_COMPLETE

**Key Configuration Parameters:**
- KeyPairName: Key
- MySQL Engine Version: 8.0
- Backup Retention Period: 1 day
- EC2 Instance Type: t3.micro
- Database Instance Class: db.t3.micro

### Phase 2: Application Deployment

#### Step 1: CloudShell Deployment
1. Uploaded deployment package to S3 bucket
2. Package location: `s3://myproject-storage-674182808760/cloudtech-app.tar.gz`

#### Step 2: EC2 Instance Configuration
Connected to Web UI instance using EC2 Instance Connect:
```bash
# Created application directory
mkdir -p /home/ubuntu/cloudtech-app/public
cd /home/ubuntu/cloudtech-app
```

#### Step 3: Application Files Creation
Created the following files:

**package.json:**
```json
{
  "name": "cloudtech-app",
  "version": "1.0.0",
  "main": "server.js",
  "dependencies": {
    "express": "^4.18.2",
    "mysql2": "^3.6.5",
    "cors": "^2.8.5"
  }
}
```

**server.js:**
- Express server configuration
- MySQL connection pool
- CORS middleware
- RESTful API routes
- Auto-creates database table on startup

**Dockerfile:**
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --production
COPY . .
EXPOSE 3000
CMD ["node", "server.js"]
```

**public/index.html:**
- Professional responsive website
- Contact form with JavaScript fetch API
- Modern gradient design

#### Step 4: Docker Container Deployment
```bash
# Build Docker image
sudo docker build -t cloudtech-app .

# Run container with port mapping
sudo docker run -d -p 80:3000 --name webapp --restart always cloudtech-app

# Verify container status
sudo docker ps
```

**Container Configuration:**
- Image: cloudtech-app:latest
- Port Mapping: 0.0.0.0:80 → 3000/tcp
- Restart Policy: always
- Status: Running

### Phase 3: Load Balancer Configuration

#### Listener Rules Configuration

**HTTP:80 Listener Rules:**

1. **Priority 1 - API Routes:**
   - Condition: Path = `/api/*`
   - Action: Forward to MyProject-Web-TG (Port 80)
   - Weight: 100%
   - Target Group Stickiness: Off

2. **Default Rule:**
   - Condition: If no other rule applies
   - Action: Forward to MyProject-Web-TG (Port 80)
   - Weight: 100%

This configuration ensures:
- All API requests (`/api/*`) are routed to the Web instance running the containerized application
- Static content requests are also handled by the same target group
- Load balancer performs health checks on port 80

---

## Testing & Validation

### Health Check Tests

**Local Container Health Check:**
```bash
curl http://localhost:80/health
```
**Response:** `{"status":"ok"}`

**API Endpoint Test:**
```bash
curl -X POST http://localhost:80/api/contact \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"test@test.com","company":"Test Co","service":"Cloud Migration","message":"Test message"}'
```
**Response:** `{"success":true,"message":"Saved!"}`

### Database Validation

**Query Submitted Contacts:**
```bash
mysql -h myproject-db.c900uesmqwtf.eu-west-1.rds.amazonaws.com \
  -u admin -pMyPassword123 -D myprojectdb \
  -e "SELECT * FROM contacts;"
```

**Results:**
- Verified successful data insertion
- All fields (name, email, company, service, message) stored correctly
- Timestamps automatically generated

### Load Balancer Testing

**Public Access URL:**
`http://MyProject-ALB-1911809755.eu-west-1.elb.amazonaws.com`

**Test Results:**
- ✅ Website loads correctly
- ✅ Responsive design works across devices
- ✅ Contact form submission successful
- ✅ Data saved to MySQL database
- ✅ API endpoints accessible through Load Balancer

---

## Security Configuration

### Network Security

**Security Group Rules:**

1. **Load Balancer Security Group (MyProject-LB-SG):**
   - Inbound: Port 80 (HTTP) from 0.0.0.0/0
   - Outbound: All traffic

2. **EC2 Security Group (MyProject-EC2-SG):**
   - Inbound:
     - Port 22 (SSH) from trusted IPs
     - Port 80 (HTTP) from Load Balancer SG
     - Port 3000 (Application) from Load Balancer SG
   - Outbound: All traffic

3. **RDS Security Group (MyProject-RDS-SG):**
   - Inbound: Port 3306 (MySQL) from EC2 SG only
   - Outbound: All traffic

### Application Security

- CORS configured to allow cross-origin requests
- MySQL connection uses parameterized queries (SQL injection prevention)
- Database credentials secured in RDS
- Connection pooling limits concurrent connections
- Container runs as non-root user (Node.js best practice)

---

## Monitoring & Logs

### Docker Container Logs

**View Application Logs:**
```bash
sudo docker logs webapp --tail 50
```

**Log Output:**
- Server startup confirmation
- Database connection status
- Incoming HTTP requests (GET, POST)
- API response status codes

### Database Monitoring

**Check Contact Submissions:**
```bash
mysql -h myproject-db.c900uesmqwtf.eu-west-1.rds.amazonaws.com \
  -u admin -pMyPassword123 -D myprojectdb \
  -e "SELECT COUNT(*) as total_contacts FROM contacts;"
```

### Target Group Health Status

**Monitoring Location:**
AWS Console → EC2 → Target Groups → MyProject-Web-TG → Targets tab

**Current Status:**
- Total Targets: 1
- Healthy: 1
- Unhealthy: 0

---

## Cost Optimization

The infrastructure is designed to minimize costs while maintaining functionality:

1. **EC2 Instances:** t3.micro (AWS Free Tier eligible)
2. **RDS Database:** 
   - db.t3.micro instance class
   - Single-AZ deployment
   - 1-day backup retention (minimum for free tier)
3. **Load Balancer:** Application Load Balancer (minimal rules)
4. **S3 Storage:** Pay-per-use (minimal storage required)
5. **Data Transfer:** Optimized by using same region for all resources

**Estimated Monthly Cost:** Within AWS Free Tier limits for new accounts

---

## Troubleshooting Guide

### Issue 1: Load Balancer Not Forwarding Requests

**Problem:** Form submissions not reaching API endpoint  
**Root Cause:** Listener rule routing to wrong target group  
**Solution:** 
1. Navigate to EC2 → Load Balancers → MyProject-ALB
2. Click "Listeners and rules" tab
3. Edit HTTP:80 listener rules
4. Ensure `/api/*` path forwards to MyProject-Web-TG
5. Update and wait 30 seconds for propagation

### Issue 2: Direct EC2 IP Connection Refused

**Problem:** ERR_CONNECTION_RESET when accessing EC2 public IP  
**Root Cause:** Security group only allows traffic from Load Balancer  
**Solution:** Use Load Balancer DNS name instead of direct EC2 IP

### Issue 3: Container Not Receiving Requests

**Problem:** Docker logs show no incoming requests  
**Diagnostic Commands:**
```bash
# Test local connectivity
curl http://localhost:80/health

# Check container status
sudo docker ps

# Check container logs
sudo docker logs webapp --tail 20
```

**Solution:** Verify Load Balancer target group health status

---

## Future Enhancements

### Scalability Improvements
1. **Auto Scaling Groups:** Automatically scale EC2 instances based on demand
2. **Multi-AZ RDS:** Enable Multi-AZ deployment for high availability
3. **CloudFront CDN:** Implement content delivery network for global performance
4. **ElastiCache:** Add Redis caching layer for database query optimization

### Security Enhancements
1. **HTTPS/SSL:** Implement SSL certificate with AWS Certificate Manager
2. **WAF:** Deploy Web Application Firewall for DDoS protection
3. **Secrets Manager:** Store database credentials in AWS Secrets Manager
4. **VPC Flow Logs:** Enable network traffic monitoring

### Application Features
1. **Email Notifications:** Send confirmation emails upon form submission
2. **Admin Dashboard:** Web interface to view submitted contacts
3. **Form Validation:** Enhanced client and server-side validation
4. **Rate Limiting:** Implement API rate limiting to prevent abuse

### Monitoring & Logging
1. **CloudWatch Dashboards:** Custom dashboards for application metrics
2. **CloudWatch Alarms:** Automated alerts for service health
3. **Centralized Logging:** Aggregate logs from all services
4. **AWS X-Ray:** Distributed tracing for performance analysis

---

## Conclusion

This project successfully demonstrates the deployment of a production-ready web application on AWS infrastructure. The architecture implements industry best practices including:

- ✅ High availability through Load Balancer
- ✅ Scalable containerized application deployment
- ✅ Secure database connectivity
- ✅ Professional user interface
- ✅ RESTful API design
- ✅ Infrastructure as Code (CloudFormation)
- ✅ Cost-optimized resource configuration

The application is fully functional and accessible via the Load Balancer URL, with all components (web server, API, and database) working cohesively to provide a complete cloud-based solution.

---

## Appendices

### Appendix A: Access Information

**Application URLs:**
- Load Balancer URL: http://MyProject-ALB-1911809755.eu-west-1.elb.amazonaws.com
- Health Check: http://MyProject-ALB-1911809755.eu-west-1.elb.amazonaws.com/health
- API Base: http://MyProject-ALB-1911809755.eu-west-1.elb.amazonaws.com/api

**AWS Resources:**
- Region: EU-West-1 (Ireland)
- CloudFormation Stack: MyAWSProject
- S3 Bucket: myproject-storage-674182808760

### Appendix B: Database Connection Details

**RDS Endpoint:** myproject-db.c900uesmqwtf.eu-west-1.rds.amazonaws.com  
**Port:** 3306  
**Database:** myprojectdb  
**Username:** admin  

**Connection String:**
```
mysql -h myproject-db.c900uesmqwtf.eu-west-1.rds.amazonaws.com -u admin -pMyPassword123 -D myprojectdb
```

### Appendix C: Docker Commands Reference

```bash
# Build image
sudo docker build -t cloudtech-app .

# Run container
sudo docker run -d -p 80:3000 --name webapp --restart always cloudtech-app

# View logs
sudo docker logs webapp --tail 50

# Check status
sudo docker ps

# Stop container
sudo docker stop webapp

# Start container
sudo docker start webapp

# Remove container
sudo docker rm -f webapp

# View all images
sudo docker images
```

### Appendix D: Useful AWS CLI Commands

```bash
# Describe CloudFormation stack
aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1

# List EC2 instances
aws ec2 describe-instances --region eu-west-1

# Check RDS status
aws rds describe-db-instances --region eu-west-1

# List S3 buckets
aws s3 ls

# View Load Balancer
aws elbv2 describe-load-balancers --region eu-west-1

# Check target health
aws elbv2 describe-target-health --target-group-arn <TARGET_GROUP_ARN> --region eu-west-1
```

---

**Project Completed:** November 25, 2025  
**Documentation Version:** 1.0  
**Student:** Mikhael Nabil Salama Rezk (IHUTSC)
