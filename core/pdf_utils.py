import os
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from django.utils import timezone

# ============================================================
# BRAND DESIGN TOKENS (matches web UI)
# ============================================================
COMPANY_NAME = "SHRI RAJ CONSTRUCTION & BUILDING MATERIALS SUPPLIER"
COMPANY_SUBTITLE = "Building Materials Supplier • Earthmovers • Construction Services"

BRAND        = colors.HexColor('#16665a')   # primary teal
BRAND_DARK   = colors.HexColor('#0d423a')
BRAND_LIGHT  = colors.HexColor('#eef7f5')
ACCENT_AMBER = colors.HexColor('#d97706')

INK      = colors.HexColor('#0f172a')
MUTED    = colors.HexColor('#64748b')
FAINT    = colors.HexColor('#94a3b8')
BORDER   = colors.HexColor('#e2e8f0')
ZEBRA    = colors.HexColor('#f8fafc')
TOTAL_BG = colors.HexColor('#eaf2f0')

GREEN  = colors.HexColor('#059669')
RED    = colors.HexColor('#dc2626')
BLUE   = colors.HexColor('#2563eb')

FONT = 'AppFont'
FONT_BOLD = 'AppFont-Bold'

_FONT_REGISTERED = False


def get_indian_current_time_str():
    """Returns current date and time formatted in India Standard Time (Asia/Kolkata, IST)."""
    now_ist = timezone.localtime(timezone.now())
    return now_ist.strftime('%d-%b-%Y %I:%M %p IST')


def _first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def register_app_fonts():
    """Register Noto Sans regular + bold as the app font family (idempotent)."""
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return

    fonts_dir = os.path.join(settings.BASE_DIR, 'ledger', 'fonts')
    regular = os.path.join(fonts_dir, 'NotoSans-Regular.ttf')
    bold = os.path.join(fonts_dir, 'NotoSans-Bold.ttf')

    if not os.path.exists(bold):
        bold = _first_existing([
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
        ])

    try:
        pdfmetrics.registerFont(TTFont(FONT, regular))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, bold or regular))
        registerFontFamily(FONT, normal=FONT, bold=FONT_BOLD, italic=FONT, boldItalic=FONT_BOLD)
    except Exception:
        pass  # fall back to built-in Helvetica family

    _FONT_REGISTERED = True


def get_registered_font():
    register_app_fonts()
    try:
        pdfmetrics.getFont(FONT)
        return FONT
    except Exception:
        return 'Helvetica'


# ============================================================
# SHARED PARAGRAPH STYLES
# ============================================================

def get_pdf_styles(font_name=None):
    """Consistent style kit used by all PDF reports."""
    font_name = font_name or get_registered_font()
    base = getSampleStyleSheet()['Normal']

    def _style(name, **kw):
        return ParagraphStyle(name, parent=base, fontName=font_name, **kw)

    return {
        'font': font_name,
        'header':       _style('PdfHeader', fontSize=8.5, leading=10.5, textColor=colors.white),
        'header_c':     _style('PdfHeaderC', fontSize=8.5, leading=10.5, textColor=colors.white, alignment=1),
        'header_r':     _style('PdfHeaderR', fontSize=8.5, leading=10.5, textColor=colors.white, alignment=2),
        'body':         _style('PdfBody', fontSize=8, leading=10.5, textColor=INK),
        'body_r':       _style('PdfBodyR', fontSize=8, leading=10.5, textColor=INK, alignment=2),
        'body_c':       _style('PdfBodyC', fontSize=8, leading=10.5, textColor=INK, alignment=1),
        'muted':        _style('PdfMuted', fontSize=7.5, leading=9.5, textColor=MUTED),
        'total':        _style('PdfTotal', fontSize=8.5, leading=11, textColor=BRAND_DARK),
        'total_r':      _style('PdfTotalR', fontSize=8.5, leading=11, textColor=BRAND_DARK, alignment=2),
        'total_c':      _style('PdfTotalC', fontSize=8.5, leading=11, textColor=BRAND_DARK, alignment=1),
    }


# ============================================================
# HEADER BANNER
# ============================================================

def build_pdf_header_elements(font_name, report_title, report_subtitle=None, extra_meta=None):
    """Premium branded header: teal banner + amber accent line + meta strip."""
    register_app_fonts()
    styles = getSampleStyleSheet()

    def _s(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], fontName=font_name, **kw)

    company_style = _s('CompName', fontSize=13.5, leading=16, textColor=colors.white)
    company_sub   = _s('CompSub', fontSize=7.5, leading=10, textColor=colors.HexColor('#bcd8d1'))
    title_style   = _s('RepTitle', fontSize=12.5, leading=15, textColor=colors.white, alignment=2)
    sub_style     = _s('RepSub', fontSize=7.5, leading=10, textColor=colors.HexColor('#bcd8d1'), alignment=2)

    left_block = [
        Paragraph(f"<b>{COMPANY_NAME}</b>", company_style),
        Spacer(1, 1.5),
        Paragraph(COMPANY_SUBTITLE, company_sub),
    ]

    right_block = [Paragraph(f"<b>{report_title.upper()}</b>", title_style)]
    if report_subtitle:
        right_block.append(Spacer(1, 1.5))
        right_block.append(Paragraph(report_subtitle, sub_style))

    banner = Table(
        [[left_block, right_block]],
        colWidths=['62%', '38%'],
    )
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 14),
        ('RIGHTPADDING', (-1, -1), (-1, -1), 14),
        ('LEFTPADDING', (1, 0), (1, 0), 6),
        ('RIGHTPADDING', (0, 0), (0, 0), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 11),
        ('LINEBELOW', (0, 0), (-1, -1), 2.2, ACCENT_AMBER),
    ]))

    elements = [banner]

    if extra_meta:
        meta_style = _s('MetaStrip', fontSize=8, leading=11, textColor=colors.HexColor('#334155'))
        meta_table = Table([[Paragraph(extra_meta, meta_style)]], colWidths=['100%'])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), ZEBRA),
            ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(Spacer(1, 8))
        elements.append(meta_table)

    elements.append(Spacer(1, 12))
    return elements


# ============================================================
# KPI SUMMARY CARDS
# ============================================================

def build_summary_cards(cards, font_name=None, card_width=None):
    """
    Build a row of KPI cards.
    cards: list of dicts {label, value, color(optional hex str), sub(optional)}
    """
    font_name = font_name or get_registered_font()
    styles = getSampleStyleSheet()

    def _s(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], fontName=font_name, **kw)

    label_style = _s('CardLbl', fontSize=6.8, leading=9, textColor=FAINT, alignment=1)
    value_style = _s('CardVal', fontSize=12.5, leading=15, alignment=1)
    sub_style   = _s('CardSub', fontSize=6.8, leading=9, alignment=1)

    row = []
    accent_cmds = []
    n = len(cards)
    width = card_width or (190 * mm / max(n, 1))

    for i, card in enumerate(cards):
        hex_color = card.get('color', '#16665a')
        value_style_i = ParagraphStyle(
            f'CardVal{i}', parent=value_style,
            textColor=colors.HexColor(hex_color),
        )
        cell = [Paragraph(card['label'].upper(), label_style), Spacer(1, 2)]
        cell.append(Paragraph(f"<b>{card['value']}</b>", value_style_i))
        if card.get('sub'):
            cell.append(Spacer(1, 1))
            cell.append(Paragraph(card['sub'], sub_style))
        row.append(cell)
        accent_cmds.append(('LINEABOVE', (i, 0), (i, 0), 2.4, colors.HexColor(hex_color)))

    cards_table = Table([row], colWidths=[width] * n)
    cards_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fbfcfd')),
        ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.6, BORDER),
    ] + accent_cmds))

    return cards_table


# ============================================================
# DATA TABLE STYLING (zebra rows, totals footer)
# ============================================================

def apply_data_table_style(table, total_row=False, header_bg=None):
    """Professional zebra-striped table with branded header and optional totals row."""
    cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), header_bg or BRAND),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ('LINEBELOW', (0, 0), (-1, 0), 1.4, ACCENT_AMBER),
        ('LINEBELOW', (0, -1), (-1, -1), 0.6, BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 5.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    if total_row:
        cmds += [
            ('BACKGROUND', (0, -1), (-1, -1), TOTAL_BG),
            ('LINEABOVE', (0, -1), (-1, -1), 1.3, BRAND),
        ]
    table.setStyle(TableStyle(cmds))
    return table


# ============================================================
# FOOTER (page numbers + brand note) — pass to document.build()
# ============================================================

def make_pdf_footer(font_name=None):
    """Returns onFirstPage/onLaterPages callbacks drawing a branded footer."""
    font_name = font_name or get_registered_font()

    def _draw(canvas, doc):
        canvas.saveState()
        page_w, _page_h = canvas._pagesize
        margin = 12 * mm
        y = 8.5 * mm

        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.6)
        canvas.line(margin, y + 4.2 * mm, page_w - margin, y + 4.2 * mm)

        canvas.setFont(font_name, 7)
        canvas.setFillColor(FAINT)
        canvas.drawString(margin, y, f"{COMPANY_NAME}")
        canvas.setFillColor(MUTED)
        canvas.drawRightString(page_w - margin, y, f"Page {doc.page}")

        canvas.setFont(font_name, 6.5)
        canvas.setFillColor(FAINT)
        canvas.drawCentredString(page_w / 2, y - 3.2 * mm, "Generated via Business Insights System")
        canvas.restoreState()

    return _draw


def finish_document(document, elements, font_name=None):
    """Build the PDF with branded footers wired in."""
    footer = make_pdf_footer(font_name)
    document.build(elements, onFirstPage=footer, onLaterPages=footer)


# ============================================================
# CLOSING NOTE
# ============================================================

def build_thankyou_note(text="Thank you for your business!", font_name=None):
    font_name = font_name or get_registered_font()
    styles = getSampleStyleSheet()
    note = ParagraphStyle(
        'ThankYou', parent=styles['Normal'], fontName=font_name,
        fontSize=8.5, leading=11, textColor=MUTED, alignment=1,
    )
    return [Spacer(1, 14), Paragraph(f"<i>{text}</i>", note)]
