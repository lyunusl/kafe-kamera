"""Motoru AugeLab Studio'nun gerçek Python'unda çalıştırır ve sonucu 0.1.0'daki uygulama içi algılamayla karşılaştırır.

  .venv\\Scripts\\python egitim/dene_motor.py [video] [--adim 2] [--imgsz 960] [--onceki-yok] [--kare]

Hazır sahne (kafe-kamera.pmod) gerekmez: Studio'nun sahne döngüsü egitim/motor_dongusu.py ile taklit edilir. Motor klasörü
panelin Studio'ya yerleştirdiğinin aynısıdır (studio.motoru_yerlestir: kafe_motor, motor/deps, model) ve geçici bir
klasöre kurulur; Studio'nun kendi ortamına bir şey kurulmaz. Karşılaştırma:
  önceki  git'teki main dalının analiz.algila() işlevi, bu geliştirme ortamında (.venv'deki torch + ultralytics)
  motor   kafe_motor, Studio'nun Python'unda (Studio'nun torch / numpy / OpenCV'si + motor/deps)
Aynı olmalı: kare sayısı, işlenen kare numaraları, her karedeki iz numaraları. Kutular ve noktalar yuvarlama ile
torch sürümü farkı kadar ayrışabilir; en büyük farklar yazılır.
--kare: tek karelik işi de dener (yüz gizleme için kullanılan tahmin).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
GECICI = Path(tempfile.mkdtemp(prefix="kafe-motor-"))
os.environ["KAFE_KAMERA_VERI"] = str(GECICI / "veri")
sys.path.insert(0, str(KOK))
import studio  # noqa: E402
import studio_kurulum  # noqa: E402
import yollar  # noqa: E402


def motor_calistir(py: Path, motor: Path, tur: str, ortam_ek: dict) -> tuple[dict, dict]:
    cikti = GECICI / f"{tur}-sonuc.json"
    cikti.unlink(missing_ok=True)  # önceki işin sonucu okunmasın
    ortam = {k: v for k, v in os.environ.items() if not k.startswith(("KAFE_", "PYTHON"))}
    ortam.update({k: str(v) for k, v in ortam_ek.items()})
    ortam.update(KAFE_IS=f"{tur}#dene", KAFE_CIKTI=str(cikti), KAFE_ILERLEME=str(GECICI / f"{tur}.ilerleme"),
                 PYTHONIOENCODING="utf-8")
    r = subprocess.run([str(py), "-I", str(KOK / "egitim" / "motor_dongusu.py"), str(motor)], env=ortam, cwd=str(GECICI),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"motor çalışmadı ({r.returncode}):\n{r.stderr[-3000:]}")
    return json.loads(cikti.read_text(encoding="utf-8")), json.loads(r.stdout.strip().splitlines()[-1])


def onceki_algila(video: Path, adim: int, imgsz: int) -> tuple[dict, float]:
    """main dalındaki (0.1.0) analiz.algila(): ultralytics bu süreçte, .venv'deki torch ile."""
    kaynak = subprocess.run(["git", "show", "main:analiz.py"], cwd=KOK, capture_output=True, check=True).stdout
    yol = GECICI / "analiz_010.py"
    yol.write_bytes(kaynak)
    os.environ.update(YOLO_CONFIG_DIR=str(GECICI / "yolo"), YOLO_OFFLINE="1", YOLO_VERBOSE="False")
    spec = importlib.util.spec_from_file_location("analiz_010", yol)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    import renkler

    bas = time.perf_counter()
    veri = mod.algila(video, GECICI / "onbellek-010.json", adim, imgsz, str(yollar.MODEL), renkler.coz(None))
    return veri, time.perf_counter() - bas


def karsilastir(a: dict, b: dict) -> dict:
    out = {"alanlar_ayni": all(a[k] == b[k] for k in ("W", "H", "n", "adim")) and abs(a["fps"] - b["fps"]) < 1e-6,
           "kare_sayisi": (len(a["kareler"]), len(b["kareler"])),
           "kare_numaralari_ayni": [k["i"] for k in a["kareler"]] == [k["i"] for k in b["kareler"]],
           "zamanlar_ayni": [k["t"] for k in a["kareler"]] == [k["t"] for k in b["kareler"]]}
    iz_farki, kutu, nokta, guven, kisi_a, kisi_b = 0, 0.0, 0.0, 0.0, 0, 0
    ilk_fark = None
    for ka, kb in zip(a["kareler"], b["kareler"]):
        kisi_a += len(ka["d"])
        kisi_b += len(kb["d"])
        ia, ib = [d["id"] for d in ka["d"]], [d["id"] for d in kb["d"]]
        if ia != ib:
            iz_farki += 1
            ilk_fark = ilk_fark or {"i": ka["i"], "onceki": ia, "motor": ib}
            continue
        for da, db in zip(ka["d"], kb["d"]):
            kutu = max(kutu, max(abs(x - y) for x, y in zip(da["b"], db["b"])))
            for pa, pb in zip(da["k"], db["k"]):
                nokta = max(nokta, abs(pa[0] - pb[0]), abs(pa[1] - pb[1]))
                guven = max(guven, abs(pa[2] - pb[2]))
    out.update(iz_listesi_farkli_kare=iz_farki, ilk_iz_farki=ilk_fark, kisi_algilama=(kisi_a, kisi_b),
               en_buyuk_kutu_farki_px=round(kutu, 2), en_buyuk_nokta_farki_px=round(nokta, 2), en_buyuk_guven_farki=round(guven, 3),
               iz_numaralari=(len({d["id"] for k in a["kareler"] for d in k["d"]}), len({d["id"] for k in b["kareler"] for d in k["d"]})))
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?", default=str(KOK / "ornekler" / "videolar" / "salon.mp4"))
    ap.add_argument("--adim", type=int, default=2)
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--onceki-yok", action="store_true", help="0.1.0 algılamasını çalıştırma, yalnızca motoru dene")
    ap.add_argument("--kare", action="store_true", help="tek karelik işi de dene")
    ap.add_argument("--kaydet", help="iki sonucu da bu klasöre yaz")
    a = ap.parse_args()
    video = Path(a.video).resolve()
    exe = studio_kurulum.kurulu_studio()
    if exe is None:
        raise SystemExit("AugeLab Studio kurulu değil.")
    py = exe.parent / "Python" / "python.exe"
    motor = studio.motoru_yerlestir(GECICI / "kafe_engine")
    print("motor klasörü:", sorted(p.name for p in motor.iterdir()))
    sonuc = {}
    if a.kare:
        import cv2

        cap = cv2.VideoCapture(str(video))
        cap.set(cv2.CAP_PROP_POS_FRAMES, 100)
        ok, fr = cap.read()
        cap.release()
        resim = GECICI / "kare.png"
        cv2.imwrite(str(resim), fr)
        k, bilgi = motor_calistir(py, motor, "kare", {"KAFE_GIRDI": resim})
        resim.unlink()
        print("tek kare:", {"W": k.get("W"), "H": k.get("H"), "kisi": len(k.get("kisiler", [])), "hata": k.get("hata")}, bilgi)
        bos, _ = motor_calistir(py, motor, "kare", {"KAFE_GIRDI": GECICI / "olmayan.png"})
        print("olmayan kare (motor hata yazmalı):", bos)
        if "hata" not in bos:
            raise SystemExit("olmayan kare için motor hata yazmadı")
    m, bilgi = motor_calistir(py, motor, "video", {"KAFE_GIRDI": video, "KAFE_ADIM": a.adim, "KAFE_IMGSZ": a.imgsz})
    if "hata" in m:
        raise SystemExit(f"motor hata yazdı: {m['hata']}")
    print("motor:", json.dumps(bilgi, ensure_ascii=False))
    sonuc["motor"] = m
    if not a.onceki_yok:
        o, sure = onceki_algila(video, a.adim, a.imgsz)
        print(f"önceki (0.1.0, uygulama içinde): {sure:.1f} sn")
        sonuc["onceki"] = o
        print(json.dumps(karsilastir(o, m), ensure_ascii=False, indent=1))
    if a.kaydet:
        Path(a.kaydet).mkdir(parents=True, exist_ok=True)
        for ad, v in sonuc.items():
            (Path(a.kaydet) / f"{ad}.json").write_text(json.dumps(v), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    finally:
        import shutil

        shutil.rmtree(GECICI, ignore_errors=True)  # geçici motor klasörü ve önbellek
