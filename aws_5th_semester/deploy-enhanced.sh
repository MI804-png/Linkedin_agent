#!/bin/bash
# Enhanced Website Deployment Script for AWS CloudShell
# This script creates a professional website with database connectivity

echo "================================================"
echo "  CloudTech Solutions - Enhanced Deployment"
echo "================================================"

# Get RDS endpoint from existing stack
RDS_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name MyAWSProject \
  --region eu-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`RDSEndpoint`].OutputValue' \
  --output text 2>/dev/null)

if [ -z "$RDS_ENDPOINT" ]; then
  echo "Error: Cannot find RDS endpoint. Make sure MyAWSProject stack exists."
  exit 1
fi

echo "✓ Found RDS endpoint: $RDS_ENDPOINT"

# Get Web UI Instance ID
INSTANCE_IP=$(aws cloudformation describe-stacks \
  --stack-name MyAWSProject \
  --region eu-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`WebUIInstanceIP`].OutputValue' \
  --output text)

echo "✓ Found EC2 instance: $INSTANCE_IP"

# Create temporary directory
TEMP_DIR="/tmp/cloudtech-deploy"
rm -rf $TEMP_DIR
mkdir -p $TEMP_DIR
cd $TEMP_DIR

echo ""
echo "Creating application files..."

# Create package.json
cat > package.json << 'EOF'
{
  "name": "cloudtech-api",
  "version": "1.0.0",
  "main": "server.js",
  "dependencies": {
    "express": "^4.18.2",
    "mysql2": "^3.6.5",
    "cors": "^2.8.5"
  }
}
EOF

# Create server.js with actual RDS endpoint
cat > server.js << EOF
const express = require('express');
const mysql = require('mysql2/promise');
const cors = require('cors');
const path = require('path');
const app = express();

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

const dbConfig = {
  host: '${RDS_ENDPOINT}',
  user: 'admin',
  password: 'MyPassword123',
  database: 'myprojectdb',
  waitForConnections: true,
  connectionLimit: 10
};

const pool = mysql.createPool(dbConfig);

async function initDB() {
  try {
    const conn = await pool.getConnection();
    await conn.query(\`
      CREATE TABLE IF NOT EXISTS contacts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) NOT NULL,
        company VARCHAR(255),
        service VARCHAR(255) NOT NULL,
        message TEXT NOT NULL,
        timestamp DATETIME NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_email (email)
      )
    \`);
    console.log('✓ Database initialized');
    conn.release();
  } catch (err) {
    console.error('DB Error:', err.message);
  }
}

initDB();

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

app.get('/api', (req, res) => {
  res.json({
    message: 'CloudTech Solutions API',
    version: '1.0.0',
    database: 'MySQL RDS Connected',
    endpoints: {
      contact: 'POST /api/contact',
      contacts: 'GET /api/contacts',
      count: 'GET /api/contacts/count'
    }
  });
});

app.post('/api/contact', async (req, res) => {
  try {
    const { name, email, company, service, message, timestamp } = req.body;
    
    if (!name || !email || !service || !message) {
      return res.status(400).json({ error: 'Missing required fields' });
    }

    const [result] = await pool.query(
      'INSERT INTO contacts (name, email, company, service, message, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
      [name, email, company || null, service, message, timestamp || new Date()]
    );

    res.status(201).json({
      success: true,
      message: 'Contact saved to database!',
      contactId: result.insertId
    });
  } catch (err) {
    console.error('Error:', err);
    res.status(500).json({ error: 'Failed to save contact' });
  }
});

app.get('/api/contacts', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT * FROM contacts ORDER BY created_at DESC LIMIT 50');
    res.json({ success: true, count: rows.length, contacts: rows });
  } catch (err) {
    res.status(500).json({ error: 'Failed to retrieve contacts' });
  }
});

app.get('/api/contacts/count', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT COUNT(*) as total FROM contacts');
    res.json({ success: true, totalContacts: rows[0].total });
  } catch (err) {
    res.status(500).json({ error: 'Failed to get count' });
  }
});

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(3000, '0.0.0.0', () => {
  console.log('✓ Server running on port 3000');
  console.log('✓ Database: ${RDS_ENDPOINT}');
});
EOF

# Create Dockerfile
cat > Dockerfile << 'EOF'
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --production
COPY server.js ./
RUN mkdir -p public
COPY public/index.html ./public/
EXPOSE 3000
CMD ["node", "server.js"]
EOF

# Create public directory and index.html
mkdir -p public
cat > public/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CloudTech Solutions - AWS Project</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; line-height: 1.6; color: #333; }
        header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem 0; position: fixed; width: 100%; top: 0; z-index: 1000; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        nav { display: flex; justify-content: space-between; align-items: center; max-width: 1200px; margin: 0 auto; padding: 0 2rem; }
        .logo { font-size: 1.5rem; font-weight: bold; }
        .nav-links { display: flex; list-style: none; gap: 2rem; }
        .nav-links a { color: white; text-decoration: none; transition: opacity 0.3s; }
        .nav-links a:hover { opacity: 0.8; }
        .hero { margin-top: 70px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 100px 2rem; text-align: center; }
        .hero h1 { font-size: 3rem; margin-bottom: 1rem; }
        .hero p { font-size: 1.3rem; margin-bottom: 2rem; }
        .cta-button { background: white; color: #667eea; padding: 1rem 2rem; border: none; border-radius: 50px; font-size: 1.1rem; cursor: pointer; text-decoration: none; display: inline-block; }
        .features { max-width: 1200px; margin: 4rem auto; padding: 0 2rem; }
        .features h2 { text-align: center; font-size: 2.5rem; margin-bottom: 3rem; color: #667eea; }
        .feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 2rem; }
        .feature-card { background: white; padding: 2rem; border-radius: 15px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); text-align: center; transition: transform 0.3s; }
        .feature-card:hover { transform: translateY(-10px); }
        .feature-icon { font-size: 3rem; margin-bottom: 1rem; }
        .feature-card h3 { color: #667eea; margin-bottom: 1rem; }
        .stats { background: #f8f9fa; padding: 4rem 2rem; margin: 4rem 0; }
        .stats-container { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 2rem; text-align: center; }
        .stat-box h3 { font-size: 3rem; color: #667eea; margin-bottom: 0.5rem; }
        .contact { max-width: 800px; margin: 4rem auto; padding: 0 2rem; }
        .contact h2 { text-align: center; font-size: 2.5rem; margin-bottom: 2rem; color: #667eea; }
        .form-container { background: white; padding: 3rem; border-radius: 15px; box-shadow: 0 5px 30px rgba(0,0,0,0.1); }
        .form-group { margin-bottom: 1.5rem; }
        .form-group label { display: block; margin-bottom: 0.5rem; font-weight: 500; }
        .form-group input, .form-group textarea, .form-group select { width: 100%; padding: 0.8rem; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 1rem; }
        .form-group textarea { resize: vertical; min-height: 120px; }
        .submit-btn { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem 3rem; border: none; border-radius: 50px; font-size: 1.1rem; cursor: pointer; width: 100%; }
        .message { margin-top: 1rem; padding: 1rem; border-radius: 8px; text-align: center; display: none; }
        .message.success { background: #d4edda; color: #155724; }
        .message.error { background: #f8d7da; color: #721c24; }
        footer { background: #2c3e50; color: white; text-align: center; padding: 2rem; margin-top: 4rem; }
        .aws-badges { display: flex; justify-content: center; gap: 1rem; flex-wrap: wrap; margin-top: 1rem; }
        .badge { background: #667eea; padding: 0.5rem 1rem; border-radius: 20px; font-size: 0.9rem; }
    </style>
</head>
<body>
    <header>
        <nav>
            <div class="logo">☁️ CloudTech Solutions</div>
            <ul class="nav-links">
                <li><a href="#home">Home</a></li>
                <li><a href="#features">Features</a></li>
                <li><a href="#contact">Contact</a></li>
            </ul>
        </nav>
    </header>

    <section id="home" class="hero">
        <h1>🚀 Welcome to CloudTech Solutions</h1>
        <p>Powered by AWS Cloud Infrastructure with Database Integration</p>
        <a href="#contact" class="cta-button">Get Started</a>
    </section>

    <section id="features" class="features">
        <h2>Our AWS Infrastructure</h2>
        <div class="feature-grid">
            <div class="feature-card">
                <div class="feature-icon">🌐</div>
                <h3>VPC & Networking</h3>
                <p>Secure VPC with multi-AZ deployment</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">💻</div>
                <h3>EC2 with Docker</h3>
                <p>Containerized applications on t3.micro</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🗄️</div>
                <h3>RDS MySQL</h3>
                <p>Managed database with auto-backups</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">📦</div>
                <h3>S3 Storage</h3>
                <p>Scalable object storage solution</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">⚖️</div>
                <h3>Load Balancer</h3>
                <p>High availability traffic distribution</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🔒</div>
                <h3>Security Groups</h3>
                <p>Multi-layer security protection</p>
            </div>
        </div>
    </section>

    <section class="stats">
        <div class="stats-container">
            <div class="stat-box"><h3>99.9%</h3><p>Uptime SLA</p></div>
            <div class="stat-box"><h3>2</h3><p>Availability Zones</p></div>
            <div class="stat-box"><h3>6</h3><p>AWS Services</p></div>
            <div class="stat-box"><h3>24/7</h3><p>Monitoring</p></div>
        </div>
    </section>

    <section id="contact" class="contact">
        <h2>Contact Us</h2>
        <div class="form-container">
            <form id="contactForm">
                <div class="form-group">
                    <label for="name">Full Name *</label>
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
                    <label for="service">Service *</label>
                    <select id="service" name="service" required>
                        <option value="">-- Select --</option>
                        <option value="Cloud Migration">Cloud Migration</option>
                        <option value="Infrastructure">Infrastructure Setup</option>
                        <option value="DevOps">DevOps Consulting</option>
                        <option value="Database">Database Management</option>
                        <option value="Security">Security Audit</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="message">Message *</label>
                    <textarea id="message" name="message" required></textarea>
                </div>
                <button type="submit" class="submit-btn">Submit</button>
            </form>
            <div id="formMessage" class="message"></div>
        </div>
    </section>

    <footer>
        <h3 style="color: #FF9900; margin-bottom: 1rem;">Powered by AWS Services</h3>
        <div class="aws-badges">
            <span class="badge">VPC</span>
            <span class="badge">EC2</span>
            <span class="badge">RDS MySQL</span>
            <span class="badge">S3</span>
            <span class="badge">ALB</span>
            <span class="badge">Docker</span>
        </div>
        <p style="margin-top: 2rem;">© 2025 CloudTech Solutions | EU-West-1</p>
    </footer>

    <script>
        document.getElementById('contactForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = {
                name: document.getElementById('name').value,
                email: document.getElementById('email').value,
                company: document.getElementById('company').value,
                service: document.getElementById('service').value,
                message: document.getElementById('message').value,
                timestamp: new Date().toISOString()
            };

            const messageDiv = document.getElementById('formMessage');
            const submitBtn = document.querySelector('.submit-btn');
            
            submitBtn.disabled = true;
            submitBtn.textContent = 'Submitting...';

            try {
                const response = await fetch('/api/contact', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });

                const result = await response.json();

                if (response.ok) {
                    messageDiv.className = 'message success';
                    messageDiv.textContent = '✓ Success! Your message was saved to the database.';
                    messageDiv.style.display = 'block';
                    document.getElementById('contactForm').reset();
                } else {
                    throw new Error(result.error || 'Submission failed');
                }
            } catch (error) {
                messageDiv.className = 'message error';
                messageDiv.textContent = '✗ Error: ' + error.message;
                messageDiv.style.display = 'block';
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Submit';
                setTimeout(() => messageDiv.style.display = 'none', 5000);
            }
        });

        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                document.querySelector(this.getAttribute('href')).scrollIntoView({ behavior: 'smooth' });
            });
        });
    </script>
</body>
</html>
EOF

echo "✓ Application files created"
echo ""
echo "Creating deployment package..."

# Create tarball
tar -czf cloudtech-app.tar.gz *

echo "✓ Package created"
echo ""
echo "================================================"
echo "  Deployment package ready!"
echo "================================================"
echo ""
echo "Files created in: $TEMP_DIR"
echo "Package: cloudtech-app.tar.gz"
echo ""
echo "To deploy to your EC2 instance, you have 2 options:"
echo ""
echo "Option 1: Upload via S3 (EASIEST)"
echo "  1. Upload to S3:"
echo "     aws s3 cp cloudtech-app.tar.gz s3://myproject-storage-674182808760/"
echo ""
echo "  2. SSH to EC2 and download:"
echo "     ssh -i Key.pem ubuntu@$INSTANCE_IP"
echo "     aws s3 cp s3://myproject-storage-674182808760/cloudtech-app.tar.gz ."
echo "     tar -xzf cloudtech-app.tar.gz"
echo "     sudo docker build -t cloudtech-app ."
echo "     sudo docker stop webapp && sudo docker rm webapp"
echo "     sudo docker run -d -p 80:3000 --name webapp --restart always cloudtech-app"
echo ""
echo "Option 2: Direct SSH (if you have key file)"
echo "  scp -i Key.pem cloudtech-app.tar.gz ubuntu@$INSTANCE_IP:~/"
echo "  ssh -i Key.pem ubuntu@$INSTANCE_IP"
echo "  tar -xzf cloudtech-app.tar.gz"
echo "  sudo docker build -t cloudtech-app ."
echo "  sudo docker stop webapp && sudo docker rm webapp"
echo "  sudo docker run -d -p 80:3000 --name webapp --restart always cloudtech-app"
echo ""
echo "================================================"
