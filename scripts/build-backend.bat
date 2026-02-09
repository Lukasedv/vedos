@echo off
setlocal

cd /d "%~dp0\..\backend"

echo [build-backend] Installing PyInstaller if needed...
pip install pyinstaller 2>nul

echo [build-backend] Building vedos-backend with PyInstaller...
python -m PyInstaller --noconfirm --onedir --name vedos-backend vedos\app.py
if errorlevel 1 (
    echo [build-backend] PyInstaller failed.
    exit /b 1
)

echo [build-backend] Copying output to backend-dist...
if exist "..\backend-dist" rmdir /s /q "..\backend-dist"
xcopy /E /I /Y dist\vedos-backend ..\backend-dist

echo [build-backend] Done.
