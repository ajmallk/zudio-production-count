from django.db import models
from django.contrib.auth.models import User
import uuid

# Fixed Article-Size Mapping
ARTICLE_SIZE_MAP = {
    36: '301070789001',
    37: '301070789002',
    38: '301070789003',
    39: '301070789004',
    40: '301070789005',
    41: '301070789006',
}

SIZE_CHOICES = [(s, str(s)) for s in sorted(ARTICLE_SIZE_MAP.keys())]


class ProductionBatch(models.Model):
    """Represents a production order batch"""
    batch_id = models.CharField(max_length=50, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    is_printed = models.BooleanField(default=False)
    printed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Batch {self.batch_id}"

    @property
    def total_qr_count(self):
        return self.qrcodes.count()

    @property
    def scanned_count(self):
        return self.qrcodes.filter(is_scanned=True).count()

    @property
    def unscanned_count(self):
        return self.total_qr_count - self.scanned_count

    class Meta:
        ordering = ['-created_at']


class QRCode(models.Model):
    """Individual QR code record"""
    qr_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    batch = models.ForeignKey(ProductionBatch, on_delete=models.CASCADE, related_name='qrcodes')
    article_number = models.CharField(max_length=20)
    size = models.IntegerField()
    qr_data = models.TextField()  # Full QR string: FT-{article}-{size}-{uuid}-{timestamp}
    qr_image = models.ImageField(upload_to='qrcodes/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_scanned = models.BooleanField(default=False)
    scanned_at = models.DateTimeField(null=True, blank=True)
    scanned_by_device = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"QR {self.qr_id} | Art:{self.article_number} | Size:{self.size}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_scanned'], name='qr_is_scanned_idx'),
            models.Index(fields=['size', 'is_scanned'], name='qr_size_scanned_idx'),
            models.Index(fields=['qr_data'], name='qr_data_idx'),
        ]


class ScanEvent(models.Model):
    """Audit log for every scan attempt"""
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('already_scanned', 'Already Scanned'),
        ('invalid', 'Invalid QR'),
    ]
    qr_code = models.ForeignKey(QRCode, on_delete=models.SET_NULL, null=True, blank=True, related_name='scan_events')
    scanned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    qr_data_raw = models.TextField()
    device_info = models.CharField(max_length=500, blank=True)
    scanned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"Scan [{self.status}] at {self.scanned_at}"

    class Meta:
        ordering = ['-scanned_at']
        indexes = [
            models.Index(fields=['status'], name='scan_status_idx'),
            models.Index(fields=['scanned_at'], name='scan_at_idx'),
            models.Index(fields=['qr_code', 'status'], name='scan_qr_status_idx'),
        ]


class OrderItem(models.Model):
    """Size + quantity line within a batch"""
    batch = models.ForeignKey(ProductionBatch, on_delete=models.CASCADE, related_name='order_items')
    size = models.IntegerField()
    article_number = models.CharField(max_length=20)
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"Size {self.size} x {self.quantity}"

    class Meta:
        unique_together = ('batch', 'size')
