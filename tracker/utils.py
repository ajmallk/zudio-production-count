import qrcode
import uuid
import os
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
import re

ARTICLE_SIZE_MAP = {
    36: '301070789001',
    37: '301070789002',
    38: '301070789003',
    39: '301070789004',
    40: '301070789005',
    41: '301070789006',
}

# Pre-load fonts once at import time to avoid repeated disk hits per QR
_FONT_LARGE  = None
_FONT_MEDIUM = None
_FONT_SMALL  = None
_FONT_CENTER = None   # big bold font for the centered size overlay


def _load_fonts():
    global _FONT_LARGE, _FONT_MEDIUM, _FONT_SMALL, _FONT_CENTER
    if _FONT_LARGE is not None:
        return
    try:
        font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'arial.ttf')
        _FONT_LARGE  = ImageFont.truetype(font_path, 24)
        _FONT_MEDIUM = ImageFont.truetype(font_path, 14)
        _FONT_SMALL  = ImageFont.truetype(font_path, 11)
        _FONT_CENTER = ImageFont.truetype(font_path, 20)   # center overlay
    except Exception:
        _FONT_LARGE  = ImageFont.load_default()
        _FONT_MEDIUM = ImageFont.load_default()
        _FONT_SMALL  = ImageFont.load_default()
        _FONT_CENTER = ImageFont.load_default()


def generate_qr_data(article_number, size, name=''):
    """Generate unique QR data string — compact format for fast scanning"""
    unique_id = str(uuid.uuid4()).replace('-', '')[:12].upper()
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    return f"FT-{article_number}-{size}-{unique_id}-{timestamp}"


def create_qr_image(qr_data, size, article_number, name=''):
    """
    Create QR code image.
    - Size label is rendered in the exact centre of the QR module grid
      inside a small white pill/badge so the QR is still scannable.
    - Article and Name labels appear below.
    Uses ERROR_CORRECT_H so the centre-overwrite zone is recoverable.
    """
    _load_fonts()

    # ERROR_CORRECT_H (30 %) gives us a safe area in the centre to overwrite
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=8,
        border=2,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="#1a1a2e", back_color="white").convert('RGBA')
    qr_width, qr_height = qr_img.size

    # ── Canvas ────────────────────────────────────────────────────────────
    # label_height: row for article + row for name (if present)
    label_height = 90 if name else 65
    canvas_width  = qr_width  + 20
    canvas_height = qr_height + label_height
    canvas = Image.new('RGBA', (canvas_width, canvas_height), (255, 255, 255, 255))
    canvas.paste(qr_img, (10, 5))

    draw = ImageDraw.Draw(canvas)

    # ── Centre overlay: SIZE badge ────────────────────────────────────────
    size_text = str(size)
    sb = draw.textbbox((0, 0), size_text, font=_FONT_CENTER)
    sw, sh = sb[2] - sb[0], sb[3] - sb[1]

    # Pill background: white rectangle with border, centred on QR
    pad_x, pad_y = 10, 5
    pill_w = sw + pad_x * 2
    pill_h = sh + pad_y * 2

    # QR image starts at (10, 5) on canvas
    qr_cx = 10 + qr_width  // 2
    qr_cy = 5  + qr_height // 2

    pill_x0 = qr_cx - pill_w // 2
    pill_y0 = qr_cy - pill_h // 2
    pill_x1 = pill_x0 + pill_w
    pill_y1 = pill_y0 + pill_h

    draw.rounded_rectangle(
        [pill_x0, pill_y0, pill_x1, pill_y1],
        radius=6,
        fill=(255, 255, 255, 240),
        outline="#e94560",
        width=2,
    )
    # Draw size number inside pill
    draw.text(
        (pill_x0 + pad_x - sb[0], pill_y0 + pad_y - sb[1]),
        size_text, fill="#e94560", font=_FONT_CENTER
    )

    # ── Row below QR: Article ─────────────────────────────────────────────
    art_text = f"Art: {article_number}"
    ab = draw.textbbox((0, 0), art_text, font=_FONT_MEDIUM)
    aw = ab[2] - ab[0]
    draw.text(
        ((canvas_width - aw) / 2, qr_height + 10),
        art_text, fill="#555555", font=_FONT_MEDIUM
    )

    # ── Row below: Name (large + prominent) ──────────────────────────────
    if name:
        name_text = name[:28]
        nb = draw.textbbox((0, 0), name_text, font=_FONT_LARGE)
        nw = nb[2] - nb[0]
        draw.text(
            ((canvas_width - nw) / 2, qr_height + 34),
            name_text, fill="#4f46e5", font=_FONT_LARGE   # large indigo
        )

    output = BytesIO()
    canvas.convert('RGB').save(output, format='PNG', optimize=True)
    output.seek(0)
    return output


def generate_qr_codes_for_batch(batch, order_items_data):
    """
    Efficiently generate QR codes for a batch using bulk_create.
    order_items_data: list of {'size': int, 'article': str, 'quantity': int, 'name': str}
    Returns list of created QRCode objects.
    """
    from .models import QRCode, OrderItem

    created = []
    for item in order_items_data:
        size     = item['size']
        quantity = item['quantity']
        article_number = item.get('article') or ARTICLE_SIZE_MAP.get(size, '')
        name           = item.get('name', '').strip()

        if not article_number:
            continue

        # Create or update the order item
        OrderItem.objects.get_or_create(
            batch=batch,
            size=size,
            defaults={
                'article_number': article_number,
                'name': name,
                'quantity': quantity,
            }
        )

        # Build QRCode objects in memory
        qr_objects = []
        for _ in range(quantity):
            qr_data = generate_qr_data(article_number, size, name)
            qr_objects.append(QRCode(
                batch=batch,
                article_number=article_number,
                name=name,
                size=size,
                qr_data=qr_data,
            ))

        # Bulk create then attach images
        QRCode.objects.bulk_create(qr_objects)
        for qr_obj in qr_objects:
            qr_img_bytes = create_qr_image(qr_obj.qr_data, size, article_number, name)
            filename = f"qr_{str(qr_obj.qr_id)[:8]}.png"
            qr_obj.qr_image.save(filename, ContentFile(qr_img_bytes.read()), save=True)
            created.append(qr_obj)

    return created


def parse_qr_data(qr_string):
    """
    Parse QR data string: FT-{article}-{size}-{uuid}-{timestamp}
    Returns dict or None
    """
    pattern = r'^FT-(\d+)-(\d+)-([A-Z0-9]+)-(\d{14})$'
    match = re.match(pattern, qr_string.strip())
    if match:
        return {
            'article': match.group(1),
            'size': int(match.group(2)),
            'uid': match.group(3),
            'timestamp': match.group(4),
        }
    return None


def extract_text_from_image(image_file):
    """
    Use pytesseract OCR to extract article number and size from image.
    Returns dict {'article': str, 'size': int} or None
    """
    try:
        import pytesseract
        img = Image.open(image_file)
        text = pytesseract.image_to_string(img)
        article_match = re.search(r'3010707890\d{2}', text.replace(' ', '').replace('\n', ''))
        size_match = re.search(r'\b(36|37|38|39|40|41)\b', text)
        if article_match and size_match:
            return {
                'article': article_match.group(0),
                'size': int(size_match.group(0))
            }
    except Exception as e:
        print(f"OCR Error: {e}")
    return None
