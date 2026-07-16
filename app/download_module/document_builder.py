"""
Builders that turn approved content items into Word (.docx), PDF,
PNG and JPG files.

Content bodies are LLM-generated markdown. A small parser maps them to
headings, bullets and styled runs so the exported documents look formatted
rather than raw.
"""
import io
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from docx import Document
from docx.shared import Pt, RGBColor

from PIL import Image, ImageDraw, ImageFont

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable
)

from service_utils.log_management import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Markdown parsing (shared by both builders)
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_INLINE_RE = re.compile(
    r"(\*\*(?P<bold>.+?)\*\*"
    r"|__(?P<bold2>.+?)__"
    r"|\*(?P<italic>[^*\n]+?)\*"
    r"|_(?P<italic2>[^_\n]+?)_"
    r"|`(?P<code>[^`\n]+?)`"
    r"|\[(?P<linktext>[^\]]+)\]\((?P<linkurl>[^)\s]+)\))"
)


def _parse_inline(text: str) -> List[Tuple[str, bool, bool]]:
    """Parse inline markdown into (text, bold, italic) runs."""
    text = _HTML_TAG_RE.sub("", text)
    runs: List[Tuple[str, bool, bool]] = []
    pos = 0
    for match in _INLINE_RE.finditer(text):
        if match.start() > pos:
            runs.append((text[pos:match.start()], False, False))
        if match.group("bold") is not None:
            runs.append((match.group("bold"), True, False))
        elif match.group("bold2") is not None:
            runs.append((match.group("bold2"), True, False))
        elif match.group("italic") is not None:
            runs.append((match.group("italic"), False, True))
        elif match.group("italic2") is not None:
            runs.append((match.group("italic2"), False, True))
        elif match.group("code") is not None:
            runs.append((match.group("code"), False, False))
        elif match.group("linktext") is not None:
            runs.append((match.group("linktext"), False, False))
            runs.append((f" ({match.group('linkurl')})", False, True))
        pos = match.end()
    if pos < len(text):
        runs.append((text[pos:], False, False))
    return [r for r in runs if r[0]]


def _parse_blocks(markdown_text: str) -> List[Dict[str, Any]]:
    """
    Parse markdown into blocks:
      {"type": "heading", "level": 1-4, "runs": [...]}
      {"type": "bullet",  "runs": [...]}
      {"type": "para",    "runs": [...]}
      {"type": "rule"}
    """
    blocks: List[Dict[str, Any]] = []
    paragraph_lines: List[str] = []

    def flush_paragraph():
        if paragraph_lines:
            joined = " ".join(paragraph_lines)
            blocks.append({"type": "para", "runs": _parse_inline(joined)})
            paragraph_lines.clear()

    for raw_line in (markdown_text or "").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush_paragraph()
            level = min(len(heading.group(1)), 4)
            blocks.append({"type": "heading", "level": level,
                           "runs": _parse_inline(heading.group(2))})
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            flush_paragraph()
            blocks.append({"type": "rule"})
            continue

        bullet = re.match(r"^[-*•+]\s+(.*)$", stripped)
        if bullet:
            flush_paragraph()
            blocks.append({"type": "bullet", "runs": _parse_inline(bullet.group(1))})
            continue

        numbered = re.match(r"^(\d+[.)])\s+(.*)$", stripped)
        if numbered:
            flush_paragraph()
            runs = [(f"{numbered.group(1)} ", False, False)] + _parse_inline(numbered.group(2))
            blocks.append({"type": "bullet_num", "runs": runs})
            continue

        paragraph_lines.append(stripped)

    flush_paragraph()
    return blocks


def _format_date(value: Any) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    try:
        return value.strftime("%d %b %Y")
    except Exception:
        return str(value)


def _item_meta_line(item: Dict[str, Any]) -> str:
    parts = []
    if item.get("content_type"):
        parts.append(f"Type: {str(item['content_type']).title()}")
    if item.get("quarter"):
        parts.append(f"Quarter: {item['quarter']}")
    approved = _format_date(item.get("approved_on"))
    if approved:
        parts.append(f"Approved: {approved}")
    return "  |  ".join(parts)


# ---------------------------------------------------------------------------
# Word builder
# ---------------------------------------------------------------------------

def build_docx(doc_title: str, items: List[Dict[str, Any]]) -> bytes:
    """Build a formatted Word document from export items."""
    document = Document()

    title_para = document.add_heading(doc_title, level=0)
    subtitle = document.add_paragraph()
    run = subtitle.add_run(
        f"Exported from Lottie on {datetime.now().strftime('%d %b %Y')}"
        + (f"  •  {len(items)} item(s)" if len(items) > 1 else "")
    )
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    for index, item in enumerate(items):
        if index > 0:
            document.add_page_break()

        document.add_heading(item["title"], level=1)

        meta = _item_meta_line(item)
        if meta:
            meta_para = document.add_paragraph()
            meta_run = meta_para.add_run(meta)
            meta_run.font.size = Pt(8)
            meta_run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

        for block in _parse_blocks(item["body"]):
            if block["type"] == "heading":
                text = "".join(r[0] for r in block["runs"])
                document.add_heading(text, level=min(block["level"] + 1, 4))
            elif block["type"] == "rule":
                document.add_paragraph()
            elif block["type"] in ("bullet", "bullet_num"):
                style = "List Bullet" if block["type"] == "bullet" else None
                para = document.add_paragraph(style=style)
                runs = block["runs"]
                if block["type"] == "bullet_num":
                    para.paragraph_format.left_indent = Pt(18)
                for text, bold, italic in runs:
                    p_run = para.add_run(text)
                    p_run.bold = bold
                    p_run.italic = italic
            else:
                para = document.add_paragraph()
                for text, bold, italic in block["runs"]:
                    p_run = para.add_run(text)
                    p_run.bold = bold
                    p_run.italic = italic

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# PDF builder
# ---------------------------------------------------------------------------

_DEJAVU_DIR = "/usr/share/fonts/truetype/dejavu"
_pdf_fonts_registered = False


def _pdf_fonts() -> Tuple[str, str]:
    """Register a Unicode-capable font when available; fall back to Helvetica."""
    global _pdf_fonts_registered
    regular = os.path.join(_DEJAVU_DIR, "DejaVuSans.ttf")
    bold = os.path.join(_DEJAVU_DIR, "DejaVuSans-Bold.ttf")
    if os.path.exists(regular) and os.path.exists(bold):
        if not _pdf_fonts_registered:
            pdfmetrics.registerFont(TTFont("LottieSans", regular))
            pdfmetrics.registerFont(TTFont("LottieSans-Bold", bold))
            _pdf_fonts_registered = True
        return "LottieSans", "LottieSans-Bold"
    return "Helvetica", "Helvetica-Bold"


def _pdf_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _runs_to_pdf_markup(runs: List[Tuple[str, bool, bool]]) -> str:
    parts = []
    for text, bold, italic in runs:
        chunk = _pdf_escape(text)
        if bold:
            chunk = f"<b>{chunk}</b>"
        if italic:
            chunk = f"<i>{chunk}</i>"
        parts.append(chunk)
    return "".join(parts) or " "


def build_pdf(doc_title: str, items: List[Dict[str, Any]]) -> bytes:
    """Build a formatted PDF from export items."""
    font, font_bold = _pdf_fonts()

    styles = {
        "title": ParagraphStyle("LotTitle", fontName=font_bold, fontSize=20,
                                leading=24, spaceAfter=4),
        "subtitle": ParagraphStyle("LotSubtitle", fontName=font, fontSize=8,
                                   leading=11, textColor="#888888", spaceAfter=14),
        "item_title": ParagraphStyle("LotItemTitle", fontName=font_bold, fontSize=15,
                                     leading=19, spaceBefore=6, spaceAfter=4),
        "meta": ParagraphStyle("LotMeta", fontName=font, fontSize=7.5,
                               leading=10, textColor="#888888", spaceAfter=10),
        "h": ParagraphStyle("LotHeading", fontName=font_bold, fontSize=12,
                            leading=16, spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("LotBody", fontName=font, fontSize=10,
                               leading=15, alignment=TA_LEFT, spaceAfter=6),
        "bullet": ParagraphStyle("LotBullet", fontName=font, fontSize=10,
                                 leading=15, leftIndent=14, bulletIndent=4, spaceAfter=3),
    }

    story = [
        Paragraph(_pdf_escape(doc_title), styles["title"]),
        Paragraph(
            f"Exported from Lottie on {datetime.now().strftime('%d %b %Y')}"
            + (f"  •  {len(items)} item(s)" if len(items) > 1 else ""),
            styles["subtitle"],
        ),
    ]

    for index, item in enumerate(items):
        if index > 0:
            story.append(PageBreak())

        story.append(Paragraph(_pdf_escape(item["title"]), styles["item_title"]))
        meta = _item_meta_line(item)
        if meta:
            story.append(Paragraph(_pdf_escape(meta), styles["meta"]))

        for block in _parse_blocks(item["body"]):
            if block["type"] == "heading":
                size = {1: 13, 2: 12, 3: 11, 4: 10.5}.get(block["level"], 11)
                style = ParagraphStyle(f"LotH{block['level']}", parent=styles["h"], fontSize=size)
                story.append(Paragraph(_runs_to_pdf_markup(block["runs"]), style))
            elif block["type"] == "rule":
                story.append(HRFlowable(width="100%", thickness=0.5, color="#cccccc",
                                        spaceBefore=8, spaceAfter=8))
            elif block["type"] == "bullet":
                story.append(Paragraph(_runs_to_pdf_markup(block["runs"]),
                                       styles["bullet"], bulletText="•"))
            elif block["type"] == "bullet_num":
                story.append(Paragraph(_runs_to_pdf_markup(block["runs"]), styles["bullet"]))
            else:
                story.append(Paragraph(_runs_to_pdf_markup(block["runs"]), styles["body"]))

    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=doc_title,
    )
    pdf.build(story)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Image builders (PNG / JPG)
# ---------------------------------------------------------------------------

_IMG_WIDTH = 1240            # ~A4 width at 150 dpi
_IMG_MARGIN = 90

_IMG_FONT_FILES = {
    (False, False): "DejaVuSans.ttf",
    (True, False): "DejaVuSans-Bold.ttf",
    (False, True): "DejaVuSans-Oblique.ttf",
    (True, True): "DejaVuSans-BoldOblique.ttf",
}


def _image_font(bold: bool, italic: bool, size: int):
    path = os.path.join(_DEJAVU_DIR, _IMG_FONT_FILES[(bold, italic)])
    if not os.path.exists(path):
        path = os.path.join(_DEJAVU_DIR, _IMG_FONT_FILES[(False, False)])
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default(size=size)


def _build_image(doc_title: str, items: List[Dict[str, Any]], fmt: str) -> bytes:
    """Render export items onto a single tall image and return encoded bytes."""
    text_width = _IMG_WIDTH - 2 * _IMG_MARGIN
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def wrap(runs, size, bold_default=False, indent=0):
        """Wrap styled runs into lines of (word, font) segments."""
        tokens = []
        for text, bold, italic in runs:
            font = _image_font(bold or bold_default, italic, size)
            for word in text.split():
                tokens.append((word, font))
        lines, current, current_w = [], [], 0
        max_w = text_width - indent
        for word, font in tokens:
            word_w = probe.textlength(word + " ", font=font)
            if current and current_w + word_w > max_w:
                lines.append(current)
                current, current_w = [], 0
            current.append((word, font))
            current_w += word_w
        if current:
            lines.append(current)
        return lines or [[]]

    ops = []

    def add_text(runs, size, bold=False, indent=0, gap=14, color=(30, 30, 30)):
        ops.append({
            "lines": wrap(runs, size, bold, indent),
            "line_height": int(size * 1.4),
            "indent": indent,
            "gap": gap,
            "color": color,
        })

    grey = (136, 136, 136)
    dark = (10, 10, 10)

    add_text([(doc_title, True, False)], 34, gap=6, color=dark)
    subtitle = (
        f"Exported from Lottie on {datetime.now().strftime('%d %b %Y')}"
        + (f"  •  {len(items)} item(s)" if len(items) > 1 else "")
    )
    add_text([(subtitle, False, False)], 15, gap=28, color=grey)

    for index, item in enumerate(items):
        if index > 0:
            ops.append({"rule": True, "gap": 28})
        add_text([(item["title"], True, False)], 26, gap=6, color=dark)
        meta = _item_meta_line(item)
        if meta:
            add_text([(meta, False, False)], 14, gap=18, color=grey)

        for block in _parse_blocks(item["body"]):
            if block["type"] == "heading":
                size = {1: 24, 2: 22, 3: 20, 4: 19}.get(block["level"], 20)
                add_text(block["runs"], size, bold=True, gap=8, color=dark)
            elif block["type"] == "rule":
                ops.append({"rule": True, "gap": 18})
            elif block["type"] == "bullet":
                add_text([("•", False, False)] + block["runs"], 18, indent=28, gap=6)
            elif block["type"] == "bullet_num":
                add_text(block["runs"], 18, indent=28, gap=6)
            else:
                add_text(block["runs"], 18, gap=14)

    total_height = 2 * _IMG_MARGIN
    for op in ops:
        if op.get("rule"):
            total_height += 2 + op["gap"]
        else:
            total_height += len(op["lines"]) * op["line_height"] + op["gap"]

    image = Image.new("RGB", (_IMG_WIDTH, max(total_height, 400)), "white")
    draw = ImageDraw.Draw(image)
    y = _IMG_MARGIN
    for op in ops:
        if op.get("rule"):
            draw.line(
                [(_IMG_MARGIN, y), (_IMG_WIDTH - _IMG_MARGIN, y)],
                fill=(204, 204, 204), width=2,
            )
            y += 2 + op["gap"]
            continue
        for line in op["lines"]:
            x = _IMG_MARGIN + op["indent"]
            for word, font in line:
                draw.text((x, y), word, font=font, fill=op["color"])
                x += probe.textlength(word + " ", font=font)
            y += op["line_height"]
        y += op["gap"]

    buffer = io.BytesIO()
    if fmt == "jpg":
        image.save(buffer, format="JPEG", quality=90)
    else:
        image.save(buffer, format="PNG")
    return buffer.getvalue()


def build_png(doc_title: str, items: List[Dict[str, Any]]) -> bytes:
    """Build a PNG image from export items."""
    return _build_image(doc_title, items, "png")


def build_jpg(doc_title: str, items: List[Dict[str, Any]]) -> bytes:
    """Build a JPG image from export items."""
    return _build_image(doc_title, items, "jpg")
