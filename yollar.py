"""Klasörler ve paketlenmiş dosyalar.

KAYNAK: programla gelen dosyalar (web sayfaları, model, AugeLab Studio motoru, hazır sahne, örnekler). Exe'de geçici
        açılma klasörü.
VERI:   kullanıcının verisi (ayarlar, videolar, çıktılar). Exe'de %LOCALAPPDATA%\\KafeKamera,
        kaynak koddan çalışırken proje içindeki veri/ klasörü. KAFE_KAMERA_VERI ortam değişkeniyle değiştirilebilir.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

SURUM = "0.2.0"
DONDURULMUS = bool(getattr(sys, "frozen", False))
KAYNAK = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _veri() -> Path:
    ortam = os.environ.get("KAFE_KAMERA_VERI")
    if ortam:
        return Path(ortam).resolve()
    if DONDURULMUS:
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "KafeKamera"
    return Path(__file__).resolve().parent / "veri"


VERI = _veri()
AYAR = VERI / "ayar"
VIDEOLAR = VERI / "videolar"
CIKTI = VERI / "cikti"
ONBELLEK = VERI / "onbellek"
GECMIS = VERI / "gecmis"
GECICI = VERI / "gecici"  # yüzleri açık geçici dosyalar: yalnızca iş sürerken durur (gecicileri_sil)
KAYIT_GECICI = GECICI / "kayit"  # canlı kameradan alınıp analiz edilecek ham parça

WEB = KAYNAK / "web"
ORNEKLER = KAYNAK / "ornekler"
ORNEK_KODLAR = ("salon", "teras", "kasa", "bahce")
MODEL = KAYNAK / "modeller" / "yolo11s-pose.pt"  # programla gelir; yalnızca AugeLab Studio'daki motor açar


def gizle(metin: str) -> str:
    """Panelde ya da günlükte gösterilen metindeki kullanıcı klasörünü kısaltır (Windows kullanıcı adı görünmesin)."""
    metin = str(metin)
    for ortam, yerine in (("LOCALAPPDATA", "%LOCALAPPDATA%"), ("APPDATA", "%APPDATA%"), ("USERPROFILE", "%USERPROFILE%")):
        yol = os.environ.get(ortam)
        if yol:
            for bicim in {yol, yol.replace("\\", "/")}:
                metin = metin.replace(bicim, yerine)
    return metin


def ffmpeg() -> str:
    """Programla gelen ffmpeg (imageio-ffmpeg paketi); yoksa PATH'teki."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    yol = shutil.which("ffmpeg")
    if not yol:
        raise SystemExit("ffmpeg bulunamadı.")
    return yol


_IS_NESNESI = None


def cocuk_bagla(surec) -> None:
    """Program kapanınca (pencere kapatılsa bile) bu alt süreç de kapansın: Windows iş nesnesi (job object)."""
    global _IS_NESNESI
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        if _IS_NESNESI is None:
            class Temel(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

            class GirdiCikti(ctypes.Structure):
                _fields_ = [(ad, ctypes.c_uint64) for ad in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                             "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

            class Genis(ctypes.Structure):
                _fields_ = [("BasicLimitInformation", Temel), ("IoInfo", GirdiCikti), ("ProcessMemoryLimit", ctypes.c_size_t),
                            ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

            h = k32.CreateJobObjectW(None, None)
            bilgi = Genis()
            bilgi.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not h or not k32.SetInformationJobObject(h, 9, ctypes.byref(bilgi), ctypes.sizeof(bilgi)):
                return
            _IS_NESNESI = h
        k32.AssignProcessToJobObject(_IS_NESNESI, int(surec._handle))
    except Exception:
        pass


def gecicileri_sil(deneme: int = 1, bekle_sn: float = 1.0) -> list[Path]:
    """Yüzleri gizlenmemiş geçici dosyaları (canlı kameranın analiz bekleyen ham parçaları) siler. Açılışta, program
    kapanırken ve her yeni iş başlarken çağrılır (iş aynı anda tek olduğu için o anda süren bir kayıt yoktur): program ya da
    Studio çökmüşse kalan parça en geç bir sonraki işte ya da açılışta silinir. Silinemeyen (kullanımda) dosya kalır."""
    import time

    kalan: list[Path] = []
    for n in range(max(1, deneme)):
        if not GECICI.is_dir():
            return []
        kalan = []
        for p in sorted(GECICI.rglob("*"), reverse=True):
            try:
                if p.is_file():
                    p.unlink()
            except OSError:
                kalan.append(p)
        if not kalan:
            return []
        if n + 1 < deneme:
            time.sleep(bekle_sn)
    return kalan  # silinemeyen (kullanımda) dosyalar: açılışta yeniden denenir


def hazirla() -> bool:
    """Veri klasörünü kurar, örnek videoları ve ayarları (yoksa) kopyalar. İlk kurulumsa True döner."""
    ilk = not VERI.exists()
    for d in (AYAR, VIDEOLAR, CIKTI, ONBELLEK):
        d.mkdir(parents=True, exist_ok=True)
    gecicileri_sil()
    for kod in ORNEK_KODLAR:
        for kaynak, hedef in ((ORNEKLER / "videolar" / f"{kod}.mp4", VIDEOLAR / f"{kod}.mp4"),
                              (ORNEKLER / "ayar" / f"{kod}.json", AYAR / f"{kod}.json")):
            if kaynak.exists() and not hedef.exists():
                shutil.copy2(kaynak, hedef)
    return ilk
