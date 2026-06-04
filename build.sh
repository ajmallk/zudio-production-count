#!/usr/bin/env bash
# build.sh — Render build script for VKC Footwear QR Tracking System
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate
