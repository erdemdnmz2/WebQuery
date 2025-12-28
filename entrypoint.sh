#!/bin/bash
set -e

# Veritabanını oluştur (eğer yoksa)
python create_db.py

# Uygulamayı başlat
exec "$@"
