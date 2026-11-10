"""Kafe / restoran kamera analizi.

Bir güvenlik kamerası videosundan şunları çıkarır:
  - masa oturumları (hangi masa, kaç kişi, kaç saniye), doluluk ve devir
  - ilk garson teması süresi, ilgilenilmeyen masa uyarısı, kirli masa süresi
  - çalışan süre dağılımı (servis, tezgâh, yürüme, boşta)
  - kasa kuyruğu ve sıraya girmeden çıkanlar
Yüzler her karede piksellenir; kimlik tanıma yapılmaz.

Kullanım (kaynak koddan):
  python analiz.py veri/videolar/salon.mp4 veri/ayar/salon.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict, deque
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import renkler
import yollar

_GIZLI = {"creationflags": subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, "CREATE_NO_WINDOW") else {}
KP = 0.35  # keypoint güven eşiği

# ---------------------------------------------------------------- algılama


def kareleri_gez(video: Path, veri: dict, fn) -> None:
    """Önbellekteki her algılama için videoyu yeniden çözer (model çalıştırmadan): fn(hsv, det)."""
    cap = cv2.VideoCapture(str(video))
    sozluk = {kr["i"]: kr for kr in veri["kareler"]}
    i = -1
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        i += 1
        kr = sozluk.get(i)
        if kr is None or not kr["d"]:
            continue
        hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
        for d in kr["d"]:
            fn(hsv, d)
    cap.release()


def arka_plan(video: Path, veri: dict, adet: int = 40):
    """Kişiler çıkarılmış arka plan (HSV) ve hiç boş görülmemiş pikseller."""
    cap = cv2.VideoCapture(str(video))
    kar = veri["kareler"]
    secilen = [kar[int(j)] for j in np.linspace(0, len(kar) - 1, min(adet, len(kar)))]
    kareler, kutular = [], []
    for kr in secilen:
        cap.set(cv2.CAP_PROP_POS_FRAMES, kr["i"])
        ok, fr = cap.read()
        if ok:
            kareler.append(fr)
            kutular.append([d["b"] for d in kr["d"]])
    cap.release()
    return renkler.arka_plan(kareler, kutular)


def renk_puanla(video: Path, veri: dict, renk_list: list[dict]) -> dict:
    """Çalışan renk puanlarını hesaplar; renk değişince algılama tekrarlanmaz."""
    arkalar = renkler.arka_maskeleri(*arka_plan(video, veri), renk_list)

    def fn(hsv, d):
        d["o"] = round(renkler.puan(hsv, d["b"], d["k"], renk_list, arkalar), 3)
    kareleri_gez(video, veri, fn)
    veri["renk_imza"] = renkler.imza(renk_list)
    return veri


def renk_tara(video: Path, veri: dict, cikti: Path) -> list[dict]:
    """Bütün hazır renkleri dener: hangi renk kaç kişiyi çalışan sayıyor, ayrım ne kadar net."""
    hazir = renkler.coz(list(renkler.HAZIR))
    arkalar = renkler.arka_maskeleri(*arka_plan(video, veri), hazir)
    say = defaultdict(lambda: np.zeros(len(hazir)))
    adet = defaultdict(int)

    def fn(hsv, d):
        adet[d["id"]] += 1
        say[d["id"]] += np.array([renkler.oran(hsv, d["b"], d["k"], r, a) > r["esik"] for r, a in zip(hazir, arkalar)], float)
    kareleri_gez(video, veri, fn)
    izler = [pid for pid in adet if adet[pid] >= 5]
    tablo = []
    for j, r in enumerate(hazir):
        kesir = np.array([say[pid][j] / adet[pid] for pid in izler]) if izler else np.zeros(0)
        cal = kesir >= 0.35
        ayrim = float(kesir[cal].mean() - (kesir[~cal].mean() if (~cal).any() else 0.0)) if cal.any() else 0.0
        tablo.append({"renk": r["kod"], "ad": r["ad"], "calisan_iz": int(cal.sum()), "toplam_iz": len(izler),
                      "ayrim": round(ayrim, 2), "zayif": bool(r.get("zayif"))})
    tablo.sort(key=lambda x: -x["ayrim"])
    cikti.mkdir(parents=True, exist_ok=True)
    (cikti / "renk_tarama.json").write_text(json.dumps(tablo, ensure_ascii=False, indent=1), encoding="utf-8")
    return tablo


def algila(video: Path, onbellek: Path, adim: int, imgsz: int, model_adi: str, renk_list: list[dict]) -> dict:
    from ultralytics import YOLO

    model = YOLO(model_adi)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"Video açılamadı: {video.name}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    toplam = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    kareler = []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if i % adim == 0:
            r = model.track(fr, persist=True, tracker="bytetrack.yaml", conf=0.2, iou=0.6, imgsz=imgsz, verbose=False)[0]
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
            kareler.append({"i": i, "t": round(i / fps, 3), "d": dets})
            if len(kareler) % 25 == 0:
                print(f"  algılama: {i}" + (f" / {toplam} kare (%{100 * i // toplam})" if toplam > 0 else " kare"), flush=True)
        i += 1
    cap.release()
    if not kareler:
        raise SystemExit(f"Videodan kare okunamadı: {video.name}")
    print(f"  algılama: {i} / {i} kare (%100)", flush=True)
    veri = {"fps": fps, "W": W, "H": H, "n": i, "adim": adim, "kareler": kareler}
    print("  çalışan renkleri hesaplanıyor", flush=True)
    veri = renk_puanla(video, veri, renk_list)
    onbellek.parent.mkdir(parents=True, exist_ok=True)
    onbellek.write_text(json.dumps(veri), encoding="utf-8")
    return veri


# ---------------------------------------------------------------- geometri


def capa(b, k):
    """Kişinin konum noktası: kalça ortası, yoksa kutunun alt-orta bölgesi."""
    ka = [k[i] for i in (11, 12) if k[i][2] > KP]
    if len(ka) == 2:
        return ((ka[0][0] + ka[1][0]) / 2, (ka[0][1] + ka[1][1]) / 2)
    return ((b[0] + b[2]) / 2, b[1] + 0.62 * (b[3] - b[1]))


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


def yuzleri_gizle(fr: np.ndarray, model=None) -> np.ndarray:
    """Tek bir karede bütün yüzleri pikseller (bölge çizme karesi gibi kaydedilen görüntüler için)."""
    if model is None:
        from ultralytics import YOLO
        model = YOLO(str(yollar.MODEL))
    r = model(fr, conf=0.15, imgsz=1280, verbose=False)[0]
    if r.boxes is not None and r.keypoints is not None:
        for b, k in zip(r.boxes.xyxy.tolist(), r.keypoints.data.tolist()):
            piksel(fr, *bas_bolgesi(b, k))
    return fr


def olcekle(poly: np.ndarray, s: float) -> np.ndarray:
    c = poly.mean(0)
    return (c + (poly - c) * s).astype(np.float32)


def icinde(poly: np.ndarray, p) -> bool:
    return cv2.pointPolygonTest(poly, (float(p[0]), float(p[1])), False) >= 0


def oturma_orani(k) -> float | None:
    """(diz - kalça) / (kalça - omuz) dikey oranı: ayakta ~0,7-1,1, otururken < 0,45."""
    om = [k[i] for i in (5, 6) if k[i][2] > KP]
    ka = [k[i] for i in (11, 12) if k[i][2] > KP]
    di = [k[i] for i in (13, 14) if k[i][2] > KP]
    if not om or not ka or not di:
        return None
    oy, ky, dy = (float(np.mean([p[1] for p in g])) for g in (om, ka, di))
    if ky - oy < 5:
        return None
    return (dy - ky) / (ky - oy)


def oturanlar(veri: dict, masa_polileri: list) -> set:
    """Duruşu çoğunlukla oturur olan ya da bir masada baştan sona kıpırdamadan kalan izler."""
    dur = defaultdict(list)
    konum = defaultdict(list)
    for kr in veri["kareler"]:
        for d in kr["d"]:
            o = oturma_orani(d["k"])
            if o is not None:
                dur[d["id"]].append(o < 0.45)
            konum[d["id"]].append((kr["t"], capa(d["b"], d["k"]), d["b"][3] - d["b"][1]))
    sonuc = {pid for pid, v in dur.items() if len(v) >= 5 and np.mean(v) >= 0.5}
    for pid, ks in konum.items():
        # duruşu görülebilen ve ayakta olan (masada servis yapan garson) bu kurala girmez;
        # yalnızca dizleri hiç görünmeyen (masanın arkasında oturan) kişiler için
        if pid in sonuc or len(dur[pid]) >= 5 or len(ks) < 5 or ks[-1][0] - ks[0][0] < 4.0 or not masa_polileri:
            continue
        p = np.array([a for _, a, _ in ks])
        boy = float(np.median([h for _, _, h in ks]))
        sabit = np.mean(np.hypot(*(p - np.median(p, 0)).T) < 0.6 * boy) >= 0.8
        masada = np.mean([any(icinde(m, a) for m in masa_polileri) for a in p]) >= 0.7
        if sabit and masada:
            sonuc.add(pid)
    return sonuc


# ---------------------------------------------------------------- iz birleştirme


def izleri_birlestir(veri: dict) -> dict:
    """Kopan izleri (kısa süre kaybolup yakında yeniden çıkan kişi) tek kimliğe bağlar."""
    ozet = {}
    for kr in veri["kareler"]:
        for d in kr["d"]:
            a = capa(d["b"], d["k"])
            h = d["b"][3] - d["b"][1]
            o = ozet.setdefault(d["id"], {"t0": kr["t"], "p0": a, "h": [], "o": []})
            o["t1"], o["p1"] = kr["t"], a
            o["h"].append(h)
            o["o"].append(d["o"] > 1.0)
    harita = {}
    devam = set()
    for pid in sorted(ozet, key=lambda q: ozet[q]["t0"]):
        o = ozet[pid]
        en_iyi, en_d = None, 1e9
        for qid, q in ozet.items():
            if qid == pid or qid in devam or q["t1"] >= o["t0"] or o["t0"] - q["t1"] > 2.0:
                continue
            if (np.mean(o["o"]) >= 0.35) != (np.mean(q["o"]) >= 0.35):
                continue
            d = float(np.hypot(o["p0"][0] - q["p1"][0], o["p0"][1] - q["p1"][1]))
            if d < 0.6 * max(np.median(o["h"]), np.median(q["h"])) and d < en_d:
                en_iyi, en_d = qid, d
        if en_iyi is not None:
            devam.add(en_iyi)
            harita[pid] = en_iyi

    def kok(p):
        while p in harita:
            p = harita[p]
        return p

    for kr in veri["kareler"]:
        for d in kr["d"]:
            d["id"] = kok(d["id"])
    return veri


# ---------------------------------------------------------------- çizim

_FONTLAR: dict = {}


def font(boyut: int, kalin: bool = True):
    anahtar = (boyut, kalin)
    if anahtar not in _FONTLAR:
        for ad in (["seguisb.ttf", "segoeuib.ttf"] if kalin else ["segoeui.ttf"]) + ["arial.ttf"]:
            try:
                _FONTLAR[anahtar] = ImageFont.truetype(f"C:/Windows/Fonts/{ad}", boyut)
                break
            except OSError:
                continue
        else:
            _FONTLAR[anahtar] = ImageFont.load_default()
    return _FONTLAR[anahtar]


def etiket(ciz: ImageDraw.ImageDraw, xy, metin, zemin, yazi=(255, 255, 255), boyut=20, orta=False):
    f = font(boyut)
    l, t, r, b = ciz.textbbox((0, 0), metin, font=f)
    w, h = r - l, b - t
    x, y = xy
    if orta:
        x -= (w + 16) / 2
    x = min(max(6, x), ciz.im.size[0] - w - 22)
    ciz.rounded_rectangle([x, y, x + w + 16, y + h + 12], radius=8, fill=zemin)
    ciz.text((x + 8, y + 5 - t), metin, font=f, fill=yazi)
    return w + 16, h + 12


def sure(sn: float) -> str:
    sn = max(0, int(round(sn)))
    if sn >= 3600:
        return f"{sn // 3600}:{sn % 3600 // 60:02d}:{sn % 60:02d}"
    return f"{sn // 60}:{sn % 60:02d}"


def okunur(sn: float) -> str:
    """Uyarı metinleri için: 45 sn, 12 dk, 1 sa 05 dk."""
    sn = int(round(sn))
    if sn < 120:
        return f"{sn} sn"
    if sn < 3600:
        return f"{sn // 60} dk"
    return f"{sn // 3600} sa {sn % 3600 // 60:02d} dk"


def saat_sn(metin: str) -> int:
    h, m, s_ = (int(x) for x in metin.split(":"))
    return h * 3600 + m * 60 + s_


def zaman_fonksiyonu(noktalar: list):
    """Kayıt cihazı hızlandırması: ekrandaki saat okumalarından video saniyesi → gerçek saniye.
    noktalar: [[video_sn, "SS:DD:ss"], ...]. Uçlarda son eğimle uzatılır. Dönüş: (fonksiyon, başlangıç saati sn)."""
    nk = sorted((float(v), saat_sn(c)) for v, c in noktalar)
    xs = np.array([v for v, _ in nk])
    ys = np.array([c for _, c in nk], dtype=float)
    for j in range(1, len(ys)):  # gece yarısını geçerse
        while ys[j] < ys[j - 1]:
            ys[j] += 86400

    def f(tv: float) -> float:
        if len(xs) == 1:
            return float(tv)
        if tv < xs[0]:
            e = (ys[1] - ys[0]) / (xs[1] - xs[0])
            return float(ys[0] + (tv - xs[0]) * e)
        if tv > xs[-1]:
            e = (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
            return float(ys[-1] + (tv - xs[-1]) * e)
        return float(np.interp(tv, xs, ys))

    bas = f(0.0)
    return (lambda tv: f(tv) - bas), bas


RENK = {  # BGR
    "bos": (120, 200, 120),
    "dolu": (235, 160, 60),
    "bekliyor": (60, 200, 250),
    "uyari": (60, 70, 240),
    "kirli": (70, 150, 220),
    "temizleniyor": (200, 190, 90),
}
RGB = {k: (v[2], v[1], v[0]) for k, v in RENK.items()}
TR = {"bos": "boş", "dolu": "dolu", "bekliyor": "garson bekliyor", "uyari": "ilgilenilmedi", "kirli": "temizlenmedi", "temizleniyor": "temizleniyor"}

# ---------------------------------------------------------------- analiz


def analiz(video: Path, ayar: dict, veri: dict, cikti: Path) -> dict:
    W, H, fps, adim = veri["W"], veri["H"], veri["fps"], veri["adim"]
    dt = adim / fps
    toplam_sure = veri["n"] / fps
    saat0 = None  # kayıt cihazının ekran saati (varsa)
    if ayar.get("zaman_noktalari"):
        gercek, saat0 = zaman_fonksiyonu(ayar["zaman_noktalari"])
        for kr in veri["kareler"]:
            kr["t"] = round(gercek(kr["t"]), 3)
        toplam_sure = gercek(veri["n"] / fps)
        dt = toplam_sure / max(1, len(veri["kareler"]))
    # düşük kare hızlı / hızlandırılmış kayıtta eşikler en az birkaç kare olsun
    E = lambda sn, kare: max(sn, kare * dt)
    px = lambda poly: (np.array(poly, dtype=np.float32) * np.array([W, H], dtype=np.float32))

    masalar = []
    for m in ayar.get("masalar", []):
        p = px(m["poly"])
        masalar.append({
            "ad": m["ad"], "servisli": bool(m.get("basta_servisli")), "poly": p, "musteri": olcekle(p, ayar.get("masa_musteri_olcek", 1.0)),
            "personel": olcekle(p, ayar.get("masa_personel_olcek", 1.3)), "merkez": p.mean(0),
            "durum": "bos", "var_bas": None, "yok_bas": None, "oturum": None, "kirli_bas": None,
            "pers_bas": None, "dolu_sn": 0.0, "kirli_sn": 0.0, "temizlik": [],
            **({"durum": "kirli", "kirli_bas": 0.0} if m.get("basta_kirli") else {}),
        })
    bolgeler = [{"ad": b["ad"], "tur": b["tur"], "poly": px(b["poly"])} for b in ayar.get("bolgeler", [])]
    uyari_sn = ayar.get("bekleme_uyari_sn", 6)
    servis = ayar.get("masa_servisi", True)  # False: self servis; garson bekleme ve kirli masa izlenmez
    esik_o = ayar.get("calisan_esik", 1.0)  # renk puanı; 1 = rengin kendi eşiği

    # roller: iz boyunca önlük rengi oyu
    oy = defaultdict(list)
    for kr in veri["kareler"]:
        for d in kr["d"]:
            oy[d["id"]].append(d["o"])
    personel = {pid for pid, v in oy.items() if len(v) >= 3 and np.mean(np.array(v) > esik_o) >= ayar.get("calisan_kare_orani", 0.35)}
    # oturan ya da masada baştan sona kıpırdamayan kişi müşteridir; rengi ne olursa olsun çalışan sayılmaz
    oturan_izler = oturanlar(veri, [m["musteri"] for m in masalar])
    personel -= oturan_izler
    dusuk_fps = dt > 0.5  # hızlandırılmış kayıt: hız güvenilmez, oturur duruş aranır
    birlesme = ayar.get("oturum_birlesme_sn", E(5.0, 25))  # aynı masada kısa aradan sonra yeniden görülen grup aynı oturumdur
    # çalışan alanına (tezgâhın arkası, mutfak) giren kişi kıyafetinden bağımsız çalışandır
    alanlar = [bz["poly"] for bz in bolgeler if bz["tur"] == "calisan_alani"]
    if alanlar:
        say = defaultdict(lambda: [0, 0])
        for kr in veri["kareler"]:
            for d in kr["d"]:
                b = d["b"]
                ic = any(icinde(a, ((b[0] + b[2]) / 2, b[3])) or icinde(a, capa(b, d["k"])) for a in alanlar)
                say[d["id"]][0] += ic
                say[d["id"]][1] += 1
        personel |= {pid for pid, (ic, top) in say.items() if top >= 3 and ic / top >= ayar.get("calisan_alani_orani", 0.3)}

    gecmis = defaultdict(lambda: deque(maxlen=64))
    ilk_gor, son_gor, son_konum = {}, {}, {}
    calisan = defaultdict(lambda: {"servis": 0.0, "tezgah": 0.0, "yurume": 0.0, "bosta": 0.0})
    musteri = defaultdict(lambda: {"kuyruk": 0.0, "oturdu": False, "durdu": 0.0})
    oturumlar, uyarilar, kuyruk_seri, doluluk_seri, calisan_seri = [], [], [], [], []
    isi = np.zeros((27, 48), np.float32)
    son_bas = {}  # pid -> (t, elips) ; iz kısa süre koparsa yüz gizli kalsın

    cap = cv2.VideoCapture(str(video))
    cikti.mkdir(parents=True, exist_ok=True)
    gecici = cikti / "_ham.mp4"
    yaz = cv2.VideoWriter(str(gecici), cv2.VideoWriter_fourcc(*"mp4v"), fps / adim, (W, H))
    kare_sozluk = {kr["i"]: kr for kr in veri["kareler"]}
    orta_kare = veri["kareler"][len(veri["kareler"]) // 2]["i"]
    i = -1
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        i += 1
        kr = kare_sozluk.get(i)
        if kr is None:
            continue
        t = kr["t"]
        kisiler = []
        for d in kr["d"]:
            pid, b, k = d["id"], d["b"], d["k"]
            a = capa(b, k)
            h = max(1.0, b[3] - b[1])
            g = gecmis[pid]
            g.append((t, a[0], a[1]))
            ilk_gor.setdefault(pid, t)
            son_gor[pid] = t
            son_konum[pid] = a
            eski = next((q for q in g if t - q[0] <= E(0.6, 2.5)), g[0])
            gecen = t - eski[0]
            if gecen >= E(0.3, 1):
                hiz = float(np.hypot(a[0] - eski[1], a[1] - eski[2])) / gecen / h
                duruyor = hiz < ayar.get("durma_hizi", 0.30)
            else:
                hiz, duruyor = 0.0, ilk_gor[pid] <= E(0.25, 1)
            oo = oturma_orani(k)
            oturuyor = (oo < 0.45) if oo is not None else (pid in oturan_izler)
            kisiler.append({"id": pid, "b": b, "k": k, "a": a, "ayak": ((b[0] + b[2]) / 2, b[3]), "p": pid in personel, "duruyor": duruyor, "hiz": hiz, "masa": None,
                            "oturuyor": oturuyor})
            son_bas[pid] = (t, bas_bolgesi(b, k))

        # --- yüzleri gizle (kısa süre önce kaybolan izler dahil)
        for pid, (tb, el) in list(son_bas.items()):
            if t - tb > E(1.5, 2):
                del son_bas[pid]
            else:
                piksel(fr, *el)
        if i == orta_kare:
            cv2.imwrite(str(cikti / "kare.jpg"), fr, [cv2.IMWRITE_JPEG_QUALITY, 88])

        # --- müşteri → masa
        for p in kisiler:
            if p["p"]:
                continue
            gx, gy = int(p["a"][0] / W * 48), int(p["a"][1] / H * 27)
            if 0 <= gx < 48 and 0 <= gy < 27:
                isi[gy, gx] += dt
            aday = [m for m in masalar if icinde(m["musteri"], p["a"])]
            if aday and p["duruyor"] and (p["oturuyor"] or not dusuk_fps):
                m = min(aday, key=lambda m: float(np.hypot(*(m["merkez"] - np.array(p["a"])))))
                p["masa"] = m["ad"]
                musteri[p["id"]]["oturdu"] = True
            if p["duruyor"]:
                musteri[p["id"]]["durdu"] += dt
            for bz in bolgeler:
                if bz["tur"] == "kuyruk" and p["duruyor"] and (icinde(bz["poly"], p["ayak"]) or icinde(bz["poly"], p["a"])):
                    musteri[p["id"]]["kuyruk"] += dt
                    p["kuyruk"] = True

        # --- çalışan süreleri
        for p in kisiler:
            if not p["p"]:
                continue
            c = calisan[p["id"]]
            yavas = p["hiz"] < ayar.get("servis_hizi", 0.55)
            masada = next((m for m in masalar if yavas and (icinde(m["personel"], p["ayak"]) or icinde(m["personel"], p["a"]))), None)
            tezgahta = any(bz["tur"] in ("tezgah", "calisan_alani") and (icinde(bz["poly"], p["ayak"]) or icinde(bz["poly"], p["a"])) for bz in bolgeler)
            p["pmasa"] = masada["ad"] if masada else None
            if masada is not None:
                c["servis"] += dt
            elif tezgahta:
                c["tezgah"] += dt
            elif not p["duruyor"]:
                c["yurume"] += dt
            else:
                c["bosta"] += dt

        # --- masa durum makinesi
        for m in masalar:
            oturan = sum(1 for p in kisiler if p["masa"] == m["ad"])
            pers = any(p["p"] and p.get("pmasa") == m["ad"] for p in kisiler)
            if oturan > 0:
                m["yok_bas"] = None
                if m["var_bas"] is None:
                    m["var_bas"] = t
                # video başında da en az 0,6 sn görünmeli: tek karelik yanlış algılama (boş sandalye) oturum açmasın
                kp_ = m.get("kapanan")
                if m["oturum"] is None and kp_ is not None and m["var_bas"] - kp_["bitis"] <= birlesme:
                    m["dolu_sn"] += max(0.0, t - kp_["bitis"] - dt)  # aradaki kısa boşluk da dolu
                    kp_["bitis"] = None
                    m["oturum"], m["kapanan"] = kp_, None
                    m["kirli_bas"] = m["pers_bas"] = None
                elif m["oturum"] is None and t - m["var_bas"] >= E(0.6, 2):
                    if kp_ is not None:
                        oturumlar.append(kp_)
                        m["kapanan"] = None
                    m["oturum"] = {"masa": m["ad"], "bas": round(m["var_bas"], 2), "bitis": None, "kisi": oturan, "ilk_temas": None,
                                   "basta_dolu": m["var_bas"] <= E(0.3, 1), "uyari": False, "servis_sn": 0.0, "sayim": []}
                    if (m["servisli"] and m["oturum"]["basta_dolu"]) or not servis:  # self serviste garson beklenmez
                        m["oturum"]["ilk_temas"] = m["oturum"]["bas"]
                    m["kirli_bas"] = None
                    m["pers_bas"] = None
                    m["dolu_sn"] += max(0.0, t - m["var_bas"] - dt)  # bekleme süresindeki 0,6 sn de dolu sayılsın
            else:
                m["var_bas"] = None
                if m["yok_bas"] is None:
                    m["yok_bas"] = t
            o = m["oturum"]
            if o is not None:
                if oturan > 0:
                    o["sayim"].append(oturan)
                    o["kisi"] = max(1, int(round(float(np.percentile(o["sayim"], 95)))))
                m["dolu_sn"] += dt
                if pers:
                    o["servis_sn"] += dt
                    if o["ilk_temas"] is None:
                        o["ilk_temas"] = round(t, 2)
                if o["ilk_temas"] is None and not o["uyari"] and t - o["bas"] >= uyari_sn:
                    o["uyari"] = True
                    uyarilar.append({"t": round(t, 2), "masa": m["ad"], "tur": "ilgilenilmedi",
                                     "metin": f"{m['ad']}: {okunur(t - o['bas'])}dir garson gelmedi" + (" (video başından beri oturuyor)" if o["basta_dolu"] else "")})
                if oturan == 0 and m["yok_bas"] is not None and t - m["yok_bas"] >= E(1.2, 3):
                    o["bitis"] = round(m["yok_bas"], 2)
                    m["kapanan"] = o  # birleşme süresi dolunca listeye eklenir
                    m["oturum"] = None
                    if servis and o["bitis"] - o["bas"] >= E(2.0, 4):
                        m["kirli_bas"] = o["bitis"]
            elif m["kirli_bas"] is not None:
                m["kirli_sn"] += dt
                if pers:
                    if m["pers_bas"] is None:
                        m["pers_bas"] = t
                    m["pers_son"] = t
                elif m["pers_bas"] is not None and t - m["pers_son"] >= E(0.8, 2):
                    if m["pers_son"] - m["pers_bas"] >= E(1.0, 1):
                        m["temizlik"].append({"bekleme": round(m["pers_bas"] - m["kirli_bas"], 1), "sure": round(m["pers_son"] - m["pers_bas"], 1)})
                        m["kirli_bas"] = None
                    m["pers_bas"] = None
            if m.get("kapanan") is not None and m["oturum"] is None and m["var_bas"] is None and t - m["kapanan"]["bitis"] > birlesme:
                oturumlar.append(m["kapanan"])
                m["kapanan"] = None
            o = m["oturum"]
            if o is not None:
                m["durum"] = "uyari" if (o["ilk_temas"] is None and o["uyari"]) else ("bekliyor" if o["ilk_temas"] is None else "dolu")
            else:
                m["durum"] = ("temizleniyor" if m["pers_bas"] is not None else "kirli") if m["kirli_bas"] is not None else "bos"

        kuyruk = sum(1 for p in kisiler if p.get("kuyruk"))
        kuyruk_seri.append([round(t, 2), kuyruk])
        calisan_seri.append(sum(1 for p in kisiler if p["p"]))
        doluluk_seri.append([round(t, 2), sum(1 for m in masalar if m["oturum"] is not None)])

        # --- çizim
        kat = fr.copy()
        for m in masalar:
            cv2.fillPoly(kat, [m["poly"].astype(np.int32)], RENK[m["durum"]])
        for bz in bolgeler:
            cv2.fillPoly(kat, [bz["poly"].astype(np.int32)], (200, 120, 200) if bz["tur"] == "kuyruk" else ((60, 180, 120) if bz["tur"] == "calisan_alani" else (60, 140, 250)))
        fr = cv2.addWeighted(kat, 0.28, fr, 0.72, 0)
        for m in masalar:
            cv2.polylines(fr, [m["poly"].astype(np.int32)], True, RENK[m["durum"]], 3, cv2.LINE_AA)
        for bz in bolgeler:
            cv2.polylines(fr, [bz["poly"].astype(np.int32)], True, (200, 120, 200) if bz["tur"] == "kuyruk" else ((60, 180, 120) if bz["tur"] == "calisan_alani" else (60, 140, 250)), 2, cv2.LINE_AA)
        for p in kisiler:
            x1, y1, x2, y2 = [int(v) for v in p["b"]]
            renk = (40, 140, 255) if p["p"] else (200, 210, 60)
            L = max(10, int(0.18 * min(x2 - x1, y2 - y1)))
            for (cx, cy, sx, sy) in ((x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)):
                cv2.line(fr, (cx, cy), (cx + sx * L, cy), renk, 3, cv2.LINE_AA)
                cv2.line(fr, (cx, cy), (cx, cy + sy * L), renk, 3, cv2.LINE_AA)
        im = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
        ciz = ImageDraw.Draw(im, "RGBA")
        for p in kisiler:
            x1, y1 = p["b"][0], p["b"][1]
            etiket(ciz, (x1, max(54, y1 - 26)), "Çalışan" if p["p"] else "Müşteri", (255, 140, 40, 235) if p["p"] else (40, 170, 190, 235), boyut=15)
        for m in masalar:
            o = m["oturum"]
            if o is not None:
                metin = f"{m['ad']} · {o['kisi']} kişi · {sure(t - o['bas'])}"
                if m["durum"] in ("bekliyor", "uyari"):
                    metin += " · " + TR[m["durum"]]
            elif m["durum"] == "kirli":
                metin = f"{m['ad']} · temizlenmedi {sure(t - m['kirli_bas'])}"
            elif m["durum"] == "temizleniyor":
                metin = f"{m['ad']} · temizleniyor {sure(t - m['pers_bas'])}"
            else:
                metin = f"{m['ad']} · boş"
            ust = m["poly"][:, 1].min()
            etiket(ciz, (float(m["merkez"][0]), max(54, float(ust) - 34)), metin, RGB[m["durum"]] + (240,), yazi=(15, 20, 30), boyut=18, orta=True)
        for bz in bolgeler:
            ek = f" · {kuyruk} kişi" if bz["tur"] == "kuyruk" else ""
            etiket(ciz, (float(bz["poly"][:, 0].min()) + 6, float(bz["poly"][:, 1].min()) + 6), bz["ad"] + ek, (200, 120, 200, 235) if bz["tur"] == "kuyruk" else ((120, 180, 60, 235) if bz["tur"] == "calisan_alani" else (250, 140, 60, 235)), yazi=(15, 20, 30), boyut=17)
        zaman_yazi = sure((saat0 + t) % 86400).rjust(8, "0") if saat0 is not None else sure(t)
        w0, _ = etiket(ciz, (16, 14), f"{ayar['ad'].upper()}  {zaman_yazi}", (10, 14, 28, 225), boyut=22)
        ozet = f"Müşteri {sum(1 for p in kisiler if not p['p'])} · Çalışan {sum(1 for p in kisiler if p['p'])}"
        if masalar:
            ozet = f"Dolu {sum(1 for m in masalar if m['oturum'] is not None)}/{len(masalar)} · " + ozet
        etiket(ciz, (16 + w0 + 10, 14), ozet, (10, 14, 28, 225), boyut=22)
        etiket(ciz, (16, H - 44), "Yüzler gizlendi · kimlik tanıma yok", (10, 14, 28, 225), yazi=(160, 235, 200), boyut=17)
        yaz.write(cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR))
    cap.release()
    yaz.release()
    # tarayıcıda oynasın diye H.264'e çevir
    subprocess.run([yollar.ffmpeg(), "-y", "-loglevel", "error", "-i", str(gecici), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21", "-movflags", "+faststart", str(cikti / "isaretli.mp4")],
                   check=True, stdin=subprocess.DEVNULL, **_GIZLI)
    gecici.unlink(missing_ok=True)

    # --- kapanış: açık oturumlar
    for m in masalar:
        if m.get("kapanan") is not None:
            oturumlar.append(m["kapanan"])
        if m["oturum"] is not None:
            oturumlar.append(m["oturum"])
    oturumlar.sort(key=lambda o: o["bas"])
    for n, o in enumerate(oturumlar, 1):
        son = o["bitis"] if o["bitis"] is not None else toplam_sure
        o["no"] = n
        o["sure"] = round(son - o["bas"], 1)
        o["devam"] = o["bitis"] is None
        o["bekleme"] = None if (o["ilk_temas"] is None or o["basta_dolu"] or not servis) else round(o["ilk_temas"] - o["bas"], 1)
        o["servis_sn"] = round(o["servis_sn"], 1)
        o.pop("sayim", None)

    masa_ozet = []
    for m in masalar:
        os_ = [o for o in oturumlar if o["masa"] == m["ad"]]
        masa_ozet.append({
            "ad": m["ad"], "poly": [[round(float(x) / W, 4), round(float(y) / H, 4)] for x, y in m["poly"]],
            "oturum": len(os_), "doluluk": min(100.0, round(100 * m["dolu_sn"] / toplam_sure, 1)), "dolu_sn": round(m["dolu_sn"], 1),
            "ort_sure": round(float(np.mean([o["sure"] for o in os_])), 1) if os_ else 0.0,
            "kisi": int(sum(o["kisi"] for o in os_)), "kirli_sn": round(m["kirli_sn"], 1),
            "temizlik": m["temizlik"], "son_durum": m["durum"],
            "temizlik_bekleme": round(float(np.mean([x["bekleme"] for x in m["temizlik"]])), 1) if m["temizlik"] else None,
            "temizlik_suresi": round(float(np.mean([x["sure"] for x in m["temizlik"]])), 1) if m["temizlik"] else None,
        })
        if m["kirli_bas"] is not None and m["pers_bas"] is None and toplam_sure - m["kirli_bas"] >= E(3, 6):
            uyarilar.append({"t": round(toplam_sure, 2), "masa": m["ad"], "tur": "temizlenmedi",
                             "metin": f"{m['ad']}: müşteri kalkalı {okunur(toplam_sure - m['kirli_bas'])} oldu, masa temizlenmedi"})

    yuvalar = []  # her yuva bir kişi: [son görülme, süre toplamları]
    for pid, c in sorted(calisan.items(), key=lambda kv: ilk_gor[kv[0]]):
        if sum(c.values()) < E(1.0, 2):
            continue
        yuva = next((y for y in yuvalar if y[0] < ilk_gor[pid] + E(2.0, 3)), None)  # 2 sn'ye kadar çakışma: aynı kişinin çift izi
        if yuva is None:
            yuva = [0.0, {"servis": 0.0, "tezgah": 0.0, "yurume": 0.0, "bosta": 0.0}]
            yuvalar.append(yuva)
        yuva[0] = son_gor[pid]
        for k, v in c.items():
            yuva[1][k] += v
    calisanlar = []
    for _, c in yuvalar:
        top = sum(c.values())
        if top < E(1.5, 3):
            continue
        calisanlar.append({"ad": f"Çalışan {chr(65 + len(calisanlar))}", "toplam": round(top, 1), **{k: round(v, 1) for k, v in c.items()},
                           "aktif_yuzde": round(100 * (top - c["bosta"]) / top, 1)})

    # çalışan sayısı: iz yuvaları kopmalarla şişer, "aynı anda görünen" çift kutuyla şişer; küçüğü alınır
    ayni_anda = int(np.percentile(calisan_seri, 95)) if calisan_seri else 0
    calisan_say = min(len(calisanlar), ayni_anda) if calisanlar and ayni_anda else len(calisanlar)
    if len(calisanlar) > calisan_say:
        # kişiler birbirinden ayrılamadı: uydurma kişi satırları yerine tek toplam satır
        top = {k: round(sum(c[k] for c in calisanlar), 1) for k in ("toplam", "servis", "tezgah", "yurume", "bosta")}
        calisanlar = [{"ad": f"Tüm çalışanlar (aynı anda en çok {calisan_say})", **top,
                       "aktif_yuzde": round(100 * (top["toplam"] - top["bosta"]) / top["toplam"], 1) if top["toplam"] else 0.0}]
    musteri_izleri = [pid for pid in ilk_gor if pid not in personel and son_gor[pid] - ilk_gor[pid] >= E(1.5, 3)]
    kuyruktakiler = [round(musteri[pid]["kuyruk"], 1) for pid in musteri_izleri if musteri[pid]["kuyruk"] >= E(1.0, 2)]
    donen = 0
    if any(b["tur"] == "kuyruk" for b in bolgeler):
        for pid in musteri_izleri:
            ms = musteri[pid]
            omur = son_gor[pid] - ilk_gor[pid]
            x, y = son_konum[pid][0] / W, son_konum[pid][1] / H
            kenarda = min(x, 1 - x, y, 1 - y) < 0.14
            if omur >= E(2.0, 4) and ms["durdu"] < 0.6 * omur and not ms["oturdu"] and son_gor[pid] < toplam_sure - E(1.0, 2) and ilk_gor[pid] > E(0.5, 1) and kenarda:
                donen += 1
                uyarilar.append({"t": round(son_gor[pid], 2), "masa": "", "tur": "donen", "metin": "Bir müşteri kuyruğu görüp sıraya girmeden çıktı"})

    bekl = [o["bekleme"] for o in oturumlar if o["bekleme"] is not None]
    sonuc = {
        "ad": ayar["ad"], "video": video.name, "calisan_renkleri": [r["ad"] for r in renkler.coz(ayar.get("calisan_renkleri"))], "sure": round(toplam_sure, 1), "saat_bas": saat0, "masa_servisi": servis, "W": W, "H": H,
        "ozet": {
            "oturum": len(oturumlar),
            "ort_oturma": round(float(np.mean([o["sure"] for o in oturumlar])), 1) if oturumlar else None,
            "doluluk": round(float(np.mean([m["doluluk"] for m in masa_ozet])), 1) if masa_ozet else None,
            "ort_bekleme": round(float(np.mean(bekl)), 1) if bekl else None,
            "uyari": len(uyarilar), "musteri": len(musteri_izleri), "calisan": calisan_say,
            "calisan_ayni_anda": ayni_anda,
            "calisan_ort": round(float(np.mean(calisan_seri)), 2) if calisan_seri else 0.0,
            "calisan_suresi": round(float(np.sum(calisan_seri)) * dt, 1),
            "kuyruk_en_cok": max((q for _, q in kuyruk_seri), default=0) if any(b["tur"] == "kuyruk" for b in bolgeler) else None,
            "kuyruk_ort_bekleme": round(float(np.mean(kuyruktakiler)), 1) if kuyruktakiler else None,
            "donen": donen if any(b["tur"] == "kuyruk" for b in bolgeler) else None,
        },
        "masalar": masa_ozet, "oturumlar": oturumlar, "calisanlar": calisanlar, "uyarilar": sorted(uyarilar, key=lambda u: u["t"]),
        "kuyruk_seri": kuyruk_seri[::2], "doluluk_seri": doluluk_seri[::2],
        "bolgeler": [{"ad": b["ad"], "tur": b["tur"], "poly": [[round(float(x) / W, 4), round(float(y) / H, 4)] for x, y in b["poly"]]} for b in bolgeler],
        "isi": [[round(float(v), 2) for v in satir] for satir in isi],
        "izler": [{"id": pid, "ilk": round(ilk_gor[pid], 1), "son": round(son_gor[pid], 1), "durdu": round(musteri[pid]["durdu"], 1), "kuyruk": round(musteri[pid]["kuyruk"], 1),
                   "x": round(son_konum[pid][0] / W, 2), "y": round(son_konum[pid][1] / H, 2)} for pid in musteri_izleri],
    }
    (cikti / "sonuc.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    return sonuc


def calistir(video: Path, ayar_yol: Path, adim: int = 2, imgsz: int = 960, model: str | None = None, yeniden: bool = False,
             cikti_adi: str | None = None, renk_dene: bool = False) -> dict | None:
    """Bir videoyu analiz eder; sonuç cikti/<ad>/ altına yazılır. Dönüş: sonuç sözlüğü."""
    video, ayar_yol = Path(video), Path(ayar_yol)
    ayar = json.loads(ayar_yol.read_text(encoding="utf-8"))
    renk_list = renkler.coz(ayar.get("calisan_renkleri"))
    onbellek = yollar.ONBELLEK / f"{video.stem}.json"
    if onbellek.exists() and not yeniden:
        veri = json.loads(onbellek.read_text(encoding="utf-8"))
        if veri.get("renk_imza") != renkler.imza(renk_list):
            print("  kıyafet rengi değişti, çalışan puanları yenileniyor", flush=True)
            veri = renk_puanla(video, veri, renk_list)
            onbellek.write_text(json.dumps(veri), encoding="utf-8")
    else:
        veri = algila(video, onbellek, adim, imgsz, model or str(yollar.MODEL), renk_list)
    if not veri["kareler"]:
        raise SystemExit(f"Videoda kare yok: {video.name}")
    cikti = yollar.CIKTI / (cikti_adi or video.stem)
    if renk_dene:
        print(f"{'renk':<10}{'çalışan sayılan iz':>20}{'ayrım':>8}")
        for r in renk_tara(video, veri, cikti):
            if not r["calisan_iz"]:
                continue
            notlar = []
            if r["calisan_iz"] > 0.4 * r["toplam_iz"]:
                notlar.append("kişilerin çoğunu yakalıyor, müşteriler de bu renkte")
            if r["zayif"]:
                notlar.append("müşterilerde de sık")
            print(f"{r['ad']:<10}{str(r['calisan_iz']) + ' / ' + str(r['toplam_iz']):>20}{r['ayrim']:>8.2f}" + (f"   ({'; '.join(notlar)})" if notlar else ""))
        print("Listede olmayan renkler kimseyi yakalamadı.")
        print("Çalışanların giydiği rengi seç. İyi renk: ayrım 1'e yakın, yakaladığı iz sayısı az (izler kopabildiği için")
        print("bir çalışan birkaç iz olarak görünebilir). Kimseyi yakalamıyorsa ya da herkesi yakalıyorsa ayar sayfasından")
        print("'Kareden seç' ile çalışanın kıyafetinden özel renk al.")
        return None
    veri = izleri_birlestir(veri)
    s = analiz(video, ayar, veri, cikti)
    print(json.dumps(s["ozet"], ensure_ascii=False), flush=True)
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("ayar")
    ap.add_argument("--adim", type=int, default=2, help="her kaç karede bir işlensin")
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--model", default=None)
    ap.add_argument("--yeniden", action="store_true", help="algılama önbelleğini yok say")
    ap.add_argument("--cikti-adi", help="cikti/ altındaki klasör adı (varsayılan: video adı)")
    ap.add_argument("--renk-dene", action="store_true", help="bütün hazır kıyafet renklerini dene, hangisinin çalışanı ayırdığını yaz")
    a = ap.parse_args()
    yollar.hazirla()
    calistir(Path(a.video), Path(a.ayar), a.adim, a.imgsz, a.model, a.yeniden, a.cikti_adi, a.renk_dene)


if __name__ == "__main__":
    main()
