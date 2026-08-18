import os
from datetime import datetime
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from django.utils import timezone

COMPANY_NAME = "SHRI RAJ CONSTRUCTION & BUILDING MATERIALS SUPPLIER"
COMPANY_SUBTITLE = "Building Materials Supplier • Earthmovers • Construction Services"

def get_indian_current_time_str():
    """Returns current date and time formatted in India Standard Time (Asia/Kolkata, IST)."""
    now_ist = timezone.localtime(timezone.now())
    return now_ist.strftime('%d-%b-%Y %I:%M %p IST')

def get_registered_font():
    font_path = os.path.join(settings.BASE_DIR, 'ledger', 'fonts', 'NotoSans-Regular.ttf')
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont('AppFont', font_path))
            return 'AppFont'
        except Exception:
            pass
    if os.path.exists('/System/Library/Fonts/Supplemental/Georgia.ttf'):
        try:
            pdfmetrics.registerFont(TTFont('AppFont', '/System/Library/Fonts/Supplemental/Georgia.ttf'))
            return 'AppFont'
        except Exception:
            pass
    return 'Helvetica'

def build_pdf_header_elements(font_name, report_title, report_subtitle=None, extra_meta=None):
    styles = getSampleStyleSheet()
    
    comp_name_style = ParagraphStyle(
        'CompNameStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#0F172A'),
        alignment=1,
    )
    
    comp_sub_style = ParagraphStyle(
        'CompSubStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#475569'),
        alignment=1,
    )
    
    report_title_style = ParagraphStyle(
        'ReportTitleStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1,
    )
    
    report_sub_style = ParagraphStyle(
        'ReportSubStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#64748B'),
        alignment=1,
    )
    
    elements = [
        Paragraph(f"<b>{COMPANY_NAME}</b>", comp_name_style),
        Spacer(1, 2),
        Paragraph(COMPANY_SUBTITLE, comp_sub_style),
        Spacer(1, 6),
    ]
    
    # Decorative line
    line_table = Table([['']], colWidths=['100%'])
    line_table.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, -1), 1.5, colors.HexColor('#1E3A8A')),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(line_table)
    elements.append(Spacer(1, 8))
    
    elements.append(Paragraph(f"<b>{report_title.upper()}</b>", report_title_style))
    if report_subtitle:
        elements.append(Spacer(1, 2))
        elements.append(Paragraph(report_subtitle, report_sub_style))
        
    if extra_meta:
        elements.append(Spacer(1, 3))
        meta_style = ParagraphStyle(
            'MetaStyle',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#334155'),
            alignment=1,
        )
        elements.append(Paragraph(extra_meta, meta_style))
        
    elements.append(Spacer(1, 12))
    return elements
