#!/usr/bin/env bash
set -e

echo "=== Synchronizing Remote Database Schema ==="
python scripts/init_db.py

echo "=== Booting Production Office API Engine ==="
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2