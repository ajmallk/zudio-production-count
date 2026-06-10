"""
Quick setup script - run after starting PostgreSQL
"""
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vkc_footwear.settings')

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.contrib.auth.models import User

# Create superuser (admin)
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@vkc.com', 'admin123')
    print("[OK] Admin user created: username=admin, password=admin123")
else:
    print("[INFO] Admin user already exists")

# Create staff user
if not User.objects.filter(username='staff').exists():
    User.objects.create_user('staff', 'staff@vkc.com', 'staff123')
    print("[OK] Staff user created: username=staff, password=staff123")
else:
    print("[INFO] Staff user already exists")

print("\n[OK] Setup complete!")
print("\n Login Credentials:")
print("   Admin  -> username: admin   | password: admin123")
print("   Staff  -> username: staff   | password: staff123")
print("\n[*] Run the server: python manage.py runserver")
