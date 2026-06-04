from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('', views.dashboard, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api/live-stats/', views.live_stats, name='live_stats'),

    # Order creation
    path('orders/create/', views.create_order, name='create_order'),
    path('orders/ocr/', views.ocr_upload, name='ocr_upload'),
    path('orders/review/', views.review_order, name='review_order'),
    path('orders/generate/', views.generate_batch, name='generate_batch'),
    path('orders/', views.batch_list, name='batch_list'),
    path('orders/batch/<int:batch_id>/', views.batch_detail, name='batch_detail'),
    path('orders/batch/<int:batch_id>/print/', views.print_batch, name='print_batch'),

    # Scanner
    path('scanner/', views.scanner, name='scanner'),
    path('api/scan/', views.process_scan, name='process_scan'),
    path('api/sync-offline/', views.sync_offline_scans, name='sync_offline'),

    # Reports
    path('reports/', views.reports, name='reports'),
    path('reports/export/excel/', views.export_excel, name='export_excel'),
    path('reports/export/pdf/', views.export_pdf, name='export_pdf'),
]
