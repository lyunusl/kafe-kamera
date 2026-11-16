# -*- mode: python ; coding: utf-8 -*-
# Tek dosyalık Windows exe'si: kurulum\derle.cmd çalıştırır.
# Exe'de torch ve ultralytics YOKTUR: kişi algılama kullanıcının AugeLab Studio'sunda, arayüzsüz yapılır (studio.py).
# Exe yalnızca motoru (motor/kafe_motor + motor/deps), modeli ve hazır sahneyi taşır; panel bunları Studio'nun özel blok
# klasörünün yanına kopyalar.
import os
from pathlib import Path

root = Path(SPECPATH).parent

# Hazır sahne: sahne dosyası yalnızca Studio'dan kaydedilebildiği için bir kez Studio'da kurulup kaydedilir (kurulum/sablon.py).
# Depoda tutulmaz (.gitignore: *.pmod); exe'ye girer ve panel onu arayüzsüz çalıştırır.
sahne = root / "kurulum" / "sahne" / "kafe-kamera.pmod"
if not sahne.is_file():
    raise SystemExit(f"Hazır sahne yok: kurulum/sahne/kafe-kamera.pmod. kurulum/sablon.py ile üretip Studio'da Dosya → Farklı Kaydet ile kaydedin.")
if not (root / "motor" / "deps" / "ultralytics" / "__init__.py").is_file():
    raise SystemExit("motor/deps hazır değil: .venv\\Scripts\\python kurulum\\motor_deps.py")

datas = [
    (str(root / "web"), "web"),
    (str(root / "ornekler"), "ornekler"),
    (str(root / "modeller" / "yolo11s-pose.pt"), "modeller"),
    # ekran kartı modeli bunlardan kullanıcının bilgisayarında üretilir (NVIDIA dosyaları exe'de yoktur, ayrıca indirilir)
    (str(root / "modeller" / "yolo11s-pose.fp16.onnx"), "modeller"),
    (str(root / "modeller" / "yolo11s-pose.onnx"), "modeller"),
    (str(root / "motor" / "kafe_motor"), "motor/kafe_motor"),
    (str(root / "renkler.py"), "motor/kafe_motor"),  # panelle ortak modüller motorun içinde de bulunur
    (str(root / "gizlilik.py"), "motor/kafe_motor"),
    (str(root / "rtsp_yokla.py"), "motor/kafe_motor"),
    (str(root / "gorunum.py"), "motor/kafe_motor"),
    (str(root / "gpu_ortak.py"), "motor/kafe_motor"),
    (str(root / "motor" / "deps"), "motor/deps"),
    (str(sahne), "kurulum/sahne"),
    (str(root / "LICENSE"), "."),
]

a = Analysis(
    [str(root / "uygulama.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=["analiz", "kamera", "rapor", "renkler", "yollar", "studio", "studio_blok", "studio_kurulum", "certifi",
                   "gizlilik", "rtsp_yokla", "canli", "gorunum", "sifre_kasasi", "ekran_karti", "gpu_ortak"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["torch", "torchvision", "ultralytics", "lap", "polars", "scipy", "matplotlib", "pandas", "IPython", "jupyter",
              "notebook", "pytest", "tensorboard", "sentry_sdk", "mcp"],
    noarchive=False,
    optimize=0,
)
# Derleme önbelleği (__pycache__) pakete girmez: içinde derleyen bilgisayarın dosya yolları kalır.
a.datas = [(ad, yol, tur) for ad, yol, tur in a.datas if "__pycache__" not in ad.replace("\\", "/").split("/")]
# Visual C++ çalışma kitaplıkları Windows'un kendi klasöründen alınır (PATH'teki eski bir kopya pakete girmesin).
_sistem = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32"
_crt = {"msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "msvcp140_atomic_wait.dll", "msvcp140_codecvt_ids.dll",
        "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll", "vcomp140.dll"}
a.binaries = [(ad, str(_sistem / ad), tur) if ad.lower() in _crt and (_sistem / ad).is_file() else (ad, yol, tur) for ad, yol, tur in a.binaries]
pyz = PYZ(a.pure)

splash = Splash(
    str(root / "packaging" / "splash.png"),
    binaries=a.binaries,
    datas=a.datas,
    always_on_top=False,
)

exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
    a.binaries,
    a.datas,
    [],
    name="KafeKamera",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(root / "packaging" / "kafekamera.ico")],
)
