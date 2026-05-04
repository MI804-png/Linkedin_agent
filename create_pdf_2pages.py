#!/usr/bin/env python
"""Create a professional 2-page CV PDF"""
import subprocess
import sys

# Install reportlab for PDF creation
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
except ImportError:
    print("Installing reportlab...")
    subprocess.run([sys.executable, "-m", "pip", "install", "reportlab", "-q"], check=True)
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

# Create PDF - 2 PAGES CONDENSED
pdf_path = r'd:\cv_portofolio\Mikhael_CV.pdf'
doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.3*inch, bottomMargin=0.3*inch, leftMargin=0.4*inch, rightMargin=0.4*inch)

# Styles
styles = getSampleStyleSheet()
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=18,
    textColor=colors.HexColor('#1a1a1a'),
    spaceAfter=2,
    alignment=TA_CENTER,
    fontName='Helvetica-Bold'
)

contact_style = ParagraphStyle(
    'Contact',
    parent=styles['Normal'],
    fontSize=9,
    textColor=colors.HexColor('#404040'),
    spaceAfter=0,
    alignment=TA_CENTER,
    fontName='Helvetica'
)

heading_style = ParagraphStyle(
    'CustomHeading',
    parent=styles['Heading2'],
    fontSize=12,
    textColor=colors.HexColor('#1a3a6b'),
    spaceAfter=8,
    spaceBefore=3,
    fontName='Helvetica-Bold',
    borderColor=colors.HexColor('#1a3a6b'),
    borderWidth=1,
    borderPadding=4
)

subheading_style = ParagraphStyle(
    'SubHeading',
    parent=styles['Heading3'],
    fontSize=11,
    textColor=colors.HexColor('#1a1a1a'),
    spaceAfter=2,
    spaceBefore=3,
    fontName='Helvetica-Bold'
)

body_style = ParagraphStyle(
    'CustomBody',
    parent=styles['BodyText'],
    fontSize=10,
    alignment=TA_LEFT,
    spaceAfter=2,
    leading=11
)

bullet_style = ParagraphStyle(
    'Bullet',
    parent=styles['Normal'],
    fontSize=10,
    spaceAfter=1,
    leading=11,
    leftIndent=15,
    textColor=colors.HexColor('#2a2a2a')
)

normal_style = ParagraphStyle(
    'Normal',
    parent=styles['Normal'],
    fontSize=10,
    spaceAfter=1,
    leading=12,
    textColor=colors.HexColor('#2a2a2a')
)

# Content
story = []

# Header
story.append(Paragraph("MIKHAEL NABIL SALAMA REZK", title_style))
story.append(Paragraph("Senior Full Stack Developer & Cloud Infrastructure Engineer", contact_style))
story.append(Spacer(1, 0.01*inch))
story.append(Paragraph("📍 Kecskemét, Hungary | 📞 +36 70 635 5765 | 📧 Mikhael.Nabil.Salama.Rezk@gmail.com", contact_style))
story.append(Paragraph("🔗 GitHub: https://github.com/MI804-png | 💼 LinkedIn: https://www.linkedin.com/in/mikhael-nabil-salama-rezk-065b6b197/", contact_style))
story.append(Spacer(1, 0.12*inch))

# Professional Summary
story.append(Paragraph("PROFESSIONAL SUMMARY", heading_style))
story.append(Paragraph(
    "Results-driven Full Stack Developer with proven expertise in web development, cloud infrastructure, and AI agent development. Demonstrated track record delivering high-performance applications that improve efficiency by 10-20%. Proficient in modern web technologies, enterprise architecture, and cloud platforms.",
    body_style
))
story.append(Spacer(1, 0.06*inch))

# Core Competencies
story.append(Paragraph("CORE COMPETENCIES", heading_style))
story.append(Paragraph("<b>Languages:</b> HTML5, CSS3, JavaScript, PHP, Java, C#, Python, C++", normal_style))
story.append(Paragraph("<b>Databases & Backend:</b> SQL Server, Oracle SQL, MongoDB, T-SQL, Entity Framework Core, Database Design, CRUD Operations", normal_style))
story.append(Paragraph("<b>Cloud & DevOps:</b> AWS (EC2, VPC, RDS, S3, ALB, ASG), Docker, CloudFormation, Infrastructure Design", normal_style))
story.append(Paragraph("<b>Frameworks & Patterns:</b> ASP.NET Core, Bootstrap, Clean Architecture, MVC, Entity Framework", normal_style))
story.append(Spacer(1, 0.04*inch))

# Professional Experience
story.append(Paragraph("PROFESSIONAL EXPERIENCE", heading_style))

story.append(Paragraph("Cloud Infrastructure Engineer | AWS 5th Semester Project | Oct 2024 – Present", subheading_style))
story.append(Paragraph("• Architected and deployed multi-AZ cloud infrastructure using AWS services (EC2, VPC, RDS, S3, ALB, Auto Scaling Groups)", bullet_style))
story.append(Paragraph("• Containerized applications using Docker for consistent deployment across environments", bullet_style))
story.append(Paragraph("• Implemented auto-scaling policies and load balancing achieving 99.9% system uptime", bullet_style))
story.append(Spacer(1, 0.02*inch))

story.append(Paragraph("AI Agent Developer | Microsoft Copilot Studio | Dec 2024 – Present", subheading_style))
story.append(Paragraph("• Designed and developed conversational AI agents leveraging Microsoft Copilot Studio capabilities", bullet_style))
story.append(Paragraph("• Integrated AI agents with enterprise systems for intelligent knowledge retrieval and automation", bullet_style))
story.append(Spacer(1, 0.02*inch))

story.append(Paragraph("Senior Freelance Web Developer | Remote | Jun 2021 – Present", subheading_style))
story.append(Paragraph("• Developed responsive, mobile-first websites using modern web technologies (HTML5, CSS3, JavaScript, PHP)", bullet_style))
story.append(Paragraph("• Restaurant platform: Improved order processing efficiency by 20%; delivered 6 menu items with real-time management", bullet_style))
story.append(Paragraph("• Delivery service platform: Increased customer engagement by 15% with real-time tracking simulation", bullet_style))
story.append(Spacer(1, 0.02*inch))

story.append(Paragraph("Network Systems Technician | John von Neumann University | Nov 2022 – Present", subheading_style))
story.append(Paragraph("• Configured and optimized network systems using Cisco Packet Tracer across enterprise infrastructure", bullet_style))
story.append(Paragraph("• Reduced network downtime by 25% through proactive system monitoring and troubleshooting", bullet_style))
story.append(Spacer(1, 0.04*inch))

# Key Projects
story.append(Paragraph("FEATURED PROJECTS", heading_style))
story.append(Paragraph(
    "<b>Restaurant Management System</b> – HTML5, CSS3, JavaScript, PHP, SQL Server. Order management with real-time inventory tracking. Order processing improved by 20%.",
    bullet_style
))
story.append(Paragraph(
    "<b>Delivery Service Platform</b> – Bootstrap, HTML5, JavaScript. Real-time tracking system. Customer engagement increased by 15%.",
    bullet_style
))
story.append(Paragraph(
    "<b>Task Management Application</b> – Java, SQL Server, JDBC. Desktop application with user authentication and CRUD operations. Task completion improved by 10%.",
    bullet_style
))
story.append(Paragraph(
    "<b>Smart News Classifier</b> – Python, Scikit-learn, Machine Learning. NLP-based classification of 400K+ UCI News articles with high accuracy.",
    bullet_style
))
story.append(Spacer(1, 0.04*inch))

# Education & Certifications
story.append(Paragraph("EDUCATION & CERTIFICATIONS", heading_style))
story.append(Paragraph("<b>Bachelor of Science in Computer Science</b> – John von Neumann University, 6th Semester (Expected Graduation 2026)", bullet_style))
story.append(Paragraph("<b>Diploma in Informatics & Telecommunications</b> – Don Bosco Institute, July 2022", bullet_style))
story.append(Paragraph("<b>Professional Certifications:</b> Erasmus+ Business Camp (PAR University, 3 ECTS), Full Stack Web Developer, Java Mastery, Google Cloud Developer, Employability Skills Training", bullet_style))
story.append(Spacer(1, 0.04*inch))

# Add page break before Technical Skills
story.append(PageBreak())

# Technical Skills
story.append(Paragraph("TECHNICAL SKILLS & EXPERTISE", heading_style))
story.append(Paragraph(
    "<b>Frontend Development:</b> HTML5, CSS3, JavaScript, Bootstrap, Responsive Design, Mobile-First Approach",
    bullet_style
))
story.append(Paragraph(
    "<b>Backend Development:</b> PHP, Java, C#, Python, C++, RESTful APIs, Web Services",
    bullet_style
))
story.append(Paragraph(
    "<b>Enterprise Frameworks:</b> ASP.NET Core, Entity Framework Core, MVC Architecture, Clean Architecture Patterns",
    bullet_style
))
story.append(Paragraph(
    "<b>Database Systems:</b> SQL Server, Oracle SQL, MongoDB, T-SQL, Database Design, CRUD Operations, Entity Framework Migrations, Relational Design",
    bullet_style
))
story.append(Paragraph(
    "<b>Cloud & Infrastructure:</b> AWS (EC2, VPC, RDS, S3, ALB, Auto Scaling), Docker, CloudFormation, Infrastructure as Code",
    bullet_style
))
story.append(Paragraph(
    "<b>AI & Machine Learning:</b> Microsoft Copilot Studio, Scikit-learn, Pandas, NumPy, Natural Language Processing, Data Analysis",
    bullet_style
))
story.append(Paragraph(
    "<b>Tools & Methodologies:</b> Git/GitHub, Agile, Waterfall, Project Management, Cisco Packet Tracer, Network Configuration",
    bullet_style
))
story.append(Spacer(1, 0.06*inch))

# Languages
story.append(Paragraph("LANGUAGES", heading_style))
story.append(Paragraph("<b>Italian:</b> C1 (Proficient) | <b>English:</b> B2 (Intermediate) | <b>Arabic:</b> Native Speaker", normal_style))
story.append(Spacer(1, 0.06*inch))

# GitHub Profile
story.append(Paragraph("GITHUB & PORTFOLIO", heading_style))
story.append(Paragraph(
    "<b>GitHub Repository:</b> https://github.com/MI804-png | <b>Portfolio Website:</b> https://github.com/MI804-png/portfolio",
    normal_style
))
story.append(Paragraph(
    "All 8 featured projects available on GitHub with complete documentation, source code, and technical specifications. Professional portfolio website showcases experience, skills, and project achievements with responsive design.",
    body_style
))
story.append(Spacer(1, 0.06*inch))

story.append(Paragraph(
    "References available upon request",
    normal_style
))

# Build PDF
doc.build(story)
print("✓ Professional 2-page PDF created successfully: " + pdf_path)
