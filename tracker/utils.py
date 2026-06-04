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


def generate_qr_data(article_number, size):
    """Generate unique QR data string"""
    unique_id = str(uuid.uuid4()).replace('-', '')[:12].upper()
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    return f"FT-{article_number}-{size}-{unique_id}-{timestamp}"


def create_qr_image(qr_data, size, article_number):
    """Create QR code image with size displayed in center"""
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=8,
        border=2,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    # Generate QR as image
    qr_img = qr.make_image(fill_color="#1a1a2e", back_color="white").convert('RGBA')
    qr_width, qr_height = qr_img.size

    # Create final canvas with label space
    canvas_width = qr_width + 40
    canvas_height = qr_height + 80
    canvas = Image.new('RGBA', (canvas_width, canvas_height), (255, 255, 255, 255))

    # Paste QR
    canvas.paste(qr_img, (20, 10))

    # Draw size label at bottom
    draw = ImageDraw.Draw(canvas)

    # Try to load a font, fall back to default
    try:
        font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'arial.ttf')
        font_large = ImageFont.truetype(font_path, 28)
        font_small = ImageFont.truetype(font_path, 14)
    except Exception:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Size label
    size_text = f"SIZE: {size}"
    bbox = draw.textbbox((0, 0), size_text, font=font_large)
    text_w = bbox[2] - bbox[0]
    draw.text(
        ((canvas_width - text_w) / 2, qr_height + 15),
        size_text,
        fill="#e94560",
        font=font_large
    )

    # Article label
    art_text = f"Art: {article_number}"
    bbox2 = draw.textbbox((0, 0), art_text, font=font_small)
    text_w2 = bbox2[2] - bbox2[0]
    draw.text(
        ((canvas_width - text_w2) / 2, qr_height + 50),
        art_text,
        fill="#666666",
        font=font_small
    )

    # Save to bytes
    output = BytesIO()
    canvas = canvas.convert('RGB')
    canvas.save(output, format='PNG', quality=95)
    output.seek(0)
    return output


def generate_qr_codes_for_batch(batch, order_items_data):
    """
    Generate QR codes for a batch.
    order_items_data: list of {'size': int, 'quantity': int}
    Returns list of created QRCode objects
    """
    from .models import QRCode, OrderItem

    created = []
    for item in order_items_data:
        size = item['size']
        quantity = item['quantity']
        article_number = ARTICLE_SIZE_MAP.get(size, '')

        if not article_number:
            continue

        # Create or get the order item
        order_item, _ = OrderItem.objects.get_or_create(
            batch=batch,
            size=size,
            defaults={'article_number': article_number, 'quantity': quantity}
        )

        for _ in range(quantity):
            qr_data = generate_qr_data(article_number, size)
            qr_img_bytes = create_qr_image(qr_data, size, article_number)

            qr_obj = QRCode(
                batch=batch,
                article_number=article_number,
                size=size,
                qr_data=qr_data,
            )
            filename = f"qr_{str(qr_obj.qr_id)[:8]}.png"
            qr_obj.qr_image.save(filename, ContentFile(qr_img_bytes.read()), save=False)
            qr_obj.save()
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

        # Look for article number pattern
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
