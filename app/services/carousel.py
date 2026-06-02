"""
Carousel PDF generator — creates a LinkedIn-style slide deck using ReportLab.
Each slide has a headline, body text, and optional bullet points.
Square format (1080x1080px) matches LinkedIn carousel dimensions.
"""

import io
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# ---------------------------------------------------------------------------
# Design constants — LinkedIn carousel is square (1080x1080px ~ 7.5x7.5in)
# ---------------------------------------------------------------------------

SLIDE_SIZE = (7.5 * inch, 7.5 * inch)
W, H = SLIDE_SIZE

# Color palette — dark professional theme
BG_COLOR        = colors.HexColor("#0A0A0A")   # near-black background
ACCENT_COLOR    = colors.HexColor("#0077B5")   # LinkedIn blue
TEXT_PRIMARY    = colors.HexColor("#FFFFFF")   # white
TEXT_SECONDARY  = colors.HexColor("#A0A0A0")   # muted grey
DIVIDER_COLOR   = colors.HexColor("#1E1E1E")   # subtle divider

# Padding
PAD = 0.5 * inch


# ---------------------------------------------------------------------------
# Slide renderers
# ---------------------------------------------------------------------------

def draw_background(c: canvas.Canvas):
    c.setFillColor(BG_COLOR)
    c.rect(0, 0, W, H, fill=1, stroke=0)


def draw_accent_bar(c: canvas.Canvas):
    """Thin LinkedIn-blue bar on the left edge."""
    c.setFillColor(ACCENT_COLOR)
    c.rect(0, 0, 6, H, fill=1, stroke=0)


def draw_slide_number(c: canvas.Canvas, num: int, total: int):
    c.setFillColor(TEXT_SECONDARY)
    c.setFont("Helvetica", 11)
    c.drawRightString(W - PAD, PAD * 0.6, f"{num} / {total}")


def draw_branding(c: canvas.Canvas, author: str):
    """Author name bottom-left."""
    c.setFillColor(ACCENT_COLOR)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(PAD, PAD * 0.6, author)


def wrap_text_lines(text: str, font: str, size: float, max_width: float, c: canvas.Canvas) -> list[str]:
    """Manually wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if c.stringWidth(test, font, size) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_cover_slide(c: canvas.Canvas, title: str, subtitle: str, author: str, slide_num: int, total: int):
    """Slide 1 — big title + subtitle."""
    draw_background(c)
    draw_accent_bar(c)

    # Big title
    title_font_size = 44
    title_lines = wrap_text_lines(title, "Helvetica-Bold", title_font_size, W - PAD * 2.5, c)
    y = H * 0.62
    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica-Bold", title_font_size)
    for line in title_lines:
        c.drawString(PAD + 10, y, line)
        y -= title_font_size * 1.3

    # Divider
    y -= 14
    c.setStrokeColor(ACCENT_COLOR)
    c.setLineWidth(2)
    c.line(PAD + 10, y, W * 0.5, y)
    y -= 24

    # Subtitle
    c.setFillColor(TEXT_SECONDARY)
    c.setFont("Helvetica", 18)
    sub_lines = wrap_text_lines(subtitle, "Helvetica", 18, W - PAD * 2.5, c)
    for line in sub_lines:
        c.drawString(PAD + 10, y, line)
        y -= 26

    draw_slide_number(c, slide_num, total)
    draw_branding(c, author)


def draw_content_slide(c: canvas.Canvas, headline: str, body: str, bullets: list[str], slide_num: int, total: int, author: str):
    """Regular content slide — headline + body or bullets."""
    draw_background(c)
    draw_accent_bar(c)

    # Headline
    c.setFillColor(ACCENT_COLOR)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(PAD + 10, H - PAD * 1.2, f"0{slide_num - 1}" if slide_num <= 10 else str(slide_num - 1))

    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica-Bold", 28)
    headline_lines = wrap_text_lines(headline, "Helvetica-Bold", 28, W - PAD * 2.5, c)
    y = H - PAD * 1.8
    for line in headline_lines:
        c.drawString(PAD + 10, y, line)
        y -= 36

    # Divider
    y -= 8
    c.setStrokeColor(DIVIDER_COLOR)
    c.setLineWidth(1)
    c.line(PAD + 10, y, W - PAD, y)
    y -= 24

    if bullets:
        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica", 16)
        for bullet in bullets:
            bullet_lines = wrap_text_lines(f"• {bullet}", "Helvetica", 16, W - PAD * 2.8, c)
            for line in bullet_lines:
                c.drawString(PAD + 10, y, line)
                y -= 26
            y -= 6
    elif body:
        c.setFillColor(colors.HexColor("#D0D0D0"))
        c.setFont("Helvetica", 17)
        body_lines = wrap_text_lines(body, "Helvetica", 17, W - PAD * 2.5, c)
        for line in body_lines:
            c.drawString(PAD + 10, y, line)
            y -= 28

    draw_slide_number(c, slide_num, total)
    draw_branding(c, author)


def draw_cta_slide(c: canvas.Canvas, cta_text: str, author: str, slide_num: int, total: int):
    """Last slide — call to action."""
    draw_background(c)
    draw_accent_bar(c)

    # Big CTA
    c.setFillColor(ACCENT_COLOR)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(PAD + 10, H * 0.62, "TAKEAWAY")

    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica-Bold", 26)
    cta_lines = wrap_text_lines(cta_text, "Helvetica-Bold", 26, W - PAD * 2.5, c)
    y = H * 0.52
    for line in cta_lines:
        c.drawString(PAD + 10, y, line)
        y -= 36

    # Follow prompt
    y -= 20
    c.setFillColor(TEXT_SECONDARY)
    c.setFont("Helvetica", 15)
    c.drawString(PAD + 10, y, "Follow for more developer content →")

    draw_slide_number(c, slide_num, total)
    draw_branding(c, author)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_carousel_pdf(slides: list[dict], author: str = "Harsimranjit Singh") -> bytes:
    """
    Generate a carousel PDF from a list of slide dicts.

    Slide dict format:
    {
        "type": "cover" | "content" | "cta",
        "headline": str,
        "body": str,          # for content slides without bullets
        "bullets": [str],     # for content slides with bullets
        "subtitle": str,      # cover only
        "cta_text": str,      # cta only
    }

    Returns raw PDF bytes.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=SLIDE_SIZE)
    total = len(slides)

    for i, slide in enumerate(slides):
        slide_num = i + 1
        slide_type = slide.get("type", "content")

        if slide_type == "cover":
            draw_cover_slide(
                c,
                title=slide.get("headline", ""),
                subtitle=slide.get("subtitle", ""),
                author=author,
                slide_num=slide_num,
                total=total,
            )
        elif slide_type == "cta":
            draw_cta_slide(
                c,
                cta_text=slide.get("cta_text", ""),
                author=author,
                slide_num=slide_num,
                total=total,
            )
        else:
            draw_content_slide(
                c,
                headline=slide.get("headline", ""),
                body=slide.get("body", ""),
                bullets=slide.get("bullets", []),
                slide_num=slide_num,
                total=total,
                author=author,
            )

        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.read()