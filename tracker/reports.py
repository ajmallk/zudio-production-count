"""Report generation: PDF (ReportLab) and Excel (openpyxl)"""
import io
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Q
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def get_date_range(period, date_from=None, date_to=None):
    now = timezone.now()
    today = now.date()
    if period == 'day':
        return timezone.make_aware(datetime.combine(today, datetime.min.time())), now
    elif period == 'week':
        start = today - timedelta(days=today.weekday())
        return timezone.make_aware(datetime.combine(start, datetime.min.time())), now
    elif period == 'month':
        start = today.replace(day=1)
        return timezone.make_aware(datetime.combine(start, datetime.min.time())), now
    elif period == 'year':
        start = today.replace(month=1, day=1)
        return timezone.make_aware(datetime.combine(start, datetime.min.time())), now
    elif period == 'custom' and date_from and date_to:
        return timezone.make_aware(datetime.combine(date_from, datetime.min.time())), \
               timezone.make_aware(datetime.combine(date_to, datetime.max.time()))
    else:
        start = today.replace(day=1)
        return timezone.make_aware(datetime.combine(start, datetime.min.time())), now


def build_report_data(period='month', date_from=None, date_to=None):
    from .models import QRCode, ScanEvent

    start_dt, end_dt = get_date_range(period, date_from, date_to)

    # Production report: QR codes printed by date/article/size
    qr_codes = QRCode.objects.filter(created_at__range=(start_dt, end_dt))
    production_data = []
    for qr in qr_codes.values('article_number', 'size', 'created_at__date').annotate(count=Count('id')).order_by('created_at__date', 'article_number', 'size'):
        production_data.append({
            'date': str(qr['created_at__date']),
            'article': qr['article_number'],
            'size': qr['size'],
            'printed': qr['count'],
        })

    # Stock report: scanned vs unscanned by article/size
    stock_data = []
    for item in QRCode.objects.values('article_number', 'size').distinct().order_by('article_number', 'size'):
        total = QRCode.objects.filter(article_number=item['article_number'], size=item['size']).count()
        scanned = QRCode.objects.filter(article_number=item['article_number'], size=item['size'], is_scanned=True).count()
        pct = round((scanned / total * 100), 1) if total > 0 else 0
        stock_data.append({
            'article': item['article_number'],
            'size': item['size'],
            'printed': total,
            'scanned': scanned,
            'unscanned': total - scanned,
            'completion': pct,
        })

    # Audit log
    audit_data = []
    for event in ScanEvent.objects.filter(scanned_at__range=(start_dt, end_dt)).select_related('qr_code').order_by('-scanned_at')[:500]:
        audit_data.append({
            'timestamp': event.scanned_at.strftime('%Y-%m-%d %H:%M:%S'),
            'qr_id': str(event.qr_code.qr_id) if event.qr_code else 'N/A',
            'size': event.qr_code.size if event.qr_code else 'N/A',
            'article': event.qr_code.article_number if event.qr_code else 'N/A',
            'status': event.get_status_display(),
            'device': event.device_info or 'Unknown',
        })

    return production_data, stock_data, audit_data, start_dt, end_dt


def generate_excel_report(period='month', date_from=None, date_to=None):
    production_data, stock_data, audit_data, start_dt, end_dt = build_report_data(period, date_from, date_to)

    wb = openpyxl.Workbook()

    # ── Styles ──
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill("solid", fgColor="1a1a2e")
    center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    def style_sheet(ws, headers, data_rows, col_widths):
        ws.append(headers)
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = border
        for row_data in data_rows:
            ws.append(row_data)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = center_align
                cell.border = border
        for i, w in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.row_dimensions[1].height = 25

    # ── Production Sheet ──
    ws1 = wb.active
    ws1.title = "Production Report"
    style_sheet(ws1,
                ['Date', 'Article Number', 'Size', 'QR Codes Printed'],
                [[d['date'], d['article'], d['size'], d['printed']] for d in production_data],
                [15, 20, 10, 18])

    # ── Stock Sheet ──
    ws2 = wb.create_sheet("Stock Report")
    style_sheet(ws2,
                ['Article Number', 'Size', 'Printed', 'Scanned', 'Unscanned', 'Completion %'],
                [[d['article'], d['size'], d['printed'], d['scanned'], d['unscanned'], d['completion']] for d in stock_data],
                [20, 10, 12, 12, 12, 15])

    # ── Audit Sheet ──
    ws3 = wb.create_sheet("Audit Log")
    style_sheet(ws3,
                ['Timestamp', 'QR ID', 'Size', 'Article', 'Status', 'Device'],
                [[d['timestamp'], d['qr_id'], d['size'], d['article'], d['status'], d['device']] for d in audit_data],
                [20, 38, 10, 20, 16, 30])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def generate_pdf_report(period='month', date_from=None, date_to=None):
    production_data, stock_data, audit_data, start_dt, end_dt = build_report_data(period, date_from, date_to)

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4),
                            rightMargin=1*cm, leftMargin=1*cm,
                            topMargin=1.5*cm, bottomMargin=1*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', fontSize=16, fontName='Helvetica-Bold',
                                 textColor=colors.HexColor('#1a1a2e'), alignment=TA_CENTER, spaceAfter=6)
    sub_style = ParagraphStyle('Sub', fontSize=10, fontName='Helvetica',
                               textColor=colors.grey, alignment=TA_CENTER, spaceAfter=12)
    section_style = ParagraphStyle('Section', fontSize=13, fontName='Helvetica-Bold',
                                   textColor=colors.HexColor('#e94560'), spaceBefore=12, spaceAfter=6)

    header_bg = colors.HexColor('#1a1a2e')
    alt_row = colors.HexColor('#f0f4ff')

    def make_table(headers, rows):
        data = [headers] + rows
        t = Table(data, repeatRows=1)
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), header_bg),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, alt_row]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('ROWHEIGHT', (0, 0), (-1, -1), 18),
        ])
        t.setStyle(style)
        return t

    story = []
    story.append(Paragraph("VKC Footwear — Production & QR Stock Report", title_style))
    story.append(Paragraph(f"Period: {start_dt.strftime('%d %b %Y')} to {end_dt.strftime('%d %b %Y')}", sub_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e94560')))
    story.append(Spacer(1, 10))

    # Production
    story.append(Paragraph("Production Report (QR Codes Printed)", section_style))
    if production_data:
        rows = [[d['date'], d['article'], str(d['size']), str(d['printed'])] for d in production_data]
        story.append(make_table(['Date', 'Article Number', 'Size', 'QR Printed'], rows))
    else:
        story.append(Paragraph("No production data for this period.", styles['Normal']))

    story.append(Spacer(1, 16))

    # Stock
    story.append(Paragraph("Stock Report (Scanned vs Unscanned)", section_style))
    if stock_data:
        rows = [[d['article'], str(d['size']), str(d['printed']), str(d['scanned']),
                 str(d['unscanned']), f"{d['completion']}%"] for d in stock_data]
        story.append(make_table(['Article Number', 'Size', 'Printed', 'Scanned', 'Unscanned', 'Completion %'], rows))
    else:
        story.append(Paragraph("No stock data available.", styles['Normal']))

    story.append(Spacer(1, 16))

    # Audit
    story.append(Paragraph("Audit Log (Scan Events)", section_style))
    if audit_data:
        rows = [[d['timestamp'], d['qr_id'][:16] + '...', str(d['size']),
                 d['article'], d['status'], d['device'][:25]] for d in audit_data]
        story.append(make_table(['Timestamp', 'QR ID', 'Size', 'Article', 'Status', 'Device'], rows))
    else:
        story.append(Paragraph("No scan events in this period.", styles['Normal']))

    doc.build(story)
    output.seek(0)
    return output


def generate_batch_pdf(batch):
    """Generate printable PDF sheet with all QR codes for a batch"""
    from .models import QRCode
    from reportlab.platypus import Image as RLImage

    qr_codes = QRCode.objects.filter(batch=batch).order_by('size')
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4,
                            rightMargin=1*cm, leftMargin=1*cm,
                            topMargin=1.5*cm, bottomMargin=1*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('T', fontSize=14, fontName='Helvetica-Bold',
                                 textColor=colors.HexColor('#1a1a2e'), alignment=TA_CENTER, spaceAfter=4)
    info_style = ParagraphStyle('I', fontSize=8, fontName='Helvetica',
                                textColor=colors.grey, alignment=TA_CENTER, spaceAfter=12)

    story = []
    story.append(Paragraph(f"VKC Footwear — QR Code Sheet", title_style))
    story.append(Paragraph(f"Batch: {batch.batch_id} | Generated: {batch.created_at.strftime('%d %b %Y %H:%M')}", info_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e94560')))
    story.append(Spacer(1, 8))

    # Build grid: 4 per row
    QR_SIZE = 4.5 * cm
    items_per_row = 4
    row_data = []
    current_row = []

    for qr in qr_codes:
        if qr.qr_image and qr.qr_image.path and __import__('os').path.exists(qr.qr_image.path):
            cell_content = [
                RLImage(qr.qr_image.path, width=QR_SIZE, height=QR_SIZE),
                Paragraph(f"<b>Size {qr.size}</b>", ParagraphStyle('c', fontSize=8, alignment=TA_CENTER)),
                Paragraph(qr.article_number, ParagraphStyle('c2', fontSize=6, textColor=colors.grey, alignment=TA_CENTER)),
            ]
        else:
            cell_content = [Paragraph(f"QR\nSize {qr.size}", ParagraphStyle('c', fontSize=8, alignment=TA_CENTER))]
        current_row.append(cell_content)
        if len(current_row) == items_per_row:
            row_data.append(current_row)
            current_row = []

    if current_row:
        while len(current_row) < items_per_row:
            current_row.append([Spacer(1, 1)])
        row_data.append(current_row)

    if row_data:
        col_w = [QR_SIZE + 0.5*cm] * items_per_row
        t = Table(row_data, colWidths=col_w, rowHeights=[QR_SIZE + 1.5*cm] * len(row_data))
        t.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ]))
        story.append(t)

    doc.build(story)
    output.seek(0)
    return output
