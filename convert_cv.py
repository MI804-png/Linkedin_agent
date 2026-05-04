#!/usr/bin/env python
"""Convert CV to PDF"""
import subprocess
import sys
import os

# First, try to install fpdf2 if needed
try:
    from fpdf import FPDF
except ImportError:
    print("Installing fpdf2...")
    subprocess.run([sys.executable, "-m", "pip", "install", "fpdf2", "-q"], check=False)
    from fpdf import FPDF

# Read the markdown file
md_file = r'c:\cv_portofolio\CV_Professional_Template.md'
pdf_file = r'c:\cv_portofolio\Mikhael_CV.pdf'

with open(md_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove markdown formatting
content = content.replace('# ', '').replace('## ', '').replace('### ', '')
content = content.replace('**', '').replace('---', '')
content = content.replace('_', '').replace('[', '').replace(']', '')

# Create PDF
pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", size=10)

# Add content
for line in content.split('\n'):
    line = line.strip()
    if line:
        try:
            pdf.multi_cell(0, 5, line)
        except:
            # Skip problematic characters
            pass

# Save PDF
pdf.output(pdf_file)
print(f"✓ Professional PDF created: {pdf_file}")
