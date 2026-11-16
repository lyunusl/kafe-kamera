"""Yüz gizleme: bir kişinin baş bölgesini pikseller, kimse bulunamayan kareyi bütünüyle bulanıklaştırır.

Hem panelde (analiz.py: işaretli video, bağlantı denemesi karesi) hem AugeLab Studio'daki motorda (kafe_motor: canlı önizleme)
aynı kod kullanılır; motor bu dosyanın kopyasını taşır (studio.motor_kaynaklari).
"""
from __future__ import annotations

import cv2
import numpy as np

KP = 0.35  # keypoint güven eşiği (analiz.KP ile aynı)


def bas_bolgesi(b, k):
    """Yüzü örtecek elips: (cx, cy, rx, ry)."""
    x1, y1, x2, y2 = b
    w, h = x2 - x1, y2 - y1
    pts = np.array([k[i][:2] for i in range(5) if k[i][2] > KP], dtype=float)
    om = [k[i] for i in (5, 6) if k[i][2] > KP]
    omuz = abs(om[0][0] - om[1][0]) if len(om) == 2 else 0.0
    if len(pts) >= 2:
        c = pts.mean(0)
        r = float(np.linalg.norm(pts - c, axis=1).max()) * 2.1
    elif len(pts) == 1:
        c, r = pts[0], 0.0
    else:
        c, r = np.array([(x1 + x2) / 2, y1 + 0.11 * h]), 0.0
    r = max(r, 0.55 * omuz, 0.11 * h, 0.2 * w, 9.0)
    r = min(r, max(0.27 * h, 12.0))
    r *= 1.15
    return float(c[0]), float(c[1]), r, r * 1.2


def piksel(fr, cx, cy, rx, ry):
    H, W = fr.shape[:2]
    xa, xb = int(max(0, cx - rx)), int(min(W, cx + rx))
    ya, yb = int(max(0, cy - ry)), int(min(H, cy + ry))
    if xb - xa < 4 or yb - ya < 4:
        return
    roi = fr[ya:yb, xa:xb]
    blok = max(5, int(rx / 2.2))
    kucuk = cv2.resize(roi, (max(2, (xb - xa) // blok), max(2, (yb - ya) // blok)), interpolation=cv2.INTER_AREA)
    buyuk = cv2.resize(kucuk, (xb - xa, yb - ya), interpolation=cv2.INTER_NEAREST)
    maske = np.zeros(roi.shape[:2], np.uint8)
    cv2.ellipse(maske, (int(cx - xa), int(cy - ya)), (int(rx), int(ry)), 0, 0, 360, 255, -1)
    roi[maske > 0] = buyuk[maske > 0]


BULANIK_GENISLIK = 24  # kimse bulunamayan kare bu genişliğe küçültülüp büyütülür: yüz seçilmez, masalar kabaca görünür


def tamamen_bulaniklastir(fr: np.ndarray) -> np.ndarray:
    """Bütün kareyi yüz tanınmayacak kadar bulanıklaştırır (1280 piksellik karede yaklaşık 53 piksellik bloklar, sonra
    yumuşatma). Masalar, tezgâh ve odanın düzeni kabaca görünür kalır; bölgeler yine çizilebilir."""
    H, W = fr.shape[:2]
    w = max(2, min(W, BULANIK_GENISLIK))
    h = max(2, int(round(H * w / W)))
    kucuk = cv2.resize(fr, (w, h), interpolation=cv2.INTER_AREA)
    buyuk = cv2.resize(kucuk, (W, H), interpolation=cv2.INTER_LINEAR)
    k = max(3, (W // w) | 1)
    return cv2.GaussianBlur(buyuk, (k, k), 0)
