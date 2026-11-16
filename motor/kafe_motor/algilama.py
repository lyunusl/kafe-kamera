"""Kişi algılama, takip ve iskelet noktaları (Ultralytics YOLO11s-pose + ByteTrack).

Ayarlar Kafe Kamera 0.1.0'daki analiz.algila() ve analiz.yuzleri_gizle() ile aynıdır; önbellekteki eski algılamalar ve
örnek çıktılar karşılaştırılabilir kalır:
  video karesi : model.track(kare, persist=True, tracker="bytetrack.yaml", conf=0.2, iou=0.6, imgsz=<iş>)
  tek kare     : model(kare, conf=0.15, imgsz=1280)  (yalnızca yüz gizlemek için; takip yok)
"""
from __future__ import annotations

import os
import tempfile

TAKIP = {"tracker": "bytetrack.yaml", "conf": 0.2, "iou": 0.6}
TEK_KARE = {"conf": 0.15, "imgsz": 1280}


def ultralytics_ayarla(veri: str | None) -> None:
    """Ultralytics ayarlarını kullanıcının genel klasörüne değil Kafe Kamera'nın veri klasörüne yazsın, internete çıkmasın,
    eksik paket kurmaya kalkmasın. ultralytics içe aktarılmadan önce çağrılmalı."""
    klasor = os.path.join(veri, ".ultralytics") if veri else os.path.join(tempfile.gettempdir(), "kafe-kamera-ultralytics")
    os.environ["YOLO_CONFIG_DIR"] = klasor
    os.environ["YOLO_OFFLINE"] = "1"
    os.environ["YOLO_VERBOSE"] = "False"
    os.environ["YOLO_AUTOINSTALL"] = "False"


def model_ac(yol: str):
    from ultralytics import YOLO

    if not os.path.isfile(yol):
        raise FileNotFoundError(f"model dosyası yok: {os.path.basename(yol)}")
    return YOLO(yol)


def surumler() -> dict:
    import sys

    out = {}
    for ad in ("ultralytics", "torch", "numpy", "cv2"):
        m = sys.modules.get(ad)
        if m is not None:
            out[ad] = str(getattr(m, "__version__", "?"))
    return out


def takip_et(model, kare, imgsz: int) -> list[dict]:
    """Bir video karesi: izli kişiler [{id, b, k, o}] (0.1.0 ile aynı yuvarlama; o = çalışan renk puanı, panel hesaplar)."""
    r = model.track(kare, persist=True, imgsz=imgsz, verbose=False, **TAKIP)[0]
    dets = []
    if r.boxes is not None and r.boxes.id is not None and r.keypoints is not None:
        ids = r.boxes.id.int().tolist()
        kutular = r.boxes.xyxy.tolist()
        kps = r.keypoints.data.tolist()
        for pid, b, k in zip(ids, kutular, kps):
            dets.append({
                "id": pid,
                "b": [round(v, 1) for v in b],
                "k": [[round(p[0], 1), round(p[1], 1), round(p[2], 2)] for p in k],
                "o": 0.0,
            })
    return dets


def tek_kare(model, kare) -> list[dict]:
    """Tek kare (takip yok): bütün kişilerin kutusu ve iskelet noktaları [{b, k}]. Panel bunlarla yüzleri pikseller."""
    r = model(kare, verbose=False, **TEK_KARE)[0]
    out = []
    if r.boxes is not None and r.keypoints is not None:
        for b, k in zip(r.boxes.xyxy.tolist(), r.keypoints.data.tolist()):
            out.append({"b": [float(v) for v in b], "k": [[float(p[0]), float(p[1]), float(p[2])] for p in k]})
    return out


def takip_et_hepsi(model, kare, imgsz: int, izci: str = "bytetrack.yaml") -> tuple[list[dict], list]:
    """takip_et ile aynı izli kişiler, ayrıca yüz gizleme için karedeki bütün tespitler [(kutu, noktalar)]: izi henüz
    oluşmamış bir kişinin yüzü de gizlenir."""
    r = model.track(kare, persist=True, imgsz=imgsz, verbose=False, **{**TAKIP, "tracker": izci})[0]
    dets, hepsi = [], []
    if r.boxes is not None and r.keypoints is not None:
        kutular = r.boxes.xyxy.tolist()
        kps = r.keypoints.data.tolist()
        hepsi = list(zip(kutular, kps))
        if r.boxes.id is not None:
            for pid, b, k in zip(r.boxes.id.int().tolist(), kutular, kps):
                dets.append({"id": pid, "b": [round(v, 1) for v in b],
                             "k": [[round(q[0], 1), round(q[1], 1), round(q[2], 2)] for q in k], "o": 0.0})
    return dets, hepsi
