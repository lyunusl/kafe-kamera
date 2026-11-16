"""Ekran kartı desteği sınamaları: cihaz seçimi, işlemciye düşme, motor dosyası anahtarı, indirme ve doğrulama
(yerel sahte dizinle; internete çıkmaz), arayüz sözleşmesi.

  .venv\\Scripts\\python egitim\\dene_gpu.py

Bu bilgisayarda gerçek NVIDIA dosyaları da denensin isterseniz KAFE_DENE_GPU_DEPS=<indirilmiş klasör> verin (ör. veri
klasöründeki gpu/dosyalar/trt-11.4.0.106-sm120); verilmezse gerçek ekran kartı denemeleri atlanır.
"""
from __future__ import annotations

import hashlib
import http.server
import io
import os
import shutil
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
GECICI = Path(tempfile.mkdtemp(prefix="kafe-gpu-dene-"))
os.environ["KAFE_KAMERA_VERI"] = str(GECICI / "veri")

import yollar  # noqa: E402

yollar.hazirla()
import gpu_ortak  # noqa: E402
import studio  # noqa: E402

SONUC = []


def denetle(ad: str, kosul) -> None:
    SONUC.append((ad, bool(kosul)))
    print(("  geçti  " if kosul else "  KALDI  ") + ad, flush=True)


# ---------------------------------------------------------------- motor paketi (Studio'ya giden kopya)
MOTOR = studio.motoru_yerlestir(GECICI / "motor")
sys.path.insert(0, str(MOTOR))
sys.path.append(str(MOTOR / "deps"))
from kafe_motor import algilama  # noqa: E402
from kafe_motor import gpu_ortak as m_ortak  # noqa: E402
from kafe_motor.gpu import trt_arka  # noqa: E402

algilama.ultralytics_ayarla(str(GECICI / "veri"))
PT = str(MOTOR / "modeller" / "yolo11s-pose.pt")
GERCEK_DEPS = os.environ.get("KAFE_DENE_GPU_DEPS")
KART = {"ad": "Deneme Kartı", "surucu": "610.88", "cuda_surucu": 13030, "cc": "120", "bellek_mb": 8000}


def ortam(**kw):
    for k in ("KAFE_CIHAZ", "KAFE_GPU_HASSASIYET", "KAFE_GPU_DEPS", "KAFE_GPU_MOTORLAR"):
        os.environ.pop(k, None)
    for k, v in kw.items():
        os.environ[k] = str(v)
    trt_arka._EKLENDI.clear()


print("Motor dosyası anahtarı ve giriş boyutları")
denetle("16:9 görüntü 960'ta 544x960", gpu_ortak.letterbox_hw(720, 1280, 960) == (544, 960)
        and gpu_ortak.letterbox_hw(1080, 1920, 960) == (544, 960) and gpu_ortak.letterbox_hw(360, 640, 960) == (544, 960))
denetle("4:3 736x960, PAL 800x960, kare 960x960, 640'ta 384x640",
        gpu_ortak.letterbox_hw(480, 640, 960) == (736, 960) and gpu_ortak.letterbox_hw(576, 704, 960) == (800, 960)
        and gpu_ortak.letterbox_hw(1080, 1080, 960) == (960, 960) and gpu_ortak.letterbox_hw(720, 1280, 640) == (384, 640))
from kafe_motor.gpu import pose  # noqa: E402

denetle("panel ile motor aynı boyutu hesaplar",
        all(gpu_ortak.letterbox_hw(h, w, s) == (pose.letterbox_shape(h, w, s)["in_h"], pose.letterbox_shape(h, w, s)["in_w"])
            for h, w, s in ((720, 1280, 960), (480, 640, 960), (576, 704, 960), (1080, 1080, 960), (720, 1280, 640),
                            (1520, 2688, 960))))
a0 = gpu_ortak.motor_anahtari(KART, "11.4.0.106", (544, 960), "fp16")
degisen = [gpu_ortak.motor_anahtari({**KART, "ad": "Başka Kart"}, "11.4.0.106", (544, 960), "fp16"),
           gpu_ortak.motor_anahtari({**KART, "surucu": "620.10"}, "11.4.0.106", (544, 960), "fp16"),
           gpu_ortak.motor_anahtari({**KART, "cc": "89"}, "11.4.0.106", (544, 960), "fp16"),
           gpu_ortak.motor_anahtari(KART, "11.5.0.1", (544, 960), "fp16"),
           gpu_ortak.motor_anahtari(KART, "11.4.0.106", (736, 960), "fp16"),
           gpu_ortak.motor_anahtari(KART, "11.4.0.106", (544, 960), "fp32")]
denetle("anahtar kart, sürücü, mimari, TensorRT, boyut ya da hassasiyet değişince değişir",
        a0 == gpu_ortak.motor_anahtari(dict(KART), "11.4.0.106", (544, 960), "fp16") and len(set(degisen + [a0])) == 7)
denetle("panel ile motor aynı motor dosyası adını üretir",
        gpu_ortak.motor_adi(KART, "11.4.0.106", (544, 960), "fp16") == m_ortak.motor_adi(KART, "11.4.0.106", (544, 960), "fp16"))
denetle("INT8 sunulmaz", "int8" not in gpu_ortak.HASSASIYETLER and set(gpu_ortak.ONNX) == {"fp16", "fp32"})
denetle("kart uygunluğu: kart yok / eski sürücü / eski kart / uygun",
        not gpu_ortak.kart_uygun_mu(None)[0] and "bulunamadı" in gpu_ortak.kart_uygun_mu(None)[1]
        and "sürücüsü eski" in gpu_ortak.kart_uygun_mu({**KART, "cuda_surucu": 12080})[1]
        and "desteklenmiyor" in gpu_ortak.kart_uygun_mu({**KART, "cc": "61"})[1]
        and gpu_ortak.kart_uygun_mu(KART) == (True, None))

print("Cihaz seçimi ve işlemciye düşme (motor)")
gercek_kart = m_ortak.kart_bilgisi


def kart_sahte(k):
    m_ortak.kart_bilgisi = lambda: k


ortam(KAFE_CIHAZ="islemci")
m = algilama.model_ac(PT)
denetle("işlemci seçimi: ekran kartı hiç denenmez", m.gpu is None and m.durum["cihaz"] == "islemci" and m.durum["neden"] is None)
kart_sahte(None)
ortam(KAFE_CIHAZ="otomatik", KAFE_GPU_MOTORLAR=GECICI / "motorlar")
m = algilama.model_ac(PT)
denetle("kart yok: otomatik işlemcide, neden bildirilir (kart_yok)", m.durum["cihaz"] == "islemci" and m.durum["kart_yok"]
        and "bulunamadı" in m.durum["neden"])
kart_sahte({**KART, "cuda_surucu": 12080})
ortam(KAFE_CIHAZ="ekran_karti", KAFE_GPU_MOTORLAR=GECICI / "motorlar")
m = algilama.model_ac(PT)
denetle("eski sürücü: işlemciye düşer, neden sürücü", m.durum["cihaz"] == "islemci" and "R580" in m.durum["neden"])
kart_sahte(KART)
bos = GECICI / "bos-deps"
bos.mkdir()
ortam(KAFE_CIHAZ="ekran_karti", KAFE_GPU_DEPS=bos, KAFE_GPU_MOTORLAR=GECICI / "motorlar")
m = algilama.model_ac(PT)
denetle("dosyalar eksik (boş klasör): işlemciye düşer, neden dosyalar", m.durum["cihaz"] == "islemci"
        and "dosyaları" in m.durum["neden"])
ortam(KAFE_CIHAZ="ekran_karti", KAFE_GPU_MOTORLAR=GECICI / "motorlar")
m = algilama.model_ac(PT)
denetle("dosyalar indirilmemiş (ortam yok): neden 'indirilmemiş'", m.durum["cihaz"] == "islemci"
        and "indirilmemiş" in m.durum["neden"])
import numpy as np  # noqa: E402

kare = np.zeros((360, 640, 3), np.uint8)
dets, hepsi = algilama.takip_et_hepsi(m, kare, 960, "bytetrack.yaml")
denetle("işlemcideki takip çalışır (boş kare, iş durmaz)", dets == [] and m._cpu is not None)


class SahteGpu:
    """Ekran kartı yolunun hata vermesi (bellek yetmedi, sürücü hatası) benzetimi."""

    def __init__(self, hata):
        self.hata = hata

    def algila(self, kare, imgsz):
        raise self.hata


m.gpu = SahteGpu(trt_arka.GpuHatasi("Ekran kartının belleği yetmedi."))
m.durum["cihaz"] = "ekran_karti"
algilama.takip_et_hepsi(m, kare, 960, "bytetrack.yaml")
denetle("çalışırken bellek yetmezse işlemciye geçer ve nedenini yazar", m.gpu is None and m.durum["cihaz"] == "islemci"
        and "belleği yetmedi" in m.durum["neden"])
m.gpu = SahteGpu(RuntimeError("cuda driver"))
algilama.takip_et_hepsi(m, kare, 960, "bytetrack.yaml")
denetle("beklenmeyen sürücü hatasında da iş durmaz", m.gpu is None and "hata" in m.durum["neden"])

if GERCEK_DEPS and gercek_kart() is not None:
    print("Gerçek ekran kartı (bu bilgisayar)")
    m_ortak.kart_bilgisi = gercek_kart
    motorlar = GECICI / "gercek-motorlar"
    motorlar.mkdir()
    ortam(KAFE_CIHAZ="ekran_karti", KAFE_GPU_DEPS=GERCEK_DEPS, KAFE_GPU_MOTORLAR=motorlar)
    m = algilama.model_ac(PT)
    denetle("dosyalar varken ekran kartı yolu açılır", m.gpu is not None and m.durum["cihaz"] == "ekran_karti")
    algilama.takip_et_hepsi(m, kare, 960, "bytetrack.yaml")
    denetle("motor dosyası yoksa o boyut işlemcide, eksik boyut bildirilir",
            m.durum["cihaz"] == "islemci" and m.durum["eksik"] == ["544x960"] and "hazırlanmadı" in m.durum["neden"])
    k = gercek_kart()
    bozuk = motorlar / gpu_ortak.motor_adi(k, gpu_ortak.TRT_SURUM, (544, 960), "fp16")
    bozuk.write_bytes(b"bozuk motor dosyasi" * 100)
    m = algilama.model_ac(PT)
    algilama.takip_et_hepsi(m, kare, 960, "bytetrack.yaml")
    denetle("bozuk motor dosyası: işlemciye düşer, çökmez", m.gpu is None and m.durum["cihaz"] == "islemci"
            and "bozuk" in (m.durum["neden"] or ""))
    bozuk.unlink()
else:
    print("(gerçek ekran kartı denemeleri atlandı: KAFE_DENE_GPU_DEPS verilmedi ya da kart yok)")
m_ortak.kart_bilgisi = gercek_kart

print("İndirme ve doğrulama (yerel sahte dizin)")
import ekran_karti  # noqa: E402


def sahte_whl(uyeler: dict[str, bytes]) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for ad, veri in uyeler.items():
            z.writestr(ad, veri)
    return b.getvalue()


libs = sahte_whl({"tensorrt_libs/__init__.py": b"# libs", "tensorrt_libs/nvinfer_11.dll": b"N" * 5000,
                  "tensorrt_libs/nvinfer_plugin_11.dll": b"P" * 300, "tensorrt_libs/nvonnxparser_11.dll": b"O" * 200,
                  "tensorrt_libs/nvinfer_builder_resource_sm120_11.dll": b"R" * 4000,
                  "tensorrt_libs/nvinfer_builder_resource_sm89_11.dll": b"X" * 4000,
                  "tensorrt_libs/nvinfer_builder_resource_ptx_11.dll": b"X" * 4000,
                  "tensorrt_cu13_libs-11.4.0.106.dist-info/LICENSE.txt": b"license",
                  "tensorrt_cu13_libs-11.4.0.106.dist-info/RECORD": b"x"})
bind = sahte_whl({"tensorrt_bindings/__init__.py": b"# b", "tensorrt_bindings/tensorrt.cp312-win_amd64.pyd": b"B" * 900,
                  "tensorrt_bindings/plugin/__init__.py": b"#"})
cudart = sahte_whl({"nvidia/cu13/bin/x86_64/cudart64_13.dll": b"C" * 700, "nvidia/cu13/include/x.h": b"h"})
DOSYALAR = {"libs.whl": libs, "bind.whl": bind, "cudart.whl": cudart}
ISTEKLER = []


class Sunucu(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        ad = self.path.strip("/")
        ISTEKLER.append((ad, self.headers.get("Range")))
        veri = DOSYALAR.get(ad)
        if veri is None:
            self.send_response(404)
            self.end_headers()
            return
        bas = 0
        if self.headers.get("Range"):
            bas = int(self.headers["Range"].split("=")[1].split("-")[0])
            self.send_response(206)
        else:
            self.send_response(200)
        self.send_header("Content-Length", str(len(veri) - bas))
        self.end_headers()
        self.wfile.write(veri[bas:])


sunucu = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Sunucu)
threading.Thread(target=sunucu.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{sunucu.server_address[1]}"
ASIL = gpu_ortak.PAKETLER


def paketler(bozuk_sha: bool = False):
    out = []
    for asil, ad in zip(ASIL, ("libs.whl", "bind.whl", "cudart.whl")):
        veri = DOSYALAR[ad]
        out.append({**asil, "dosya": ad, "url": f"{URL}/{ad}", "boyut": len(veri),
                    "sha256": ("0" * 64) if bozuk_sha and ad == "bind.whl" else hashlib.sha256(veri).hexdigest()})
    return out


ekran_karti.kart = lambda tazele=False: dict(KART)
ekran_karti.ayar_yaz(cihaz="islemci")  # indirme sonrası Studio'da hazırlama denenmesin
gpu_ortak.PAKETLER = paketler()
ekran_karti.gpu_ortak.PAKETLER = gpu_ortak.PAKETLER
d0 = ekran_karti.api_durum()
denetle("indirmeden önce: durum 'indirilmedi', indirme boyutu bayt olarak bilinir",
        d0["durum"] == "indirilmedi" and d0["indirme_boyutu"] == sum(len(v) for v in DOSYALAR.values())
        and set(d0) == {"durum", "kart", "indirme_boyutu", "indirilen", "toplam", "mesaj", "secim", "kullanilan", "hassasiyet"})
# yarım kalmış indirme: libs'in yarısı .part olarak var -> kaldığı yerden sürer
(ekran_karti.kok() / "indirilen").mkdir(parents=True, exist_ok=True)
(ekran_karti.kok() / "indirilen" / "libs.whl.part").write_bytes(libs[: len(libs) // 2])
ok, _ = ekran_karti.indir_baslat()
for _ in range(100):
    if ekran_karti.IS.get("bitti"):
        break
    time.sleep(0.1)
hedef = ekran_karti.dosyalar_klasoru(KART)
denetle("indirme biter, hata yok", ok and ekran_karti.IS.get("bitti") and not ekran_karti.IS.get("hata"))
denetle("yarım dosya kaldığı yerden sürdü (Range)", ("libs.whl", f"bytes={len(libs) // 2}-") in ISTEKLER)
acilan = sorted(str(p.relative_to(hedef)).replace("\\", "/") for p in hedef.rglob("*") if p.is_file())
denetle("yalnızca gerekli dosyalar açıldı (bu kartın mimarisi, başka mimari ve başlık dosyası yok)",
        "tensorrt_libs/nvinfer_builder_resource_sm120_11.dll" in acilan
        and not any("sm89" in a or "ptx" in a or a.endswith(".h") or a.endswith("RECORD") for a in acilan)
        and "nvidia/cu13/bin/x86_64/cudart64_13.dll" in acilan and "tensorrt_bindings/tensorrt.cp312-win_amd64.pyd" in acilan)
denetle("indirilen paketler silindi, bilgi dosyası yazıldı", not (ekran_karti.kok() / "indirilen").exists()
        and (hedef / gpu_ortak.BILGI_DOSYASI).is_file() and ekran_karti.dosyalar_hazir(KART)[0])
ekran_karti.ayar_yaz(cihaz="otomatik")
ort = ekran_karti.ortam()
denetle("motor ortamı: dosyalar hazırsa KAFE_GPU_DEPS verilir, Studio'nun paketlerine yazılmaz",
        ort.get("KAFE_GPU_DEPS") == str(hedef) and ort["KAFE_CIHAZ"] == "otomatik" and str(yollar.VERI) in ort["KAFE_GPU_DEPS"])
(hedef / "tensorrt_libs" / "nvinfer_11.dll").write_bytes(b"kesik")
denetle("açılan dosya bozulursa hazır sayılmaz ve ortam verilmez", not ekran_karti.dosyalar_hazir(KART)[0]
        and "KAFE_GPU_DEPS" not in ekran_karti.ortam())
# özet tutmazsa
shutil.rmtree(ekran_karti.kok() / "dosyalar", ignore_errors=True)
gpu_ortak.PAKETLER = paketler(bozuk_sha=True)
ekran_karti.gpu_ortak.PAKETLER = gpu_ortak.PAKETLER
ekran_karti.IS.clear()
ekran_karti.indir_baslat()
for _ in range(100):
    if ekran_karti.IS.get("bitti"):
        break
    time.sleep(0.1)
denetle("SHA-256 tutmazsa: hata, dosya silinir, klasör hazır değil",
        "doğrulanamadı" in (ekran_karti.IS.get("hata") or "") and not ekran_karti.dosyalar_hazir(KART)[0]
        and not list((ekran_karti.kok() / "indirilen").glob("bind.whl*")))
denetle("arayüz durumu hata ve Türkçe ileti", ekran_karti.api_durum()["durum"] == "hata"
        and "doğrulanamadı" in ekran_karti.api_durum()["mesaj"])
gpu_ortak.PAKETLER = ekran_karti.gpu_ortak.PAKETLER = ASIL
denetle("gerçek paket listesi: sabit sürüm, resmi dizin, SHA-256 ve boyut",
        all(p["url"].startswith(("https://pypi.nvidia.com/", "https://files.pythonhosted.org/")) and len(p["sha256"]) == 64
            and p["boyut"] > 0 and p["surum"] in p["dosya"] for p in ASIL) and gpu_ortak.indirme_boyutu() > 1_900_000_000)
sunucu.shutdown()

print("Panel: seçim, beklenen cihaz, iş parçacığı")
ekran_karti.ayar_yaz(cihaz="islemci")
denetle("işlemci seçilince beklenen işlemci, ortamda dosya yok", ekran_karti.beklenen()["cihaz"] == "islemci"
        and "KAFE_GPU_DEPS" not in ekran_karti.ortam())
try:
    ekran_karti.ayar_yaz(hassasiyet="int8")
    int8 = False
except ValueError:
    int8 = True
denetle("ayar INT8'i kabul etmez", int8 and ekran_karti.ayar()["hassasiyet"] == "fp16")
import canli  # noqa: E402

ekran_karti.beklenen = lambda: {"cihaz": "ekran_karti", "hassasiyet": "fp16", "neden": None}
gpu_ip = canli.is_parcacigi_siniri(1, 32, {})
ekran_karti.beklenen = lambda: {"cihaz": "islemci", "hassasiyet": None, "neden": None}
denetle("ekran kartında süreç başına en çok 2 iş parçacığı, işlemcide 4", gpu_ip == canli.GPU_IS_PARCACIGI == 2
        and canli.is_parcacigi_siniri(1, 32, {}) == 4)

print()
kalan = [ad for ad, ok in SONUC if not ok]
print(f"{len(SONUC) - len(kalan)}/{len(SONUC)} denetim geçti" + (f" · kalanlar: {kalan}" if kalan else ""))
shutil.rmtree(GECICI, ignore_errors=True)
sys.exit(1 if kalan else 0)
