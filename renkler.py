"""Çalışan kıyafet renkleri.

Çalışan, müşteriden kıyafet rengiyle ayrılır (kimlik tanıma yok). Ayar dosyasında:

  "calisan_renkleri": ["turuncu"]                      # tek renk
  "calisan_renkleri": ["siyah", "beyaz"]               # garson siyah, mutfak beyaz
  "calisan_renkleri": [{"renk": "yesil", "esik": 0.15}] # hazır rengin eşiğini değiştir
  "calisan_renkleri": [{"ad": "Firma yeşili", "ton": [[60, 80]], "doygunluk": [100, 255], "parlaklik": [60, 255], "esik": 0.12, "bolge": "govde"}]

Renk aralıkları OpenCV HSV ölçeğindedir: ton 0-179, doygunluk ve parlaklık 0-255.
"esik": gövde bölgesindeki piksellerin en az bu oranı renge uyarsa o kare "çalışan rengi" sayılır.
"bolge": "onluk" (omuzdan dizlere, önlük için) ya da "govde" (omuzdan kalçaya, gömlek/tişört için).
"""
from __future__ import annotations

import hashlib
import json

import warnings

import cv2
import numpy as np

KP = 0.35

# zayif=True: müşterilerde de sık görülen renk; tek başına güvenilmez
HAZIR: dict[str, dict] = {
    "turuncu": {"ad": "Turuncu", "ton": [[0, 11], [176, 179]], "doygunluk": [150, 255], "parlaklik": [110, 255], "esik": 0.07, "bolge": "onluk", "hex": "#ff7a1a"},
    "kirmizi": {"ad": "Kırmızı", "ton": [[0, 7], [170, 179]], "doygunluk": [130, 255], "parlaklik": [80, 255], "esik": 0.10, "bolge": "govde", "hex": "#e0262b"},
    "bordo": {"ad": "Bordo", "ton": [[0, 8], [165, 179]], "doygunluk": [90, 255], "parlaklik": [30, 115], "esik": 0.15, "bolge": "govde", "hex": "#7a1525"},
    "sari": {"ad": "Sarı", "ton": [[20, 34]], "doygunluk": [110, 255], "parlaklik": [120, 255], "esik": 0.10, "bolge": "govde", "hex": "#f5c518"},
    "yesil": {"ad": "Yeşil", "ton": [[38, 85]], "doygunluk": [80, 255], "parlaklik": [45, 255], "esik": 0.10, "bolge": "govde", "hex": "#2f9e44"},
    "turkuaz": {"ad": "Turkuaz", "ton": [[85, 100]], "doygunluk": [90, 255], "parlaklik": [80, 255], "esik": 0.10, "bolge": "govde", "hex": "#1fb5b0"},
    "mavi": {"ad": "Mavi", "ton": [[100, 124]], "doygunluk": [140, 255], "parlaklik": [90, 255], "esik": 0.12, "bolge": "govde", "hex": "#1f6fe0"},
    "lacivert": {"ad": "Lacivert", "ton": [[105, 130]], "doygunluk": [80, 255], "parlaklik": [25, 110], "esik": 0.25, "bolge": "govde", "hex": "#1b2a5c", "zayif": True},
    "mor": {"ad": "Mor", "ton": [[125, 150]], "doygunluk": [70, 255], "parlaklik": [50, 255], "esik": 0.10, "bolge": "govde", "hex": "#7b3fbf"},
    "pembe": {"ad": "Pembe", "ton": [[150, 172]], "doygunluk": [70, 255], "parlaklik": [120, 255], "esik": 0.10, "bolge": "govde", "hex": "#e84a9a"},
    "siyah": {"ad": "Siyah", "ton": [[0, 179]], "doygunluk": [0, 255], "parlaklik": [0, 50], "esik": 0.45, "bolge": "govde", "hex": "#151515", "zayif": True},
    "beyaz": {"ad": "Beyaz", "ton": [[0, 179]], "doygunluk": [0, 35], "parlaklik": [185, 255], "esik": 0.40, "bolge": "govde", "hex": "#f4f4f4", "zayif": True},
}


def coz(liste) -> list[dict]:
    """Ayar dosyasındaki 'calisan_renkleri' listesini tam tanımlara çevirir."""
    if not liste:
        liste = ["turuncu"]
    if isinstance(liste, (str, dict)):
        liste = [liste]
    out = []
    for r in liste:
        if isinstance(r, str):
            if r not in HAZIR:
                raise ValueError(f"Bilinmeyen renk: {r}. Seçenekler: {', '.join(HAZIR)}")
            out.append({"kod": r, **HAZIR[r]})
        else:
            taban = HAZIR.get(r.get("renk", ""), {})
            t = {"kod": r.get("renk", "ozel"), "bolge": "govde", "esik": 0.12, "ad": "Özel", **taban, **{k: v for k, v in r.items() if k != "renk"}}
            for alan in ("ton", "doygunluk", "parlaklik"):
                if alan not in t:
                    raise ValueError(f"Özel renkte '{alan}' eksik: {r}")
            if t["ton"] and not isinstance(t["ton"][0], (list, tuple)):
                t["ton"] = [t["ton"]]
            out.append(t)
    return out


SURUM = 2  # renk hesabı değişince önbellekteki puanlar yenilensin


def imza(renkler: list[dict]) -> str:
    alanlar = [SURUM] + [{k: r[k] for k in ("ton", "doygunluk", "parlaklik", "esik", "bolge")} for r in renkler]
    return hashlib.sha1(json.dumps(alanlar, sort_keys=True).encode()).hexdigest()[:12]


def maske(hsv: np.ndarray, r: dict) -> np.ndarray:
    """Renge uyan pikseller (tam kare ya da bir parça)."""
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    m = np.zeros(h.shape, bool)
    for a, b in r["ton"]:
        m |= (h >= a) & (h <= b)
    return m & (s >= r["doygunluk"][0]) & (s <= r["doygunluk"][1]) & (v >= r["parlaklik"][0]) & (v <= r["parlaklik"][1])


def arka_plan(kareler: list, kutular: list) -> tuple[np.ndarray, np.ndarray]:
    """Kişi kutuları dışarıda bırakılarak örnek karelerin ortancası: masa, sandalye, zemin.
    Dönüş: (arka plan HSV, hiç boş görülmemiş piksel maskesi). Yarım çözünürlükte hesaplanır."""
    H, W = kareler[0].shape[:2]
    w2, h2 = W // 2, H // 2
    yig = np.full((len(kareler), h2, w2, 3), np.nan, np.float32)
    for j, (fr, kut) in enumerate(zip(kareler, kutular)):
        g = cv2.resize(fr, (w2, h2), interpolation=cv2.INTER_AREA).astype(np.float32)
        for x1, y1, x2, y2 in kut:
            g[max(0, int(y1 / 2)):int(y2 / 2) + 1, max(0, int(x1 / 2)):int(x2 / 2) + 1] = np.nan
        yig[j] = g
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        med = np.nanmedian(yig, 0)
    bos = np.isnan(med).any(2)
    med = np.nan_to_num(med, nan=0).astype(np.uint8)
    med = cv2.resize(med, (W, H), interpolation=cv2.INTER_NEAREST)
    bos = cv2.resize(bos.astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST) > 0
    return cv2.cvtColor(med, cv2.COLOR_BGR2HSV), bos


def arka_maskeleri(arka_hsv: np.ndarray, bos: np.ndarray, renkler: list) -> list:
    """Her renk için arka planda zaten o renkte olan pikseller (ahşap sandalye, turuncu duvar...)."""
    return [maske(arka_hsv, r) & ~bos for r in renkler]


def _roi(hsv: np.ndarray, kutu, kp, bolge: str):
    x1, y1, x2, y2 = kutu
    w, h = x2 - x1, y2 - y1
    om = [kp[i] for i in (5, 6) if kp[i][2] > KP]
    ka = [kp[i] for i in (11, 12) if kp[i][2] > KP]
    if len(om) == 2 and len(ka) >= 1:
        xs = [p[0] for p in om + ka]
        ya = min(p[1] for p in om)
        yb = max(p[1] for p in ka)
        yb = yb + (0.8 if bolge == "onluk" else 0.1) * (yb - ya)
        xa, xb = min(xs), max(xs)
    else:
        xa, xb = x1 + 0.25 * w, x2 - 0.25 * w
        ya, yb = (y1 + 0.22 * h, y1 + 0.82 * h) if bolge == "onluk" else (y1 + 0.20 * h, y1 + 0.55 * h)
    H, W = hsv.shape[:2]
    xa, xb = int(max(0, xa)), int(min(W, xb))
    ya, yb = int(max(0, ya)), int(min(H, yb))
    if xb - xa < 4 or yb - ya < 4:
        return None
    return ya, yb, xa, xb


def oran(hsv: np.ndarray, kutu, kp, r: dict, arka: np.ndarray | None = None) -> float:
    """Gövde bölgesinde bu renge uyan piksel oranı. Dağınık pikseller (ten, ahşap kenarı) açma işlemiyle silinir;
    arka planda da bu renkte olan pikseller (sandalye, masa) sayılmaz."""
    k = _roi(hsv, kutu, kp, r["bolge"])
    if k is None:
        return 0.0
    ya, yb, xa, xb = k
    m = maske(hsv[ya:yb, xa:xb], r)
    if arka is not None:
        m &= ~arka[ya:yb, xa:xb]
    ks = max(3, (xb - xa) // 12) | 1
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ks, ks))) > 0
    return float(m.mean())


def puan(hsv: np.ndarray, kutu, kp, renkler: list, arkalar: list | None = None) -> float:
    """1'in üstü: bu karede kişi seçili çalışan renklerinden birini giyiyor."""
    arkalar = arkalar or [None] * len(renkler)
    return max(oran(hsv, kutu, kp, r, a) / r["esik"] for r, a in zip(renkler, arkalar))
