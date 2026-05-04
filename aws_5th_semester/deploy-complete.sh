#!/bin/bash
# Complete Enhanced Website Deployment for AWS CloudShell
# Just upload this file to CloudShell and run: bash deploy-complete.sh

echo "================================================"
echo "  CloudTech Solutions - Complete Deployment"
echo "================================================"

# Get resource information
echo "Getting AWS resource information..."
RDS_ENDPOINT=$(aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`RDSEndpoint`].OutputValue' --output text 2>/dev/null)
BUCKET=$(aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' --output text 2>/dev/null)
INSTANCE_IP=$(aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`WebUIInstanceIP`].OutputValue' --output text 2>/dev/null)

if [ -z "$RDS_ENDPOINT" ] || [ -z "$BUCKET" ] || [ -z "$INSTANCE_IP" ]; then
    echo "ERROR: Cannot find stack resources. Make sure MyAWSProject is deployed."
    exit 1
fi

echo "✓ RDS Endpoint: $RDS_ENDPOINT"
echo "✓ S3 Bucket: $BUCKET"
echo "✓ EC2 Instance: $INSTANCE_IP"
echo ""

# Create working directory
WORK_DIR="/tmp/cloudtech-deploy-$(date +%s)"
mkdir -p $WORK_DIR
cd $WORK_DIR

echo "Creating application files..."

# ===== CREATE PACKAGE.JSON =====
cat > package.json << 'EOF'
{
  "name": "cloudtech-solutions-api",
  "version": "1.0.0",
  "description": "CloudTech Solutions API with MySQL Database",
  "main": "server.js",
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "express": "^4.18.2",
    "mysql2": "^3.6.5",
    "cors": "^2.8.5"
  }
}
EOF

# ===== CREATE SERVER.JS =====
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
  connectionLimit: 10,
  queueLimit: 0
};

const pool = mysql.createPool(dbConfig);

async function initDatabase() {
  try {
    const connection = await pool.getConnection();
    await connection.query(\`
      CREATE TABLE IF NOT EXISTS contacts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) NOT NULL,
        company VARCHAR(255),
        service VARCHAR(255) NOT NULL,
        message TEXT NOT NULL,
        timestamp DATETIME NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_email (email),
        INDEX idx_created_at (created_at)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    \`);
    console.log('✓ Database table initialized');
    connection.release();
  } catch (error) {
    console.error('Database initialization error:', error.message);
  }
}

initDatabase();

app.get('/health', (req, res) => {
  res.json({ 
    status: 'healthy', 
    timestamp: new Date().toISOString(),
    database: 'connected'
  });
});

app.get('/api', (req, res) => {
  res.json({
    message: 'CloudTech Solutions API',
    version: '1.0.0',
    status: 'running',
    database: 'MySQL RDS',
    rdsEndpoint: '${RDS_ENDPOINT}',
    endpoints: {
      health: 'GET /health',
      api: 'GET /api',
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
      return res.status(400).json({ 
        error: 'Missing required fields',
        required: ['name', 'email', 'service', 'message']
      });
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return res.status(400).json({ error: 'Invalid email format' });
    }

    const [result] = await pool.query(
      'INSERT INTO contacts (name, email, company, service, message, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
      [name, email, company || null, service, message, timestamp || new Date()]
    );

    res.status(201).json({
      success: true,
      message: 'Contact saved successfully to database!',
      contactId: result.insertId,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Database error:', error);
    res.status(500).json({ 
      error: 'Failed to save contact',
      details: error.message 
    });
  }
});

app.get('/api/contacts', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 50;
    const offset = parseInt(req.query.offset) || 0;

    const [rows] = await pool.query(
      'SELECT id, name, email, company, service, message, timestamp, created_at FROM contacts ORDER BY created_at DESC LIMIT ? OFFSET ?',
      [limit, offset]
    );

    res.json({
      success: true,
      count: rows.length,
      contacts: rows,
      pagination: { limit, offset }
    });

  } catch (error) {
    console.error('Database error:', error);
    res.status(500).json({ 
      error: 'Failed to retrieve contacts',
      details: error.message 
    });
  }
});

app.get('/api/contacts/count', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT COUNT(*) as total FROM contacts');
    
    res.json({
      success: true,
      totalContacts: rows[0].total,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Database error:', error);
    res.status(500).json({ 
      error: 'Failed to get contact count',
      details: error.message 
    });
  }
});

app.get('/api/contact/:id', async (req, res) => {
  try {
    const [rows] = await pool.query(
      'SELECT * FROM contacts WHERE id = ?',
      [req.params.id]
    );

    if (rows.length === 0) {
      return res.status(404).json({ error: 'Contact not found' });
    }

    res.json({ success: true, contact: rows[0] });

  } catch (error) {
    console.error('Database error:', error);
    res.status(500).json({ 
      error: 'Failed to retrieve contact',
      details: error.message 
    });
  }
});

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.use((req, res) => {
  res.status(404).json({ error: 'Endpoint not found', path: req.path });
});

const PORT = 3000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(\`
╔════════════════════════════════════════════╗
║   CloudTech Solutions API Server           ║
║   Status: Running ✓                        ║
║   Port: \${PORT}                               ║
║   Database: MySQL RDS                      ║
║   RDS: ${RDS_ENDPOINT}                     ║
╚════════════════════════════════════════════╝
  \`);
});
EOF

# ===== CREATE DOCKERFILE =====
cat > Dockerfile << 'EOF'
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --production

COPY server.js ./
RUN mkdir -p public
COPY public/index.html ./public/

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

CMD ["node", "server.js"]
EOF

# ===== CREATE INDEX.HTML =====
mkdir -p public
cat > public/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CloudTech Solutions - AWS Cloud Infrastructure</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }
        
        header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem 0; position: fixed; width: 100%; top: 0; z-index: 1000; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        nav { display: flex; justify-content: space-between; align-items: center; max-width: 1200px; margin: 0 auto; padding: 0 2rem; }
        .logo { font-size: 1.5rem; font-weight: bold; }
        .nav-links { display: flex; list-style: none; gap: 2rem; }
        .nav-links a { color: white; text-decoration: none; transition: opacity 0.3s; }
        .nav-links a:hover { opacity: 0.8; }
        
        .hero { margin-top: 70px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 100px 2rem; text-align: center; }
        .hero h1 { font-size: 3rem; margin-bottom: 1rem; animation: fadeInDown 1s; }
        .hero p { font-size: 1.3rem; margin-bottom: 2rem; animation: fadeInUp 1s; }
        .cta-button { background: white; color: #667eea; padding: 1rem 2rem; border: none; border-radius: 50px; font-size: 1.1rem; cursor: pointer; text-decoration: none; display: inline-block; transition: transform 0.3s; }
        .cta-button:hover { transform: scale(1.05); }
        
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
        .stat-box p { font-size: 1.2rem; color: #666; }
        
        .contact { max-width: 800px; margin: 4rem auto; padding: 0 2rem; }
        .contact h2 { text-align: center; font-size: 2.5rem; margin-bottom: 2rem; color: #667eea; }
        .form-container { background: white; padding: 3rem; border-radius: 15px; box-shadow: 0 5px 30px rgba(0,0,0,0.1); }
        .form-group { margin-bottom: 1.5rem; }
        .form-group label { display: block; margin-bottom: 0.5rem; color: #333; font-weight: 500; }
        .form-group input, .form-group textarea, .form-group select { width: 100%; padding: 0.8rem; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 1rem; transition: border-color 0.3s; }
        .form-group input:focus, .form-group textarea:focus, .form-group select:focus { outline: none; border-color: #667eea; }
        .form-group textarea { resize: vertical; min-height: 120px; }
        .submit-btn { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem 3rem; border: none; border-radius: 50px; font-size: 1.1rem; cursor: pointer; width: 100%; transition: transform 0.3s; }
        .submit-btn:hover { transform: scale(1.02); }
        .submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }
        
        .message { margin-top: 1rem; padding: 1rem; border-radius: 8px; text-align: center; display: none; }
        .message.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .message.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        
        footer { background: #2c3e50; color: white; text-align: center; padding: 2rem; margin-top: 4rem; }
        .aws-info { background: #34495e; padding: 2rem; margin-top: 2rem; border-radius: 10px; }
        .aws-info h3 { color: #FF9900; margin-bottom: 1rem; }
        .aws-badges { display: flex; justify-content: center; gap: 1rem; flex-wrap: wrap; margin-top: 1rem; }
        .badge { background: #667eea; padding: 0.5rem 1rem; border-radius: 20px; font-size: 0.9rem; }
        
        @keyframes fadeInDown { from { opacity: 0; transform: translateY(-30px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
        
        @media (max-width: 768px) {
            .hero h1 { font-size: 2rem; }
            .hero p { font-size: 1rem; }
            .nav-links { gap: 1rem; font-size: 0.9rem; }
            .form-container { padding: 1.5rem; }
        }
    </style>
</head>
<body>
    <header>
        <nav>
            <div class="logo">☁️ CloudTech Solutions</div>
            <ul class="nav-links">
                <li><a href="#home">Home</a></li>
                <li><a href="#features">Features</a></li>
                <li><a href="#stats">Stats</a></li>
                <li><a href="#contact">Contact</a></li>
            </ul>
        </nav>
    </header>

    <section id="home" class="hero">
        <h1>🚀 Welcome to CloudTech Solutions</h1>
        <p>Professional AWS Cloud Infrastructure with Database Integration</p>
        <a href="#contact" class="cta-button">Get Started Today</a>
    </section>

    <section id="features" class="features">
        <h2>Our AWS Infrastructure</h2>
        <div class="feature-grid">
            <div class="feature-card">
                <div class="feature-icon">🌐</div>
                <h3>VPC & Networking</h3>
                <p>Secure Virtual Private Cloud with multi-AZ deployment for high availability</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">💻</div>
                <h3>EC2 with Docker</h3>
                <p>Containerized applications running on t3.micro instances</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🗄️</div>
                <h3>RDS MySQL</h3>
                <p>Managed database with automated backups and monitoring</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">📦</div>
                <h3>S3 Storage</h3>
                <p>Scalable object storage with versioning enabled</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">⚖️</div>
                <h3>Load Balancer</h3>
                <p>Application Load Balancer for traffic distribution</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🔒</div>
                <h3>Security Groups</h3>
                <p>Multi-layer security protecting your infrastructure</p>
            </div>
        </div>
    </section>

    <section id="stats" class="stats">
        <div class="stats-container">
            <div class="stat-box">
                <h3>99.9%</h3>
                <p>Uptime SLA</p>
            </div>
            <div class="stat-box">
                <h3>2</h3>
                <p>Availability Zones</p>
            </div>
            <div class="stat-box">
                <h3>6+</h3>
                <p>AWS Services</p>
            </div>
            <div class="stat-box">
                <h3>24/7</h3>
                <p>Monitoring</p>
            </div>
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
                    <label for="email">Email Address *</label>
                    <input type="email" id="email" name="email" required>
                </div>
                <div class="form-group">
                    <label for="company">Company Name</label>
                    <input type="text" id="company" name="company">
                </div>
                <div class="form-group">
                    <label for="service">Service Interest *</label>
                    <select id="service" name="service" required>
                        <option value="">-- Select a Service --</option>
                        <option value="Cloud Migration">Cloud Migration</option>
                        <option value="Infrastructure Setup">Infrastructure Setup</option>
                        <option value="DevOps Consulting">DevOps Consulting</option>
                        <option value="Database Management">Database Management</option>
                        <option value="Security Audit">Security Audit</option>
                        <option value="Performance Optimization">Performance Optimization</option>
                        <option value="Other">Other</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="message">Message *</label>
                    <textarea id="message" name="message" required></textarea>
                </div>
                <button type="submit" class="submit-btn">Submit Inquiry</button>
            </form>
            <div id="formMessage" class="message"></div>
        </div>
    </section>

    <footer>
        <div class="aws-info">
            <h3>Powered by AWS Services</h3>
            <div class="aws-badges">
                <span class="badge">Amazon VPC</span>
                <span class="badge">Amazon EC2</span>
                <span class="badge">Amazon RDS</span>
                <span class="badge">Amazon S3</span>
                <span class="badge">Elastic Load Balancing</span>
                <span class="badge">Docker</span>
            </div>
        </div>
        <p style="margin-top: 2rem;">© 2025 CloudTech Solutions | Deployed on AWS EU-West-1 Region</p>
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
                    messageDiv.textContent = '✓ Success! Your message has been saved to our MySQL database.';
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
                submitBtn.textContent = 'Submit Inquiry';
                
                setTimeout(() => {
                    messageDiv.style.display = 'none';
                }, 5000);
            }
        });

        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });
    </script>
</body>
</html>
HTMLEOF

# ===== CREATE DEPLOYMENT SCRIPT FOR EC2 =====
cat > deploy-on-ec2.sh << 'EOF'
#!/bin/bash
echo "Deploying CloudTech application..."

tar -xzf cloudtech-app.tar.gz
cd cloudtech-app

sudo docker build -t cloudtech-app .
sudo docker stop webapp 2>/dev/null || true
sudo docker rm webapp 2>/dev/null || true
sudo docker run -d -p 80:3000 --name webapp --restart always cloudtech-app

echo ""
echo "✓ Deployment complete!"
echo "✓ Application running on port 80"
echo ""
echo "Test with:"
echo "  curl http://localhost/health"
echo "  curl http://localhost/api"
EOF

chmod +x deploy-on-ec2.sh

echo "✓ Files created successfully"
echo ""

# Create deployment package
echo "Creating deployment package..."
mkdir cloudtech-app
cp package.json server.js Dockerfile cloudtech-app/
cp -r public cloudtech-app/
cd cloudtech-app
tar -czf ../cloudtech-app.tar.gz *
cd ..

echo "✓ Package created: cloudtech-app.tar.gz"
echo ""

# Upload to S3
echo "Uploading to S3..."
aws s3 cp cloudtech-app.tar.gz s3://$BUCKET/ --region eu-west-1
aws s3 cp deploy-on-ec2.sh s3://$BUCKET/ --region eu-west-1

echo ""
echo "================================================"
echo "✓✓✓ DEPLOYMENT PACKAGE UPLOADED TO S3! ✓✓✓"
echo "================================================"
echo ""
echo "Package uploaded to: s3://$BUCKET/cloudtech-app.tar.gz"
echo ""
echo "════════════════════════════════════════════════"
echo "  NEXT STEPS - Run on EC2 Instance:"
echo "════════════════════════════════════════════════"
echo ""
echo "Option 1: SSH from your computer (if you have Key.pem):"
echo ""
echo "  ssh -i Key.pem ubuntu@$INSTANCE_IP << 'ENDSSH'"
echo "  aws s3 cp s3://$BUCKET/cloudtech-app.tar.gz ."
echo "  tar -xzf cloudtech-app.tar.gz"
echo "  sudo docker build -t cloudtech-app ."
echo "  sudo docker stop webapp 2>/dev/null; sudo docker rm webapp 2>/dev/null"
echo "  sudo docker run -d -p 80:3000 --name webapp --restart always cloudtech-app"
echo "  echo '✓ Deployment complete!'"
echo "  ENDSSH"
echo ""
echo "Option 2: Use AWS Systems Manager Session Manager:"
echo ""
echo "  1. Go to EC2 Console → Instances"
echo "  2. Select your instance → Connect → Session Manager"
echo "  3. Run these commands:"
echo ""
echo "     aws s3 cp s3://$BUCKET/cloudtech-app.tar.gz ."
echo "     tar -xzf cloudtech-app.tar.gz"
echo "     sudo docker build -t cloudtech-app ."
echo "     sudo docker stop webapp; sudo docker rm webapp"
echo "     sudo docker run -d -p 80:3000 --name webapp --restart always cloudtech-app"
echo ""
echo "════════════════════════════════════════════════"
echo "  After Deployment, Test Your Website:"
echo "════════════════════════════════════════════════"
echo ""
echo "Load Balancer URL (copy to browser):"
aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`WebUIURL`].OutputValue' --output text 2>/dev/null
echo ""
echo "Direct EC2 URL: http://$INSTANCE_IP"
echo ""
echo "API Endpoint: http://$INSTANCE_IP:3000/api"
echo ""
echo "Health Check: http://$INSTANCE_IP:3000/health"
echo ""
echo "════════════════════════════════════════════════"
echo "  To View Contacts in Database:"
echo "════════════════════════════════════════════════"
echo ""
echo "  ssh -i Key.pem ubuntu@$INSTANCE_IP"
echo "  mysql -h $RDS_ENDPOINT -u admin -p"
echo "  # Password: MyPassword123"
echo "  USE myprojectdb;"
echo "  SELECT * FROM contacts;"
echo ""
echo "================================================"
echo "✓ Script complete! Files ready in S3."
echo "================================================"
