import json
import uuid
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.db.models import Count, Q, Sum
from django.contrib.auth import authenticate, login, logout

from .models import ProductionBatch, QRCode, ScanEvent, OrderItem, ARTICLE_SIZE_MAP
from .forms import OrderItemForm, BatchNotesForm, OCRUploadForm, DateRangeFilterForm
from .utils import generate_qr_codes_for_batch, parse_qr_data, extract_text_from_image
from .reports import generate_excel_report, generate_pdf_report, generate_batch_pdf


# ─────────────────────────────────────────────────────
#  AUTH
# ─────────────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect(request.GET.get('next', 'dashboard'))
        error = 'Invalid username or password.'
    return render(request, 'tracker/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')


# ─────────────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────────────
@login_required
def dashboard(request):
    total_printed = QRCode.objects.count()
    total_scanned = QRCode.objects.filter(is_scanned=True).count()
    total_unscanned = total_printed - total_scanned

    # Recent batches
    recent_batches = ProductionBatch.objects.all()[:8]

    # Breakdown by article/size
    breakdown = []
    for size, article in sorted(ARTICLE_SIZE_MAP.items()):
        printed = QRCode.objects.filter(size=size).count()
        scanned = QRCode.objects.filter(size=size, is_scanned=True).count()
        if printed > 0:
            breakdown.append({
                'size': size,
                'article': article,
                'printed': printed,
                'scanned': scanned,
                'unscanned': printed - scanned,
                'pct': round(scanned / printed * 100, 1),
            })

    # Today's stats
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_printed = QRCode.objects.filter(created_at__gte=today_start).count()
    today_scanned = QRCode.objects.filter(is_scanned=True, scanned_at__gte=today_start).count()

    # Recent scans
    recent_scans = ScanEvent.objects.select_related('qr_code').order_by('-scanned_at')[:10]

    context = {
        'total_printed': total_printed,
        'total_scanned': total_scanned,
        'total_unscanned': total_unscanned,
        'today_printed': today_printed,
        'today_scanned': today_scanned,
        'recent_batches': recent_batches,
        'breakdown': breakdown,
        'recent_scans': recent_scans,
        'completion_pct': round(total_scanned / total_printed * 100, 1) if total_printed > 0 else 0,
    }
    return render(request, 'tracker/dashboard.html', context)


# ─────────────────────────────────────────────────────
#  ORDER CREATION (3-STEP)
# ─────────────────────────────────────────────────────
@login_required
def create_order(request):
    """Step 1 & 2: Build order items in session"""
    # Load session cart
    cart = request.session.get('order_cart', [])
    article_map = {str(k): v for k, v in ARTICLE_SIZE_MAP.items()}

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'add_item':
            size = int(request.POST.get('size', 0))
            quantity = int(request.POST.get('quantity', 0))
            if size in ARTICLE_SIZE_MAP and quantity > 0:
                # Check duplicate size
                for item in cart:
                    if item['size'] == size:
                        item['quantity'] = quantity
                        break
                else:
                    cart.append({
                        'size': size,
                        'article': ARTICLE_SIZE_MAP[size],
                        'quantity': quantity
                    })
                request.session['order_cart'] = cart
                messages.success(request, f"Size {size} × {quantity} added to order.")
            else:
                messages.error(request, "Invalid size or quantity.")

        elif action == 'remove_item':
            size = int(request.POST.get('size', 0))
            cart = [i for i in cart if i['size'] != size]
            request.session['order_cart'] = cart

        elif action == 'clear_cart':
            request.session['order_cart'] = []
            cart = []

        return redirect('create_order')

    form = OrderItemForm()
    ocr_form = OCRUploadForm()
    total_qty = sum(i['quantity'] for i in cart)

    return render(request, 'tracker/create_order.html', {
        'form': form,
        'ocr_form': ocr_form,
        'cart': cart,
        'total_qty': total_qty,
        'article_map_json': json.dumps(article_map),
        'size_choices': sorted(ARTICLE_SIZE_MAP.keys()),
    })


@login_required
def ocr_upload(request):
    """Handle OCR image upload, return extracted article+size as JSON"""
    if request.method == 'POST':
        form = OCRUploadForm(request.POST, request.FILES)
        if form.is_valid():
            result = extract_text_from_image(request.FILES['image'])
            if result:
                # Validate against map
                size = result['size']
                expected_article = ARTICLE_SIZE_MAP.get(size)
                if expected_article and result['article'] == expected_article:
                    return JsonResponse({'success': True, 'article': result['article'], 'size': size})
                else:
                    return JsonResponse({'success': False, 'error': f'Article-size mismatch. Expected {expected_article} for size {size}.'})
            return JsonResponse({'success': False, 'error': 'Could not extract article number and size from image. Please try a clearer image or enter manually.'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def review_order(request):
    """Step 3: Review and confirm order"""
    cart = request.session.get('order_cart', [])
    if not cart:
        messages.error(request, 'Your order is empty. Please add items first.')
        return redirect('create_order')

    total_qty = sum(i['quantity'] for i in cart)
    notes_form = BatchNotesForm()

    return render(request, 'tracker/review_order.html', {
        'cart': cart,
        'total_qty': total_qty,
        'notes_form': notes_form,
    })


@login_required
def generate_batch(request):
    """Generate QR codes for the confirmed batch"""
    if request.method != 'POST':
        return redirect('create_order')

    cart = request.session.get('order_cart', [])
    if not cart:
        messages.error(request, 'Order is empty.')
        return redirect('create_order')

    notes = request.POST.get('notes', '')

    # Create batch
    batch_id = f"BATCH-{timezone.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:6].upper()}"
    batch = ProductionBatch.objects.create(
        batch_id=batch_id,
        created_by=request.user,
        notes=notes,
    )

    # Generate QR codes
    generate_qr_codes_for_batch(batch, cart)

    # Clear cart
    request.session['order_cart'] = []

    messages.success(request, f'✅ Batch {batch_id} created with {batch.total_qr_count} QR codes!')
    return redirect('batch_detail', batch_id=batch.id)


@login_required
def batch_detail(request, batch_id):
    """View a batch and its QR codes"""
    batch = get_object_or_404(ProductionBatch, id=batch_id)
    qr_codes = batch.qrcodes.all().order_by('size', 'created_at')
    sizes = qr_codes.values_list('size', flat=True).distinct().order_by('size')

    # Filter by size if requested
    filter_size = request.GET.get('size')
    if filter_size:
        qr_codes = qr_codes.filter(size=filter_size)

    return render(request, 'tracker/batch_detail.html', {
        'batch': batch,
        'qr_codes': qr_codes,
        'sizes': sizes,
        'filter_size': filter_size,
        'order_items': batch.order_items.all(),
    })


@login_required
def print_batch(request, batch_id):
    """Download printable PDF of QR codes"""
    batch = get_object_or_404(ProductionBatch, id=batch_id)
    pdf_bytes = generate_batch_pdf(batch)

    # Mark as printed
    if not batch.is_printed:
        batch.is_printed = True
        batch.printed_at = timezone.now()
        batch.save()

    response = HttpResponse(pdf_bytes.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="VKC_Batch_{batch.batch_id}.pdf"'
    return response


@login_required
def batch_list(request):
    batches = ProductionBatch.objects.all()
    return render(request, 'tracker/batch_list.html', {'batches': batches})


# ─────────────────────────────────────────────────────
#  SCANNING
# ─────────────────────────────────────────────────────
@login_required
def scanner(request):
    return render(request, 'tracker/scanner.html')


@login_required
@require_POST
def process_scan(request):
    """Process a scanned QR code"""
    try:
        data = json.loads(request.body)
        qr_string = data.get('qr_data', '').strip()
        device_info = data.get('device_info', '')[:500]
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Invalid request data'})

    if not qr_string:
        return JsonResponse({'status': 'invalid', 'message': 'Empty QR data'})

    # Try to find QR by qr_data field
    try:
        qr_obj = QRCode.objects.get(qr_data=qr_string)
    except QRCode.DoesNotExist:
        # Log invalid scan
        ScanEvent.objects.create(
            qr_code=None,
            status='invalid',
            qr_data_raw=qr_string[:500],
            device_info=device_info,
            scanned_by=request.user,
        )
        return JsonResponse({
            'status': 'invalid',
            'message': '❌ Invalid QR Code — not found in system',
        })

    if qr_obj.is_scanned:
        ScanEvent.objects.create(
            qr_code=qr_obj,
            status='already_scanned',
            qr_data_raw=qr_string[:500],
            device_info=device_info,
            scanned_by=request.user,
        )
        return JsonResponse({
            'status': 'already_scanned',
            'message': f'⚠️ Already Scanned',
            'scanned_at': qr_obj.scanned_at.strftime('%d %b %Y %H:%M:%S') if qr_obj.scanned_at else '',
            'size': qr_obj.size,
            'article': qr_obj.article_number,
        })

    # Mark as scanned
    qr_obj.is_scanned = True
    qr_obj.scanned_at = timezone.now()
    qr_obj.scanned_by_device = device_info[:200]
    qr_obj.save()

    ScanEvent.objects.create(
        qr_code=qr_obj,
        status='success',
        qr_data_raw=qr_string[:500],
        device_info=device_info,
        scanned_by=request.user,
    )

    # Live count for this size
    size_scanned = QRCode.objects.filter(size=qr_obj.size, is_scanned=True).count()
    size_total = QRCode.objects.filter(size=qr_obj.size).count()

    return JsonResponse({
        'status': 'success',
        'message': f'✅ +1 Added — Size {qr_obj.size}',
        'size': qr_obj.size,
        'article': qr_obj.article_number,
        'batch': qr_obj.batch.batch_id,
        'size_scanned': size_scanned,
        'size_total': size_total,
    })


# ─────────────────────────────────────────────────────
#  REPORTS
# ─────────────────────────────────────────────────────
@login_required
def reports(request):
    form = DateRangeFilterForm(request.GET or None)
    period = request.GET.get('period', 'month')
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')

    date_from = None
    date_to = None
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    from .reports import build_report_data, get_date_range
    production_data, stock_data, audit_data, start_dt, end_dt = build_report_data(period, date_from, date_to)

    return render(request, 'tracker/reports.html', {
        'form': form,
        'production_data': production_data,
        'stock_data': stock_data,
        'audit_data': audit_data[:50],
        'period': period,
        'date_from': date_from_str or '',
        'date_to': date_to_str or '',
        'start_dt': start_dt,
        'end_dt': end_dt,
    })


@login_required
def export_excel(request):
    period = request.GET.get('period', 'month')
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else None
    date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else None

    excel_bytes = generate_excel_report(period, date_from, date_to)
    filename = f"VKC_Report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response = HttpResponse(
        excel_bytes.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_pdf(request):
    period = request.GET.get('period', 'month')
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else None
    date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else None

    pdf_bytes = generate_pdf_report(period, date_from, date_to)
    filename = f"VKC_Report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response = HttpResponse(pdf_bytes.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─────────────────────────────────────────────────────
#  API (for offline scan queue sync)
# ─────────────────────────────────────────────────────
@login_required
@require_POST
def sync_offline_scans(request):
    """Sync offline scan queue"""
    try:
        data = json.loads(request.body)
        scans = data.get('scans', [])
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid data'})

    results = []
    for scan in scans:
        qr_string = scan.get('qr_data', '').strip()
        device_info = scan.get('device_info', '')[:500]

        try:
            qr_obj = QRCode.objects.get(qr_data=qr_string)
        except QRCode.DoesNotExist:
            ScanEvent.objects.create(
                status='invalid', qr_data_raw=qr_string[:500],
                device_info=device_info, scanned_by=request.user
            )
            results.append({'qr': qr_string, 'status': 'invalid'})
            continue

        if qr_obj.is_scanned:
            results.append({'qr': qr_string, 'status': 'already_scanned'})
            continue

        qr_obj.is_scanned = True
        qr_obj.scanned_at = timezone.now()
        qr_obj.scanned_by_device = device_info[:200]
        qr_obj.save()

        ScanEvent.objects.create(
            qr_code=qr_obj, status='success',
            qr_data_raw=qr_string[:500],
            device_info=device_info, scanned_by=request.user
        )
        results.append({'qr': qr_string, 'status': 'success'})

    return JsonResponse({'success': True, 'results': results})


# ─────────────────────────────────────────────────────
#  LIVE DASHBOARD STATS (AJAX)
# ─────────────────────────────────────────────────────
@login_required
def live_stats(request):
    total_printed = QRCode.objects.count()
    total_scanned = QRCode.objects.filter(is_scanned=True).count()
    return JsonResponse({
        'total_printed': total_printed,
        'total_scanned': total_scanned,
        'total_unscanned': total_printed - total_scanned,
        'completion_pct': round(total_scanned / total_printed * 100, 1) if total_printed else 0,
    })
