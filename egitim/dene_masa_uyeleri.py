"""Masa üyeleri ve ara verme: sentetik izlerle masa oturumu kuralları (Studio gerekmez).

  .venv\\Scripts\\python egitim/dene_masa_uyeleri.py

Denenenler: kısa süre kalkıp aynı kıyafetle dönen kişi aynı oturumda ve tek müşteri kalır; ara verilmiş masaya farklı
görünümde biri gelirse oturumu devralmaz; iki masadaki birbirine benzeyen kişiler karışmaz (eşleştirme masa içinde); yerinden
ayrılmadan iz numarası değişirse yeni üye olmaz; herkes ara verme süresinden uzun giderse oturum kapanır; masanın yanından
geçen çalışan üye olmaz. Ayrıca görünüm özetinin kendisi (gerçek bir karede) ve hız.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("KAFE_KAMERA_VERI", tempfile.mkdtemp(prefix="kafe-uye-"))
kok = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(kok))
import numpy as np  # noqa: E402

import analiz  # noqa: E402
import gorunum  # noqa: E402

sonuclar = []


def denetle(ad, kosul):
    sonuclar.append((ad, bool(kosul)))
    print(("  geçti  " if kosul else "  KALDI  ") + ad, flush=True)


W, H, FPS = 1280, 720, 4.0
MASA_A = [[0.10, 0.30], [0.30, 0.30], [0.30, 0.70], [0.10, 0.70]]
MASA_B = [[0.60, 0.30], [0.80, 0.30], [0.80, 0.70], [0.60, 0.70]]


def ozet(ton: int) -> list:
    """Sentetik görünüm özeti: üst ve alt gövde tek bir ton kutusunda."""
    v = [0.0] * gorunum.BOYUT
    v[ton] = 1.0
    v[gorunum.H_KUTU + gorunum.GRI_KUTU + ton] = 1.0
    return v


def oturan(pid: int, x: float, y: float, g, o: float = 0.0) -> dict:
    """(x, y) kalça ortası (piksel) olan, oturur duruşlu kişi (diz kalçaya yakın)."""
    k = [[x, y - 160, 0.9]] * 5 + [[x - 30, y - 100, 0.9], [x + 30, y - 100, 0.9]] + [[x, y - 50, 0.9]] * 4 + \
        [[x - 20, y, 0.9], [x + 20, y, 0.9], [x - 20, y + 30, 0.9], [x + 20, y + 30, 0.9], [x - 20, y + 60, 0.9], [x + 20, y + 60, 0.9]]
    return {"id": pid, "b": [x - 50, y - 190, x + 50, y + 70], "k": k, "o": o, "g": g}


def ayakta(pid: int, x: float, y: float, g, o: float = 0.0) -> dict:
    k = [[x, y - 160, 0.9]] * 5 + [[x - 30, y - 100, 0.9], [x + 30, y - 100, 0.9]] + [[x, y - 50, 0.9]] * 4 + \
        [[x - 20, y, 0.9], [x + 20, y, 0.9], [x - 20, y + 90, 0.9], [x + 20, y + 90, 0.9], [x - 20, y + 180, 0.9], [x + 20, y + 180, 0.9]]
    return {"id": pid, "b": [x - 50, y - 190, x + 50, y + 200], "k": k, "o": o, "g": g}


def calistir(olaylar, sure: float, ayar_ek: dict | None = None) -> dict:
    """olaylar: t -> [algılama] üreten işlev. Analiz videosuz (canlı yol ile aynı)."""
    kareler = []
    n = int(sure * FPS)
    for i in range(n):
        t = round(i / FPS, 3)
        kareler.append({"i": i, "t": t, "d": olaylar(t)})
    veri = {"fps": FPS, "W": W, "H": H, "n": n, "adim": 1, "kareler": kareler}
    ayar = {"ad": "Deneme", "masalar": [{"ad": "Masa A", "poly": MASA_A}, {"ad": "Masa B", "poly": MASA_B}],
            "bolgeler": [], "calisan_renkleri": ["turuncu"], "bekleme_uyari_sn": 600, **(ayar_ek or {})}
    veri = analiz.izleri_birlestir(veri)
    return analiz.analiz(None, ayar, veri, Path(os.environ["KAFE_KAMERA_VERI"]) / "cikti" / "deneme")


AX, AY = 0.20 * W, 0.50 * H   # masa A'nın ortası
BX, BY = 0.70 * W, 0.50 * H
KIRMIZI, MAVI = ozet(0), ozet(8)


def masa(s: dict, ad: str) -> dict:
    return next(m for m in s["masalar"] if m["ad"] == ad)


print("Kısa ara ve aynı kıyafetle dönüş")
s = calistir(lambda t: [oturan(1, AX, AY, KIRMIZI)] if t < 60 else ([oturan(2, AX + 5, AY, KIRMIZI)] if t >= 180 else []), 260)
denetle("3 dk lavabo arası: tek oturum, tek müşteri, kalış aradan dahil",
        masa(s, "Masa A")["oturum"] == 1 and s["ozet"]["musteri"] == 1 and s["oturumlar"][0]["sure"] >= 250
        and s["oturumlar"][0].get("ara_sayisi") == 1)

print("Ara verilmiş masaya başka biri")
s = calistir(lambda t: [oturan(1, AX, AY, KIRMIZI)] if t < 60 else ([oturan(2, AX + 5, AY, MAVI)] if t >= 120 else []), 200)
denetle("farklı görünüşte gelen oturumu devralmaz: iki oturum, iki müşteri",
        masa(s, "Masa A")["oturum"] == 2 and s["ozet"]["musteri"] == 2 and s["oturumlar"][0]["sure"] < 70)

print("İki masada birbirine benzeyen kişiler")


def iki_masa(t):
    d = [oturan(2, BX, BY, KIRMIZI)]
    if t < 30:
        d.append(oturan(1, AX, AY, KIRMIZI))
    if t >= 40:
        d.append(oturan(3, BX + 40, BY, KIRMIZI))  # A'dakine benzeyen biri B'ye oturur
    return d


s = calistir(iki_masa, 100)
a_, b_ = masa(s, "Masa A"), masa(s, "Masa B")
an_a = next(m for m in s["anlik"]["masalar"] if m["ad"] == "Masa A")
an_b = next(m for m in s["anlik"]["masalar"] if m["ad"] == "Masa B")
denetle("eşleştirme masa içinde: B'ye oturan A'nın üyesi sayılmaz, A ara verir",
        an_a["durum"] == "ara" and an_a["uyeler"] == {"masada": 0, "ara_verdi": 1} and an_b["uyeler"]["masada"] == 2
        and s["ozet"]["musteri"] == 3 and a_["oturum"] == 1 and b_["oturum"] == 1)

print("Yerinde iz numarası değişimi")
s = calistir(lambda t: [oturan(1 if t < 30 else 2, AX, AY, KIRMIZI if t < 30 else None)], 60)
an = next(m for m in s["anlik"]["masalar"] if m["ad"] == "Masa A")
denetle("yerinden ayrılmayan kişinin izi değişse de tek üye, tek müşteri (görünüm olmasa da konumdan)",
        masa(s, "Masa A")["oturum"] == 1 and an["uyeler"] == {"masada": 1, "ara_verdi": 0} and s["ozet"]["musteri"] == 1)

print("Ara verme süresinden uzun yokluk")
s = calistir(lambda t: [oturan(1, AX, AY, KIRMIZI)] if t < 30 else ([oturan(2, AX, AY, KIRMIZI)] if t >= 80 else []), 120,
             {"masa_ara_sn": 20})
denetle("herkes ara verme süresinden (20 sn) uzun gidince oturum kapanır; dönen yeni oturum açar",
        masa(s, "Masa A")["oturum"] == 2 and s["oturumlar"][0]["sure"] < 40)
denetle("ara bitince oturum ayrılış anında biter (bekleme süresi kalışa eklenmez)", abs(s["oturumlar"][0]["bitis"] - 30) < 3)

print("Masanın yanından geçen çalışan")


def calisan_gecer(t):
    d = [oturan(1, AX, AY, KIRMIZI)]
    if 20 <= t < 40:
        d.append(ayakta(9, AX + 60, AY - 20, MAVI, o=2.5))  # turuncu kıyafetli çalışan, masada duruyor
    return d


s = calistir(calisan_gecer, 60)
an = next(m for m in s["anlik"]["masalar"] if m["ad"] == "Masa A")
s2 = calistir(lambda t: calisan_gecer(25.0) if t < 30 else [oturan(1, AX, AY, KIRMIZI)], 40)
an2 = next(m for m in s2["anlik"]["masalar"] if m["ad"] == "Masa A")
denetle("çalışan üye olmaz: müşteri 1, masada 1 üye", s["ozet"]["musteri"] == 1 and an["uyeler"]["masada"] == 1
        and s["ozet"]["calisan"] >= 1 and an2["uyeler"]["masada"] == 1)

print("Görünüm özeti gerçek karede")
import cv2  # noqa: E402

cap = cv2.VideoCapture(str(kok / "ornekler" / "videolar" / "salon.mp4"))
_, fr = cap.read()
cap.release()
hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
kisi = oturan(1, 400, 400, None)
g = gorunum.tanimlayici(hsv, kisi["b"], kisi["k"])
denetle("özet 30 sayı, iki bölge ayrı ayrı 1'e toplanır", g is not None and len(g) == 30
        and abs(sum(g[:15]) - 1) < 0.02 and abs(sum(g[15:]) - 1) < 0.02)
denetle("benzerlik: aynısı 1, ayrık renkler 0", abs(gorunum.benzerlik(g, g) - 1) < 1e-3 and gorunum.benzerlik(KIRMIZI, MAVI) < 1e-6)
bas = time.perf_counter()
for _ in range(500):
    gorunum.tanimlayici(hsv, kisi["b"], kisi["k"])
ms = (time.perf_counter() - bas) / 500 * 1000
print(f"  görünüm özeti: kişi başına {ms:.2f} ms (720p)", flush=True)
denetle("görünüm özeti ucuz (kişi başına < 2 ms)", ms < 2.0)
denetle("yüz eşleştirme kapalı", gorunum.YUZ_ESLEME is False and gorunum.yuz_benzerligi() is None)

kalan = [ad for ad, ok in sonuclar if not ok]
print(f"\n{len(sonuclar) - len(kalan)}/{len(sonuclar)} denetim geçti" + (f" · kalanlar: {kalan}" if kalan else ""))
sys.exit(1 if kalan else 0)
