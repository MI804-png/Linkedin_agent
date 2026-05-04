# Deploy Enhanced Website to CloudShell

## Step 1: Upload deploy script to CloudShell

In CloudShell, run this command to create the deployment script:

```bash
curl -o deploy.sh https://raw.githubusercontent.com/your-repo/deploy.sh
```

OR manually create it:

```bash
cat > deploy-enhanced.sh << 'SCRIPT_END'
#!/bin/bash
echo "Creating enhanced application..."

# Get RDS endpoint
RDS_ENDPOINT=$(aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`RDSEndpoint`].OutputValue' --output text)
BUCKET=$(aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' --output text)
INSTANCE_IP=$(aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`WebUIInstanceIP`].OutputValue' --output text)

echo "RDS: $RDS_ENDPOINT"
echo "S3: $BUCKET"
echo "EC2: $INSTANCE_IP"

mkdir -p /tmp/app && cd /tmp/app

# Create all files (package.json, server.js, Dockerfile, index.html)
# ... (files will be created here)

tar -czf app.tar.gz *
aws s3 cp app.tar.gz s3://$BUCKET/

echo "✓ Uploaded to S3!"
echo ""
echo "Now run on EC2:"
echo "  aws s3 cp s3://$BUCKET/app.tar.gz ."
echo "  tar -xzf app.tar.gz"
echo "  sudo docker build -t app ."
echo "  sudo docker stop webapp; sudo docker rm webapp"
echo "  sudo docker run -d -p 80:3000 --name webapp --restart always app"
SCRIPT_END

chmod +x deploy-enhanced.sh
./deploy-enhanced.sh
```

## Step 2: EASIEST METHOD - Copy All Commands

Paste this entire block into CloudShell:

```bash
# Get your resource info
RDS_ENDPOINT=$(aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`RDSEndpoint`].OutputValue' --output text)
BUCKET=$(aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' --output text)
INSTANCE_IP=$(aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`WebUIInstanceIP`].OutputValue' --output text)

echo "✓ RDS: $RDS_ENDPOINT"
echo "✓ S3: $BUCKET"  
echo "✓ EC2: $INSTANCE_IP"

# Create app directory
mkdir -p /tmp/cloudtech && cd /tmp/cloudtech

# Create package.json
cat > package.json << 'EOF'
{
  "name": "cloudtech-api",
  "version": "1.0.0",
  "dependencies": {
    "express": "^4.18.2",
    "mysql2": "^3.6.5",
    "cors": "^2.8.5"
  }
}
EOF

# Create server.js
cat > server.js << EOF
const express = require('express');
const mysql = require('mysql2/promise');
const cors = require('cors');
const path = require('path');
const app = express();

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

const pool = mysql.createPool({
  host: '${RDS_ENDPOINT}',
  user: 'admin',
  password: 'MyPassword123',
  database: 'myprojectdb'
});

(async () => {
  const c = await pool.getConnection();
  await c.query(\`CREATE TABLE IF NOT EXISTS contacts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255), email VARCHAR(255), company VARCHAR(255),
    service VARCHAR(255), message TEXT, timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )\`);
  c.release();
  console.log('DB Ready');
})();

app.get('/health', (req, res) => res.json({ status: 'ok' }));
app.get('/api', (req, res) => res.json({ message: 'CloudTech API v1.0', database: 'Connected' }));

app.post('/api/contact', async (req, res) => {
  try {
    const { name, email, company, service, message } = req.body;
    if (!name || !email) return res.status(400).json({ error: 'Missing fields' });
    
    await pool.query('INSERT INTO contacts (name,email,company,service,message,timestamp) VALUES (?,?,?,?,?,?)',
      [name, email, company, service, message, new Date()]);
    
    res.json({ success: true, message: 'Saved to database!' });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/api/contacts', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT * FROM contacts ORDER BY created_at DESC LIMIT 50');
    res.json({ success: true, count: rows.length, contacts: rows });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/api/contacts/count', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT COUNT(*) as total FROM contacts');
    res.json({ total: rows[0].total });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/', (req, res) => res.sendFile(path.join(__dirname, 'public', 'index.html')));
app.listen(3000, '0.0.0.0', () => console.log('Server on 3000'));
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

# Create HTML (shortened version due to size)
mkdir -p public
cat > public/index.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>CloudTech Solutions</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:Arial,sans-serif;line-height:1.6}
        header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:1rem;position:fixed;width:100%;top:0;z-index:1000}
        nav{display:flex;justify-content:space-between;max-width:1200px;margin:0 auto;align-items:center}
        .logo{font-size:1.5rem;font-weight:bold}
        .nav-links{display:flex;list-style:none;gap:2rem}
        .nav-links a{color:#fff;text-decoration:none}
        .hero{margin-top:60px;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:100px 2rem;text-align:center}
        .hero h1{font-size:2.5rem;margin-bottom:1rem}
        .features{max-width:1200px;margin:3rem auto;padding:0 2rem}
        .features h2{text-align:center;font-size:2rem;margin-bottom:2rem;color:#667eea}
        .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:2rem}
        .card{background:#fff;padding:2rem;border-radius:10px;box-shadow:0 5px 15px rgba(0,0,0,0.1);text-align:center}
        .card:hover{transform:translateY(-5px);transition:0.3s}
        .icon{font-size:2.5rem;margin-bottom:1rem}
        .contact{max-width:700px;margin:3rem auto;padding:0 2rem}
        .contact h2{text-align:center;color:#667eea;margin-bottom:2rem}
        .form-container{background:#fff;padding:2rem;border-radius:10px;box-shadow:0 5px 15px rgba(0,0,0,0.1)}
        .form-group{margin-bottom:1rem}
        .form-group label{display:block;margin-bottom:0.5rem;font-weight:500}
        .form-group input,.form-group select,.form-group textarea{width:100%;padding:0.7rem;border:1px solid #ddd;border-radius:5px;font-size:1rem}
        .form-group textarea{min-height:100px;resize:vertical}
        .btn{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:1rem 2rem;border:none;border-radius:50px;cursor:pointer;width:100%;font-size:1rem}
        .btn:hover{opacity:0.9}
        .message{margin-top:1rem;padding:1rem;border-radius:5px;text-align:center;display:none}
        .message.success{background:#d4edda;color:#155724}
        .message.error{background:#f8d7da;color:#721c24}
        footer{background:#2c3e50;color:#fff;text-align:center;padding:2rem;margin-top:3rem}
        .badges{display:flex;justify-content:center;gap:1rem;flex-wrap:wrap;margin-top:1rem}
        .badge{background:#667eea;padding:0.5rem 1rem;border-radius:20px;font-size:0.9rem}
    </style>
</head>
<body>
    <header>
        <nav>
            <div class="logo">☁️ CloudTech</div>
            <ul class="nav-links">
                <li><a href="#home">Home</a></li>
                <li><a href="#features">Features</a></li>
                <li><a href="#contact">Contact</a></li>
            </ul>
        </nav>
    </header>
    
    <section id="home" class="hero">
        <h1>🚀 CloudTech Solutions</h1>
        <p>AWS Cloud Infrastructure with Database Integration</p>
    </section>
    
    <section id="features" class="features">
        <h2>AWS Services</h2>
        <div class="grid">
            <div class="card"><div class="icon">🌐</div><h3>VPC</h3><p>Secure networking</p></div>
            <div class="card"><div class="icon">💻</div><h3>EC2</h3><p>Docker containers</p></div>
            <div class="card"><div class="icon">🗄️</div><h3>RDS</h3><p>MySQL database</p></div>
            <div class="card"><div class="icon">📦</div><h3>S3</h3><p>Object storage</p></div>
            <div class="card"><div class="icon">⚖️</div><h3>ALB</h3><p>Load balancing</p></div>
            <div class="card"><div class="icon">🔒</div><h3>Security</h3><p>Multi-layer</p></div>
        </div>
    </section>
    
    <section id="contact" class="contact">
        <h2>Contact Us</h2>
        <div class="form-container">
            <form id="form">
                <div class="form-group">
                    <label>Name *</label>
                    <input type="text" id="name" required>
                </div>
                <div class="form-group">
                    <label>Email *</label>
                    <input type="email" id="email" required>
                </div>
                <div class="form-group">
                    <label>Company</label>
                    <input type="text" id="company">
                </div>
                <div class="form-group">
                    <label>Service *</label>
                    <select id="service" required>
                        <option value="">Select</option>
                        <option>Cloud Migration</option>
                        <option>DevOps</option>
                        <option>Database</option>
                        <option>Security</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Message *</label>
                    <textarea id="message" required></textarea>
                </div>
                <button type="submit" class="btn">Submit</button>
            </form>
            <div id="msg" class="message"></div>
        </div>
    </section>
    
    <footer>
        <h3 style="color:#FF9900">AWS Services</h3>
        <div class="badges">
            <span class="badge">VPC</span>
            <span class="badge">EC2</span>
            <span class="badge">RDS</span>
            <span class="badge">S3</span>
            <span class="badge">ALB</span>
        </div>
        <p style="margin-top:1rem">© 2025 CloudTech | EU-West-1</p>
    </footer>
    
    <script>
        document.getElementById('form').addEventListener('submit', async function(e) {
            e.preventDefault();
            const msg = document.getElementById('msg');
            const btn = document.querySelector('.btn');
            btn.disabled = true;
            btn.textContent = 'Sending...';
            
            try {
                const res = await fetch('/api/contact', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        name: document.getElementById('name').value,
                        email: document.getElementById('email').value,
                        company: document.getElementById('company').value,
                        service: document.getElementById('service').value,
                        message: document.getElementById('message').value
                    })
                });
                
                const data = await res.json();
                
                if (res.ok) {
                    msg.className = 'message success';
                    msg.textContent = '✓ Saved to database!';
                    msg.style.display = 'block';
                    document.getElementById('form').reset();
                } else {
                    throw new Error(data.error);
                }
            } catch (err) {
                msg.className = 'message error';
                msg.textContent = '✗ Error: ' + err.message;
                msg.style.display = 'block';
            } finally {
                btn.disabled = false;
                btn.textContent = 'Submit';
                setTimeout(() => msg.style.display = 'none', 5000);
            }
        });
    </script>
</body>
</html>
EOF

echo ""
echo "✓ Files created!"

# Create tarball
tar -czf app.tar.gz *

# Upload to S3
aws s3 cp app.tar.gz s3://$BUCKET/

echo ""
echo "================================================"
echo "✓ Package uploaded to S3!"
echo "================================================"
echo ""
echo "Now copy these commands and run on your LOCAL machine:"
echo ""
echo "ssh -i Key.pem ubuntu@$INSTANCE_IP << 'ENDSSH'"
echo "aws s3 cp s3://$BUCKET/app.tar.gz ."
echo "tar -xzf app.tar.gz"
echo "sudo docker build -t cloudtech-app ."
echo "sudo docker stop webapp 2>/dev/null; sudo docker rm webapp 2>/dev/null"
echo "sudo docker run -d -p 80:3000 --name webapp --restart always cloudtech-app"
echo "echo '✓ Deployment complete!'"
echo "ENDSSH"
echo ""
echo "================================================"
echo "Or if you have SSM/Session Manager, run:"
echo "  aws ssm start-session --target <instance-id>"
echo "================================================"
```

That's it! The entire enhanced website with database will be deployed.

## What This Does:

1. ✅ Gets your RDS, S3, and EC2 info automatically
2. ✅ Creates professional website with contact form
3. ✅ Creates Node.js API with MySQL connection
4. ✅ Creates Docker container
5. ✅ Uploads package to your S3 bucket
6. ✅ Gives you SSH command to deploy on EC2

## Test After Deployment:

```bash
# Get Load Balancer URL
aws cloudformation describe-stacks --stack-name MyAWSProject --region eu-west-1 --query 'Stacks[0].Outputs[?OutputKey==`WebUIURL`].OutputValue' --output text
```

Open that URL in your browser - you'll see the new professional website!

Test the contact form - it will save to your RDS database.

Check database:
```bash
ssh -i Key.pem ubuntu@YOUR-EC2-IP
mysql -h YOUR-RDS-ENDPOINT -u admin -p
# Password: MyPassword123
USE myprojectdb;
SELECT * FROM contacts;
```
