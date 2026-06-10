from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Q
from django.urls import reverse
from .models import ProductionBatch, QRCode, ScanEvent, OrderItem


# ─── Custom Admin Site ─────────────────────────────────────────────────────────
class VKCAdminSite(admin.AdminSite):
    site_header  = "VKC QR Tracker — Admin"
    site_title   = "VKC Admin"
    index_title  = "Production Control Panel"
    site_url     = "/dashboard/"          # "View Site" link → app dashboard

admin_site = VKCAdminSite(name="vkc_admin")


# ─── Inline: OrderItems inside a Batch ────────────────────────────────────────
class OrderItemInline(admin.TabularInline):
    model   = OrderItem
    extra   = 0
    fields  = ['size', 'article_number', 'name', 'quantity']
    readonly_fields = []
    show_change_link = False


# ─── ProductionBatch ──────────────────────────────────────────────────────────
@admin.register(ProductionBatch)
class ProductionBatchAdmin(admin.ModelAdmin):
    list_display  = [
        'batch_badge', 'created_by', 'created_at_fmt',
        'total_qr_count', 'scanned_count', 'completion_bar',
        'print_status', 'printed_at_fmt',
    ]
    list_filter   = ['is_printed', 'created_at', 'created_by']
    search_fields = ['batch_id', 'notes', 'created_by__username']
    readonly_fields = ['batch_id', 'created_at', 'printed_at', 'total_qr_count', 'scanned_count']
    inlines       = [OrderItemInline]
    date_hierarchy = 'created_at'
    list_per_page = 25
    actions = ['mark_as_printed', 'mark_as_unprinted']

    fieldsets = [
        ('Batch Info', {
            'fields': ['batch_id', 'created_by', 'created_at', 'notes'],
        }),
        ('Print Status', {
            'fields': ['is_printed', 'printed_at'],
        }),
        ('Stats (read-only)', {
            'fields': ['total_qr_count', 'scanned_count'],
            'classes': ['collapse'],
        }),
    ]

    # ── Computed columns ──
    @admin.display(description='Batch ID', ordering='batch_id')
    def batch_badge(self, obj):
        url = reverse('admin:tracker_productionbatch_change', args=[obj.pk])
        return format_html(
            '<a href="{}" style="background:#eef2ff;color:#4f46e5;padding:3px 8px;'
            'border-radius:5px;font-size:0.78rem;font-weight:700;font-family:monospace;">{}</a>',
            url, obj.batch_id
        )

    @admin.display(description='Created', ordering='created_at')
    def created_at_fmt(self, obj):
        return format_html(
            '<span style="font-size:0.8rem;color:#64748b;">{}</span>',
            obj.created_at.strftime('%d %b %Y  %H:%M')
        )

    @admin.display(description='Printed At')
    def printed_at_fmt(self, obj):
        if obj.printed_at:
            return format_html(
                '<span style="font-size:0.8rem;color:#64748b;">{}</span>',
                obj.printed_at.strftime('%d %b %Y  %H:%M')
            )
        return format_html('<span style="color:#94a3b8;font-size:0.75rem;">—</span>')

    @admin.display(description='Completion')
    def completion_bar(self, obj):
        total   = obj.total_qr_count
        scanned = obj.scanned_count
        if total == 0:
            return format_html('<span style="color:#94a3b8;">—</span>')
        pct = round(scanned / total * 100)
        color = '#10b981' if pct >= 80 else '#f59e0b' if pct >= 50 else '#ef4444'
        return format_html(
            '<div style="display:flex;align-items:center;gap:6px;min-width:110px;">'
            '<div style="flex:1;background:#e2e8f0;border-radius:4px;height:6px;overflow:hidden;">'
            '<div style="width:{}%;background:{};height:100%;border-radius:4px;"></div></div>'
            '<span style="font-size:0.75rem;font-weight:700;color:{};">{}%</span></div>',
            pct, color, color, pct
        )

    @admin.display(description='Print', boolean=False, ordering='is_printed')
    def print_status(self, obj):
        if obj.is_printed:
            return format_html(
                '<span style="background:#d1fae5;color:#065f46;padding:2px 8px;'
                'border-radius:12px;font-size:0.73rem;font-weight:700;">✓ Printed</span>'
            )
        return format_html(
            '<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;'
            'border-radius:12px;font-size:0.73rem;font-weight:700;">✗ Pending</span>'
        )

    # ── Actions ──
    @admin.action(description="Mark selected batches as Printed")
    def mark_as_printed(self, request, queryset):
        updated = queryset.filter(is_printed=False).update(
            is_printed=True, printed_at=timezone.now()
        )
        self.message_user(request, f"✅ {updated} batch(es) marked as printed.")

    @admin.action(description="Mark selected batches as Unprinted")
    def mark_as_unprinted(self, request, queryset):
        updated = queryset.update(is_printed=False, printed_at=None)
        self.message_user(request, f"↩ {updated} batch(es) marked as unprinted.")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by')


# ─── QRCode ───────────────────────────────────────────────────────────────────
@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display  = [
        'qr_id_short', 'article_badge', 'size_badge', 'name',
        'batch_link', 'scan_status', 'scanned_at_fmt', 'created_at_fmt',
    ]
    list_filter   = ['is_scanned', 'size', 'article_number', 'created_at']
    search_fields = ['qr_id', 'qr_data', 'article_number', 'name', 'batch__batch_id']
    readonly_fields = ['qr_id', 'created_at', 'qr_image', 'qr_data', 'scanned_at']
    date_hierarchy = 'created_at'
    list_per_page = 50
    actions = ['mark_scanned', 'mark_unscanned']

    fieldsets = [
        ('Identity', {
            'fields': ['qr_id', 'batch', 'article_number', 'name', 'size'],
        }),
        ('QR Data', {
            'fields': ['qr_data', 'qr_image'],
            'classes': ['collapse'],
        }),
        ('Scan Status', {
            'fields': ['is_scanned', 'scanned_at', 'scanned_by_device'],
        }),
        ('Timestamps', {
            'fields': ['created_at'],
            'classes': ['collapse'],
        }),
    ]

    @admin.display(description='QR ID', ordering='qr_id')
    def qr_id_short(self, obj):
        s = str(obj.qr_id)
        return format_html(
            '<span title="{}" style="font-family:monospace;font-size:0.75rem;'
            'color:#4f46e5;background:#eef2ff;padding:2px 6px;border-radius:4px;">{}…</span>',
            s, s[:12]
        )

    @admin.display(description='Article', ordering='article_number')
    def article_badge(self, obj):
        return format_html(
            '<code style="background:#f0fdf4;color:#15803d;padding:2px 7px;'
            'border-radius:4px;font-size:0.75rem;">{}</code>',
            obj.article_number
        )

    @admin.display(description='Size', ordering='size')
    def size_badge(self, obj):
        return format_html(
            '<span style="background:#ede9fe;color:#5b21b6;padding:2px 8px;'
            'border-radius:12px;font-size:0.78rem;font-weight:700;">{}</span>',
            obj.size
        )

    @admin.display(description='Batch', ordering='batch__batch_id')
    def batch_link(self, obj):
        url = reverse('admin:tracker_productionbatch_change', args=[obj.batch_id])
        return format_html(
            '<a href="{}" style="color:#4f46e5;font-size:0.78rem;font-weight:600;'
            'text-decoration:none;">{}</a>',
            url, str(obj.batch.batch_id)[:18] + '…'
        )

    @admin.display(description='Status', ordering='is_scanned')
    def scan_status(self, obj):
        if obj.is_scanned:
            return format_html(
                '<span style="background:#d1fae5;color:#065f46;padding:2px 10px;'
                'border-radius:12px;font-size:0.73rem;font-weight:700;">✓ Scanned</span>'
            )
        return format_html(
            '<span style="background:#fef3c7;color:#92400e;padding:2px 10px;'
            'border-radius:12px;font-size:0.73rem;font-weight:700;">◌ Pending</span>'
        )

    @admin.display(description='Scanned At')
    def scanned_at_fmt(self, obj):
        if obj.scanned_at:
            return format_html(
                '<span style="font-size:0.78rem;color:#64748b;">{}</span>',
                obj.scanned_at.strftime('%d %b %Y  %H:%M')
            )
        return format_html('<span style="color:#cbd5e1;font-size:0.75rem;">—</span>')

    @admin.display(description='Created', ordering='created_at')
    def created_at_fmt(self, obj):
        return format_html(
            '<span style="font-size:0.78rem;color:#94a3b8;">{}</span>',
            obj.created_at.strftime('%d %b %Y')
        )

    @admin.action(description="Mark selected QR codes as Scanned")
    def mark_scanned(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(is_scanned=False).update(
            is_scanned=True, scanned_at=now
        )
        self.message_user(request, f"✅ {updated} QR code(s) marked as scanned.")

    @admin.action(description="Reset selected QR codes to Unscanned")
    def mark_unscanned(self, request, queryset):
        updated = queryset.update(is_scanned=False, scanned_at=None, scanned_by_device='')
        self.message_user(request, f"↩ {updated} QR code(s) reset to unscanned.")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('batch')


# ─── ScanEvent ────────────────────────────────────────────────────────────────
@admin.register(ScanEvent)
class ScanEventAdmin(admin.ModelAdmin):
    list_display  = [
        'scanned_at_fmt', 'status_badge', 'qr_link',
        'article_info', 'size_info', 'scanned_by', 'device_short',
    ]
    list_filter   = ['status', 'scanned_at', 'scanned_by']
    search_fields = ['qr_data_raw', 'device_info', 'scanned_by__username',
                     'qr_code__article_number']
    readonly_fields = ['scanned_at', 'qr_code', 'qr_data_raw', 'device_info',
                       'status', 'scanned_by']
    date_hierarchy = 'scanned_at'
    list_per_page = 50

    @admin.display(description='Timestamp', ordering='scanned_at')
    def scanned_at_fmt(self, obj):
        return format_html(
            '<span style="font-size:0.8rem;white-space:nowrap;color:#475569;">{}</span>',
            obj.scanned_at.strftime('%d %b %Y  %H:%M:%S')
        )

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        colors = {
            'success':        ('#d1fae5', '#065f46'),
            'already_scanned':('#fef3c7', '#92400e'),
            'invalid':        ('#fee2e2', '#991b1b'),
        }
        bg, fg = colors.get(obj.status, ('#f1f5f9', '#475569'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;'
            'border-radius:12px;font-size:0.73rem;font-weight:700;">{}</span>',
            bg, fg, obj.get_status_display()
        )

    @admin.display(description='QR Code')
    def qr_link(self, obj):
        if obj.qr_code:
            url = reverse('admin:tracker_qrcode_change', args=[obj.qr_code_id])
            s   = str(obj.qr_code.qr_id)
            return format_html(
                '<a href="{}" style="font-family:monospace;font-size:0.73rem;color:#4f46e5;">'
                '{}…</a>', url, s[:12]
            )
        return format_html('<span style="color:#ef4444;font-size:0.75rem;">N/A</span>')

    @admin.display(description='Article')
    def article_info(self, obj):
        if obj.qr_code:
            return format_html(
                '<code style="background:#f0fdf4;color:#15803d;padding:2px 6px;'
                'border-radius:4px;font-size:0.73rem;">{}</code>',
                obj.qr_code.article_number
            )
        return '—'

    @admin.display(description='Size')
    def size_info(self, obj):
        if obj.qr_code:
            return format_html(
                '<span style="background:#ede9fe;color:#5b21b6;padding:2px 7px;'
                'border-radius:10px;font-size:0.75rem;font-weight:700;">{}</span>',
                obj.qr_code.size
            )
        return '—'

    @admin.display(description='Device')
    def device_short(self, obj):
        d = obj.device_info or ''
        short = (d[:35] + '…') if len(d) > 35 else d
        return format_html(
            '<span style="font-size:0.72rem;color:#94a3b8;" title="{}">{}</span>',
            d, short or '—'
        )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'qr_code', 'scanned_by'
        )

    def has_add_permission(self, request):
        return False   # Scan events are created by the system only

    def has_change_permission(self, request, obj=None):
        return False   # Read-only audit log


# ─── OrderItem ────────────────────────────────────────────────────────────────
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = [
        'batch_link', 'size_badge', 'article_badge', 'name', 'quantity_badge',
    ]
    list_filter  = ['size', 'article_number']
    search_fields = ['batch__batch_id', 'article_number', 'name']
    list_per_page = 50

    @admin.display(description='Batch', ordering='batch__batch_id')
    def batch_link(self, obj):
        url = reverse('admin:tracker_productionbatch_change', args=[obj.batch_id])
        return format_html(
            '<a href="{}" style="color:#4f46e5;font-size:0.8rem;font-weight:600;'
            'text-decoration:none;font-family:monospace;">{}</a>',
            url, str(obj.batch.batch_id)[:20]
        )

    @admin.display(description='Size', ordering='size')
    def size_badge(self, obj):
        return format_html(
            '<span style="background:#ede9fe;color:#5b21b6;padding:2px 8px;'
            'border-radius:12px;font-size:0.8rem;font-weight:700;">{}</span>',
            obj.size
        )

    @admin.display(description='Article', ordering='article_number')
    def article_badge(self, obj):
        return format_html(
            '<code style="background:#f0fdf4;color:#15803d;padding:2px 7px;'
            'border-radius:4px;font-size:0.75rem;">{}</code>',
            obj.article_number
        )

    @admin.display(description='Qty', ordering='quantity')
    def quantity_badge(self, obj):
        return format_html(
            '<span style="background:#dbeafe;color:#1e40af;padding:2px 10px;'
            'border-radius:12px;font-size:0.82rem;font-weight:800;">{}</span>',
            obj.quantity
        )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('batch')
