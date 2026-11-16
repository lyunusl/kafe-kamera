"""Masa üyeleri için kısa ömürlü görünüm özeti: yalnızca kıyafet renkleri (gövde üstü ve altı), yüz yok.

Bir masadan kısa süre kalkıp (lavabo, kasa, telefon) geri dönen müşteri, aynı masanın ara veren üyelerinden biriyle bu
özetle eşleştirilir; böylece oturum bölünmez ve aynı kişi iki müşteri sayılmaz. Özet:
  - iskelet noktalarından bulunan iki bölgenin (omuz-kalça arası gövde, kalça-diz arası) HSV renk dağılımıdır,
  - yalnızca bellekte, masanın oturumu ve ara verme süresi boyunca tutulur; diske, günlüğe ya da sonuç dosyalarına
    yazılmaz, oturum kapanınca silinir,
  - yalnızca aynı masanın üyeleri arasında karşılaştırılır (genel bir kişi kimliği yoktur, kameralar ve oturumlar arası
    hiç eşleştirme yapılmaz).
Hem panelde (video dosyası analizi) hem AugeLab Studio'daki motorda (canlı) aynı kod kullanılır.
"""
from __future__ import annotations

import numpy as np

KP = 0.35
H_KUTU = 12          # renkli pikseller için ton kutusu
GRI_KUTU = 3         # renksiz pikseller için parlaklık kutusu (koyu / orta / açık)
BOYUT = 2 * (H_KUTU + GRI_KUTU)
UST_AGIRLIK = 0.7    # oturan kişide alt gövde çoğu zaman masanın arkasında kalır


def _bolge(kutu, kp, ust: bool):
    x1, y1, x2, y2 = kutu
    w, h = x2 - x1, y2 - y1
    om = [kp[i] for i in (5, 6) if kp[i][2] > KP]
    ka = [kp[i] for i in (11, 12) if kp[i][2] > KP]
    di = [kp[i] for i in (13, 14) if kp[i][2] > KP]
    if ust:
        if len(om) == 2 and ka:
            xs = [p[0] for p in om + ka]
            return min(xs), min(p[1] for p in om), max(xs), max(p[1] for p in ka)
        return x1 + 0.25 * w, y1 + 0.2 * h, x2 - 0.25 * w, y1 + 0.55 * h
    if ka and di:
        xs = [p[0] for p in ka + di]
        return min(xs) - 0.05 * w, max(p[1] for p in ka), max(xs) + 0.05 * w, max(p[1] for p in di)
    return x1 + 0.2 * w, y1 + 0.55 * h, x2 - 0.2 * w, y1 + 0.85 * h


def _dagilim(hsv: np.ndarray, b) -> np.ndarray | None:
    H, W = hsv.shape[:2]
    xa, ya, xb, yb = (int(max(0, b[0])), int(max(0, b[1])), int(min(W, b[2])), int(min(H, b[3])))
    if xb - xa < 6 or yb - ya < 6:
        return None
    roi = hsv[ya:yb, xa:xb].reshape(-1, 3).astype(np.int32)
    renkli = (roi[:, 1] > 50) & (roi[:, 2] > 40)
    ton = np.bincount((roi[renkli, 0] * H_KUTU // 180).clip(0, H_KUTU - 1), minlength=H_KUTU)
    gri = np.bincount((roi[~renkli, 2] * GRI_KUTU // 256).clip(0, GRI_KUTU - 1), minlength=GRI_KUTU)
    v = np.concatenate([ton, gri]).astype(np.float32)
    toplam = float(v.sum())
    return v / toplam if toplam > 0 else None


def tanimlayici(hsv: np.ndarray, kutu, kp) -> list[float] | None:
    """Kişinin görünüm özeti (30 sayı, iki bölge) ya da üst gövde görünmüyorsa None."""
    ust = _dagilim(hsv, _bolge(kutu, kp, True))
    if ust is None:
        return None
    alt = _dagilim(hsv, _bolge(kutu, kp, False))
    alt = alt if alt is not None else np.zeros(H_KUTU + GRI_KUTU, np.float32)
    return [round(float(x), 3) for x in np.concatenate([ust, alt])]


def benzerlik(a, b) -> float:
    """0-1 arası (Bhattacharyya katsayısı; üst gövde 0,7, alt gövde 0,3 ağırlıklı; alt bölge birinde yoksa yalnız üst)."""
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    n = H_KUTU + GRI_KUTU
    ust = float(np.sqrt(np.clip(a[:n] * b[:n], 0, None)).sum())
    if a[n:].sum() <= 0 or b[n:].sum() <= 0:
        return ust
    alt = float(np.sqrt(np.clip(a[n:] * b[n:], 0, None)).sum())
    return UST_AGIRLIK * ust + (1 - UST_AGIRLIK) * alt


class Ortalama:
    """Bir üyenin birkaç karedeki özetlerinin ortalaması (en çok son N kare)."""

    def __init__(self, n: int = 30):
        self.n, self.liste = n, []

    def ekle(self, g) -> None:
        if g is not None:
            self.liste.append(np.asarray(g, np.float32))
            del self.liste[:-self.n]

    def deger(self):
        if not self.liste:
            return None
        m = np.mean(self.liste, axis=0)
        n = H_KUTU + GRI_KUTU
        for s in (slice(0, n), slice(n, 2 * n)):
            t = float(m[s].sum())
            if t > 0:
                m[s] /= t
        return m


# ---- yüz ile eşleştirme: kapalı. Açmak için gerekenler raporda; burada yalnızca bağlantı noktası var.
YUZ_ESLEME = False


def yuz_benzerligi(*_a, **_k) -> float | None:
    """Kapalı (YUZ_ESLEME = False). Kafe Kamera yüzleri gizler ve kimlik tanımaz; yüz özeti hesaplanmaz."""
    return None
