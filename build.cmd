@echo off
rem dist\KafeKamera.exe uretir (tek dosya; hedef bilgisayarda Python gerekmez).
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  py -3.12 -m venv .venv || python -m venv .venv || goto :hata
)
.venv\Scripts\python -m pip install -q --upgrade pip || goto :hata
.venv\Scripts\python -m pip install -q -r requirements.txt pyinstaller==6.22.3 || goto :hata

rem YOLO11s-pose agirliklari (Ultralytics, AGPL-3.0) depoda gelir; ozeti kontrol edilir
.venv\Scripts\python -c "import hashlib,sys; h=hashlib.sha256(open('modeller/yolo11s-pose.pt','rb').read()).hexdigest(); sys.exit(0 if h=='1060bda4a27012060eca246f9b2adeea22eabb045a1e58f8d229be29b7ebc2ba' else 'model ozeti tutmuyor: '+h)" || goto :hata

.venv\Scripts\python packaging\make_icon.py || goto :hata
.venv\Scripts\pyinstaller --noconfirm --clean KafeKamera.spec || goto :hata

echo.
echo Hazir: %cd%\dist\KafeKamera.exe
exit /b 0

:hata
echo Derleme basarisiz.
exit /b 1
