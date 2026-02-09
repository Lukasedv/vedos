#!/bin/bash
set -e

cd "$(dirname "$0")/../backend"

echo "[build-backend] Installing PyInstaller if needed..."
pip install pyinstaller 2>/dev/null || true

echo "[build-backend] Building vedos-backend with PyInstaller..."
python -m PyInstaller --noconfirm --onedir --name vedos-backend vedos/app.py

echo "[build-backend] Copying output to backend-dist/..."
rm -rf ../backend-dist
cp -r dist/vedos-backend ../backend-dist/

echo "[build-backend] Done."
