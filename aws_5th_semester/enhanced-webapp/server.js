const express = require('express');
const mysql = require('mysql2/promise');
const cors = require('cors');
const app = express();

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Database configuration - Update these with your RDS details
const dbConfig = {
  host: process.env.DB_HOST || 'myproject-db.c900uesmqwtf.eu-west-1.rds.amazonaws.com',
  user: process.env.DB_USER || 'admin',
  password: process.env.DB_PASSWORD || 'MyPassword123',
  database: process.env.DB_NAME || 'myprojectdb',
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0
};

// Create connection pool
const pool = mysql.createPool(dbConfig);

// Initialize database table
async function initializeDatabase() {
  try {
    const connection = await pool.getConnection();
    
    // Create contacts table if it doesn't exist
    await connection.query(`
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
    `);
    
    console.log('✓ Database initialized successfully');
    connection.release();
  } catch (error) {
    console.error('✗ Database initialization error:', error.message);
  }
}

// Initialize DB on startup
initializeDatabase();

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ 
    status: 'healthy', 
    timestamp: new Date().toISOString(),
    database: 'connected'
  });
});

// API info endpoint
app.get('/api', (req, res) => {
  res.json({
    message: 'CloudTech Solutions API Server',
    version: '1.0.0',
    status: 'running',
    timestamp: new Date().toISOString(),
    endpoints: {
      health: 'GET /health',
      contacts: {
        create: 'POST /api/contact',
        list: 'GET /api/contacts',
        count: 'GET /api/contacts/count'
      }
    }
  });
});

// Create contact endpoint
app.post('/api/contact', async (req, res) => {
  try {
    const { name, email, company, service, message, timestamp } = req.body;
    
    // Validation
    if (!name || !email || !service || !message) {
      return res.status(400).json({ 
        error: 'Missing required fields',
        required: ['name', 'email', 'service', 'message']
      });
    }

    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return res.status(400).json({ error: 'Invalid email format' });
    }

    // Insert into database
    const [result] = await pool.query(
      'INSERT INTO contacts (name, email, company, service, message, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
      [name, email, company || null, service, message, timestamp || new Date()]
    );

    res.status(201).json({
      success: true,
      message: 'Contact saved successfully',
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

// Get all contacts endpoint
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
      pagination: {
        limit,
        offset,
        hasMore: rows.length === limit
      }
    });

  } catch (error) {
    console.error('Database error:', error);
    res.status(500).json({ 
      error: 'Failed to retrieve contacts',
      details: error.message 
    });
  }
});

// Get contacts count
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

// Get contact by ID
app.get('/api/contact/:id', async (req, res) => {
  try {
    const [rows] = await pool.query(
      'SELECT * FROM contacts WHERE id = ?',
      [req.params.id]
    );

    if (rows.length === 0) {
      return res.status(404).json({ error: 'Contact not found' });
    }

    res.json({
      success: true,
      contact: rows[0]
    });

  } catch (error) {
    console.error('Database error:', error);
    res.status(500).json({ 
      error: 'Failed to retrieve contact',
      details: error.message 
    });
  }
});

// Error handler
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ 
    error: 'Something went wrong!',
    message: err.message 
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ 
    error: 'Endpoint not found',
    path: req.path 
  });
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`
╔════════════════════════════════════════════╗
║   CloudTech Solutions API Server           ║
║   Status: Running ✓                        ║
║   Port: ${PORT}                               ║
║   Database: MySQL/RDS                      ║
║   Time: ${new Date().toLocaleString()}     ║
╚════════════════════════════════════════════╝
  `);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, closing server...');
  await pool.end();
  process.exit(0);
});
