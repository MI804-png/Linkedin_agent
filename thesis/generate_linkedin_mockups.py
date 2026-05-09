"""
Generate LinkedIn Easy Apply workflow mockups matching the real screenshots.
"""
from PIL import Image, ImageDraw, ImageFont
import os

OUT = r'd:\cv_portofolio\thesis\screenshots'
os.makedirs(OUT, exist_ok=True)

# LinkedIn colours
LI_BLUE   = (10, 102, 194)
LI_BLUE_H = (9, 90, 172)     # hover
LI_GREEN  = (5, 118, 66)
LI_BG     = (243, 242, 239)
LI_WHITE  = (255, 255, 255)
LI_BORDER = (224, 223, 220)
LI_DARK   = (0, 0, 0)
LI_GRAY   = (102, 102, 102)
LI_LGRAY  = (230, 230, 230)
LI_PBGRAY = (240, 240, 240)
LI_RED    = (188, 0, 0)
LI_PROGBG = (204, 204, 204)

W, H = 1280, 900

def try_font(size=14, bold=False):
    for path in (["C:/Windows/Fonts/arialbd.ttf"] if bold else []) + [
        "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/calibri.ttf"]:
        try: return ImageFont.truetype(path, size)
        except: pass
    return ImageFont.load_default()

def txt(d, x, y, text, size=14, bold=False, color=LI_DARK, anchor=None):
    fnt = try_font(size, bold)
    if anchor == 'center':
        bb = d.textbbox((0, 0), text, font=fnt)
        x = x - (bb[2] - bb[0]) // 2
    d.text((x, y), text, fill=color, font=fnt)

def li_navbar(d, W):
    """LinkedIn top navbar."""
    d.rectangle([0, 0, W, 52], fill=LI_WHITE)
    d.line([0, 52, W, 52], fill=LI_BORDER, width=1)
    # LinkedIn logo (blue square)
    d.rounded_rectangle([16, 10, 48, 42], radius=4, fill=LI_BLUE)
    txt(d, 22, 15, "in", size=20, bold=True, color=LI_WHITE)
    # Search bar
    d.rounded_rectangle([58, 12, 280, 40], radius=4, fill=LI_PBGRAY, outline=LI_BORDER, width=1)
    txt(d, 68, 20, "Search", size=13, color=LI_GRAY)
    # Nav icons text
    for i, (icon, label) in enumerate([("🏠","Home"),("👥","My Network"),("💼","Jobs"),
                                        ("💬","Messaging"),("🔔","Notifications"),("👤","Me")]):
        nx = 360 + i * 120
        txt(d, nx, 8, icon, size=16)
        txt(d, nx - 2, 30, label, size=11, color=LI_GRAY)

def modal_shell(d, mx, my, mw, mh):
    """White modal with shadow."""
    d.rectangle([mx+4, my+4, mx+mw+4, my+mh+4], fill=(180,180,180))
    d.rectangle([mx, my, mx+mw, my+mh], fill=LI_WHITE, outline=LI_BORDER, width=1)

def progress_bar(d, mx, my, mw, pct, label=""):
    """LinkedIn apply progress bar."""
    bar_y = my + 48
    d.rectangle([mx+1, bar_y, mx+mw-1, bar_y+4], fill=LI_PROGBG)
    filled = int((mw - 2) * pct / 100)
    if filled > 0:
        d.rectangle([mx+1, bar_y, mx+1+filled, bar_y+4], fill=LI_BLUE)
    if label:
        txt(d, mx+mw-50, bar_y-18, label, size=12, color=LI_GRAY)

def li_field(d, x, y, w, label, value="", required=False, h=40):
    """Form field with label."""
    req = " *" if required else ""
    txt(d, x, y, label+req, size=13, color=LI_DARK)
    fy = y + 22
    d.rounded_rectangle([x, fy, x+w, fy+h], radius=3, fill=LI_WHITE,
                        outline=LI_BLUE if value else LI_LGRAY, width=2 if value else 1)
    if value:
        txt(d, x+10, fy+(h-16)//2, value, size=13, color=LI_DARK)
    return fy + h + 8

def li_btn(d, x, y, w, h, label, color=LI_BLUE, textcolor=LI_WHITE, outline=False):
    if outline:
        d.rounded_rectangle([x, y, x+w, y+h], radius=20, fill=LI_WHITE, outline=color, width=2)
        fnt = try_font(14, bold=True)
        bb = d.textbbox((0,0), label, font=fnt)
        d.text((x+(w-(bb[2]-bb[0]))//2, y+(h-(bb[3]-bb[1]))//2-1), label, fill=color, font=fnt)
    else:
        d.rounded_rectangle([x, y, x+w, y+h], radius=20, fill=color)
        fnt = try_font(14, bold=True)
        bb = d.textbbox((0,0), label, font=fnt)
        d.text((x+(w-(bb[2]-bb[0]))//2, y+(h-(bb[3]-bb[1]))//2-1), label, fill=textcolor, font=fnt)

def radio(d, x, y, checked=False):
    d.ellipse([x, y, x+18, y+18], fill=LI_WHITE, outline=LI_BLUE if checked else LI_LGRAY, width=2)
    if checked:
        d.ellipse([x+4, y+4, x+14, y+14], fill=LI_BLUE)

# ── FIGURE A: Job Search Results ─────────────────────────────────────────────
img = Image.new('RGB', (W, H), LI_BG)
d = ImageDraw.Draw(img)
li_navbar(d, W)

# Search bar with filters
d.rectangle([0, 53, W, 100], fill=LI_WHITE)
d.line([0, 100, W, 100], fill=LI_BORDER, width=1)
d.rounded_rectangle([20, 62, 200, 90], radius=4, fill=LI_PBGRAY, outline=LI_BORDER)
txt(d, 30, 70, "Full Stack Developer", size=13)
d.rounded_rectangle([210, 62, 340, 90], radius=4, fill=LI_PBGRAY, outline=LI_BORDER)
txt(d, 220, 70, "Hungary", size=13)
d.rounded_rectangle([350, 62, 420, 90], radius=20, fill=LI_BLUE)
txt(d, 373, 70, "Search", size=13, color=LI_WHITE)
# filter pills
for i, (lbl, active) in enumerate([("Jobs",""), ("Past week",""), ("Easy Apply","active"),
                                     ("Experience level",""), ("Remote","")]):
    px = 440 + i * 130
    if active:
        d.rounded_rectangle([px, 62, px+len(lbl)*8+16, 90], radius=14, fill=LI_BLUE)
        txt(d, px+8, 70, lbl, size=12, color=LI_WHITE)
    else:
        d.rounded_rectangle([px, 62, px+len(lbl)*8+16, 90], radius=14, fill=LI_WHITE, outline=LI_LGRAY)
        txt(d, px+8, 70, lbl, size=12, color=LI_DARK)

# Left panel: job list
d.rectangle([0, 101, 420, H], fill=LI_WHITE)
d.line([420, 101, 420, H], fill=LI_BORDER, width=1)
txt(d, 20, 112, "Full Stack Developer in Hungary", size=16, bold=True)
txt(d, 20, 136, "100+ results", size=12, color=LI_GRAY)

jobs = [
    ("Full Stack Engineer (Node.JS) ✓", "Q1 Technologies, Inc.", "Budapest, Hungary (On-site)", True, True),
    ("Player Management - Backend Software Engineer ✓", "Betsson Group", "Budapest, Hungary (On-site)", True, False),
    ("Full Stack Developer ✓", "MelonApp toborzás", "Székesfehérvár, Hungary (Remote)", False, False),
    ("Power Platform Engineer Configuration & Governance", "Dexian Europe", "Budapest Metropolitan Area (On-site)", False, False),
]
for i, (title, company, loc, viewed, highlighted) in enumerate(jobs):
    jy = 162 + i * 112
    bg = (232, 243, 255) if highlighted else LI_WHITE
    d.rectangle([0, jy, 418, jy+108], fill=bg)
    d.line([20, jy+108, 400, jy+108], fill=LI_BORDER, width=1)
    # company logo placeholder
    d.rounded_rectangle([20, jy+10, 60, jy+50], radius=4, fill=LI_LGRAY)
    txt(d, 28, jy+22, "Q" if "Q1" in company else company[0], size=18, bold=True, color=LI_GRAY)
    txt(d, 70, jy+10, title[:42], size=13, bold=True, color=LI_BLUE if not highlighted else LI_BLUE)
    txt(d, 70, jy+30, company, size=12, color=LI_DARK)
    txt(d, 70, jy+48, loc, size=12, color=LI_GRAY)
    if viewed:
        txt(d, 70, jy+68, "Viewed · Promoted · ", size=11, color=LI_GRAY)
    else:
        txt(d, 70, jy+68, "Promoted · ", size=11, color=LI_GRAY)
    txt(d, 200 if viewed else 140, jy+66, "Easy Apply", size=11, color=LI_BLUE)

# Right panel: job detail
d.rectangle([422, 101, W, H], fill=LI_WHITE)
# Company logo
d.rounded_rectangle([440, 115, 500, 175], radius=4, fill=(230, 245, 230))
txt(d, 452, 135, "Q1", size=22, bold=True, color=(0,100,0))
txt(d, 512, 115, "Q1 Technologies, Inc.", size=14, bold=True)
txt(d, 440, 185, "Full Stack Engineer (Node.JS)  ✓", size=20, bold=True)
txt(d, 440, 215, "Budapest, Hungary  ·  1 hour ago  ·  5 applicants", size=13, color=LI_GRAY)
txt(d, 440, 238, "Promoted by hirer  ·  ", size=13, color=LI_GRAY)
txt(d, 583, 238, "Company review time is typically 1 week", size=13, color=LI_GREEN)
# badges
for bi, badge in enumerate(["On-site", "Contract"]):
    bx = 440 + bi * 120
    d.rounded_rectangle([bx, 260, bx+100, 284], radius=12, fill=LI_WHITE, outline=LI_LGRAY, width=2)
    txt(d, bx+8, 265, f"✓ {badge}", size=12, color=LI_DARK)
# buttons
li_btn(d, 440, 296, 160, 44, "in  Easy Apply")
li_btn(d, 612, 296, 100, 44, "Save", color=LI_WHITE, textcolor=LI_BLUE, outline=True)
# premium card
d.rounded_rectangle([440, 356, W-20, 440], radius=6, fill=(255,250,240), outline=(200,170,100))
txt(d, 456, 368, "See how you compare to 5 applicants", size=14, bold=True)
txt(d, 456, 392, "Access exclusive applicant insights, see jobs where you have", size=12, color=LI_GRAY)
txt(d, 456, 410, "the highest chance of hearing back, and more.", size=12, color=LI_GRAY)
txt(d, 456, 428, "🏷️  Try Premium for Ft 0", size=13, color=(180,130,0))

img.save(f'{OUT}/fig_li_jobs_search.png')
print('fig_li_jobs_search saved')

# ── FIGURE B: Easy Apply — Step 1: Contact Info (0%) ─────────────────────────
img = Image.new('RGB', (W, H), LI_BG)
d = ImageDraw.Draw(img)
li_navbar(d, W)
# dimmed background
d.rectangle([0, 53, W, H], fill=(0,0,0,80))
img2 = img.convert('RGBA')
overlay = Image.new('RGBA', img2.size, (0, 0, 0, 100))
img = Image.alpha_composite(img2, overlay).convert('RGB')
d = ImageDraw.Draw(img)
li_navbar(d, W)

# Job page in background (faint)
d.rectangle([62, 115, 740, 580], fill=LI_WHITE)

MX, MY, MW, MH = 230, 80, 820, 730
modal_shell(d, MX, MY, MW, MH)
# Modal header
txt(d, MX+20, MY+12, "Apply to Q1 Technologies, Inc.", size=18, bold=True)
d.line([MX, MY+44, MX+MW, MY+44], fill=LI_BORDER, width=1)
# × close
txt(d, MX+MW-32, MY+10, "✕", size=18, color=LI_GRAY)
# Progress bar 0%
progress_bar(d, MX, MY, MW, 0, "0%")
# Section heading
txt(d, MX+20, MY+65, "Contact info", size=16, bold=True)
# Profile row
d.ellipse([MX+20, MY+95, MX+80, MY+155], fill=LI_BLUE)
txt(d, MX+34, MY+112, "MN", size=22, bold=True, color=LI_WHITE)
txt(d, MX+95, MY+95, "MiKhael Nabil Salama Rezk", size=15, bold=True)
txt(d, MX+95, MY+118, "Graduated from Don Bosco Institute of Technology (D.B.I.T)", size=12, color=LI_GRAY)
txt(d, MX+95, MY+138, "Kecskemét, Bács-Kiskun, Hungary", size=12, color=LI_GRAY)
d.line([MX+20, MY+165, MX+MW-20, MY+165], fill=LI_BORDER, width=1)
# Fields
y = MY + 185
y = li_field(d, MX+20, y, MW-40, "Email address", "mikhael.nabil.salama.rezk@gmail.com", required=True)
y += 5
y = li_field(d, MX+20, y, (MW-60)//2, "Phone country code", "Hungary (+36)", required=True)
y += 5
li_field(d, MX+20, y, (MW-60)//2, "Mobile phone number", "706355765", required=True)
y += 70
txt(d, MX+20, y+10, "Submitting this application won't change your LinkedIn profile.", size=12, color=LI_GRAY)
txt(d, MX+20, y+30, "Application powered by LinkedIn.  ", size=12, color=LI_GRAY)
txt(d, MX+280, y+30, "Help Center", size=12, color=LI_BLUE)
# Buttons
d.line([MX, MY+MH-70, MX+MW, MY+MH-70], fill=LI_BORDER, width=1)
li_btn(d, MX+MW-120, MY+MH-58, 100, 40, "Next")

img.save(f'{OUT}/fig_li_apply_step1_contact.png')
print('fig_li_apply_step1_contact saved')

# ── FIGURE C: Easy Apply — Step 2: Resume ────────────────────────────────────
img = Image.new('RGB', (W, H), LI_BG)
d = ImageDraw.Draw(img)
li_navbar(d, W)
d.rectangle([62, 115, 740, 580], fill=LI_WHITE)
modal_shell(d, MX, MY, MW, MH)
txt(d, MX+20, MY+12, "Apply to Q1 Technologies, Inc.", size=18, bold=True)
d.line([MX, MY+44, MX+MW, MY+44], fill=LI_BORDER, width=1)
txt(d, MX+MW-32, MY+10, "✕", size=18, color=LI_GRAY)
progress_bar(d, MX, MY, MW, 33, "33%")
txt(d, MX+20, MY+65, "Resume", size=16, bold=True)
txt(d, MX+20, MY+93, "Be sure to include an updated resume", size=13, color=LI_GRAY)
# Resume list
resumes = [
    ("1_d46b57b682bb47d3ab26dcff07509415.pdf", "5/8/2026", False),
    ("1_d46b57b682bb47d3ab26dcff07509415.pdf", "5/7/2026", False),
    ("Mikhael_CV.pdf",                          "5/7/2026", True),
    ("1_d46b57b682bb47d3ab26dcff07509415.pdf", "5/7/2026", False),
    ("Mikhael_CV.pdf",                          "5/7/2026", False),
]
for ri, (fname, date, selected) in enumerate(resumes):
    ry = MY + 120 + ri * 80
    border_color = LI_BLUE if selected else LI_LGRAY
    bw = 3 if selected else 1
    d.rounded_rectangle([MX+20, ry, MX+MW-20, ry+68], radius=6,
                        fill=LI_WHITE, outline=border_color, width=bw)
    # PDF icon
    d.rounded_rectangle([MX+34, ry+8, MX+72, ry+60], radius=4, fill=(188, 0, 0))
    txt(d, MX+38, ry+24, "PDF", size=13, bold=True, color=LI_WHITE)
    txt(d, MX+82, ry+14, fname, size=13, color=LI_DARK)
    txt(d, MX+82, ry+36, f"324 KB  ·  Last used on {date}", size=12, color=LI_GRAY)
    # download icon
    txt(d, MX+MW-90, ry+20, "↓", size=18, color=LI_GRAY)
    # radio
    radio(d, MX+MW-48, ry+24, checked=selected)

# Upload button
li_btn(d, MX+20, MY+530, 160, 40, "Upload resume", color=LI_WHITE, textcolor=LI_BLUE, outline=True)
d.line([MX, MY+MH-70, MX+MW, MY+MH-70], fill=LI_BORDER, width=1)
li_btn(d, MX+MW-240, MY+MH-58, 110, 40, "Back", color=LI_WHITE, textcolor=LI_DARK, outline=True)
li_btn(d, MX+MW-120, MY+MH-58, 100, 40, "Next")

img.save(f'{OUT}/fig_li_apply_step2_resume.png')
print('fig_li_apply_step2_resume saved')

# ── FIGURE D: Easy Apply — Step 3: Additional Questions (67%) ────────────────
img = Image.new('RGB', (W, H), LI_BG)
d = ImageDraw.Draw(img)
li_navbar(d, W)
d.rectangle([62, 115, 740, 580], fill=LI_WHITE)
modal_shell(d, MX, MY, MW, MH)
txt(d, MX+20, MY+12, "Apply to Q1 Technologies, Inc.", size=18, bold=True)
d.line([MX, MY+44, MX+MW, MY+44], fill=LI_BORDER, width=1)
txt(d, MX+MW-32, MY+10, "✕", size=18, color=LI_GRAY)
progress_bar(d, MX, MY, MW, 67, "67%")
txt(d, MX+20, MY+65, "Additional Questions", size=16, bold=True)

y = MY + 100
questions = [
    ("How many years of work experience do you have with Node.js?", "5"),
    ("How many years of work experience do you have with REST APIs?", "3"),
    ("How many years of work experience do you have with SQL?", "4"),
]
for q, ans in questions:
    txt(d, MX+20, y, q + " *", size=13)
    y += 24
    d.rounded_rectangle([MX+20, y, MX+MW-20, y+40], radius=3,
                        fill=LI_WHITE, outline=LI_BLUE, width=2)
    txt(d, MX+32, y+11, ans, size=14)
    y += 55

# Work authorization
txt(d, MX+20, y, "Are you legally authorized to work in Hungary? *", size=13)
y += 28
radio(d, MX+20, y, checked=True)
txt(d, MX+46, y+1, "Yes", size=13)
y += 30
radio(d, MX+20, y, checked=False)
txt(d, MX+46, y+1, "No", size=13)
y += 40

# Onsite question
txt(d, MX+20, y, "Are you comfortable working in an onsite setting? *", size=13)
y += 28
radio(d, MX+20, y, checked=False)
txt(d, MX+46, y+1, "Yes", size=13)
y += 30
radio(d, MX+20, y, checked=True)
txt(d, MX+46, y+1, "No", size=13)

d.line([MX, MY+MH-70, MX+MW, MY+MH-70], fill=LI_BORDER, width=1)
li_btn(d, MX+MW-240, MY+MH-58, 110, 40, "Back", color=LI_WHITE, textcolor=LI_DARK, outline=True)
li_btn(d, MX+MW-120, MY+MH-58, 100, 40, "Next")

img.save(f'{OUT}/fig_li_apply_step3_questions.png')
print('fig_li_apply_step3_questions saved')

# ── FIGURE E: Easy Apply — Step 4: Review (100%) ─────────────────────────────
img = Image.new('RGB', (W, H), LI_BG)
d = ImageDraw.Draw(img)
li_navbar(d, W)
d.rectangle([62, 115, 740, 580], fill=LI_WHITE)
modal_shell(d, MX, MY, MW, MH)
txt(d, MX+20, MY+12, "Apply to Q1 Technologies, Inc.", size=18, bold=True)
d.line([MX, MY+44, MX+MW, MY+44], fill=LI_BORDER, width=1)
txt(d, MX+MW-32, MY+10, "✕", size=18, color=LI_GRAY)
progress_bar(d, MX, MY, MW, 100, "100%")
txt(d, MX+20, MY+65, "Review your application", size=16, bold=True)
txt(d, MX+20, MY+90, "The employer will also receive a copy of your profile.", size=13, color=LI_GRAY)
d.line([MX+20, MY+115, MX+MW-20, MY+115], fill=LI_BORDER, width=1)
# Contact info section
txt(d, MX+20, MY+126, "Contact info", size=14, bold=True)
txt(d, MX+MW-60, MY+126, "Edit", size=13, color=LI_BLUE)
d.ellipse([MX+20, MY+150, MX+70, MY+200], fill=LI_BLUE)
txt(d, MX+30, MY+165, "MN", size=18, bold=True, color=LI_WHITE)
txt(d, MX+82, MY+150, "MiKhael Nabil Salama Rezk", size=14, bold=True)
txt(d, MX+82, MY+170, "Graduated from Don Bosco Institute of Technology (D.B.I.T)", size=12, color=LI_GRAY)
txt(d, MX+82, MY+188, "Kecskemét, Bács-Kiskun, Hungary", size=12, color=LI_GRAY)
txt(d, MX+20, MY+215, "Email address *", size=12, color=LI_GRAY)
txt(d, MX+20, MY+233, "mikha.nabil13@gmail.com", size=13)
txt(d, MX+20, MY+260, "Phone country code *", size=12, color=LI_GRAY)
txt(d, MX+20, MY+278, "Hungary (+36)", size=13)
txt(d, MX+20, MY+305, "Mobile phone number *", size=12, color=LI_GRAY)
txt(d, MX+20, MY+323, "706355765", size=13)
d.line([MX+20, MY+350, MX+MW-20, MY+350], fill=LI_BORDER, width=1)
# Resume section
txt(d, MX+20, MY+362, "Resume", size=14, bold=True)
txt(d, MX+MW-60, MY+362, "Edit", size=13, color=LI_BLUE)
txt(d, MX+20, MY+388, "Be sure to include an updated resume", size=12, color=LI_GRAY)
d.rounded_rectangle([MX+20, MY+410, MX+74, MY+462], radius=4, fill=LI_RED)
txt(d, MX+28, MY+426, "PDF", size=14, bold=True, color=LI_WHITE)
txt(d, MX+84, MY+416, "Mikhael_CV.pdf", size=14)
txt(d, MX+84, MY+438, "324 KB  ·  Last used on 5/8/2026", size=12, color=LI_GRAY)

d.line([MX, MY+MH-70, MX+MW, MY+MH-70], fill=LI_BORDER, width=1)
li_btn(d, MX+MW-240, MY+MH-58, 110, 40, "Back", color=LI_WHITE, textcolor=LI_DARK, outline=True)
li_btn(d, MX+MW-120, MY+MH-58, 100, 40, "Submit application", color=LI_BLUE)

img.save(f'{OUT}/fig_li_apply_step4_review.png')
print('fig_li_apply_step4_review saved')

# ── FIGURE F: Application Submitted ──────────────────────────────────────────
img = Image.new('RGB', (W, H), LI_BG)
d = ImageDraw.Draw(img)
li_navbar(d, W)
d.rectangle([62, 115, 740, H], fill=LI_WHITE)
# Job detail (background)
d.rounded_rectangle([62, 115, 740, 260], radius=6, fill=LI_WHITE, outline=LI_BORDER)
d.rounded_rectangle([76, 130, 120, 174], radius=4, fill=(230,245,230))
txt(d, 88, 148, "Q1", size=16, bold=True, color=(0,100,0))
txt(d, 132, 130, "Q1 Technologies, Inc.", size=13, bold=True)
txt(d, 76, 182, "Full Stack Engineer (Node.JS)  ✓", size=18, bold=True)
txt(d, 76, 210, "Budapest, Hungary  ·  1 hour ago  ·  5 applicants", size=12, color=LI_GRAY)
txt(d, 76, 230, "Promoted by hirer  ·  ", size=12, color=LI_GRAY)
txt(d, 200, 230, "Company review time is typically 1 week", size=12, color=LI_GREEN)
for bi, badge in enumerate(["On-site", "Contract"]):
    d.rounded_rectangle([76+bi*115, 252, 76+bi*115+100, 276], radius=12, fill=LI_WHITE, outline=LI_LGRAY)
    txt(d, 84+bi*115, 257, f"✓ {badge}", size=12)

# Application status card
d.rounded_rectangle([62, 290, 740, 400], radius=6, fill=LI_WHITE, outline=LI_BORDER)
txt(d, 82, 306, "Application status", size=15, bold=True)
d.line([82, 330, 720, 330], fill=LI_BORDER, width=1)
d.ellipse([82, 345, 98, 361], fill=LI_LGRAY, outline=LI_LGRAY)
txt(d, 108, 346, "Application submitted", size=14, bold=True)
txt(d, 108, 368, "now", size=12, color=LI_GRAY)
txt(d, 108, 386, "View resume", size=13, color=LI_BLUE)

# People you can reach
d.rounded_rectangle([62, 416, 740, 540], radius=6, fill=LI_WHITE, outline=LI_BORDER)
txt(d, 82, 432, "People you can reach out to", size=15, bold=True)
txt(d, 82, 460, "Meet the hiring team", size=13, color=LI_GRAY)
d.ellipse([82, 484, 122, 524], fill=(200,200,200))
txt(d, 130, 488, "S M A ASHRAF  · 3rd", size=13, bold=True)
txt(d, 130, 510, "SAP SuccessFactors Consultant (EC, RCM) | HR Analyst | Technology Recruiter", size=11, color=LI_GRAY)
li_btn(d, 620, 488, 100, 36, "Message", color=LI_WHITE, textcolor=LI_DARK, outline=True)

img.save(f'{OUT}/fig_li_apply_submitted.png')
print('fig_li_apply_submitted saved')

# ── FIGURE G: LinkedIn Notifications ─────────────────────────────────────────
img = Image.new('RGB', (W, H), LI_BG)
d = ImageDraw.Draw(img)
li_navbar(d, W)
d.rectangle([0, 53, W, H], fill=LI_BG)

# Left panel
d.rectangle([20, 70, 270, 340], fill=LI_WHITE, outline=LI_BORDER)
# Profile area
d.rectangle([20, 70, 270, 180], fill=(180,200,230))
d.ellipse([95, 130, 195, 230], fill=LI_WHITE, outline=LI_BORDER)
d.ellipse([105, 140, 185, 220], fill=(100,120,160))
txt(d, 128, 165, "MN", size=22, bold=True, color=LI_WHITE)
txt(d, 55, 240, "MiKhael Nabil Sala...", size=13, bold=True)
txt(d, 35, 262, "Graduated from Don Bosco Institute", size=11, color=LI_GRAY)
txt(d, 55, 278, "of Technology (D.B.I.T)", size=11, color=LI_GRAY)
txt(d, 55, 296, "Kecskemét, Bács-Kiskun", size=11, color=LI_GRAY)
txt(d, 38, 315, "🏫  John Von Neumann University", size=11)
d.rectangle([20, 348, 270, 420], fill=LI_WHITE, outline=LI_BORDER)
txt(d, 36, 362, "Manage your notifications", size=13, bold=True)
txt(d, 36, 386, "View settings", size=13, color=LI_BLUE)

# Filter tabs
d.rectangle([292, 70, W-20, 108], fill=LI_WHITE, outline=LI_BORDER)
for i, (tab, active) in enumerate([("All","active"),("Jobs",""),("My posts",""),("Mentions","")]):
    tx = 305 + i * 110
    if active:
        d.rounded_rectangle([tx-4, 76, tx+len(tab)*10, 104], radius=14, fill=LI_BLUE)
        txt(d, tx, 82, tab, size=13, color=LI_WHITE)
    else:
        d.rounded_rectangle([tx-4, 76, tx+len(tab)*10, 104], radius=14, fill=LI_WHITE, outline=LI_LGRAY)
        txt(d, tx, 82, tab, size=13, color=LI_DARK)

# Notifications
notifs = [
    ("Frontend Developer: new opportunities in Lastra a Signa.", "2m", True, "View jobs"),
    ("New opportunities in Hungary.", "1h", True, "View jobs"),
    ("1 person viewed your profile: Stay anonymous and see who's viewed your profile with Premium.", "1h", False, "Try Premium for Ft 0"),
    ("Your application was viewed for Node.js Developer at Q1 Technologies, Inc.", "1h", False, None),
    ("Maichel Sameh commented on Mohamed Hammad's post.", "2h", False, None),
]
for ni, (msg, time_ago, highlighted, btn) in enumerate(notifs):
    ny = 116 + ni * 100
    bg = (236, 245, 255) if highlighted else LI_WHITE
    d.rectangle([292, ny, W-20, ny+96], fill=bg, outline=LI_BORDER)
    if highlighted:
        d.ellipse([296, ny+36, 310, ny+50], fill=LI_BLUE)
    # icon
    d.rounded_rectangle([306, ny+8, 346, ny+48], radius=4, fill=LI_LGRAY)
    txt(d, 316, ny+18, "in", size=16, bold=True, color=LI_BLUE)
    txt(d, 356, ny+12, msg[:80], size=13)
    if len(msg) > 80:
        txt(d, 356, ny+30, msg[80:], size=13)
    txt(d, W-60, ny+12, time_ago, size=12, color=LI_GRAY)
    if btn:
        li_btn(d, 356, ny+58, 120, 30, btn, color=LI_WHITE, textcolor=LI_BLUE, outline=True)

img.save(f'{OUT}/fig_li_notifications.png')
print('fig_li_notifications saved')

print('\nAll LinkedIn mockups saved!')
