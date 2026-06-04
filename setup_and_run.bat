@echo off
echo ============================================
echo  VKC Footwear QR Tracker - Setup Script
echo ============================================
echo.

REM Check if PostgreSQL is running
echo [1/5] Checking PostgreSQL...
psql -U postgres -c "SELECT 1;" 2>nul
if %errorlevel% neq 0 (
    echo WARNING: PostgreSQL is not running or credentials incorrect.
    echo Please start PostgreSQL and update settings.py with your credentials.
    echo Default: USER=postgres, PASSWORD=admin, DB=vkc_footwear_db
    echo.
)

REM Create database
echo [2/5] Creating database vkc_footwear_db...
psql -U postgres -c "CREATE DATABASE vkc_footwear_db;" 2>nul
echo (Ignore error if database already exists)
echo.

REM Run migrations
echo [3/5] Running database migrations...
python manage.py migrate
echo.

REM Create superuser
echo [4/5] Creating admin user...
echo from django.contrib.auth.models import User; User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@vkc.com', 'admin123') | python manage.py shell
echo.

REM Create staff user
echo [5/5] Creating staff user...
echo from django.contrib.auth.models import User; User.objects.filter(username='staff').exists() or User.objects.create_user('staff', 'staff@vkc.com', 'staff123') | python manage.py shell
echo.

echo ============================================
echo  Setup Complete!
echo ============================================
echo.
echo  Admin Login:  username=admin   password=admin123
echo  Staff Login:  username=staff   password=staff123
echo.
echo  Starting development server at http://127.0.0.1:8000
echo.
python manage.py runserver
