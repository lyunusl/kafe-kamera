# -*- mode: python ; coding: utf-8 -*-
# Tek dosyalık Windows exe'si: build.cmd çalıştırır (pyinstaller --noconfirm --clean KafeKamera.spec).
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = ["analiz", "kamera", "rapor", "renkler", "yollar"]
hiddenimports += collect_submodules("ultralytics.trackers")
hiddenimports += collect_submodules("lap")
# torchvision yeni sürümde C eklentisini _C_stable adıyla dolaylı yüklüyor (NMS için gerekli)
hiddenimports += ["torchvision._C_stable", "torchvision.image_stable"]

datas = [
    ("web", "web"),
    ("ornekler", "ornekler"),
    ("modeller/yolo11s-pose.pt", "modeller"),
]
datas += collect_data_files("ultralytics", includes=["cfg/**/*.yaml"])

a = Analysis(
    ["uygulama.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["IPython", "jupyter", "notebook", "pytest", "tensorboard", "sentry_sdk"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

splash = Splash(
    "packaging/splash.png",
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
    icon=["packaging/kafekamera.ico"],
)
