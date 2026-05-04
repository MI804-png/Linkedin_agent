# CV Conversion & Management Guide

## Converting Your Markdown CV to PDF/Word

### Option 1: Using Online Tools (Easiest)

1. **MarkdownToPDF.com**
   - Go to: https://markdowntopdf.com
   - Paste content from CV_Professional_Template.md
   - Click "Convert"
   - Download PDF

2. **Pandoc Online**
   - Go to: https://pandoc.org/try
   - Paste markdown content
   - Select "Word (.docx)" from output format
   - Download converted file

### Option 2: VS Code Extensions (Recommended)

1. Install "Markdown PDF" extension:
   - Open VS Code
   - Go to Extensions (Ctrl+Shift+X)
   - Search: "Markdown PDF"
   - Click Install
   - Right-click on CV_Professional_Template.md
   - Select "Markdown PDF: Export (pdf)"
   - Or export to Word format

### Option 3: Using Pandoc (Command Line)

```bash
# Install Pandoc first from: https://pandoc.org/installing.html

# Convert to PDF
pandoc CV_Professional_Template.md -o Mikhael_CV.pdf

# Convert to Word
pandoc CV_Professional_Template.md -o Mikhael_CV.docx

# Convert to HTML
pandoc CV_Professional_Template.md -o Mikhael_CV.html
```

### Option 4: Google Docs Method

1. Create new Google Doc
2. Copy/paste content from CV_Professional_Template.md
3. Format as needed (Markdown syntax will convert automatically)
4. Download as: PDF, Word, or keep online

---

## CV Versions to Maintain

### 1. **Master Copy** (CV_Professional_Template.md)
- Store all content here
- Update first when making changes
- Version control with Git

### 2. **PDF Version** (Mikhael_CV.pdf)
- Use for: LinkedIn profile, email submissions, online applications
- Universal format, looks professional
- 1-2 pages recommended

### 3. **Word Version** (Mikhael_CV.docx)
- Use for: Companies requesting .docx format
- Easy to customize per job
- Keep formatting simple

### 4. **Text Version** (Mikhael_CV.txt)
- Use for: LinkedIn text field, online forms
- ATS (Applicant Tracking System) friendly
- Simple formatting

### 5. **Web Version** (Portfolio Website)
- Use for: Your portfolio site
- HTML formatted
- Interactive with links

---

## ATS-Friendly CV Tips

**ATS = Applicant Tracking Systems** (software that reads your CV)

### ✅ DO:
- Use standard fonts: Arial, Calibri, Times New Roman
- Use bullet points (•) for list items
- Use standard section headers
- Include specific job keywords from job posting
- Use standard formatting (no tables, no graphics)
- Save as PDF or .docx
- Use consistent formatting throughout
- Include full company names
- List dates clearly (MM/YYYY format)

### ❌ DON'T:
- Use unusual fonts or graphics
- Use headers/footers with important info
- Use tables or columns
- Use images, logos, or fancy formatting
- Use abbreviations without full names first
- Use two-column layouts
- Exceed 1-2 pages for entry level, 2-3 for senior

---

## Customizing CV Per Job Application

### Template for Each Application:

```markdown
1. Review job posting carefully
2. Note all important keywords and skills
3. Create new copy: CV_[CompanyName].docx
4. Reorder experience by relevance
5. Add specific metrics matching job requirements
6. Include keywords from job posting
7. Customize headline/summary
8. Save and submit
```

### Example Keywords to Add:

**For Full Stack Developer role, add:**
- Specific technologies mentioned (React, Node.js, etc.)
- Industry-specific terms ("scalable", "microservices", "cloud")
- Company-specific skills
- Methodologies mentioned (Agile, Scrum)

---

## PDF Optimization

### Creating Professional PDF:

1. **Quality Settings:**
   - Use high-quality conversion
   - Set to 300 DPI minimum
   - Use good margins (0.5-1 inch)

2. **File Size:**
   - Keep under 5MB
   - Compress images if needed
   - Optimize PDF using free tool: https://smallpdf.com

3. **Naming Convention:**
   - `Mikhael_CV.pdf` (generic)
   - `Mikhael_CV_FullStack.pdf` (role-specific)
   - `Mikhael_CV_2025.pdf` (dated)

---

## LinkedIn CV Upload

### Adding CV to LinkedIn Profile:

1. Go to LinkedIn Profile
2. Click on your name → "Open to work" section
3. In About section, mention:
   ```
   📥 Download my full CV: [link to your PDF]
   ```
4. Add link in your profile URL section

### Format for LinkedIn:
- Use PDF format
- Keep it 1-2 pages
- Include contact information clearly
- Add GitHub and portfolio links

---

## Version Control with Git

### Track CV Changes:

```bash
# Initialize Git if not already done
git init

# Stage CV file
git add CV_Professional_Template.md

# Commit with message
git commit -m "Update CV with new project experience"

# Push to GitHub
git push origin main
```

### Version History Example:
```
v1.0 - Initial CV
v1.1 - Added 3 new projects
v1.2 - Updated skills section
v1.3 - Added GitHub links
v2.0 - Complete portfolio integration
```

---

## Maintaining Multiple CV Versions

### Organized File Structure:
```
cv_portofolio/
├── CV_Professional_Template.md      (Master)
├── cv-versions/
│   ├── Mikhael_CV.pdf               (Main PDF)
│   ├── Mikhael_CV.docx              (Main Word)
│   ├── Mikhael_CV_FullStack.pdf     (Role-specific)
│   ├── Mikhael_CV_DataScience.pdf   (Role-specific)
│   └── Mikhael_CV_text.txt          (ATS-friendly)
└── archive/
    ├── Mikhael_CV_2024.pdf          (Old versions)
    └── Mikhael_CV_2023.pdf
```

---

## Email CV Submission Best Practices

### Filename:
```
❌ Bad: resume.pdf, cv.doc, final_FINAL_v3.pdf
✅ Good: Mikhael_CV.pdf, Mikhael_CV_2025.pdf
```

### Email Format:
```
Subject: CV Submission - [Position Title] - Mikhael

Dear Hiring Manager,

Please find attached my CV for the [Position Title] role. 
I'm excited about the opportunity to contribute to [Company Name].

Best regards,
Mikhael

Email: your.email@example.com
Phone: +1 (XXX) XXX-XXXX
LinkedIn: [LinkedIn URL]
Portfolio: [Portfolio URL]
```

---

## Tracking CV Performance

### Create Tracking Spreadsheet:

| Date | Company | Position | CV Version | Status | Notes |
|------|---------|----------|-----------|--------|-------|
| 12/22 | TechCorp | Full Stack Dev | CV_FullStack.pdf | Submitted | Applied via LinkedIn |
| 12/22 | StartupX | Senior Dev | CV_2025.pdf | Interview | Phone screen passed |
| 12/23 | BigTech | React Dev | CV_2025.pdf | Submitted | Waiting response |

### Metrics to Track:
- CV submission rate (responses/submissions)
- Average time to first response
- Most effective CV version
- Common feedback themes

---

## Tools for CV Management

### Free Tools:
- **Google Drive:** Store and share CV
- **GitHub:** Version control for CV content
- **Canva:** Design improvements
- **Grammarly:** Grammar checking
- **PDF Editor:** Edit PDFs online (ilovepdf.com)

### Paid Tools (Optional):
- **Resume.com:** Template and optimization
- **TopResume:** Professional review service
- **Jobscan:** ATS optimization checker

---

## Annual CV Update Checklist

**Every 3 Months:**
- [ ] Add new projects/experience
- [ ] Update skills section
- [ ] Review and fix any errors
- [ ] Update dates and metrics

**Every 6 Months:**
- [ ] Full review for relevance
- [ ] Update summary/headline
- [ ] Remove dated experience
- [ ] Add new certifications

**Yearly:**
- [ ] Complete overhaul
- [ ] Update contact info
- [ ] Review all links
- [ ] Update portfolio
- [ ] Create new version

---

## Quick Convert Commands

### If you have Pandoc installed:

```bash
# Convert markdown to all formats
pandoc CV_Professional_Template.md -o CV_Output.pdf
pandoc CV_Professional_Template.md -o CV_Output.docx
pandoc CV_Professional_Template.md -o CV_Output.html
pandoc CV_Professional_Template.md -o CV_Output.txt
```

---

**Last Updated:** December 22, 2025
