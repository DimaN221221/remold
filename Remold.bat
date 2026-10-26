@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem Запуск Remold з вихідного коду; при першому запуску встановлює залежності
python -c "import webview, PIL, pillow_heif, imageio_ffmpeg, pymupdf, docx, openpyxl, markdown" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    python -m pip install -r requirements.txt
)

start "" pythonw main.py %*
