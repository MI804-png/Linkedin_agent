# AWS Cloud Infrastructure Project - Quick Deployment Guide
## Complete Setup Instructions for Demonstration

**Project:** Full-Stack Web Application with Database Integration  
**Time Required:** 15-20 minutes  
**Cost:** AWS Free Tier eligible (or ~$2-5 for demo period)

---

## Prerequisites

- AWS Account with administrative access
- AWS Free Tier recommended (first 12 months)
- SSH Key Pair named **"Key"** in EU-West-1 region

---

## Step 1: Create SSH Key Pair (If Not Exists)

1. Go to **AWS Console** → **EC2** → **Key Pairs**
2. Click **"Create key pair"**
3. Name: **Key**
4. Type: **RSA**
5. Format: **.pem** (for Mac/Linux) or **.ppk** (for Windows PuTTY)
6. Click **"Create key pair"** and save the file

---

## Step 2: Deploy Infrastructure with CloudFormation

### Upload the CloudFormation Template

1. Go to **AWS Console** → Search for **"CloudFormation"**
2. Click **"Create stack"** → **"With new resources (standard)"**
3. Choose **"Upload a template file"**
4. Click **"Choose file"** and upload: **`cloudformation-template.yaml`**
5. Click **"Next"**

### Configure Stack Settings

**Stack name:** `MyAWSProject`

**Parameters:**
- KeyPairName: **Key** (the SSH key you created)
- Leave all other parameters as default

Click **"Next"** → **"Next"** → Check **"I acknowledge that AWS CloudFormation might create IAM resources"** → **"Submit"**

### Wait for Completion (5-8 minutes)

Watch the **Events** tab. Wait until Status shows: **CREATE_COMPLETE** ✓

---

## Step 3: Get Resource Information

After stack creation completes:

1. Go to **CloudFormation** → **MyAWSProject** → **Outputs** tab
2. Note down:
   - **RDS Endpoint** (looks like: `myproject-db.xxxxx.eu-west-1.rds.amazonaws.com`)
   - **Load Balancer DNS** (looks like: `MyProject-ALB-xxxxx.eu-west-1.elb.amazonaws.com`)
   - **S3 Bucket Name** (looks like: `myproject-storage-xxxxx`)

3. Go to **EC2** → **Instances**
4. Find instance named **"MyProject-Web-UI"**
5. Note its **Public IP address**

---

## Step 4: Deploy Application to EC2

### Connect to EC2 Instance

**Option A: EC2 Instance Connect (Easiest - Browser-based)**
1. Go to **EC2** → **Instances**
2. Select **MyProject-Web-UI** instance
3. Click **"Connect"** button
4. Choose **"EC2 Instance Connect"** tab
5. Click **"Connect"** (opens terminal in browser)

**Option B: SSH (Traditional)**
```bash
ssh -i "Key.pem" ubuntu@<EC2-PUBLIC-IP>
```

### Create Application Directory

```bash
mkdir -p /home/ubuntu/cloudtech-app/public
cd /home/ubuntu/cloudtech-app
```

### Create package.json

```bash
cat > package.json << 'EOF'
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
EOF
```

### Create server.js

⚠️ **IMPORTANT:** Replace `YOUR_RDS_ENDPOINT_HERE` with the actual RDS endpoint from Step 3

```bash
cat > server.js << 'EOF'
const express = require('express');
const mysql = require('mysql2/promise');
const cors = require('cors');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

const pool = mysql.createPool({
  host: 'YOUR_RDS_ENDPOINT_HERE',
  user: 'admin',
  password: 'MyPassword123',
  database: 'myprojectdb',
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0
});

async function initDatabase() {
  try {
    const connection = await pool.getConnection();
    await connection.query(`
      CREATE TABLE IF NOT EXISTS contacts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) NOT NULL,
        company VARCHAR(255),
        service VARCHAR(255),
        message TEXT,
        timestamp DATETIME,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    connection.release();
    console.log('Database initialized');
  } catch (error) {
    console.error('Database init error:', error);
  }
}

initDatabase();

app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.get('/api', (req, res) => {
  res.json({ message: 'API is running' });
});

app.post('/api/contact', async (req, res) => {
  try {
    const { name, email, company, service, message } = req.body;
    const timestamp = new Date();
    await pool.query(
      'INSERT INTO contacts (name, email, company, service, message, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
      [name, email, company, service, message, timestamp]
    );
    res.json({ success: true, message: 'Saved!' });
  } catch (error) {
    console.error('Error:', error);
    res.status(500).json({ success: false, message: 'Error saving contact' });
  }
});

app.get('/api/contacts', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT * FROM contacts ORDER BY created_at DESC');
    res.json(rows);
  } catch (error) {
    console.error('Error:', error);
    res.status(500).json({ error: 'Failed to fetch contacts' });
  }
});

app.get('/api/contacts/count', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT COUNT(*) as count FROM contacts');
    res.json({ count: rows[0].count });
  } catch (error) {
    res.status(500).json({ error: 'Failed to count contacts' });
  }
});

const PORT = 3000;
app.listen(PORT, '0.0.0.0', () => {
  console.log('Server running');
});
EOF
```

**Now edit the file to add your RDS endpoint:**
```bash
nano server.js
# Find the line: host: 'YOUR_RDS_ENDPOINT_HERE',
# Replace it with your actual RDS endpoint from Step 3
# Press Ctrl+X, then Y, then Enter to save
```

### Create Dockerfile

```bash
cat > Dockerfile << 'EOF'
FROM node:18-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --production
COPY . .
EXPOSE 3000
CMD ["node", "server.js"]
EOF
```

### Create index.html

```bash
cat > public/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CloudTech Solutions - Cloud Infrastructure Services</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem 0;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .nav-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo {
            font-size: 1.5rem;
            font-weight: bold;
        }
        nav a {
            color: white;
            text-decoration: none;
            margin-left: 2rem;
            transition: opacity 0.3s;
        }
        nav a:hover {
            opacity: 0.8;
        }
        .hero {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 100px 20px;
            text-align: center;
        }
        .hero h1 {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        .hero p {
            font-size: 1.3rem;
            margin-bottom: 2rem;
        }
        .btn {
            display: inline-block;
            padding: 12px 30px;
            background: white;
            color: #667eea;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            transition: transform 0.3s;
        }
        .btn:hover {
            transform: translateY(-2px);
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }
        .features {
            padding: 80px 20px;
            background: #f9f9f9;
        }
        .features h2 {
            text-align: center;
            font-size: 2.5rem;
            margin-bottom: 3rem;
            color: #333;
        }
        .features-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
        }
        .feature-card {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }
        .feature-card:hover {
            transform: translateY(-5px);
        }
        .feature-card h3 {
            color: #667eea;
            margin-bottom: 1rem;
        }
        .stats {
            padding: 60px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 30px;
            max-width: 1000px;
            margin: 0 auto;
        }
        .stat-item h3 {
            font-size: 3rem;
            margin-bottom: 0.5rem;
        }
        .contact-section {
            padding: 80px 20px;
        }
        .contact-section h2 {
            text-align: center;
            font-size: 2.5rem;
            margin-bottom: 3rem;
        }
        .contact-form {
            max-width: 600px;
            margin: 0 auto;
        }
        .form-group {
            margin-bottom: 1.5rem;
        }
        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: bold;
        }
        .form-group input,
        .form-group select,
        .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 1rem;
        }
        .form-group textarea {
            resize: vertical;
            min-height: 150px;
        }
        .submit-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 1.1rem;
            font-weight: bold;
            cursor: pointer;
            transition: opacity 0.3s;
        }
        .submit-btn:hover {
            opacity: 0.9;
        }
        .message {
            padding: 15px;
            margin-top: 20px;
            border-radius: 5px;
            text-align: center;
            display: none;
        }
        .message.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .message.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        footer {
            background: #333;
            color: white;
            text-align: center;
            padding: 20px;
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="nav-container">
            <div class="logo">☁️ CloudTech Solutions</div>
            <nav>
                <a href="#features">Services</a>
                <a href="#stats">About</a>
                <a href="#contact">Contact</a>
            </nav>
        </div>
    </header>

    <section class="hero">
        <div class="container">
            <h1>Transform Your Business with Cloud Technology</h1>
            <p>Enterprise-grade cloud infrastructure solutions powered by AWS</p>
            <a href="#contact" class="btn">Get Started Today</a>
        </div>
    </section>

    <section id="features" class="features">
        <div class="container">
            <h2>Our Services</h2>
            <div class="features-grid">
                <div class="feature-card">
                    <h3>☁️ Cloud Migration</h3>
                    <p>Seamlessly migrate your infrastructure to AWS with zero downtime and maximum efficiency.</p>
                </div>
                <div class="feature-card">
                    <h3>🔧 Infrastructure Management</h3>
                    <p>24/7 monitoring and management of your cloud resources for optimal performance.</p>
                </div>
                <div class="feature-card">
                    <h3>🔒 Security & Compliance</h3>
                    <p>Enterprise-level security measures and compliance with industry standards.</p>
                </div>
                <div class="feature-card">
                    <h3>📊 Data Analytics</h3>
                    <p>Advanced analytics and insights to drive your business decisions.</p>
                </div>
                <div class="feature-card">
                    <h3>🚀 DevOps Solutions</h3>
                    <p>Streamline your development pipeline with CI/CD and automation.</p>
                </div>
                <div class="feature-card">
                    <h3>💬 24/7 Support</h3>
                    <p>Round-the-clock technical support from our expert team.</p>
                </div>
            </div>
        </div>
    </section>

    <section id="stats" class="stats">
        <div class="container">
            <div class="stats-grid">
                <div class="stat-item">
                    <h3>500+</h3>
                    <p>Clients Worldwide</p>
                </div>
                <div class="stat-item">
                    <h3>99.9%</h3>
                    <p>Uptime Guarantee</p>
                </div>
                <div class="stat-item">
                    <h3>50+</h3>
                    <p>Cloud Experts</p>
                </div>
            </div>
        </div>
    </section>

    <section id="contact" class="contact-section">
        <div class="container">
            <h2>Contact Us</h2>
            <form id="contactForm" class="contact-form">
                <div class="form-group">
                    <label for="name">Name *</label>
                    <input type="text" id="name" name="name" required>
                </div>
                <div class="form-group">
                    <label for="email">Email *</label>
                    <input type="email" id="email" name="email" required>
                </div>
                <div class="form-group">
                    <label for="company">Company</label>
                    <input type="text" id="company" name="company">
                </div>
                <div class="form-group">
                    <label for="service">Service Interest *</label>
                    <select id="service" name="service" required>
                        <option value="">Select a service</option>
                        <option value="Cloud Migration">Cloud Migration</option>
                        <option value="Infrastructure Management">Infrastructure Management</option>
                        <option value="Security & Compliance">Security & Compliance</option>
                        <option value="Data Analytics">Data Analytics</option>
                        <option value="DevOps Solutions">DevOps Solutions</option>
                        <option value="24/7 Support">24/7 Support</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="message">Message *</label>
                    <textarea id="message" name="message" required></textarea>
                </div>
                <button type="submit" class="submit-btn">Send Message</button>
                <div id="formMessage" class="message"></div>
            </form>
        </div>
    </section>

    <footer>
        <p>&copy; 2025 CloudTech Solutions. All rights reserved. | Powered by AWS</p>
    </footer>

    <script>
        document.getElementById('contactForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = {
                name: document.getElementById('name').value,
                email: document.getElementById('email').value,
                company: document.getElementById('company').value,
                service: document.getElementById('service').value,
                message: document.getElementById('message').value
            };
            
            const messageDiv = document.getElementById('formMessage');
            
            try {
                const response = await fetch('/api/contact', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    messageDiv.className = 'message success';
                    messageDiv.textContent = 'Thank you! Your message has been sent successfully.';
                    document.getElementById('contactForm').reset();
                } else {
                    messageDiv.className = 'message error';
                    messageDiv.textContent = 'Sorry, there was an error. Please try again.';
                }
            } catch (error) {
                messageDiv.className = 'message error';
                messageDiv.textContent = 'Sorry, there was an error. Please try again.';
            }
            
            messageDiv.style.display = 'block';
            setTimeout(() => {
                messageDiv.style.display = 'none';
            }, 5000);
        });
    </script>
</body>
</html>
EOF
```

### Build and Run Docker Container

```bash
# Build Docker image
sudo docker build -t cloudtech-app .

# Run container with port mapping (80:3000)
sudo docker run -d -p 80:3000 --name webapp --restart always cloudtech-app

# Verify container is running
sudo docker ps

# Check logs
sudo docker logs webapp
```

You should see: **"Server running"** in the logs ✓

---

## Step 5: Configure Load Balancer Routing

### Fix Listener Rules

1. Go to **EC2** → **Load Balancers**
2. Select **MyProject-ALB**
3. Click **"Listeners and rules"** tab
4. Click on the **HTTP:80** listener
5. Find the rule with **Priority 1** (Path = `/api/*`)
6. Click the **edit icon** (pencil)
7. Scroll to **Actions** section
8. In **Target group** dropdown, select: **MyProject-Web-TG**
9. Click **"Next"** → **"Next"** → **"Update"**

Wait 30 seconds for changes to propagate.

---

## Step 6: Test the Application

### Get Your Application URL

1. Go to **EC2** → **Load Balancers**
2. Copy the **DNS name** (looks like: `MyProject-ALB-xxxxx.eu-west-1.elb.amazonaws.com`)
3. Open it in your browser: `http://YOUR-LOAD-BALANCER-DNS`

### Test Features

1. **Website loads** with professional design ✓
2. **Scroll down** to "Contact Us" section
3. **Fill out the form:**
   - Name: Your name
   - Email: Your email
   - Company: Demo Company
   - Service: Select any service
   - Message: Test message
4. Click **"Send Message"**
5. You should see: **"Thank you! Your message has been sent successfully."** ✓

### Verify Database

In your EC2 terminal:

```bash
mysql -h YOUR_RDS_ENDPOINT -u admin -pMyPassword123 -D myprojectdb -e "SELECT * FROM contacts;"
```

You should see your submitted contact! ✓

---

## Step 7: Demonstration Points

Show the administrator:

### 1. Architecture Components
- ✅ **VPC with Multi-AZ** (High availability)
- ✅ **2 EC2 Instances** (Web UI and API)
- ✅ **Application Load Balancer** (Traffic distribution)
- ✅ **RDS MySQL Database** (Persistent data storage)
- ✅ **S3 Bucket** (Application storage)
- ✅ **Security Groups** (Network security)

### 2. Application Features
- ✅ **Professional responsive website**
- ✅ **RESTful API** (5 endpoints)
- ✅ **Database integration** with connection pooling
- ✅ **Docker containerization**
- ✅ **Contact form** with real-time validation

### 3. Infrastructure as Code
- ✅ **CloudFormation template** (reproducible deployment)
- ✅ **Automated resource creation**
- ✅ **Tagged resources** for organization

### 4. Testing Endpoints

```bash
# Health check
curl http://YOUR-LOAD-BALANCER-DNS/health

# API check
curl http://YOUR-LOAD-BALANCER-DNS/api

# View contacts (in EC2 terminal)
curl http://localhost:80/api/contacts
```

### 5. Database Query

```bash
# In EC2 terminal
mysql -h YOUR_RDS_ENDPOINT -u admin -pMyPassword123 -D myprojectdb

# Run queries
SELECT COUNT(*) FROM contacts;
SELECT * FROM contacts ORDER BY created_at DESC LIMIT 5;
```

---

## Troubleshooting

### Website Not Loading
```bash
# Check if container is running
sudo docker ps

# Check container logs
sudo docker logs webapp

# Restart container
sudo docker restart webapp
```

### Form Not Submitting
- Verify Load Balancer listener rules route `/api/*` to **MyProject-Web-TG**
- Check target group health: EC2 → Target Groups → Targets tab (should show "Healthy")

### Database Connection Failed
- Verify RDS endpoint in `server.js` is correct
- Check security group allows port 3306 from EC2 security group

### Container Build Failed
```bash
# Check if Docker is installed
sudo docker --version

# If not installed
sudo apt-get update
sudo apt-get install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker
```

---

## After Demonstration: Cleanup

**To avoid charges, delete everything:**

1. Go to **CloudFormation**
2. Select **MyAWSProject** stack
3. Click **"Delete"**
4. Confirm deletion
5. Wait 10 minutes

This will automatically delete:
- All EC2 instances
- Load Balancer
- RDS database
- VPC and networking
- Target groups
- Security groups

**Manually delete S3 bucket:**
1. Go to **S3**
2. Select your bucket
3. Click **"Empty"** → Confirm
4. Click **"Delete"** → Confirm

---

## Cost Information

**During Free Tier (First 12 months):**
- EC2: 750 hours/month free (covers 1 instance)
- RDS: 750 hours/month free
- **Cost for demo:** ~$2-5 (for second EC2 + Load Balancer + a few hours)

**After Free Tier:**
- ~$46/month if left running
- ~$0.50/hour for complete stack

**Recommendation:** Delete immediately after demonstration!

---

## Files Required

Make sure you have these files ready:

1. ✅ `cloudformation-template.yaml` - Infrastructure template
2. ✅ This deployment guide - Step-by-step instructions
3. ✅ PDF documentation - Complete project report

---

## Quick Commands Reference

```bash
# Docker Commands
sudo docker ps                          # List running containers
sudo docker logs webapp                 # View logs
sudo docker restart webapp              # Restart container
sudo docker stop webapp                 # Stop container
sudo docker rm -f webapp                # Remove container

# Database Commands
mysql -h ENDPOINT -u admin -pMyPassword123 -D myprojectdb
SELECT * FROM contacts;
SELECT COUNT(*) FROM contacts;

# System Commands
curl http://localhost:80/health         # Test locally
curl http://LOAD-BALANCER-DNS/health    # Test via Load Balancer
```

---

## Success Criteria

✅ CloudFormation stack created successfully  
✅ All resources showing "Active" or "Running"  
✅ Docker container running on EC2  
✅ Website loads via Load Balancer URL  
✅ Contact form submits successfully  
✅ Data appears in MySQL database  
✅ All API endpoints responding  

---

**Total Setup Time:** 15-20 minutes  
**Demonstration Time:** 5-10 minutes  
**Cleanup Time:** 2 minutes  

**Good luck with your demonstration! 🚀**
