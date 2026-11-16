"""Geliştirici aracı: motor/deps klasörünü sabitlenmiş listeden (motor/deps.txt) doldurur.

  .venv\\Scripts\\python kurulum\\motor_deps.py              motor/deps'i baştan kurar
  .venv\\Scripts\\python kurulum\\motor_deps.py --denetle    yalnızca denetler (derle.cmd kullanır)

Motor, AugeLab Studio'nun kendi Python'unda çalışır. Studio'da torch, torchvision, numpy, OpenCV, yaml, scipy, psutil,
requests, matplotlib ve PIL vardır; ultralytics ve birkaç küçük paket yoktur. Bunlar Studio'nun ortamına KURULMAZ:
geliştirme ortamındaki (.venv) kurulu kopyaları, paket kayıtlarındaki (RECORD) dosya listesine göre motor/deps'e
kopyalanır ve motor onları sys.path'in SONUNA ekler (Studio'nun kendi torch / numpy / cv2'si önce gelir).
İnternetten bir şey indirilmez. motor/deps depoda tutulmaz (.gitignore).
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
LISTE = KOK / "motor" / "deps.txt"
HEDEF = KOK / "motor" / "deps"


def liste() -> list[tuple[str, str]]:
    """[(dağıtım adı, sürüm)]: motor/deps.txt satırları "ad==sürüm" (# ile başlayanlar açıklama)."""
    out = []
    for satir in LISTE.read_text(encoding="utf-8").splitlines():
        satir = satir.split("#", 1)[0].strip()
        if not satir:
            continue
        m = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)", satir)
        if not m:
            raise SystemExit(f"motor/deps.txt satırı okunamadı: {satir!r} (ad==sürüm olmalı)")
        out.append((m.group(1), m.group(2)))
    return out


def _normal(ad: str) -> str:
    return re.sub(r"[-_.]+", "_", ad).lower()


def _dist_info(site: Path, ad: str, surum: str) -> Path:
    for p in site.glob("*.dist-info"):
        a, _, s = p.name[: -len(".dist-info")].rpartition("-")
        if _normal(a) == _normal(ad):
            if s != surum:
                raise SystemExit(f"{ad}: geliştirme ortamında {s} kurulu, motor/deps.txt {surum} istiyor. "
                                 f".venv\\Scripts\\python -m pip install {ad}=={surum}")
            return p
    raise SystemExit(f"{ad}=={surum} geliştirme ortamında (.venv) kurulu değil: .venv\\Scripts\\python -m pip install {ad}=={surum}")


def _dosyalar(site: Path, bilgi: Path) -> list[Path]:
    """Dağıtımın site-packages içindeki dosyaları (RECORD'dan). Başlatıcılar (../../Scripts) ve önbellek girmez."""
    out = []
    with (bilgi / "RECORD").open(encoding="utf-8", newline="") as f:
        for satir in csv.reader(f):
            if not satir:
                continue
            goreli = Path(satir[0])
            if goreli.parts[0] == ".." or "__pycache__" in goreli.parts or goreli.suffix == ".pyc":
                continue
            out.append(goreli)
    return out


def kur() -> int:
    site = Path(sys.prefix) / "Lib" / "site-packages"
    if HEDEF.exists():
        shutil.rmtree(HEDEF)
    HEDEF.mkdir(parents=True)
    say = 0
    for ad, surum in liste():
        bilgi = _dist_info(site, ad, surum)
        for goreli in _dosyalar(site, bilgi):
            kaynak = site / goreli
            if not kaynak.is_file():
                continue
            hedef = HEDEF / goreli
            hedef.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(kaynak, hedef)
            say += 1
    return say


def denetle() -> list[str]:
    """Eksik ya da sürümü tutmayan dağıtımlar."""
    sorun = []
    for ad, surum in liste():
        bulundu = [p for p in HEDEF.glob("*.dist-info") if _normal(p.name[: -len(".dist-info")].rpartition("-")[0]) == _normal(ad)]
        if not bulundu:
            sorun.append(f"{ad} yok")
        elif not bulundu[0].name.endswith(f"-{surum}.dist-info"):
            sorun.append(f"{ad} sürümü {bulundu[0].name}")
    return sorun


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--denetle", action="store_true")
    a = ap.parse_args()
    if a.denetle:
        sorun = denetle() if HEDEF.is_dir() else ["motor/deps yok"]
        if sorun:
            raise SystemExit("motor/deps hazır değil (" + "; ".join(sorun) + "): .venv\\Scripts\\python kurulum\\motor_deps.py")
        print("motor/deps hazır.")
        return
    print(f"motor/deps: {kur()} dosya kopyalandı ({', '.join(a for a, _ in liste())}).")


if __name__ == "__main__":
    main()
