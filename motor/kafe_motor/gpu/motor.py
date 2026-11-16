"""Ekran kartı modeli: algilama.takip_et / takip_et_hepsi ile aynı kayıtları verir (kafe-kamera-gpu/kafe_gpu/engine.py).

Seçim (KAFE_CIHAZ): "otomatik" (kullanılabilirse ekran kartı, değilse işlemci), "islemci", "ekran_karti" (ekran kartı
istenir; olmazsa yine işlemciye düşülür ve neden bildirilir). Hassasiyet (KAFE_GPU_HASSASIYET): "fp16" (varsayılan) ya
da "fp32". INT8 yoktur.

Motor dosyaları (KAFE_GPU_MOTORLAR klasörü) kullanıcının bilgisayarında üretilir; adları gpu_ortak.motor_adi ile kart,
sürücü, TensorRT sürümü, giriş boyutu ve hassasiyete bağlıdır. Bir giriş boyutunun dosyası yoksa o boyut işlemcide
analiz edilir ve eksik boyut nabızda bildirilir (panel hazırlar ve kamerayı yeniden başlatır).
"""
from __future__ import annotations

import os

import numpy as np

ORTAM_CIHAZ = "KAFE_CIHAZ"
ORTAM_HASSASIYET = "KAFE_GPU_HASSASIYET"
ORTAM_MOTORLAR = "KAFE_GPU_MOTORLAR"
CONF, IOU = 0.2, 0.6


def ayarlar() -> tuple[str, str]:
    from .. import gpu_ortak

    cihaz = (os.environ.get(ORTAM_CIHAZ) or "otomatik").strip().lower()
    hassasiyet = (os.environ.get(ORTAM_HASSASIYET) or "fp16").strip().lower()
    return (cihaz if cihaz in gpu_ortak.CIHAZLAR else "otomatik",
            hassasiyet if hassasiyet in gpu_ortak.HASSASIYETLER else "fp16")


class GpuModel:
    """Ekran kartı ön koşulları (kart, sürücü, dosyalar, TensorRT) sağlandığında kurulur; motor dosyaları giriş boyutuna
    göre ilk karede açılır. `durum`: {"cihaz", "hassasiyet", "neden", "eksik"} (nabız ve deneme bunu bildirir)."""

    def __init__(self, hassasiyet: str, kart: dict, motorlar: str, gunluk=print):
        from . import trt_arka

        self.hassasiyet, self.kart, self.motorlar, self.gunluk = hassasiyet, kart, motorlar, gunluk
        self.trt = trt_arka.trt_ice_aktar()  # dosyalar ve DLL'ler burada denenir
        self.trt_surum = str(self.trt.__version__)
        self.calistiricilar: dict[tuple[int, int], object] = {}
        self.izciler: dict[str, object] = {}

    def motor_yolu(self, hw: tuple[int, int]) -> str:
        from .. import gpu_ortak

        return os.path.join(self.motorlar, gpu_ortak.motor_adi(self.kart, self.trt_surum, hw, self.hassasiyet))

    def calistirici(self, hw: tuple[int, int]):
        """Motor dosyası yoksa None (bu boyut işlemcide); bozuksa GpuHatasi."""
        if hw in self.calistiricilar:
            return self.calistiricilar[hw]
        from . import trt_arka

        yol = self.motor_yolu(hw)
        if not os.path.isfile(yol):
            self.calistiricilar[hw] = None
            return None
        c = trt_arka.TrtCalistirici(yol)
        c(np.zeros((1, 3, hw[0], hw[1]), np.float32))  # açılış denemesi: bellek ve sürücü burada görünür
        self.gunluk(f"ekran kartı: {os.path.basename(yol)} açıldı ({c.yukleme_sn:.2f} sn)")
        self.calistiricilar[hw] = c
        return c

    def algila(self, kare: np.ndarray, imgsz: int):
        """(dets (n,6), kpts (n,17,3)) ya da motor dosyası yoksa None."""
        from . import pose

        p = pose.letterbox_shape(kare.shape[0], kare.shape[1], imgsz)
        c = self.calistirici((p["in_h"], p["in_w"]))
        if c is None:
            return None
        x, params = pose.preprocess([kare], imgsz)
        return pose.postprocess(c(x), params, CONF, IOU)[0]

    def izci(self, ad: str, ayar):
        from .tracker import StreamTracker

        t = self.izciler.get(ad)
        if t is None:
            t = self.izciler[ad] = StreamTracker(ayar)
        return t


def kayitlar(kutular: np.ndarray, kimlikler, noktalar: np.ndarray) -> tuple[list[dict], list]:
    """algilama.takip_et_hepsi ile aynı yuvarlama: (izli kişiler [{id, b, k, o}], bütün tespitler [(kutu, noktalar)])."""
    kut = kutular.tolist()
    kps = noktalar.tolist()
    hepsi = list(zip(kut, kps))
    dets = []
    if kimlikler is not None:
        for pid, b, k in zip(kimlikler.tolist(), kut, kps):
            dets.append({"id": int(pid), "b": [round(v, 1) for v in b],
                         "k": [[round(q[0], 1), round(q[1], 1), round(q[2], 2)] for q in k], "o": 0.0})
    return dets, hepsi
