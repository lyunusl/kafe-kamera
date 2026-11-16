"""AugeLab Studio'nun Python'unda, Studio'nun sahne döngüsünü taklit ederek motoru çalıştırır (hazır sahne gerekmez).

  "<Studio>\\Python\\python.exe" -I egitim/motor_dongusu.py <motor klasörü>

Motor klasörü, panelin Studio'ya yerleştirdiği kafe_engine'in aynısıdır (studio.motoru_yerlestir). sys.path'e bloklar gibi
SONDAN eklenir: torch, numpy ve OpenCV Studio'nun kendi paketlerinden gelir. İş, bloklarda olduğu gibi ortam
değişkenlerinden okunur (KAFE_IS, KAFE_GIRDI, KAFE_CIKTI, ...). Her adımda Kafe Kaynak'ın çıktıları Kafe Algılama'ya verilir;
sonuç dosyası yazılınca biter. Ekrana hangi torch / ultralytics kopyasının yüklendiği yazılır.
"""
import json
import os
import sys
import time

klasor = os.path.abspath(sys.argv[1])
for p in (klasor, os.path.join(klasor, "deps")):
    if p not in sys.path:
        sys.path.append(p)
from kafe_motor import blok  # noqa: E402

cikti = os.environ["KAFE_CIKTI"]
kaynak_durumu, algila_durumu = {}, {}
bas = time.perf_counter()
adim = 0
while not os.path.exists(cikti):
    goruntu, sira, zaman, bitti, durum = blok.kaynak(kaynak_durumu, "")
    blok.algila(algila_durumu, goruntu, "", sira, zaman, bitti, durum)
    adim += 1
    if adim > 10_000_000:
        raise SystemExit("sonuç gelmedi")
sure = time.perf_counter() - bas
yuklenen = {ad: os.path.relpath(getattr(sys.modules[ad], "__file__", ""), sys.prefix) if ad in sys.modules else None
            for ad in ("torch", "numpy", "cv2", "ultralytics", "lap")}
if "ultralytics" in sys.modules and "deps" in (sys.modules["ultralytics"].__file__ or ""):
    yuklenen["ultralytics"] = "motor/deps"
print(json.dumps({"sure_sn": round(sure, 1), "adim": adim, "surumler": __import__("kafe_motor.algilama").algilama.surumler(),
                  "yer": yuklenen}, ensure_ascii=False))
