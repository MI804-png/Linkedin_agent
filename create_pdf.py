#!/usr/bin/env python
"""Create a professional CV PDF"""
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

# Create PDF
pdf_path = r'd:\cv_portofolio\Mikhael_CV.pdf'
doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)

# Styles
styles = getSampleStyleSheet()
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=16,
    textColor=colors.HexColor('#0066cc'),
    spaceAfter=6,
    alignment=TA_CENTER,
    fontName='Helvetica-Bold'
)

heading_style = ParagraphStyle(
    'CustomHeading',
    parent=styles['Heading2'],
    fontSize=11,
    textColor=colors.HexColor('#0066cc'),
    spaceAfter=6,
    spaceBefore=8,
    fontName='Helvetica-Bold'
)

subheading_style = ParagraphStyle(
    'SubHeading',
    parent=styles['Heading3'],
    fontSize=10,
    textColor=colors.HexColor('#333333'),
    spaceAfter=2,
    spaceBefore=4,
    fontName='Helvetica-Bold'
)

body_style = ParagraphStyle(
    'CustomBody',
    parent=styles['BodyText'],
    fontSize=9,
    alignment=TA_JUSTIFY,
    spaceAfter=4
)

normal_style = ParagraphStyle(
    'Normal',
    parent=styles['Normal'],
    fontSize=9,
    spaceAfter=2
)

# Content
story = []

# Header
story.append(Paragraph("MIKHAEL NABIL SALAMA REZK", title_style))
story.append(Paragraph("Kecskemét, Hungary | Email: Mikhael.Nabil.Salama.Rezk@gmail.com | Phone: +36 70 635 5765", normal_style))
story.append(Paragraph("GitHub: https://github.com/MI804-png | LinkedIn: https://www.linkedin.com/in/mikhael-nabil-salama-rezk-065b6b197/", normal_style))
story.append(Spacer(1, 0.15*inch))

# Professional Summary
story.append(Paragraph("PROFESSIONAL SUMMARY", heading_style))
story.append(Paragraph(
    "Aspiring Full Stack Developer with hands-on experience in web development, software engineering, and project management. "
    "Proven track record of delivering responsive websites and desktop applications that improve user engagement and operational efficiency. "
    "Skilled in modern web technologies (HTML, CSS, JavaScript, PHP), Java programming, and network systems. "
    "Eager to contribute technical expertise and collaborative skills to innovative organizations while building professional growth.",
    body_style
))
story.append(Spacer(1, 0.1*inch))

# Core Competencies
story.append(Paragraph("CORE COMPETENCIES", heading_style))
story.append(Paragraph("<b>Languages:</b> HTML, CSS, JavaScript, PHP, Java, C#, Python, C++", normal_style))
story.append(Paragraph("<b>Frameworks & Tools:</b> ASP.NET Core, Bootstrap, Entity Framework, GitHub, Cisco Packet Tracer", normal_style))
story.append(Paragraph("<b>Databases & SQL:</b> SQL Server, Oracle SQL, T-SQL, SQL, Entity Framework Core, Database Design, CRUD Operations, Migrations", normal_style))
story.append(Paragraph("<b>Cloud & DevOps:</b> AWS (EC2, VPC, RDS, S3, ALB, ASG), Docker, CloudFormation", normal_style))
story.append(Paragraph("<b>AI/ML:</b> Microsoft Copilot Studio, Scikit-learn, Pandas, NumPy, NLP", normal_style))
story.append(Paragraph("<b>Methodologies:</b> Agile, Waterfall, Project Management, Clean Architecture", normal_style))
story.append(Spacer(1, 0.1*inch))

# Professional Experience
story.append(Paragraph("PROFESSIONAL EXPERIENCE", heading_style))

story.append(Paragraph("Cloud Infrastructure Engineer | AWS 5th Semester Project | October 2024 – November 2025", subheading_style))
story.append(Paragraph("<bullet>•</bullet> Designed and deployed a highly available cloud infrastructure on Amazon Web Services (AWS)", body_style))
story.append(Paragraph("<bullet>•</bullet> Implemented multi-AZ architecture with VPC, EC2, RDS, and Application Load Balancer", body_style))
story.append(Paragraph("<bullet>•</bullet> Deployed containerized applications using Docker and AWS services for scalability", body_style))
story.append(Paragraph("<bullet>•</bullet> Technologies: AWS (EC2, VPC, RDS, S3, ALB, ASG), Docker, CloudFormation", body_style))
story.append(Paragraph("", normal_style))  # Spacing

story.append(Paragraph("AI Agent Developer | Microsoft Copilot Studio | December 2024 – Present", subheading_style))
story.append(Paragraph("<bullet>•</bullet> Designed and deployed conversational AI agents using Microsoft Copilot Studio", body_style))
story.append(Paragraph("<bullet>•</bullet> Created intelligent agents with natural language processing capabilities", body_style))
story.append(Paragraph("<bullet>•</bullet> Integrated agents with enterprise systems for knowledge retrieval and customer interactions", body_style))
story.append(Paragraph("<bullet>•</bullet> Technologies: Microsoft Copilot Studio, AI/ML, Natural Language Processing", body_style))
story.append(Paragraph("", normal_style))  # Spacing
story.append(Paragraph("Freelance Web Developer | Remote | June 2021 – Present", subheading_style))
story.append(Paragraph("• Developed responsive websites for clients using HTML, CSS, JavaScript, and PHP", normal_style))
story.append(Paragraph("• Created restaurant website that improved online order processing by 20%", normal_style))
story.append(Paragraph("• Designed and launched robotics delivery service website, improving customer engagement by 15%", normal_style))
story.append(Paragraph("• Managed version control using GitHub to ensure efficient collaboration on projects", normal_style))
story.append(Spacer(1, 0.05*inch))

story.append(Paragraph("Network Systems Assistant | John von Neumann University | November 2022 – Present", subheading_style))
story.append(Paragraph("• Configured network systems using Cisco Packet Tracer with focus on security and reliability", normal_style))
story.append(Paragraph("• Assisted in troubleshooting network issues, reducing downtime by 25%", normal_style))
story.append(Paragraph("• Contributed to implementation of secure network configurations", normal_style))
story.append(Spacer(1, 0.05*inch))

story.append(Paragraph("Project Manager Intern | Freelance | February 2022 – June 2022", subheading_style))
story.append(Paragraph("• Led small team in development of Java desktop application using Agile methodologies", normal_style))
story.append(Paragraph("• Improved project delivery time by 10% through effective planning and task prioritization", normal_style))
story.append(Paragraph("• Utilized both Waterfall and Agile models to manage workflows and team coordination", normal_style))
story.append(Spacer(1, 0.1*inch))

# Key Projects
story.append(Paragraph("KEY PROJECTS & REPOSITORIES", heading_style))

story.append(Paragraph("Restaurant Website | https://github.com/MI804-png/restaurant-website", subheading_style))
story.append(Paragraph("Fully functional restaurant website with online order management system. Technologies: HTML5, CSS3, JavaScript, PHP, SQL Server. Improved online order processing by 20%.", normal_style))
story.append(Spacer(1, 0.05*inch))

story.append(Paragraph("Robotics Delivery Service Website | https://github.com/MI804-png/delivery-service-website", subheading_style))
story.append(Paragraph("Responsive website for delivery service with real-time tracking features. Technologies: HTML, CSS, JavaScript, Bootstrap. Increased customer engagement by 15%.", normal_style))
story.append(Spacer(1, 0.05*inch))

story.append(Paragraph("Java Task Management Application | https://github.com/MI804-png/task-management-app", subheading_style))
story.append(Paragraph("Desktop application with user authentication and database operations. Technologies: Java, SQL Server. Improved task completion rates by 10%.", normal_style))
story.append(Spacer(1, 0.05*inch))

story.append(Paragraph("Smart News Classifier | https://github.com/MI804-png/smart-news-classifier", subheading_style))
story.append(Paragraph("Machine Learning project classifying news articles using Python and Scikit-learn. Trained on UCI News Aggregator dataset (400K+ articles). Technologies: Python, Pandas, NumPy, Scikit-learn, Machine Learning. Implemented NLP techniques for text preprocessing and feature extraction.", normal_style))
story.append(Spacer(1, 0.05*inch))

story.append(Paragraph("MvcMovie - ASP.NET Core Web Application | https://github.com/MI804-png/server_side", subheading_style))
story.append(Paragraph("Full-stack ASP.NET Core MVC application for movie management. Implemented complete CRUD operations, database migrations, and SQL Server integration. Technologies: C#, ASP.NET Core, Entity Framework, SQL Server, HTML, CSS, JavaScript.", normal_style))
story.append(Spacer(1, 0.05*inch))

story.append(Paragraph("Server-Side Project with Clean Architecture | https://github.com/MI804-png/serverSide5thsemester_Bolla_mikhael", subheading_style))
story.append(Paragraph("Enterprise-grade application implementing Clean Architecture design patterns with multiple project layers. ServerSideProject2 with complete source files demonstrating separation of concerns, layered architecture, and enterprise design patterns. Technologies: C#, ASP.NET, HTML, CSS, JavaScript.", normal_style))
story.append(Spacer(1, 0.05*inch))

story.append(Paragraph("Fundraising Project - ASP.NET Web Application | https://github.com/MI804-png/fundraising-project", subheading_style))
story.append(Paragraph("Comprehensive ASP.NET fundraising web application with Entity Framework and complete project documentation. Features UML diagrams, risk analysis, project scheduling, and professional presentation materials. Technologies: C#, ASP.NET, Entity Framework, SQL Server, HTML, CSS, JavaScript.", normal_style))
story.append(Spacer(1, 0.1*inch))

# Education
story.append(Paragraph("EDUCATION", heading_style))
story.append(Paragraph("Bachelor's Degree in Computer Science | John von Neumann University, Kecskemét, Hungary | Currently 6th Semester", subheading_style))
story.append(Paragraph("Diploma in Informatics & Telecommunications | Italian Industrial Technical Institute 'DON BOSCO' | Graduated: July 2022", normal_style))
story.append(Spacer(1, 0.1*inch))

# Certifications
story.append(Paragraph("CERTIFICATIONS", heading_style))
story.append(Paragraph("• Erasmus+ Business Camp Certificate – PAR University of Applied Sciences, Rijeka, Croatia (November 2025, 3 ECTS Credits)", normal_style))
story.append(Paragraph("• Full Stack Web Developer Diploma – Yat Professional", normal_style))
story.append(Paragraph("• Mastering Java Programming Course", normal_style))
story.append(Paragraph("• Cloud Developer (Google Cloud Framework) – We Company, Egypt", normal_style))
story.append(Paragraph("• Employability Skills Training Course", normal_style))
story.append(Spacer(1, 0.1*inch))

# Languages
story.append(Paragraph("LANGUAGES", heading_style))
story.append(Paragraph("Italian: Proficient (C1 Level) | English: Intermediate (B2 Level) | Arabic: Native Speaker", normal_style))
story.append(Spacer(1, 0.1*inch))

# Footer
story.append(Paragraph("References available upon request | Last Updated: December 22, 2025", normal_style))

# Build PDF
doc.build(story)
print(f"✓ Professional PDF created successfully: {pdf_path}")
