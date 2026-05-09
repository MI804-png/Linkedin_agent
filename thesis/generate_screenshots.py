"""
Generate professional-looking mockup screenshots for the AutoApply thesis.
Uses PIL to render accurate UI representations of each page.
"""
from PIL import Image, ImageDraw, ImageFont
import os
import math

OUT = 'd:/cv_portofolio/thesis/screenshots'
os.makedirs(OUT, exist_ok=True)

W, H = 1100, 700
BLUE    = (13, 110, 253)
LBLUE   = (225, 237, 255)
WHITE   = (255, 255, 255)
LGRAY   = (248, 249, 250)
MGRAY   = (206, 212, 218)
DGRAY   = (73, 80, 87)
BLACK   = (33, 37, 41)
GREEN   = (25, 135, 84)
YELLOW  = (255, 243, 205)
BYELLOW = (255, 193, 7)
RED     = (220, 53, 69)
LGREEN  = (209, 231, 221)

def tint(color, strength=0.82):
    """Return a light pastel tint of an RGB color for high-contrast text."""
    return tuple(int(c + (255 - c) * strength) for c in color)

def try_font(size=14, bold=False):
    """Try to load a font, fall back to default."""
    candidates_bold = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    for path in (candidates_bold if bold else candidates):
        try:
            return ImageFont.truetype(path, size)
        except:
            pass
    return ImageFont.load_default()

def navbar(draw, title="AutoApply", W=1100):
    draw.rectangle([0, 0, W, 56], fill=BLUE)
    fnt = try_font(20, bold=True)
    draw.text((20, 16), f"🤖  {title}", fill=WHITE, font=fnt)
    # hamburger
    for y in [20, 28, 36]:
        draw.rectangle([W-50, y, W-20, y+3], fill=WHITE)

def footer(draw, W=1100, H=700):
    draw.rectangle([0, H-40, W, H], fill=LGRAY)
    draw.line([0, H-40, W, H-40], fill=MGRAY, width=1)
    fnt = try_font(11)
    draw.text((W//2 - 200, H-26), "AutoApply © 2026 — Automated LinkedIn Job Applications",
              fill=DGRAY, font=fnt)

def card(draw, x, y, w, h, radius=8):
    draw.rounded_rectangle([x, y, x+w, y+h], radius=radius, fill=WHITE,
                            outline=MGRAY, width=1)

def button(draw, x, y, w, h, text, color=BLUE, textcolor=WHITE, radius=6):
    draw.rounded_rectangle([x, y, x+w, y+h], radius=radius, fill=color)
    fnt = try_font(14, bold=True)
    bbox = draw.textbbox((0,0), text, font=fnt)
    tw = bbox[2]-bbox[0]
    th = bbox[3]-bbox[1]
    draw.text((x+(w-tw)//2, y+(h-th)//2-1), text, fill=textcolor, font=fnt)

def field(draw, x, y, w, h=40, placeholder="", value=""):
    draw.rounded_rectangle([x, y, x+w, y+h], radius=5, fill=WHITE, outline=BLUE if value else MGRAY, width=2 if value else 1)
    fnt = try_font(13)
    txt = value if value else placeholder
    col = BLACK if value else MGRAY
    draw.text((x+12, y+(h-16)//2), txt, fill=col, font=fnt)

def label(draw, x, y, text, bold=False, size=13, color=BLACK):
    fnt = try_font(size, bold=bold)
    draw.text((x, y), text, fill=color, font=fnt)

def section_header(draw, x, y, w, text, color=BLUE):
    draw.rounded_rectangle([x, y, x+w, y+42], radius=6, fill=color)
    fnt = try_font(14, bold=True)
    draw.text((x+16, y+12), text, fill=WHITE, font=fnt)

def alert(draw, x, y, w, text, style='info'):
    colors = {'info': (YELLOW, (102,77,3)), 'success': (LGREEN, (13,110,53)), 'danger': ((248,215,218),(114,28,36))}
    bg, fg = colors.get(style, (YELLOW,(0,0,0)))
    draw.rounded_rectangle([x, y, x+w, y+48], radius=6, fill=bg, outline=fg, width=1)
    fnt = try_font(13)
    draw.text((x+16, y+15), text, fill=fg, font=fnt)

# ──────────────────────────────────────────────────
# FIG 1: Login page
# ──────────────────────────────────────────────────
img = Image.new('RGB', (W, H), LGRAY)
d = ImageDraw.Draw(img)
navbar(d)
footer(d)
# card
card(d, W//2-220, 90, 440, 360)
# heading
label(d, W//2-160, 110, "➔  Log In", bold=True, size=22)
# email
label(d, W//2-200, 165, "Email address", bold=False, size=13)
field(d, W//2-200, 185, 400, placeholder="you@example.com")
label(d, W//2-200, 240, "Password", bold=False, size=13)
field(d, W//2-200, 260, 400, placeholder="Password")
button(d, W//2-200, 315, 400, 44, "➔  Log In")
d.line([W//2-200, 375, W//2+200, 375], fill=MGRAY, width=1)
label(d, W//2-60, 385, "No account yet?  Create one", size=13, color=BLUE)
img.save(f'{OUT}/fig01_login.png')
print('fig01_login saved')

# ──────────────────────────────────────────────────
# FIG 2: Register page
# ──────────────────────────────────────────────────
img = Image.new('RGB', (W, H), LGRAY)
d = ImageDraw.Draw(img)
navbar(d)
footer(d)
card(d, W//2-220, 70, 440, 400)
label(d, W//2-160, 90, "👤+  Create Account", bold=True, size=22)
label(d, W//2-180, 130, "Free to use. No credit card required.", size=12, color=DGRAY)
label(d, W//2-200, 160, "Email address", size=13)
field(d, W//2-200, 180, 400, placeholder="you@example.com")
label(d, W//2-200, 232, "Password", size=13)
field(d, W//2-200, 252, 400, placeholder="At least 8 characters")
label(d, W//2-200, 305, "Confirm password", size=13)
field(d, W//2-200, 325, 400, placeholder="Repeat password")
button(d, W//2-200, 382, 400, 44, "👤+  Create account")
img.save(f'{OUT}/fig02_register.png')
print('fig02_register saved')

# ──────────────────────────────────────────────────
# FIG 3a: Profile & Settings page — TOP (Personal Info)
# ──────────────────────────────────────────────────
img = Image.new('RGB', (W, H), LGRAY)
d = ImageDraw.Draw(img)
navbar(d)
footer(d)
alert(d, 50, 70, W-100, "Account created! Now complete your profile.", 'success')
label(d, 50, 134, "👥  Profile & Settings", bold=True, size=26)
label(d, 50, 170, "Fill in all sections so the bot can apply on your behalf.", size=13, color=DGRAY)
# Section 1 – Personal Info
section_header(d, 50, 200, W-100, "👤  1. Personal Information")
label(d, 50, 260, "Full Name *", size=13)
field(d, 50, 280, 440, placeholder="Mikhael Nabil Salama Rezk")
label(d, 550, 260, "Phone Number *", size=13)
field(d, 550, 280, 440, placeholder="+20 123 456 7890")
label(d, 50, 345, "Location", size=13)
field(d, 50, 365, 440, placeholder="Cairo, Egypt")
label(d, 550, 345, "Current Job Title *", size=13)
field(d, 550, 365, 440, placeholder="Software Developer")
label(d, 50, 430, "LinkedIn Profile URL", size=13)
field(d, 50, 450, 440, placeholder="https://linkedin.com/in/...")
label(d, 550, 430, "GitHub Profile URL", size=13)
field(d, 550, 450, 440, placeholder="https://github.com/...")
img.save(f'{OUT}/fig03a_profile_top.png')
print('fig03a_profile_top saved')

# ──────────────────────────────────────────────────
# FIG 3b: Profile & Settings page — BOTTOM (Location / Edu / Auth / Salary)
# ──────────────────────────────────────────────────
img = Image.new('RGB', (W, H), LGRAY)
d = ImageDraw.Draw(img)
navbar(d)
footer(d)
label(d, 50, 75, "👥  Profile & Settings", bold=True, size=26)
label(d, 50, 112, "Fill in all sections so the bot can apply on your behalf.", size=13, color=DGRAY)
# Section 2 – Location & Education
section_header(d, 50, 145, W-100, "🎓  2. Location & Education")
label(d, 50, 205, "Current Location *", size=13)
field(d, 50, 225, 440, value="Budapest, Hungary")
label(d, 550, 205, "Graduation Year", size=13)
field(d, 550, 225, 440, value="2027")
label(d, 50, 285, "Years of Experience", size=13)
field(d, 50, 305, 440, value="3")
# Section 3 – Bot Behaviour
section_header(d, 50, 365, W-100, "🤖  3. Bot Behaviour & Answers")
label(d, 50, 425, "Work Authorization Answer", size=13)
field(d, 50, 445, W-100, value="Yes, I have a valid work permit.")
label(d, 50, 490, "Used when LinkedIn asks \"Are you authorized to work in X?\"", size=11, color=DGRAY)
label(d, 50, 517, "Salary / Compensation Answer", size=13)
field(d, 50, 537, W-100, value="Negotiable / 1,000,000 HUF/month")
label(d, 50, 582, "Used when LinkedIn asks for expected salary.", size=11, color=DGRAY)
button(d, 50, 618, 280, 44, "💾  Save Profile & Settings", color=BLUE)
img.save(f'{OUT}/fig03b_profile_bottom.png')
print('fig03b_profile_bottom saved')

# ──────────────────────────────────────────────────
# FIG 4a: Dashboard — TOP (Stats + Campaign + Action Buttons)
# ──────────────────────────────────────────────────
img = Image.new('RGB', (W, H), LGRAY)
d = ImageDraw.Draw(img)
navbar(d)
footer(d)
label(d, 50, 75, "📊  Dashboard", bold=True, size=26)
label(d, 50, 110, "Monitor your automation campaigns and application statistics.", size=13, color=DGRAY)

# Stats cards row
for i, (stat, val, col) in enumerate([
    ("Total Scanned", "284", BLUE),
    ("Submitted", "17", GREEN),
    ("Skipped", "231", (108,117,125)),
    ("Failures", "36", RED),
]):
    cx = 50 + i*260
    card(d, cx, 145, 240, 110)
    draw2 = d
    draw2.rectangle([cx, 145, cx+240, 155], fill=col)
    fnt_big = try_font(36, bold=True)
    fnt_sm = try_font(13)
    d.text((cx+20, 170), val, fill=col, font=fnt_big)
    d.text((cx+20, 220), stat, fill=DGRAY, font=fnt_sm)

# Campaign section
card(d, 50, 275, W-100, 100)
label(d, 70, 293, "🌐  External Watch Campaign", bold=True, size=16)
label(d, 70, 320, "Sites: WeWorkRemotely · RemoteOK · EuropeRemoteJobs · Jobicy", size=13, color=DGRAY)
label(d, 70, 345, "Keyword: Software Developer     Max per site: 10     Headless: Yes", size=13, color=DGRAY)

# Action buttons row
label(d, 50, 393, "Campaign Actions", bold=True, size=14, color=DGRAY)
button(d, 50,  415, 180, 42, "▶  Run Now",        color=GREEN)
button(d, 245, 415, 200, 42, "▶👁 Run and Watch",  color=BLUE)
button(d, 460, 415, 190, 42, "🔁  Retry Failures",  color=RED)
button(d, 665, 415, 210, 42, "🌐  External Watch",  color=(13,202,240))
button(d, 890, 415, 160, 42, "🔗  Network",         color=(108,117,125))

# Recent runs table header only
card(d, 50, 478, W-100, 190)
label(d, 70, 493, "Recent Runs", bold=True, size=16)
d.line([70, 518, W-70, 518], fill=MGRAY, width=1)
hdr_cols = ["Run ID", "Started", "Status", "Scanned", "Submitted", "Skipped"]
col_xs = [70, 190, 340, 480, 590, 700]
for i, h in enumerate(hdr_cols):
    label(d, col_xs[i], 526, h, bold=True, size=12, color=DGRAY)
rows = [
    ("#78", "08 May 2026 08:30", "✅ completed", "10", "3", "7"),
    ("#77", "07 May 2026 08:30", "✅ completed", "10", "1", "9"),
    ("#76", "06 May 2026 08:30", "✅ completed", "10", "0", "10"),
]
for ri, row in enumerate(rows):
    ry = 552 + ri*38
    bg = WHITE if ri%2==0 else LGRAY
    d.rectangle([70, ry-5, W-70, ry+28], fill=bg)
    for ci, cell in enumerate(row):
        col = GREEN if '✅' in cell else (BYELLOW if '⚠' in cell else BLACK)
        label(d, col_xs[ci], ry, cell, size=12, color=col)

img.save(f'{OUT}/fig04a_dashboard_top.png')
print('fig04a_dashboard_top saved')

# ──────────────────────────────────────────────────
# FIG 4b: Dashboard — BOTTOM (Automation Capabilities)
# ──────────────────────────────────────────────────
PURPLE = (102, 16, 242)
TEAL   = (13, 202, 240)
img = Image.new('RGB', (W, H), LGRAY)
d = ImageDraw.Draw(img)
navbar(d)
footer(d)
label(d, 50, 75, "📊  Dashboard — Automation Capabilities", bold=True, size=22)
label(d, 50, 112, "Overview of what the AutoApply bot can handle automatically.", size=13, color=DGRAY)

caps = [
    ("⚙  Multi-Platform Support", GREEN, [
        "Greenhouse, Lever, Ashby, Teamtailor, Workday, SmartRecruiters",
        "BambooHR, Recruitee, Jobvite, Generic HTML forms",
        "Cloudflare-protected pages (18-second polling bypass)",
    ]),
    ("🤖  AI + Smart Filling", PURPLE, [
        "Ollama-powered fallback for unknown dropdowns and questions",
        "Location-aware option picking (city/country context)",
        "Email auto-correction prevents stale autofill values",
    ]),
    ("🛡  Reliability", BYELLOW, [
        "Latest CV selection (newest local resume file)",
        "Viewport-adaptive scrolling (no fixed pixel dependence)",
        "Detailed run logs, per-job reports, and retry workflow",
    ]),
]
cy = 155
for title, color, bullets in caps:
    card(d, 50, cy, W-100, 155)
    # left accent
    d.rounded_rectangle([50, cy, 66, cy+155], radius=4, fill=color)
    label(d, 80, cy+18, title, bold=True, size=15, color=(20,20,20))
    d.line([80, cy+44, W-70, cy+44], fill=MGRAY, width=1)
    for bi, b in enumerate(bullets):
        label(d, 96, cy+55+bi*30, f"•  {b}", size=13, color=DGRAY)
    cy += 170

img.save(f'{OUT}/fig04b_dashboard_bottom.png')
print('fig04b_dashboard_bottom saved')

# ──────────────────────────────────────────────────
# FIG 5: Application History
# ──────────────────────────────────────────────────
img = Image.new('RGB', (W, H), LGRAY)
d = ImageDraw.Draw(img)
navbar(d)
footer(d)
label(d, 50, 75, "📋  Application History", bold=True, size=26)
label(d, 50, 110, "All applications submitted by the automation bot across all platforms.", size=13, color=DGRAY)
card(d, 50, 145, W-100, 510)
hdr_cols2 = ["#", "Job URL", "Source", "Method", "Applied At", "Status"]
col_xs2 = [60, 130, 440, 560, 690, 870]
col_ws =  [60, 300, 110, 120, 170, 110]
d.rectangle([50, 145, W-50, 185], fill=BLUE)
for i, h in enumerate(hdr_cols2):
    label(d, col_xs2[i], 162, h, bold=True, size=12, color=WHITE)
sample_jobs = [
    ("17", "greenhouse.io/jobs/senior-dev-cast-ai", "RemoteOK", "greenhouse", "08/05/26 08:34", "✅ Submitted"),
    ("16", "jobs.lever.co/synthesia/full-stack-engineer", "Jobicy", "lever", "08/05/26 08:31", "✅ Submitted"),
    ("15", "ashbyhq.com/jobs/backend-engineer", "EuroRemote", "ashby", "07/05/26 08:37", "✅ Submitted"),
    ("14", "weworkremotely.com/remote-jobs/python-dev", "WWR", "cloudflare_blocked","07/05/26 08:35", "⏭ Skipped"),
    ("13", "remoteok.com/remote-python-devs-logseq", "RemoteOK", "remoteok_signup","07/05/26 08:33", "✅ Submitted"),
    ("12", "weworkremotely.com/remote-jobs/react-dev",  "WWR","cloudflare_blocked","06/05/26 08:38", "⏭ Skipped"),
    ("11", "careers.bamboohr.com/EN/eng/python-dev",    "Jobicy","bamboo",          "06/05/26 08:35", "✅ Submitted"),
    ("10", "jobs.smartrecruiters.com/DevCo/fe-dev",     "EuroRemote","smartrecruiters","06/05/26 08:33", "✅ Submitted"),
    ("9",  "remoteok.com/remote-senior-dev-100devs",    "RemoteOK","generic",        "05/05/26 08:40", "✅ Submitted"),
    ("8",  "weworkremotely.com/remote-jobs/ts-dev",     "WWR","cloudflare_blocked", "05/05/26 08:37", "⏭ Skipped"),
    ("7",  "recruitee.com/jobs/backend-codescreen",     "EuroRemote","recruitee",    "05/05/26 08:35", "✅ Submitted"),
]
for ri, row in enumerate(sample_jobs):
    ry = 192 + ri*44
    bg = WHITE if ri%2==0 else LGRAY
    d.rectangle([50, ry, W-50, ry+40], fill=bg)
    for ci, cell in enumerate(row):
        col = GREEN if '✅' in cell else ((255,120,0) if '⏭' in cell else BLACK)
        fnt = try_font(11)
        # truncate long text
        max_w = col_ws[ci]
        display = cell
        d.text((col_xs2[ci], ry+12), display[:26], fill=col, font=fnt)

img.save(f'{OUT}/fig05_history.png')
print('fig05_history saved')

# ──────────────────────────────────────────────────
# FIG 6: External Watch Configuration
# ──────────────────────────────────────────────────
img = Image.new('RGB', (W, H), LGRAY)
d = ImageDraw.Draw(img)
navbar(d)
footer(d)
label(d, 50, 75, "⚙  External Watch Configuration", bold=True, size=26)
label(d, 50, 110, "Configure the keyword, headless mode, and per-site limits for the External Watch campaign.", size=13, color=DGRAY)
card(d, 50, 145, W-100, 200)
section_header(d, 50, 145, W-100, "🔍  Search Settings")
label(d, 70, 205, "Job Keyword", size=13)
field(d, 70, 225, 400, value="Software Developer")
label(d, 530, 205, "Max Applications per Site", size=13)
field(d, 530, 225, 200, value="10")
label(d, 70, 278, "Headless Mode", size=13)
# toggle
draw2 = d
draw2.rounded_rectangle([70, 298, 130, 326], radius=13, fill=GREEN)
draw2.ellipse([105, 300, 126, 324], fill=WHITE)
label(d, 140, 300, "Enabled (browser runs in background)", size=13, color=DGRAY)
card(d, 50, 368, W-100, 270)
section_header(d, 50, 368, W-100, "🌐  Active Job Board Sources")
for i, (site, url, status, color) in enumerate([
    ("WeWorkRemotely", "weworkremotely.com/remote-jobs/...", "Active", GREEN),
    ("RemoteOK",        "remoteok.com/remote-{keyword}-jobs", "Active", GREEN),
    ("EuropeRemoteJobs","europeremotejobs.com/jobs/...",       "Active", GREEN),
    ("Jobicy",          "jobicy.com/jobs",                     "Active", GREEN),
]):
    ry = 430 + i*48
    d.rectangle([70, ry, W-70, ry+40], fill=WHITE if i%2==0 else LGRAY)
    label(d, 80, ry+12, site, bold=True, size=13)
    label(d, 300, ry+12, url, size=12, color=DGRAY)
    label(d, W-170, ry+12, f"● {status}", size=12, color=color)
button(d, 50, 655, 200, 40, "▶  Run Now", color=GREEN)
button(d, 270, 655, 180, 40, "💾  Save Config", color=BLUE)
img.save(f'{OUT}/fig06_watch_config.png')
print('fig06_watch_config saved')

# ──────────────────────────────────────────────────
# FIG 7: Architecture Diagram  —  1600×900
# ──────────────────────────────────────────────────
W2, H2 = 1600, 900
img = Image.new('RGB', (W2, H2), (250, 251, 252))
d = ImageDraw.Draw(img)

# Title bar
d.rectangle([0, 0, W2, 64], fill=(33, 37, 41))
fnt_title = try_font(26, bold=True)
d.text((W2//2 - 380, 16), "AutoApply — Four-Layer System Architecture", fill=WHITE, font=fnt_title)

layers = [
    ("Layer 1: Presentation Layer",
     "Flask/Jinja2 Templates  ·  Login  ·  Dashboard  ·  Profile  ·  History  ·  Watch Config  ·  Chrome Extension panel",
     (13, 110, 253), 90),
    ("Layer 2: Application Logic",
     "Flask Routes (app.py)  ·  Session & Auth Management  ·  /run_external_watch  ·  /api/run_status  ·  /download endpoints",
     (25, 135, 84), 250),
    ("Layer 3: Automation Engine",
     "bot_runner.py  ·  Page Classifier (14 categories)  ·  DOM Scorer  ·  ATS Handlers  ·  Cloudflare bypass (18s poll)",
     (220, 53, 69), 410),
    ("Layer 4: Persistence",
     "SQLite DB via SQLAlchemy  ·  users table  ·  bot_runs table  ·  watch_configs table  ·  applied_jobs.json (dedup index)",
     (108, 77, 3), 570),
]
for name, detail, color, y in layers:
    d.rounded_rectangle([80, y, W2-80, y+130], radius=14, fill=tint(color), outline=color, width=3)
    # Left accent bar
    d.rounded_rectangle([80, y, 116, y+130], radius=8, fill=color)
    fnt_b = try_font(20, bold=True)
    fnt_n = try_font(16)
    d.text((130, y+22), name, fill=(20, 20, 20), font=fnt_b)
    d.text((130, y+62), detail, fill=(45, 45, 45), font=fnt_n)
    if y < 570:
        mx = W2 // 2
        d.polygon([(mx-18, y+136), (mx+18, y+136), (mx, y+154)], fill=color)
        d.line([(mx, y+130), (mx, y+136)], fill=color, width=4)

img.save(f'{OUT}/fig07_architecture.png')
print('fig07_architecture saved')

# ──────────────────────────────────────────────────
# FIG 8: DOM Scoring Engine flowchart  —  1600×900
# ──────────────────────────────────────────────────
img = Image.new('RGB', (W2, H2), (250, 251, 252))
d = ImageDraw.Draw(img)

d.rectangle([0, 0, W2, 64], fill=(33, 37, 41))
d.text((W2//2 - 340, 16), "DOM Scoring Engine — Element Evaluation Flow", fill=WHITE, font=fnt_title)

steps = [
    (80,  90,  W2-80, 155, "1.  Query all <a> and <button> elements on the current page", BLUE),
    (80,  195, W2-80, 260, "2.  For each element: compute a relevance score from text content + href attributes", BLUE),
    (80,  300, 730,  365, "\"Apply now\" / \"Apply for this job\"  →  +12 pts", GREEN),
    (830, 300, W2-80, 365, "href targets ATS domain (greenhouse / lever / ashby / teamtailor)  →  +8 pts", GREEN),
    (80,  405, 730,  470, "\"apply\" substring in text  →  +4 pts     \"/apply\" in href  →  +5 pts", (108, 77, 3)),
    (830, 405, W2-80, 470, "Social / nav links (Twitter, LinkedIn, mailto:#)  →  -10 pts", RED),
    (80,  510, W2-80, 575, "3.  Sort all candidates by score descending.  Select the highest-scoring element.", BLUE),
    (80,  615, 730,  680, "Score > 0  →  return element + absolute href  →  proceed", GREEN),
    (830, 615, W2-80, 680, "No candidates found  →  return (None, None)  →  skip apply step", RED),
]
fnt_step = try_font(16)
for x1, y1, x2, y2, text, color in steps:
    d.rounded_rectangle([x1, y1, x2, y2], radius=10, fill=tint(color), outline=color, width=2)
    d.text((x1+20, y1+20), text, fill=(20, 20, 20), font=fnt_step)

# Arrows between main pipeline steps
for yt in [155, 260, 470, 575]:
    d.polygon([(W2//2-14, yt+4), (W2//2+14, yt+4), (W2//2, yt+18)], fill=BLUE)

img.save(f'{OUT}/fig08_dom_scorer.png')
print('fig08_dom_scorer saved')

# ──────────────────────────────────────────────────
# FIG 9: Bot State Machine  —  1600×900
# ──────────────────────────────────────────────────

img = Image.new('RGB', (W2, H2), (250, 251, 252))
d = ImageDraw.Draw(img)

d.rectangle([0, 0, W2, 64], fill=(33, 37, 41))
d.text((W2//2 - 370, 16), "Bot Workflow — State Machine (Per-URL Processing Loop)", fill=WHITE, font=fnt_title)

BOX_W, BOX_H = 220, 90
fnt_box_b = try_font(16, bold=True)
fnt_box_n = try_font(14)
fnt_lbl   = try_font(13)

def sm_box(cx, cy, line1, line2='', color=BLUE):
    d.rounded_rectangle([cx-BOX_W//2, cy-BOX_H//2, cx+BOX_W//2, cy+BOX_H//2],
                         radius=12, fill=tint(color), outline=color, width=3)
    b1 = d.textbbox((0,0), line1, font=fnt_box_b)
    w1 = b1[2]-b1[0]
    d.text((cx-w1//2, cy-BOX_H//2+16), line1, fill=(20, 20, 20), font=fnt_box_b)
    if line2:
        b2 = d.textbbox((0,0), line2, font=fnt_box_n)
        w2 = b2[2]-b2[0]
        d.text((cx-w2//2, cy+6), line2, fill=(60,60,60), font=fnt_box_n)

def sm_arrow(x1, y1, x2, y2, lbl='', color=(90,90,90)):
    d.line([(x1, y1), (x2, y2)], fill=color, width=2)
    ang = math.atan2(y2-y1, x2-x1)
    sz = 12
    for da in [0.45, -0.45]:
        ex = x2 - sz*math.cos(ang-da)
        ey = y2 - sz*math.sin(ang-da)
        d.line([(x2, y2), (int(ex), int(ey))], fill=color, width=2)
    if lbl:
        mx, my = (x1+x2)//2+4, (y1+y2)//2-16
        d.text((mx, my), lbl, fill=(80,80,80), font=fnt_lbl)

# Node positions (cx, cy)
P_START   = (200, 160)
P_NAV     = (600, 160)
P_CF      = (1050, 160)
P_DETECT  = (600, 340)
P_SKIP    = (200, 520)
P_DISPATCH= (600, 520)
P_FILL    = (1050, 520)
P_SUBMIT  = (1050, 700)
P_NEXT    = (600, 700)

sm_box(*P_START,    "START",       "Job URL list",          BLUE)
sm_box(*P_NAV,      "NAVIGATE",    "wait DOMContentLoaded", BLUE)
sm_box(*P_CF,       "CLOUDFLARE?", "Poll up to 18 s",       (108,77,3))
sm_box(*P_DETECT,   "DETECT TYPE", "14 page categories",    BLUE)
sm_box(*P_SKIP,     "SKIP",        "log reason",            RED)
sm_box(*P_DISPATCH, "DISPATCH",    "ATS handler",           BLUE)
sm_box(*P_FILL,     "FILL FORM",   "name / email / CV",     BLUE)
sm_box(*P_SUBMIT,   "SUBMIT",      "log result",            GREEN)
sm_box(*P_NEXT,     "NEXT URL",    "",                      BLUE)

sm_arrow(P_START[0]+BOX_W//2,  P_START[1],    P_NAV[0]-BOX_W//2,   P_NAV[1])
sm_arrow(P_NAV[0]+BOX_W//2,    P_NAV[1],      P_CF[0]-BOX_W//2,    P_CF[1],     "no CF")
sm_arrow(P_CF[0],              P_CF[1]+BOX_H//2, P_CF[0],           P_DETECT[1]-BOX_H//2, "resolved ↓")
sm_arrow(P_CF[0]-BOX_W//2,    P_CF[1],        P_DETECT[0]+BOX_W//2, P_DETECT[1]-BOX_H//2, "CF cleared")
sm_arrow(P_DETECT[0],          P_DETECT[1]+BOX_H//2, P_SKIP[0],     P_SKIP[1]-BOX_H//2, "blocked / login")
sm_arrow(P_DETECT[0],          P_DETECT[1]+BOX_H//2, P_DISPATCH[0], P_DISPATCH[1]-BOX_H//2, "apply page")
sm_arrow(P_DISPATCH[0]+BOX_W//2, P_DISPATCH[1], P_FILL[0]-BOX_W//2, P_FILL[1])
sm_arrow(P_FILL[0],            P_FILL[1]+BOX_H//2,  P_SUBMIT[0],    P_SUBMIT[1]-BOX_H//2)
sm_arrow(P_SUBMIT[0]-BOX_W//2, P_SUBMIT[1],   P_NEXT[0]+BOX_W//2,  P_NEXT[1])
sm_arrow(P_SKIP[0]+BOX_W//2,   P_SKIP[1],     P_NEXT[0]-BOX_W//2,  P_NEXT[1])
# loop back arrow along left side
d.line([(P_NEXT[0]-BOX_W//2, P_NEXT[1]), (60, P_NEXT[1])], fill=(90,90,90), width=2)
d.line([(60, P_NEXT[1]), (60, P_START[1])], fill=(90,90,90), width=2)
d.line([(60, P_START[1]), (P_START[0]-BOX_W//2, P_START[1])], fill=(90,90,90), width=2)
d.text((10, (P_NEXT[1]+P_START[1])//2-10), "loop", fill=(90,90,90), font=fnt_lbl)

img.save(f'{OUT}/fig09_statemachine.png')
print('fig09_statemachine saved')

# ──────────────────────────────────────────────────
# FIG 10: Technology Stack  —  1800×760
# ──────────────────────────────────────────────────
# FIG 10: Technology Stack  —  2400×1400 professional redesign
# ──────────────────────────────────────────────────
W10, H10 = 2400, 1400
BG10 = (245, 247, 250)
HDR10 = (22, 33, 62)          # deep navy header
img = Image.new('RGB', (W10, H10), BG10)
d = ImageDraw.Draw(img)

# ── Header bar
d.rectangle([0, 0, W10, 100], fill=HDR10)
fnt_title10 = try_font(42, bold=True)
title10 = "AutoApply — Technology Stack Overview"
tb = d.textbbox((0,0), title10, font=fnt_title10)
d.text(((W10-(tb[2]-tb[0]))//2, 28), title10, fill=WHITE, font=fnt_title10)

# ── Fonts
fnt_sec10  = try_font(30, bold=True)   # section header

CHIP_W10 = 250
CHIP_H10 = 118
CHIP_R10 = 14
SEC_H10  = 50   # section label height
GAP_X10  = 22   # horizontal gap between chips
GAP_Y10  = 16   # vertical gap between chips inside section
ROW_Y1   = 145  # first row y (after header)
SECTION_ROW_H10 = 390

def _break_word_to_width(text, font, max_w):
    """Split long single-token text into pixel-width-safe chunks."""
    chunks = []
    cur = ""
    for ch in text:
        test = cur + ch
        bb = d.textbbox((0, 0), test, font=font)
        if (bb[2] - bb[0]) <= max_w or not cur:
            cur = test
        else:
            chunks.append(cur)
            cur = ch
    if cur:
        chunks.append(cur)
    return chunks

def _wrap_text_px(text, font, max_w):
    """Wrap text by measured pixel width using greedy line packing."""
    words = text.split()
    if not words:
        return [""]

    lines = []
    cur = ""
    for w in words:
        test = w if not cur else f"{cur} {w}"
        bb = d.textbbox((0, 0), test, font=font)
        if (bb[2] - bb[0]) <= max_w:
            cur = test
            continue

        if cur:
            lines.append(cur)
            cur = ""

        wb = d.textbbox((0, 0), w, font=font)
        if (wb[2] - wb[0]) <= max_w:
            cur = w
        else:
            lines.extend(_break_word_to_width(w, font, max_w))

    if cur:
        lines.append(cur)
    return lines

def _fit_lines(text, max_w, max_h, start_size, min_size, bold=False, max_lines=2):
    """Find largest font size whose wrapped lines fit area constraints."""
    for size in range(start_size, min_size - 1, -1):
        font = try_font(size, bold=bold)
        lines = _wrap_text_px(text, font, max_w)
        if len(lines) > max_lines:
            continue
        lh_box = d.textbbox((0, 0), "Ag", font=font)
        line_h = lh_box[3] - lh_box[1]
        total_h = len(lines) * line_h + max(0, len(lines) - 1) * 4
        if total_h <= max_h:
            return lines, font, line_h

    # Fallback at minimum size with hard cap and ellipsis on last line.
    font = try_font(min_size, bold=bold)
    lines = _wrap_text_px(text, font, max_w)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and d.textbbox((0, 0), last + "...", font=font)[2] > max_w:
            last = last[:-1]
        lines[-1] = (last + "...") if last else "..."
    lh_box = d.textbbox((0, 0), "Ag", font=font)
    line_h = lh_box[3] - lh_box[1]
    return lines, font, line_h

def _draw_centered_lines(x, y, w, h, lines, font, line_h, color):
    """Draw multiline text centered in a rectangle."""
    total_h = len(lines) * line_h + max(0, len(lines) - 1) * 4
    y0 = y + (h - total_h) // 2
    for i, ln in enumerate(lines):
        bb = d.textbbox((0, 0), ln, font=font)
        tw = bb[2] - bb[0]
        tx = x + (w - tw) // 2
        ty = y0 + i * (line_h + 4)
        d.text((tx, ty), ln, fill=color, font=font)

def chip10(cx, cy, name, role, color):
    fill_c = tint(color)
    d.rounded_rectangle([cx, cy, cx+CHIP_W10, cy+CHIP_H10],
                         radius=CHIP_R10, fill=fill_c, outline=color, width=3)

    # Top area: library/tool name
    name_lines, name_font, name_lh = _fit_lines(
        name,
        max_w=CHIP_W10 - 24,
        max_h=48,
        start_size=24,
        min_size=14,
        bold=True,
        max_lines=2,
    )
    _draw_centered_lines(
        cx + 12,
        cy + 12,
        CHIP_W10 - 24,
        48,
        name_lines,
        name_font,
        name_lh,
        (15, 15, 15),
    )

    # Bottom area: functional role/domain
    role_lines, role_font, role_lh = _fit_lines(
        role,
        max_w=CHIP_W10 - 24,
        max_h=44,
        start_size=20,
        min_size=12,
        bold=False,
        max_lines=2,
    )
    _draw_centered_lines(
        cx + 12,
        cy + CHIP_H10 - 56,
        CHIP_W10 - 24,
        44,
        role_lines,
        role_font,
        role_lh,
        (70, 70, 70),
    )

def sec_label10(x, y, text, color):
    # coloured pill label
    tb = d.textbbox((0,0), text, font=fnt_sec10)
    tw, th = tb[2]-tb[0], tb[3]-tb[1]
    px, py = 18, 8
    d.rounded_rectangle([x-px, y-py, x+tw+px, y+th+py],
                         radius=10, fill=color, outline=color, width=0)
    d.text((x, y), text, fill=WHITE, font=fnt_sec10)
    return th + py*2   # returns label block height

# ── Section data: (section_name, color, chips[(name, role)])
sections10 = [
    ("Web Framework",       (37,99,235),  [
        ("Flask 3.x",       "Routing & Sessions"),
        ("Jinja2",          "HTML Templates"),
        ("SQLAlchemy",      "ORM / Migrations"),
        ("Werkzeug",        "Auth & Hashing"),
    ]),
    ("Browser Automation",  (5,150,105),  [
        ("Playwright",      "sync_api"),
        ("Chromium",        "Headless Browser"),
        ("Stealth JS",      "webdriver Override"),
        ("APScheduler",     "Daily 08:30 UTC"),
    ]),
    ("Data & Config",       (109,40,217), [
        ("SQLite",          "Local Database"),
        ("applied_jobs.json","Dedup Index"),
        ("python-dotenv",   "Env Variables"),
        ("python-docx",     "CV Manipulation"),
    ]),
    ("ATS Platforms",       (220,38,38),  [
        ("Greenhouse",      "boards.greenhouse.io"),
        ("Lever",           "jobs.lever.co"),
        ("Ashby",           "ashbyhq.com"),
        ("BambooHR",        "bamboohr.com"),
    ]),
    ("External Job Boards", (2,132,199),  [
        ("WeWorkRemotely",  "weworkremotely.com"),
        ("RemoteOK",        "remoteok.com"),
        ("EuroRemoteJobs",  "europeremotejobs.com"),
        ("Jobicy",          "jobicy.com"),
    ]),
    ("AI & Generation",     (180,83,9),   [
        ("OpenAI GPT-4",    "Cover Letters"),
        ("Ollama / llama3", "Local LLM"),
        ("python-docx",     "CV Generation"),
        ("pytest",          "Test Runner"),
    ]),
]

# Layout: 2 columns × 3 rows, each section contains a 2×2 chip grid
COL_W_SECTION = W10 // 2
COL_INSET10 = 36
SECTION_LABEL_Y_OFFSET = 0
CHIPS_PER_ROW10 = 2

for si, (sec_name, sec_color, chips) in enumerate(sections10):
    col = si % 2
    row = si // 2

    col_left = col * COL_W_SECTION
    inner_x = col_left + COL_INSET10
    inner_w = COL_W_SECTION - (COL_INSET10 * 2)
    base_y = ROW_Y1 + row * SECTION_ROW_H10 + SECTION_LABEL_Y_OFFSET

    # section label
    sec_label10(inner_x, base_y, sec_name, sec_color)

    # 2x2 chip grid centered in the column
    chip_y = base_y + SEC_H10 + 20
    row_w = CHIPS_PER_ROW10 * CHIP_W10 + (CHIPS_PER_ROW10 - 1) * GAP_X10
    chip_start_x = inner_x + max(0, (inner_w - row_w) // 2)

    for ci, (cname, crole) in enumerate(chips):
        chip_col = ci % CHIPS_PER_ROW10
        chip_row = ci // CHIPS_PER_ROW10
        chip_x = chip_start_x + chip_col * (CHIP_W10 + GAP_X10)
        chip_y_i = chip_y + chip_row * (CHIP_H10 + GAP_Y10)
        chip10(chip_x, chip_y_i, cname, crole, sec_color)

img.save(f'{OUT}/fig10_tech_stack.png')
print('fig10_tech_stack saved')

# ──────────────────────────────────────────────────
# FIG 11: Database Schema  —  1600×900
# ──────────────────────────────────────────────────
img = Image.new('RGB', (W2, H2), (250, 251, 252))
d = ImageDraw.Draw(img)

d.rectangle([0, 0, W2, 64], fill=(33, 37, 41))
d.text((W2//2 - 420, 16), "AutoApply — Database Schema (SQLite / SQLAlchemy ORM)", fill=WHITE, font=fnt_title)

fnt_th = try_font(18, bold=True)
fnt_tf = try_font(14)

def db_table2(x, y, name, color, fields):
    TW = 380
    ROW_H = 32
    HDR_H = 52
    total_h = HDR_H + len(fields)*ROW_H + 12
    d.rounded_rectangle([x, y, x+TW, y+total_h], radius=10, fill=WHITE, outline=color, width=2)
    d.rounded_rectangle([x, y, x+TW, y+HDR_H], radius=10, fill=color)
    d.rectangle([x+2, y+HDR_H-10, x+TW-2, y+HDR_H], fill=color)
    # table name
    bn = d.textbbox((0,0), name, font=fnt_th)
    wn = bn[2]-bn[0]
    d.text((x+(TW-wn)//2, y+12), name, fill=WHITE, font=fnt_th)
    for i, (fname, ftype, pk) in enumerate(fields):
        ry = y + HDR_H + 6 + i*ROW_H
        bg = (246, 248, 250) if i%2==0 else WHITE
        d.rectangle([x+2, ry, x+TW-2, ry+ROW_H-2], fill=bg)
        icon = "🔑 " if pk else "    "
        d.text((x+14, ry+6), f"{icon}{fname}", fill=BLACK, font=fnt_tf)
        d.text((x+220, ry+6), ftype, fill=(80,80,80), font=fnt_tf)

db_table2(60, 90, "users", BLUE, [
    ("id",               "INTEGER  PK",       True),
    ("email",            "TEXT  UNIQUE",       False),
    ("password_hash",    "TEXT",               False),
    ("full_name",        "TEXT",               False),
    ("phone",            "TEXT",               False),
    ("location",         "TEXT",               False),
    ("linkedin_url",     "TEXT",               False),
    ("github_url",       "TEXT",               False),
    ("current_job_title","TEXT",               False),
    ("keywords",         "TEXT",               False),
    ("cv_path",          "TEXT",               False),
    ("created_at",       "TIMESTAMP",          False),
])

db_table2(560, 90, "bot_runs", GREEN, [
    ("id",          "INTEGER  PK",        True),
    ("user_id",     "INTEGER  FK→users",  False),
    ("started_at",  "TIMESTAMP",          False),
    ("finished_at", "TIMESTAMP",          False),
    ("status",      "TEXT",               False),
    ("scanned",     "INTEGER",            False),
    ("submitted",   "INTEGER",            False),
    ("skipped",     "INTEGER",            False),
    ("failures",    "INTEGER",            False),
    ("errors",      "INTEGER",            False),
    ("log_json",    "TEXT",               False),
])

db_table2(1060, 90, "watch_configs", (180,30,30), [
    ("id",           "INTEGER  PK",       True),
    ("user_id",      "INTEGER  FK→users", False),
    ("keyword",      "TEXT",              False),
    ("headless",     "BOOLEAN",           False),
    ("max_per_site", "INTEGER",           False),
    ("created_at",   "TIMESTAMP",         False),
])

# applied_jobs.json flat file box
d.rounded_rectangle([560, 650, 1040, 780], radius=10, fill=(255,243,205), outline=BYELLOW, width=2)
fnt_jb = try_font(16, bold=True)
fnt_jn = try_font(14)
d.text((580, 662), "applied_jobs.json  (flat-file deduplication index)", fill=(102,77,3), font=fnt_jb)
d.text((580, 694), '[ "https://boards.greenhouse.io/castai/jobs/1234",', fill=BLACK, font=fnt_jn)
d.text((580, 718), '  "https://jobs.lever.co/synthesia/abc-123", ... ]', fill=BLACK, font=fnt_jn)
d.text((580, 746), "Checked before each application — prevents duplicate submissions", fill=(80,80,80), font=fnt_jn)

# FK arrows
for sx, sy, ex, ey, lbl in [
    (440, 170, 560, 155, "user_id"),
    (440, 200, 560, 175, "user_id"),
    (940, 170, 1060, 155, "user_id"),
]:
    sm_arrow(sx, sy, ex, ey, lbl)

img.save(f'{OUT}/fig11_db_schema.png')
print('fig11_db_schema saved')

print('\nAll diagrams regenerated at 1600x900!')
print(f'Output: {OUT}')