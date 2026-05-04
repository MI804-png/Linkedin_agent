#!/usr/bin/env python
"""Convert HTML CV to PDF"""
from xhtml2pdf import pisa
import os

html_file = r'd:\cv_portofolio\Mikhael_CV.html'
pdf_file = r'd:\cv_portofolio\Mikhael_CV.pdf'

# Read HTML file
with open(html_file, 'r', encoding='utf-8') as f:
    html_content = f.read()

# Convert HTML to PDF
with open(pdf_file, 'wb') as output_file:
    pisa.CreatePDF(html_content, output_file)

print(f"PDF created successfully: {pdf_file}")
