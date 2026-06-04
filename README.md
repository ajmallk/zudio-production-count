# VKC Footwear — Production & QR Stock Tracking System

A comprehensive Django web application for tracking footwear production and stock using QR codes.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 13+
- Tesseract OCR (optional, for image-based article extraction)

### 1. Install Dependencies
```bash
pip install django psycopg2-binary pillow qrcode reportlab openpyxl pytesseract django-crispy-forms crispy-bootstrap5 djangorestframework
```

### 2. Configure Database
Edit `vkc_footwear/settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'vkc_footwear_db',
        'USER': 'postgres',
        'PASSWORD': 'your_password',   # ← Change this
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 3. Create Database
```sql
-- In psql or pgAdmin:
CREATE DATABASE vkc_footwear_db;
```

### 4. Run Migrations
```bash
python manage.py migrate
```

### 5. Create Users
```bash
python create_users.py
```

### 6. Start Server
```bash
python manage.py runserver
```

Visit: **http://127.0.0.1:8000**

---

## 🔐 Login Credentials

| Role  | Username | Password  |
|-------|----------|-----------|
| Admin | `admin`  | `admin123` |
| Staff | `staff`  | `staff123` |

---

## 📱 Features

### Order Creation (3-Step Flow)
1. **Add Items** — Select size (auto-fills article number), enter quantity, repeat for multiple sizes
2. **Review** — Full summary table with total QR count
3. **Generate** — Creates unique QR codes with UUID + timestamp, saves to DB

### QR Code Format
```
FT-{article}-{size}-{uuid12}-{timestamp}
Example: FT-301070789001-36-A1B2C3D4E5F6-20260603143000
```

### Scanning
- Full-screen camera view with corner frame overlay
- **Success**: Green card + beep sound + phone vibration
- **Duplicate**: Yellow warning with first scan timestamp
- **Invalid**: Red error card
- **Offline mode**: Queues scans in browser storage, syncs automatically when back online

### Article-Size Mapping
| Size | Article Number   |
|------|-----------------|
| 36   | 301070789001    |
| 37   | 301070789002    |
| 38   | 301070789003    |
| 39   | 301070789004    |
| 40   | 301070789005    |
| 41   | 301070789006    |

### Reports
- **Production Report**: QR codes printed by date/article/size
- **Stock Report**: Scanned vs unscanned with % completion
- **Audit Log**: Every scan event with timestamp, device, status
- **Filters**: Today / Week / Month / Year / Custom Date Range
- **Exports**: Excel (.xlsx) and PDF in one click

---

## 🗂 Project Structure
```
myproduct-count/
├── vkc_footwear/          # Django project settings
│   ├── settings.py
│   └── urls.py
├── tracker/               # Main app
│   ├── models.py          # ProductionBatch, QRCode, ScanEvent, OrderItem
│   ├── views.py           # All views
│   ├── urls.py            # URL routing
│   ├── utils.py           # QR generation, OCR
│   ├── reports.py         # PDF & Excel generators
│   └── admin.py
├── templates/tracker/     # HTML templates
│   ├── base.html          # Sidebar layout
│   ├── login.html
│   ├── dashboard.html
│   ├── create_order.html
│   ├── review_order.html
│   ├── batch_detail.html
│   ├── batch_list.html
│   ├── scanner.html
│   └── reports.html
├── static/                # Static files
├── media/                 # QR code images
├── manage.py
├── create_users.py
└── setup_and_run.bat
```

---

## 🖨 PDF Print Sheet
Navigate to any Batch → **"Print Entire Order"** — generates a PDF with 4 QR codes per row, labeled with size and article number.

## 🔌 Tesseract OCR (Optional)
Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki  
Add to PATH, then OCR image upload will work.

---

© 2026 VKC Fortune Elastomers Private Limited
