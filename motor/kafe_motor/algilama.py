"""Kişi algılama, takip ve iskelet noktaları (Ultralytics YOLO11s-pose + ByteTrack), işlemcide ya da ekran kartında.

Ayarlar Kafe Kamera 0.1.0'daki analiz.algila() ve analiz.yuzleri_gizle() ile aynıdır; önbellekteki eski algılamalar ve
örnek çıktılar karşılaştırılabilir kalır:
  video karesi : model.track(kare, persist=True, tracker="bytetrack.yaml", conf=0.2, iou=0.6, imgsz=<iş>)
  tek kare     : model(kare, conf=0.15, imgsz=1280)  (yalnızca yüz gizlemek için; takip yok; her zaman işlemcide)

Ekran kartı (kafe_motor.gpu, TensorRT): KAFE_CIHAZ otomatik | islemci | ekran_karti. Ekran kartı yolu herhangi bir
nedenle çalışmazsa (kart yok, sürücü eski, dosyalar indirilmemiş, motor dosyası yok ya da bozuk, bellek yetmedi) iş
durmaz: işlemciye geçilir ve neden `Model.durum`'da Türkçe bildirilir.
"""
from __future__ import annotations

import os
import sys
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


def _gunluk(metin: str) -> None:
    print(f"[kafe] {metin}", file=sys.stderr, flush=True)


class Model:
    """İşlemci (ultralytics YOLO, gerekince açılır) ya da ekran kartı (TensorRT) modeli."""

    def __init__(self, yol: str):
        from .gpu import motor

        if not os.path.isfile(yol):
            raise FileNotFoundError(f"model dosyası yok: {os.path.basename(yol)}")
        self.yol, self._cpu, self.gpu = yol, None, None
        self.istenen, self.hassasiyet = motor.ayarlar()
        self.durum = {"cihaz": "islemci", "istenen": self.istenen, "hassasiyet_istenen": self.hassasiyet, "hassasiyet": None,
                      "neden": None, "eksik": [], "bozuk": [],
                      "kart_yok": False, "onnxruntime_once": "onnxruntime" in sys.modules}
        if self.istenen != "islemci":
            self._gpu_ac()

    def _gpu_ac(self) -> None:
        from . import gpu_ortak
        from .gpu import motor, trt_arka

        kart = gpu_ortak.kart_bilgisi()
        uygun, neden = gpu_ortak.kart_uygun_mu(kart)
        if not uygun:
            self.durum.update(neden=neden, kart_yok=kart is None)
            return
        motorlar = os.environ.get(motor.ORTAM_MOTORLAR)
        if not motorlar:
            self.durum["neden"] = "Ekran kartı modeli için klasör verilmedi."
            return
        try:
            self.gpu = motor.GpuModel(self.hassasiyet, kart, motorlar, _gunluk)
        except trt_arka.GpuHatasi as e:
            self.durum["neden"] = str(e)
            return
        except Exception as e:  # noqa: BLE001
            self.durum["neden"] = f"Ekran kartı açılamadı ({type(e).__name__})."
            return
        self.durum.update(cihaz="ekran_karti", hassasiyet=self.hassasiyet, kart=kart.get("ad"),
                          tensorrt=self.gpu.trt_surum)

    def cpu(self):
        if self._cpu is None:
            from ultralytics import YOLO

            self._cpu = YOLO(self.yol)
        return self._cpu

    def gpu_birak(self, neden: str) -> None:
        _gunluk(f"ekran kartı bırakıldı, işlemciye geçiliyor: {neden}")
        self.gpu = None
        self.durum.update(cihaz="islemci", hassasiyet=None, neden=neden)

    def takip(self, kare, imgsz: int, izci: str | None) -> tuple[list[dict], list]:
        if self.gpu is not None:
            from .gpu import motor, pose, trt_arka

            try:
                r = self.gpu.algila(kare, imgsz)
                if r is not None:
                    self.durum["cihaz"] = "ekran_karti"
                    dets, kpts = r
                    return motor.kayitlar(*self.gpu.izci(izci or "bytetrack.yaml", izci).update(kare, dets, kpts))
                p = pose.letterbox_shape(kare.shape[0], kare.shape[1], imgsz)
                hw = f"{p['in_h']}x{p['in_w']}"
                if hw not in self.durum["eksik"]:
                    self.durum["eksik"].append(hw)
                self.durum.update(cihaz="islemci", neden=f"Ekran kartı modeli bu görüntü boyutu ({hw}) için henüz "
                                                         "hazırlanmadı; şimdilik işlemcide analiz ediliyor.")
            except trt_arka.MotorBozuk as e:
                p = pose.letterbox_shape(kare.shape[0], kare.shape[1], imgsz)
                self.durum["bozuk"].append(f"{p['in_h']}x{p['in_w']}")
                self.gpu_birak(str(e))
            except trt_arka.GpuHatasi as e:
                self.gpu_birak(str(e))
            except MemoryError:
                self.gpu_birak("Ekran kartının belleği yetmedi.")
            except Exception as e:  # noqa: BLE001  (sürücü hatası vb.: iş durmaz)
                self.gpu_birak(f"Ekran kartında hata ({type(e).__name__}).")
        return _yolo_takip(self.cpu(), kare, imgsz, izci)


def model_ac(yol: str) -> Model:
    return Model(yol)


def surumler(model: Model | None = None) -> dict:
    out = {}
    for ad in ("ultralytics", "torch", "numpy", "cv2"):
        m = sys.modules.get(ad)
        if m is not None:
            out[ad] = str(getattr(m, "__version__", "?"))
    if model is not None:
        d = model.durum
        out["cikarim"] = (f"TensorRT {d.get('tensorrt')} {str(d.get('hassasiyet')).upper()} ({d.get('kart')})"
                          if d["cihaz"] == "ekran_karti" else "işlemci")
    return out


def _yolo_takip(yolo, kare, imgsz: int, izci: str | None) -> tuple[list[dict], list]:
    r = yolo.track(kare, persist=True, imgsz=imgsz, verbose=False, **{**TAKIP, "tracker": izci or TAKIP["tracker"]})[0]
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


def takip_et(model, kare, imgsz: int) -> list[dict]:
    """Bir video karesi: izli kişiler [{id, b, k, o}] (0.1.0 ile aynı yuvarlama; o = çalışan renk puanı, panel hesaplar)."""
    if isinstance(model, Model):
        return model.takip(kare, imgsz, None)[0]
    return _yolo_takip(model, kare, imgsz, None)[0]


def tek_kare(model, kare) -> list[dict]:
    """Tek kare (takip yok): bütün kişilerin kutusu ve iskelet noktaları [{b, k}]. Panel bunlarla yüzleri pikseller.
    1280 piksel girişle çalışır; ekran kartı motorları bu boyut için üretilmediğinden her zaman işlemcide."""
    yolo = model.cpu() if isinstance(model, Model) else model
    r = yolo(kare, verbose=False, **TEK_KARE)[0]
    out = []
    if r.boxes is not None and r.keypoints is not None:
        for b, k in zip(r.boxes.xyxy.tolist(), r.keypoints.data.tolist()):
            out.append({"b": [float(v) for v in b], "k": [[float(p[0]), float(p[1]), float(p[2])] for p in k]})
    return out


def takip_et_hepsi(model, kare, imgsz: int, izci: str = "bytetrack.yaml") -> tuple[list[dict], list]:
    """takip_et ile aynı izli kişiler, ayrıca yüz gizleme için karedeki bütün tespitler [(kutu, noktalar)]: izi henüz
    oluşmamış bir kişinin yüzü de gizlenir."""
    if isinstance(model, Model):
        return model.takip(kare, imgsz, izci)
    return _yolo_takip(model, kare, imgsz, izci)
