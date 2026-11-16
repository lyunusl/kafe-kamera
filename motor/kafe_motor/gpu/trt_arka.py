"""Yerel TensorRT çalıştırıcısı (kafe-kamera-gpu/kafe_gpu/backends.py'deki TrtBackend'den; yalnızca TensorRT yolu).

NVIDIA dosyaları (tensorrt_bindings, tensorrt_libs, cudart) programla gelmez: kullanıcının indirdiği klasördedir
(KAFE_GPU_DEPS). Klasör sys.path'in SONUNA eklenir ve DLL klasörleri yalnızca bu süreç için kaydedilir; Studio'nun kendi
paketlerine dokunulmaz. ONNX Runtime kullanılmaz (Studio'nun CPU onnxruntime'ı içe aktarılmış olsa da sorun olmaz).
"""
from __future__ import annotations

import ctypes
import glob
import os
import sys
import time

import numpy as np

ORTAM_DEPS = "KAFE_GPU_DEPS"
_DLL_TUTAMAKLARI = []
_EKLENDI: list[str] = []


class GpuHatasi(RuntimeError):
    """Ekran kartı yolu kullanılamıyor; ileti Türkçe ve kullanıcıya gösterilebilir."""


class MotorBozuk(GpuHatasi):
    """Motor dosyası okunamadı ya da bu kart / TensorRT için değil: panel siler ve yeniden hazırlar."""


def deps_klasoru() -> str | None:
    d = os.environ.get(ORTAM_DEPS)
    return d if d and os.path.isdir(d) else None


def dll_klasorlerini_ekle() -> list[str]:
    if _EKLENDI:
        return _EKLENDI
    kok = deps_klasoru()
    if kok is None:
        raise GpuHatasi("Ekran kartı dosyaları indirilmemiş (Kurulum → Ekran kartı).")
    bulunan = [d for d in (os.path.join(kok, "tensorrt_libs"), os.path.join(kok, "nvidia", "cu13", "bin", "x86_64"))
               if os.path.isdir(d) and glob.glob(os.path.join(d, "*.dll"))]
    if len(bulunan) < 2:
        raise GpuHatasi("Ekran kartı dosyaları eksik ya da bozuk; Kurulum → Ekran kartı'ndan yeniden indirin.")
    for d in bulunan:
        try:
            _DLL_TUTAMAKLARI.append(os.add_dll_directory(d))
        except (OSError, AttributeError):
            pass
    # bazı NVIDIA DLL'leri kardeşlerini PATH ile arar
    os.environ["PATH"] = os.pathsep.join(bulunan + [os.environ.get("PATH", "")])
    if kok not in sys.path:
        sys.path.append(kok)
    _EKLENDI.extend(bulunan)
    return _EKLENDI


def trt_ice_aktar():
    """tensorrt_bindings (indirilen klasörden). Hata: GpuHatasi."""
    dll_klasorlerini_ekle()
    try:
        import tensorrt_bindings as trt
    except Exception as e:  # noqa: BLE001  (DLL yüklenemedi, eksik dosya)
        raise GpuHatasi(f"TensorRT yüklenemedi ({type(e).__name__}): dosyalar eksik ya da bu sürücüyle uyumsuz.") from e
    return trt


class _Cuda:
    def __init__(self):
        adlar = []
        for d in dll_klasorlerini_ekle():
            adlar += glob.glob(os.path.join(d, "cudart64_*.dll"))
        if not adlar:
            raise GpuHatasi("cudart64_13.dll bulunamadı; ekran kartı dosyalarını yeniden indirin.")
        self.lib = ctypes.WinDLL(sorted(adlar)[-1])
        for f in ("cudaMalloc", "cudaFree", "cudaMallocHost", "cudaFreeHost", "cudaMemcpyAsync", "cudaStreamCreate",
                  "cudaStreamSynchronize", "cudaStreamDestroy", "cudaMemGetInfo"):
            getattr(self.lib, f).restype = ctypes.c_int
        self.lib.cudaMemcpyAsync.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_void_p]

    @staticmethod
    def ok(r, ne):
        if r != 0:
            if r == 2:  # cudaErrorMemoryAllocation
                raise GpuHatasi("Ekran kartının belleği yetmedi.")
            raise GpuHatasi(f"Ekran kartı işlemi başarısız ({ne}, CUDA hata {r}).")

    def malloc(self, n):
        p = ctypes.c_void_p()
        self.ok(self.lib.cudaMalloc(ctypes.byref(p), ctypes.c_size_t(n)), "cudaMalloc")
        return p.value

    def host(self, n):
        p = ctypes.c_void_p()
        self.ok(self.lib.cudaMallocHost(ctypes.byref(p), ctypes.c_size_t(n)), "cudaMallocHost")
        return p.value

    def stream(self):
        s = ctypes.c_void_p()
        self.ok(self.lib.cudaStreamCreate(ctypes.byref(s)), "cudaStreamCreate")
        return s.value

    def memcpy(self, dst, src, n, tur, akis):  # tur 1 = H2D, 2 = D2H
        self.ok(self.lib.cudaMemcpyAsync(dst, src, n, tur, akis), "cudaMemcpyAsync")

    def sync(self, akis):
        self.ok(self.lib.cudaStreamSynchronize(ctypes.c_void_p(akis)), "cudaStreamSynchronize")

    def bellek(self):
        f, t = ctypes.c_size_t(), ctypes.c_size_t()
        self.lib.cudaMemGetInfo(ctypes.byref(f), ctypes.byref(t))
        return f.value, t.value


class TrtCalistirici:
    """Bir motor dosyası (tek giriş boyutu, toplu iş 1): float32 NCHW -> ham çıktı (1, 56, N) float32."""

    def __init__(self, motor_yolu: str):
        self.cuda = _Cuda()
        trt = trt_ice_aktar()
        t = time.perf_counter()
        self.logger = trt.Logger(trt.Logger.ERROR)
        self.runtime = trt.Runtime(self.logger)
        try:
            with open(motor_yolu, "rb") as f:
                veri = f.read()
        except OSError as e:
            raise MotorBozuk("Ekran kartı modeli okunamadı; yeniden hazırlanacak.") from e
        self.engine = self.runtime.deserialize_cuda_engine(veri)
        if self.engine is None:
            raise MotorBozuk("Ekran kartı modeli bozuk ya da bu kart/TensorRT için değil; yeniden hazırlanacak.")
        self.ctx = self.engine.create_execution_context()
        if self.ctx is None:
            raise GpuHatasi("Ekran kartının belleği yetmedi (model açılamadı).")
        self.inp = self.out = None
        for i in range(self.engine.num_io_tensors):
            n = self.engine.get_tensor_name(i)
            if self.engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT:
                self.inp = n
            else:
                self.out = n
        self.akis = self.cuda.stream()
        self.cap = self.cap_out = 0
        self.yukleme_sn = time.perf_counter() - t
        self.trt_surum = str(trt.__version__)

    def _ayir(self, giris, cikis):
        if giris <= self.cap and cikis <= self.cap_out:
            return
        for p in getattr(self, "_aygit", []):
            self.cuda.lib.cudaFree(ctypes.c_void_p(p))
        for p in getattr(self, "_ana", []):
            self.cuda.lib.cudaFreeHost(ctypes.c_void_p(p))
        self.d_in, self.d_out = self.cuda.malloc(giris), self.cuda.malloc(cikis)
        self.h_in, self.h_out = self.cuda.host(giris), self.cuda.host(cikis)
        self._aygit, self._ana = [self.d_in, self.d_out], [self.h_in, self.h_out]
        self.cap, self.cap_out = giris, cikis

    def __call__(self, x: np.ndarray) -> np.ndarray:
        x = np.ascontiguousarray(x, dtype=np.float32)
        if not self.ctx.set_input_shape(self.inp, x.shape):
            raise GpuHatasi(f"Ekran kartı modeli bu giriş boyutunu kabul etmedi: {tuple(x.shape)}")
        oshape = tuple(self.ctx.get_tensor_shape(self.out))
        out_bytes = int(np.prod(oshape)) * 4
        self._ayir(x.nbytes, out_bytes)
        ctypes.memmove(self.h_in, x.ctypes.data, x.nbytes)
        self.cuda.memcpy(self.d_in, self.h_in, x.nbytes, 1, self.akis)
        self.ctx.set_tensor_address(self.inp, self.d_in)
        self.ctx.set_tensor_address(self.out, self.d_out)
        if not self.ctx.execute_async_v3(self.akis):
            raise GpuHatasi("Ekran kartında çıkarım çalışmadı.")
        self.cuda.memcpy(self.h_out, self.d_out, out_bytes, 2, self.akis)
        self.cuda.sync(self.akis)
        out = np.empty(oshape, np.float32)
        ctypes.memmove(out.ctypes.data, self.h_out, out_bytes)
        return out
