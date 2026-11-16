"""Ekran kartı (NVIDIA, TensorRT) desteğinin panel ile motor arasında ortak parçaları. Bu dosya NVIDIA kodu içermez.

Panel (uygulama) ve AugeLab Studio'daki motor (kafe_motor; bu dosyanın kopyası) aynı kuralları kullanır:
  - ekran kartı bilgisi (sürücüyle gelen nvml.dll / nvcuda.dll üzerinden; ek dosya gerekmez),
  - indirilecek NVIDIA paketlerinin sabitlenmiş listesi (sürüm, adres, SHA-256, boyut) ve paketlerden alınacak dosyalar,
  - motor dosyası (TensorRT engine) anahtarı: kart modeli, sürücü, TensorRT sürümü, giriş boyutu ve hassasiyet.

NVIDIA dosyaları programla ve depoyla dağıtılmaz: kullanıcı isterse resmi dizinden (PyPI ve pypi.nvidia.com) bu
bilgisayara indirilir, NVIDIA'nın koşullarına tabidir.
"""
from __future__ import annotations

import ctypes
import hashlib
import os

TRT_SURUM = "11.4.0.106"
CUDART_SURUM = "13.5.37"
EN_AZ_CUDA_SURUCU = 13000   # cuDriverGetVersion: CUDA 13 sürücü arayüzü (NVIDIA sürücüsü R580 ya da yenisi)
EN_AZ_CC = 75               # TensorRT 11: Turing (RTX 20xx) ve sonrası
CIHAZLAR = ("otomatik", "islemci", "ekran_karti")
HASSASIYETLER = ("fp16", "fp32")
ONNX = {"fp16": "yolo11s-pose.fp16.onnx", "fp32": "yolo11s-pose.onnx"}
DOSYALAR_SURUM = f"trt-{TRT_SURUM}"
BILGI_DOSYASI = "kafe-gpu.json"   # indirilen klasördeki dosya listesi (sürüm, kart mimarisi, boyutlar)

# Resmi dizin: PyPI (files.pythonhosted.org) ve NVIDIA'nın kendi dizini (pypi.nvidia.com). Özetler dizinin bildirdiği SHA-256.
PAKETLER = [
    {"ad": "tensorrt-cu13-libs", "surum": TRT_SURUM,
     "dosya": "tensorrt_cu13_libs-11.4.0.106-py3-none-win_amd64.whl",
     "url": "https://pypi.nvidia.com/tensorrt-cu13-libs/tensorrt_cu13_libs-11.4.0.106-py3-none-win_amd64.whl",
     "sha256": "4d6a6e8b644f7f24df686c13809de7935eb3878d2a48cda1c7342c31143d4c16", "boyut": 1954140066,
     "al": ["tensorrt_libs/__init__.py", "tensorrt_libs/nvinfer_11.dll", "tensorrt_libs/nvinfer_plugin_11.dll",
            "tensorrt_libs/nvonnxparser_11.dll", "tensorrt_libs/nvinfer_builder_resource_{sm}_11.dll",
            "tensorrt_cu13_libs-11.4.0.106.dist-info/LICENSE.txt"]},
    {"ad": "tensorrt-cu13-bindings", "surum": TRT_SURUM,
     "dosya": "tensorrt_cu13_bindings-11.4.0.106-cp312-none-win_amd64.whl",
     "url": "https://files.pythonhosted.org/packages/8d/93/9ea63e5161fb60fff9b4b678ff665b712cd562264cc743c2733584a37420/"
            "tensorrt_cu13_bindings-11.4.0.106-cp312-none-win_amd64.whl",
     "sha256": "29f4a027db683f5b86824cc7df79d357a1b6f3b8401761ef6497c1ae81f21dc3", "boyut": 895997,
     "al": ["tensorrt_bindings/"]},
    {"ad": "nvidia-cuda-runtime", "surum": CUDART_SURUM,
     "dosya": "nvidia_cuda_runtime-13.5.37-py3-none-win_amd64.whl",
     "url": "https://files.pythonhosted.org/packages/35/99/e07dd9565d2e0317c1a62ff39ae9fc0542c048f74bcfc777c8be97710347/"
            "nvidia_cuda_runtime-13.5.37-py3-none-win_amd64.whl",
     "sha256": "f225d3fa5ea6bfbb58fc4979ef72375cbe661d9107f0d8a4ff22cc151525e4a9", "boyut": 2780254,
     "al": ["nvidia/cu13/bin/x86_64/cudart64_13.dll", "nvidia_cuda_runtime-13.5.37.dist-info/licenses/"]},
]
# paketteki mimariye özel motor üretici dosyaları (kart bunlardan birine uymazsa "ptx" denenir; ptx denenmedi)
SM_LISTESI = ("sm75", "sm80", "sm86", "sm89", "sm90", "sm100", "sm120")


def sm_adi(cc: str | int | None) -> str | None:
    """Kartın hesaplama yeteneği (ör. "120", "89") -> paketteki dosya adı parçası ("sm120"); desteklenmiyorsa None."""
    try:
        n = int(cc)
    except (TypeError, ValueError):
        return None
    if n < EN_AZ_CC:
        return None
    return f"sm{n}" if f"sm{n}" in SM_LISTESI else "ptx"


def indirme_boyutu() -> int:
    return sum(p["boyut"] for p in PAKETLER)


# ---------------------------------------------------------------- ekran kartı bilgisi (sürücüden)


def _dll(ad: str):
    try:
        return ctypes.WinDLL(ad) if os.name == "nt" else None
    except OSError:
        return None


def kart_bilgisi() -> dict | None:
    """İlk NVIDIA kartı: {"ad", "surucu" (ör. "610.88"), "cuda_surucu" (ör. 13030), "cc" (ör. "120")} ya da None.
    Yalnızca sürücüyle gelen dosyalar kullanılır; kart yoksa ya da sürücü kurulu değilse None."""
    cuda = _dll("nvcuda.dll")
    if cuda is None:
        return None
    try:
        if cuda.cuInit(0) != 0:
            return None
        n = ctypes.c_int()
        if cuda.cuDeviceGetCount(ctypes.byref(n)) != 0 or n.value < 1:
            return None
        dev = ctypes.c_int()
        cuda.cuDeviceGet(ctypes.byref(dev), 0)
        ad = ctypes.create_string_buffer(256)
        cuda.cuDeviceGetName(ad, 256, dev)
        ana, alt = ctypes.c_int(), ctypes.c_int()
        cuda.cuDeviceGetAttribute(ctypes.byref(ana), 75, dev)   # CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MAJOR
        cuda.cuDeviceGetAttribute(ctypes.byref(alt), 76, dev)   # ..._MINOR
        v = ctypes.c_int()
        cuda_surucu = v.value if cuda.cuDriverGetVersion(ctypes.byref(v)) == 0 else None
        bellek = ctypes.c_size_t()
        toplam_mb = None
        try:
            if cuda.cuDeviceTotalMem_v2(ctypes.byref(bellek), dev) == 0:
                toplam_mb = int(bellek.value // 2**20)
        except AttributeError:
            pass
    except OSError:
        return None
    return {"ad": ad.value.decode(errors="replace").strip(), "surucu": _surucu_surumu(), "cuda_surucu": cuda_surucu,
            "cc": f"{ana.value}{alt.value}", "bellek_mb": toplam_mb}


def _surucu_surumu() -> str | None:
    nvml = _dll("nvml.dll")
    if nvml is None:
        return None
    try:
        if nvml.nvmlInit_v2() != 0:
            return None
        buf = ctypes.create_string_buffer(96)
        r = nvml.nvmlSystemGetDriverVersion(buf, 96)
        nvml.nvmlShutdown()
        return buf.value.decode(errors="replace") if r == 0 else None
    except (OSError, AttributeError):
        return None


def kart_uygun_mu(kart: dict | None) -> tuple[bool, str | None]:
    """(uygun, neden): neden Türkçe ve kullanıcıya gösterilir."""
    if not kart:
        return False, "NVIDIA ekran kartı bulunamadı."
    if not kart.get("cuda_surucu") or kart["cuda_surucu"] < EN_AZ_CUDA_SURUCU:
        return False, (f"Ekran kartı sürücüsü eski ({kart.get('surucu') or 'sürüm okunamadı'}): NVIDIA sürücüsü R580 ya da "
                       "yenisi gerekir. Sürücüyü NVIDIA'nın sitesinden ya da Windows Update'ten güncelleyin.")
    if sm_adi(kart.get("cc")) is None:
        return False, f"Bu ekran kartı ({kart.get('ad')}) desteklenmiyor: RTX 20 serisi (Turing) ya da daha yenisi gerekir."
    return True, None


# ---------------------------------------------------------------- motor dosyası (engine)


def letterbox_hw(h: int, w: int, imgsz: int, stride: int = 32) -> tuple[int, int]:
    """Ultralytics'in kenar boşluklu küçültmesiyle modele giren (yükseklik, genişlik) (kafe_motor.gpu.pose ile aynı)."""
    r = min(imgsz / h, imgsz / w)
    nw, nh = max(round(w * r), 1), max(round(h * r), 1)
    dw, dh = ((imgsz - nw) % stride) / 2, ((imgsz - nh) % stride) / 2
    return nh + round(dh - 0.1) + round(dh + 0.1), nw + round(dw - 0.1) + round(dw + 0.1)


def motor_anahtari(kart: dict, trt_surum: str, hw: tuple[int, int], hassasiyet: str) -> str:
    """Motor dosyası şunlardan biri değişince yeniden üretilir: kart modeli ve mimarisi, sürücü, TensorRT sürümü,
    giriş boyutu, hassasiyet."""
    metin = "|".join([str(kart.get("ad")), str(kart.get("cc")), str(kart.get("surucu") or kart.get("cuda_surucu")),
                      str(trt_surum), f"{hw[0]}x{hw[1]}", hassasiyet])
    return hashlib.sha256(metin.encode("utf-8")).hexdigest()[:16]


def motor_adi(kart: dict, trt_surum: str, hw: tuple[int, int], hassasiyet: str) -> str:
    return f"yolo11s-pose-{hassasiyet}-{hw[0]}x{hw[1]}-{motor_anahtari(kart, trt_surum, hw, hassasiyet)}.engine"
