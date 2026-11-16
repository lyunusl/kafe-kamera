@echo off
rem Kafe Kamera: tek dosyalik exe (dist\arayuzsuz\KafeKamera.exe) ve kurulum dosyasi (dist\kurulum\KafeKamera-Kurulum-0.3.0.exe).
rem Exe'de torch ve ultralytics yoktur: kisi algilama kullanicinin AugeLab Studio'sunda, arayuzsuz yapilir.
rem   kurulum\derle.cmd
setlocal
cd /d "%~dp0.."

if not exist .venv\Scripts\python.exe (
  py -3.12 -m venv .venv || goto :hata
  .venv\Scripts\python -m pip install -q -r requirements-gelistirme.txt || goto :hata
)

rem YOLO11s-pose agirliklari (Ultralytics, AGPL-3.0) depoda gelir; ozeti kontrol edilir
.venv\Scripts\python -c "import hashlib,sys; h=hashlib.sha256(open('modeller/yolo11s-pose.pt','rb').read()).hexdigest(); sys.exit(0 if h=='1060bda4a27012060eca246f9b2adeea22eabb045a1e58f8d229be29b7ebc2ba' else 'model ozeti tutmuyor: '+h)" || goto :hata

rem Motorun ek kutuphaneleri (motor\deps.txt) gelistirme ortamindan kopyalanir; Studio'nun ortamina bir sey kurulmaz
.venv\Scripts\python kurulum\motor_deps.py || goto :hata

for %%S in (dene_kurulum dene_arayuzsuz) do (
  .venv\Scripts\python egitim\%%S.py >nul 2>&1 || (echo %%S basarisiz: .venv\Scripts\python egitim\%%S.py & goto :hata)
)
if not exist kurulum\sahne\kafe-kamera.pmod (
  echo Hazir sahne yok: kurulum\sahne\kafe-kamera.pmod
  echo README'deki adimlarla bir kez uretin: kurulum\sablon.py, sonra Studio'da Dosya - Farkli Kaydet.
  goto :hata
)
.venv\Scripts\python packaging\make_icon.py || goto :hata
.venv\Scripts\python -m PyInstaller kurulum\KafeKamera.spec --noconfirm --clean --distpath dist\arayuzsuz --workpath build\arayuzsuz || goto :hata
echo.
echo Hazir: dist\arayuzsuz\KafeKamera.exe

set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ISCC%" (
  "%ISCC%" /Q kurulum\KafeKamera.iss || goto :hata
  echo Kurulum dosyasi: dist\kurulum\KafeKamera-Kurulum-0.3.0.exe
) else (
  echo Inno Setup 6 kurulu degil: kurulum dosyasi uretilmedi. Kurmak icin: winget install JRSoftware.InnoSetup
)
exit /b 0

:hata
echo Derleme basarisiz.
exit /b 1
