from django.contrib import admin
from .models import ProductionBatch, QRCode, ScanEvent, OrderItem


@admin.register(ProductionBatch)
class ProductionBatchAdmin(admin.ModelAdmin):
    list_display = ['batch_id', 'created_by', 'created_at', 'total_qr_count', 'scanned_count', 'is_printed']
    list_filter = ['is_printed', 'created_at']
    search_fields = ['batch_id', 'notes']
    readonly_fields = ['batch_id', 'created_at', 'printed_at']


@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ['qr_id', 'article_number', 'size', 'batch', 'is_scanned', 'scanned_at']
    list_filter = ['is_scanned', 'size', 'article_number']
    search_fields = ['qr_data', 'article_number']
    readonly_fields = ['qr_id', 'created_at']


@admin.register(ScanEvent)
class ScanEventAdmin(admin.ModelAdmin):
    list_display = ['scanned_at', 'status', 'qr_code', 'scanned_by', 'device_info']
    list_filter = ['status', 'scanned_at']
    readonly_fields = ['scanned_at']


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['batch', 'size', 'article_number', 'quantity']
    list_filter = ['size']
