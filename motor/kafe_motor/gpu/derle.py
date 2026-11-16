"""Ekran kartı modelini (TensorRT engine) bu bilgisayarın kartı için ONNX'ten üretir (kafe-kamera-gpu/tools/build_engine.py).

Hassasiyet ONNX'ten gelir (TensorRT 11 ağları kesin türlüdür): yolo11s-pose.fp16.onnx -> FP16, yolo11s-pose.onnx -> FP32.
Her motor tek giriş boyutu içindir (16:9 görüntü, imgsz 960 -> 544x960), toplu iş 1 (her kamera kendi sürecinde).
Dosya adı gpu_ortak.motor_adi: kart, sürücü, TensorRT sürümü, boyut ve hassasiyet değişince yeni dosya üretilir.
Zamanlama önbelleği (trt.cache) aynı klasörde tutulur; ikinci üretim çok daha kısa sürer.
"""
from __future__ import annotations

import json
import os
import time


def uret(onnx: str, hedef: str, hw: tuple[int, int], onbellek: str | None = None, calisma_mb: int = 2048) -> dict:
    from . import trt_arka

    trt = trt_arka.trt_ice_aktar()
    t0 = time.perf_counter()
    logger = trt.Logger(trt.Logger.ERROR)
    builder = trt.Builder(logger)
    network = builder.create_network(0)
    parser = trt.OnnxParser(network, logger)
    if not parser.parse_from_file(onnx):
        hatalar = "; ".join(str(parser.get_error(i)) for i in range(parser.num_errors))[:300]
        raise trt_arka.GpuHatasi(f"Model dosyası okunamadı ({hatalar}).")
    cfg = builder.create_builder_config()
    cfg.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, calisma_mb << 20)
    cfg.builder_optimization_level = 3
    cache = None
    if onbellek:
        try:
            blob = open(onbellek, "rb").read() if os.path.isfile(onbellek) else b""
        except OSError:
            blob = b""
        cache = cfg.create_timing_cache(blob)
        cfg.set_timing_cache(cache, ignore_mismatch=True)
    inp = network.get_input(0)
    prof = builder.create_optimization_profile()
    h, w = hw
    prof.set_shape(inp.name, (1, 3, h, w), (1, 3, h, w), (1, 3, h, w))
    cfg.add_optimization_profile(prof)
    ser = builder.build_serialized_network(network, cfg)
    if ser is None:
        raise trt_arka.GpuHatasi("Ekran kartı modeli üretilemedi (bellek ya da sürücü sorunu olabilir).")
    gecici = hedef + ".tmp"
    with open(gecici, "wb") as f:
        f.write(ser)
    os.replace(gecici, hedef)
    if cache is not None and onbellek:
        try:
            with open(onbellek + ".tmp", "wb") as f:
                f.write(cache.serialize())
            os.replace(onbellek + ".tmp", onbellek)
        except OSError:
            pass
    sure = time.perf_counter() - t0
    bilgi = {"onnx": os.path.basename(onnx), "tensorrt": str(trt.__version__), "hw": [h, w], "sure_sn": round(sure, 1),
             "boyut_mb": round(os.path.getsize(hedef) / 2**20, 1)}
    with open(hedef + ".json", "w", encoding="utf-8") as f:
        json.dump(bilgi, f, ensure_ascii=False)
    return bilgi


def hepsini_uret(model_klasoru: str, motorlar: str, hassasiyet: str, sekiller: list[tuple[int, int]], ilerleme=None) -> dict:
    """Eksik motorları üretir; var olanlara dokunmaz. Dönüş: {"ok", "uretilen", "vardi", "sure_sn", "kart", "tensorrt"}."""
    from .. import gpu_ortak
    from . import trt_arka

    kart = gpu_ortak.kart_bilgisi()
    uygun, neden = gpu_ortak.kart_uygun_mu(kart)
    if not uygun:
        raise trt_arka.GpuHatasi(neden)
    trt = trt_arka.trt_ice_aktar()
    onnx = os.path.join(model_klasoru, gpu_ortak.ONNX[hassasiyet])
    if not os.path.isfile(onnx):
        raise trt_arka.GpuHatasi(f"Model dosyası programla gelmemiş: {os.path.basename(onnx)}")
    os.makedirs(motorlar, exist_ok=True)
    t0 = time.perf_counter()
    uretilen, vardi = [], []
    for i, hw in enumerate(sekiller):
        yol = os.path.join(motorlar, gpu_ortak.motor_adi(kart, str(trt.__version__), hw, hassasiyet))
        if os.path.isfile(yol):
            vardi.append(os.path.basename(yol))
            continue
        if ilerleme:
            ilerleme({"i": i, "toplam": len(sekiller), "hw": f"{hw[0]}x{hw[1]}", "hassasiyet": hassasiyet})
        uret(onnx, yol, hw, os.path.join(motorlar, "trt.cache"))
        uretilen.append(os.path.basename(yol))
    if ilerleme:
        ilerleme({"i": len(sekiller), "toplam": len(sekiller)})
    return {"ok": True, "uretilen": uretilen, "vardi": vardi, "sure_sn": round(time.perf_counter() - t0, 1),
            "kart": kart.get("ad"), "tensorrt": str(trt.__version__), "hassasiyet": hassasiyet}
