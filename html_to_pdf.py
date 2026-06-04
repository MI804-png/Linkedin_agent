# !/usr/bin/env python
# """Render Mikhael_CV.html into a professional PDF CV."""
# from __future__ import annotations
#!/usr/bin/env python
"""Convert Mikhael_CV.html into a styled professional PDF CV."""
from __future__ import annotations

import html
import re
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape  # This line is not needed, so we can remove it

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "reportlab", "-q"], check=True)
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = BASE_DIR / "Mikhael_CV.html"
PDF_FILE = BASE_DIR / "Mikhael_CV.pdf"


def extract_cv_text(html_text: str) -> str:
    pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if pre_match:
        return html.unescape(pre_match.group(1)).strip()

    without_tags = re.sub(r"<[^>]+>", "\n", html_text)
    return html.unescape(without_tags).strip()


def format_inline_markup(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    normalized = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", normalized)

    parts = re.split(r"(\*\*.+?\*\*)", normalized)
    formatted: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            formatted.append(f"<b>{escape(part[2:-2])}</b>")
        else:
            formatted.append(escape(part))
    return "".join(formatted)


def build_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=colors.HexColor("#0f3d75"),
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "contact": ParagraphStyle(
            "Contact",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#333333"),
            alignment=TA_CENTER,
            leading=12,
            spaceAfter=2,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=colors.HexColor("#0f3d75"),
            spaceBefore=8,
            spaceAfter=6,
            borderPadding=2,
        ),
        "subheading": ParagraphStyle(
            "Subheading",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=colors.HexColor("#222222"),
            spaceBefore=4,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#2d2d2d"),
            spaceAfter=3,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            leftIndent=14,
            firstLineIndent=-8,
            textColor=colors.HexColor("#2d2d2d"),
            spaceAfter=2,
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#555555"),
            spaceBefore=6,
        ),
    }


def build_story(cv_text: str):
    styles = build_styles()
    story = []
    lines = [line.rstrip() for line in cv_text.splitlines()]

    title_seen = False
    before_first_section = True

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line == "---":
            if story:
                story.append(Spacer(1, 0.04 * inch))
            continue

        if line.startswith("# "):
            story.append(Paragraph(format_inline_markup(line[2:]), styles["title"]))
            title_seen = True
            continue

        if line.startswith("## "):
            before_first_section = False
            story.append(Paragraph(format_inline_markup(line[3:]), styles["section"]))
            continue

        if line.startswith("### "):
            story.append(Paragraph(format_inline_markup(line[4:]), styles["subheading"]))
            continue

        if re.match(r"^[-*]\s+", line):
            bullet_text = re.sub(r"^[-*]\s+", "", line)
            story.append(Paragraph(f"- {format_inline_markup(bullet_text)}", styles["bullet"]))
            continue

        if re.match(r"^\d+\.\s+", line):
            story.append(Paragraph(format_inline_markup(line), styles["bullet"]))
            continue

        if title_seen and before_first_section:
            story.append(Paragraph(format_inline_markup(line), styles["contact"]))
            continue

        if line.lower().startswith("references available") or line.lower().startswith("last updated"):
            story.append(Paragraph(format_inline_markup(line), styles["footer"]))
            continue

        story.append(Paragraph(format_inline_markup(line), styles["body"]))

    return story


def main() -> None:
    html_content = HTML_FILE.read_text(encoding="utf-8")
    cv_text = extract_cv_text(html_content)

    document = SimpleDocTemplate(
        str(PDF_FILE),
        pagesize=letter,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
    )
    document.build(build_story(cv_text))
    print(f"Professional PDF created successfully: {PDF_FILE}")


if __name__ == "__main__":
    main()
