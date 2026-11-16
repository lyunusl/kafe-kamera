"""AugeLab Studio bloklarının çağırdığı işlevler.

Bloklar incedir: görüntüyü ve iş girişini bu işlevlere verir. Motor klasörü (kafe_engine) Studio'nun özel blok
klasörünün yanındadır:

  kafe_motor/  bu paket
  modeller/    yolo11s-pose.pt
  deps/        Studio'da olmayan kütüphaneler (ultralytics, lap; motor/deps.txt). sys.path'in SONUNA eklenir:
               torch, numpy ve OpenCV Studio'nun kendi paketlerinden gelir.
  ayar.json    {"veri": "<panelin veri klasörü>"}

Sahne:  "Kafe Kamera İşi" (metin girişi) → Kafe Kaynak → Kafe Algılama

Panel her iş için sahneyi ayrı, gizli bir süreçte çalıştırır (python -m studio run kafe-kamera.pmod --json). İşin ne
olduğu sahneye yazılmaz; sürecin ortam değişkenlerinden gelir:

  KAFE_IS            "tür#koşu". tür: deneme | video | kare | kayit. Sahnedeki metin girişinin değeri yok sayılır.
  KAFE_GIRDI         video: video dosyası; kare: tek karelik görüntü dosyası (panel işten sonra siler)
  KAFE_CIKTI         sonuç JSON'u (önce .tmp, sonra os.replace: panel yarım dosya görmez). Hata: {"hata": "..."}
  KAFE_ILERLEME      video işinde ilerleme JSON'u {"i", "toplam"} (25 algılamada bir)
  KAFE_ADIM          video: her kaçıncı kare işlenir (0.1.0'daki --adim)
  KAFE_IMGSZ         video: model giriş boyutu (0.1.0'daki --imgsz)
  KAFE_KAMERA_ADRES  kayit: canlı akış adresi. Şifre içerebilir: dosyaya, sahneye ve komut satırına yazılmaz.
  KAFE_KAYIT         kayit: yazılacak video dosyası
  KAFE_SURE_SN       kayit: kayıt süresi (saniye)
  KAFE_DUR           bu dosya oluşunca akış biter (Kafe Kaynak bir kez Bitti=True verir, sonuç yazılır)

İşler:
  deneme  siyah bir karede modeli açıp çalıştırır: Studio kurulu, lisanslı, blokları yüklüyor ve model açılıyor mu.
          Sonuç: {"ok": true, "surumler": {...}}
  video   videonun her kaçıncı karesinde kişileri izler. Sonuç 0.1.0'daki algılama sözlüğünün aynısı:
          {"fps", "W", "H", "n", "adim", "kareler": [{"i", "t", "d": [{"id", "b", "k", "o"}]}]}
  kare    tek kare: {"W", "H", "kisiler": [{"b", "k"}]}. Görüntü çıkmaz; yüzleri panel pikseller.
  kayit   canlı akışı KAFE_SURE_SN saniye 720p'ye indirip sabit kare hızıyla kaydeder (analiz panelde, kayıttan sonra).
          Sonuç: {"kare", "fps", "sure_sn", "W", "H"}
Hiçbir blok görüntü çıkışı vermez: işlenmemiş (yüzleri açık) kare Studio'nun ekranına ya da başka bir bloğa gitmez.
"""
from __future__ import annotations

import json
import os
import threading
import time

import cv2
import numpy as np

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(KOK, "modeller", "yolo11s-pose.pt")

ORTAM_IS = "KAFE_IS"
ORTAM_GIRDI = "KAFE_GIRDI"
ORTAM_CIKTI = "KAFE_CIKTI"
ORTAM_ILERLEME = "KAFE_ILERLEME"
ORTAM_ADIM = "KAFE_ADIM"
ORTAM_IMGSZ = "KAFE_IMGSZ"
ORTAM_ADRES = "KAFE_KAMERA_ADRES"
ORTAM_KAYIT = "KAFE_KAYIT"
ORTAM_SURE = "KAFE_SURE_SN"
ORTAM_DUR = "KAFE_DUR"
TURLER = ("deneme", "video", "kare", "kayit")
KAYIT_GENISLIK = 1280  # kayıt 720p'ye indirilir (0.1.0'daki ffmpeg kaydıyla aynı)
ILERLEME_ARALIGI = 25  # algılama


# ---------------------------------------------------------------- ortak


def is_ve_kosu(giris) -> tuple[str, str]:
    """İş, sürecin ortamından gelir (KAFE_IS "tür#koşu"); yoksa bloğun girişindeki metin kullanılır."""
    metin = os.environ.get(ORTAM_IS) or str(giris or "")
    tur, _, kosu = metin.strip().partition("#")
    return tur.strip().lower(), kosu.strip()


def veri_klasoru() -> str | None:
    try:
        with open(os.path.join(KOK, "ayar.json"), encoding="utf-8") as f:
            return json.load(f).get("veri")
    except (OSError, ValueError):
        return None


def durduruldu() -> bool:
    dur = os.environ.get(ORTAM_DUR)
    return bool(dur) and os.path.exists(dur)


def json_yaz(yol: str | None, veri) -> None:
    """Atomik yazım: panel yalnızca tamamlanmış dosyayı görür."""
    if not yol:
        return
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False)
    os.replace(gecici, yol)


def _goruntu(image) -> np.ndarray | None:
    if image is None:
        return None
    a = np.asarray(image)
    if a.ndim == 2:
        a = cv2.cvtColor(a, cv2.COLOR_GRAY2BGR)
    elif a.ndim == 3 and a.shape[2] == 4:
        a = a[:, :, :3]
    return np.ascontiguousarray(a) if a.ndim == 3 and a.size else None


def _sayi(ad: str, varsayilan: int, en_az: int, en_cok: int) -> int:
    try:
        return min(en_cok, max(en_az, int(float(os.environ.get(ad) or varsayilan))))
    except ValueError:
        return varsayilan


# ---------------------------------------------------------------- Kafe Kaynak


class _CanliOkuyucu:
    """Canlı akışı arka planda okur ve yalnızca son kareyi tutar; bağlantı koparsa birkaç saniyede bir yeniden bağlanır."""

    def __init__(self, adres: str):
        self.adres, self.kare, self.sira, self.fps = adres, None, 0, 0.0
        self.durum = "bekliyor: kameraya bağlanılıyor"
        self._dur = threading.Event()
        self._kilit = threading.Lock()
        threading.Thread(target=self._oku, name="kafe-canli", daemon=True).start()

    def _oku(self) -> None:
        bekle = 1.0
        if self.adres.startswith("rtsp"):
            os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        while not self._dur.is_set():
            cap = cv2.VideoCapture(self.adres, cv2.CAP_FFMPEG,
                                   [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 8000])
            if not cap.isOpened():
                cap.release()
                self.durum = "bekliyor: kameraya bağlanılamadı, yeniden deneniyor"
                self._dur.wait(bekle)
                bekle = min(10.0, bekle * 2)
                continue
            bekle = 1.0
            self.fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
            while not self._dur.is_set():
                ok, fr = cap.read()
                if not ok:
                    self.durum = "bekliyor: görüntü kesildi, yeniden bağlanılıyor"
                    break
                with self._kilit:
                    self.kare, self.sira = fr, self.sira + 1
                self.durum = "ok"
            cap.release()

    def son(self):
        with self._kilit:
            return self.kare, self.sira

    def kapat(self) -> None:
        self._dur.set()


def _kaynak_kapat(state: dict) -> None:
    if state.get("cap") is not None:
        state["cap"].release()
    if state.get("canli") is not None:
        state["canli"].kapat()
    state.clear()


def _kaynak_ac(state: dict, tur: str, kosu: str) -> str | None:
    state.update(tur=tur, kosu=kosu, n=0, bitti=False, t0=time.monotonic())
    if tur == "deneme":
        return None
    if tur in ("video", "kare"):
        yol = os.environ.get(ORTAM_GIRDI, "")
        if not yol or not os.path.isfile(yol):
            return "hata: girdi dosyası yok"
        if tur == "kare":
            state["kare"] = cv2.imread(yol, cv2.IMREAD_COLOR)
            return None if state["kare"] is not None else "hata: kare okunamadı"
        cap = cv2.VideoCapture(yol)
        if not cap.isOpened():
            return f"hata: video açılamadı: {os.path.basename(yol)}"
        state["cap"] = cap
        state["toplam"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        return None
    if tur == "kayit":
        adres = os.environ.get(ORTAM_ADRES, "")
        if not adres:
            return "hata: kameranın akış adresi verilmedi (işi Kafe Kamera başlatır)"
        state["canli"] = _CanliOkuyucu(adres)
        state["sure"] = float(_sayi(ORTAM_SURE, 900, 5, 24 * 3600))
        state["sira_canli"] = 0
        return None
    return f"hata: bilinmeyen iş: {tur or '(boş)'}"


def kaynak(state: dict, is_girisi):
    """Kafe Kaynak bloğu. Dönüş: (görüntü | None, sıra, zaman, bitti, durum).

    sıra: video dosyasında karenin numarası (0'dan); zaman: video dosyasında sıra / fps, canlı akışta koşu başından beri
    geçen saniye. Akış bitince (dosya sonu, kayıt süresi, durdurma dosyası) bir kez bitti=True döner, sonra görüntü vermez.
    Durum "hata: ..." ile başlıyorsa kaynak açılamadı (Kafe Algılama bunu sonuca yazar)."""
    tur, kosu = is_ve_kosu(is_girisi)
    if state.get("tur") != tur or state.get("kosu") != kosu:
        _kaynak_kapat(state)
        hata = _kaynak_ac(state, tur, kosu)
        if hata:
            state["hata"] = hata
    if state.get("hata"):
        if state["bitti"]:
            return None, -1, 0.0, False, state["hata"]
        state["bitti"] = True
        return None, -1, 0.0, True, state["hata"]
    if tur == "deneme":
        state["n"] += 1
        return np.zeros((360, 640, 3), np.uint8), state["n"] - 1, 0.0, False, "ok deneme karesi"
    if state["bitti"]:
        return None, -1, 0.0, False, f"bitti: {state['n']} kare"
    if durduruldu():
        state["bitti"] = True
        if state.get("canli") is not None:
            state["canli"].kapat()
        return None, -1, time.monotonic() - state["t0"], True, f"bitti: durduruldu, {state['n']} kare"
    if tur == "kare":
        if state["n"] == 0:
            state["n"] = 1
            return state.pop("kare"), 0, 0.0, False, "ok 1 kare"
        state["bitti"] = True
        return None, -1, 0.0, True, "bitti: 1 kare"
    if tur == "video":
        ok, fr = state["cap"].read()
        if not ok:
            state["bitti"] = True
            state["cap"].release()
            return None, -1, 0.0, True, f"bitti: {state['n']} kare"
        i = state["n"]
        state["n"] += 1
        return fr, i, 0.0, False, f"ok {state['n']}" + (f" / {state['toplam']}" if state["toplam"] > 0 else "") + " kare"
    # kayit: canlı akışın son karesi
    gecen = time.monotonic() - state["t0"]
    canli = state["canli"]
    if gecen >= state["sure"]:
        state["bitti"] = True
        canli.kapat()
        return None, -1, gecen, True, f"bitti: süre doldu, {state['n']} kare"
    kare, sira = canli.son()
    if kare is None or sira == state["sira_canli"]:
        return None, -1, gecen, False, canli.durum if kare is None else "ok: yeni kare bekleniyor"
    state["sira_canli"] = sira
    state["n"] += 1
    return kare, state["n"] - 1, gecen, False, f"ok {state['n']} kare"


# ---------------------------------------------------------------- Kafe Algılama


def _model(state: dict):
    if state.get("model") is None:
        from . import algilama

        algilama.ultralytics_ayarla(veri_klasoru())
        state["model"] = algilama.model_ac(MODEL)
    return state["model"]


def _maskele(metin: str) -> str:
    """Hata metninde akış adresi geçerse şifresi gizlenir; adresin kendisi de metinden çıkarılır."""
    import re

    metin = str(metin)
    adres = os.environ.get(ORTAM_ADRES)
    if adres:
        metin = metin.replace(adres, "<kamera adresi>")
    return re.sub(r"(://[^:/@\s]+:)[^@\s]*@", r"\1****@", metin)


def _bitir(state: dict, sonuc: dict) -> str:
    if "hata" in sonuc:
        sonuc["hata"] = _maskele(sonuc["hata"])
    state["yazildi"] = True
    try:
        json_yaz(os.environ.get(ORTAM_CIKTI), sonuc)
    except OSError as e:
        return f"hata: sonuç yazılamadı: {e}"
    state["son_durum"] = ("hata: " + str(sonuc["hata"])) if "hata" in sonuc else "bitti: sonuç yazıldı"
    return state["son_durum"]


def _kaynak_hatasi(durum) -> str | None:
    d = str(durum or "")
    return d[len("hata:"):].strip() if d.startswith("hata") else None


def algila(state: dict, image, is_girisi, sira=-1, zaman=0.0, bitti=False, kaynak_durum="") -> str:
    """Kafe Algılama bloğu: işi yapar, sonucu KAFE_CIKTI'ya bir kez yazar. Dönüş: durum metni."""
    tur, kosu = is_ve_kosu(is_girisi)
    if state.get("tur") != tur or state.get("kosu") != kosu:
        if state.get("yazici") is not None:
            state["yazici"].release()
        model = state.get("model")
        state.clear()
        state.update(tur=tur, kosu=kosu, model=model, yazildi=False, kareler=[], n=0)
    if state["yazildi"]:
        return state.get("son_durum", "bitti")
    hata = _kaynak_hatasi(kaynak_durum)
    if hata and bitti:
        return _bitir(state, {"hata": hata})
    try:
        if tur == "deneme":
            return _deneme(state, image)
        if tur == "kare":
            return _tek_kare(state, image, bitti)
        if tur == "video":
            return _video(state, image, sira, bitti, kaynak_durum)
        if tur == "kayit":
            return _kayit(state, image, zaman, bitti, kaynak_durum)
    except Exception as e:  # model açılamadı, ultralytics yüklenemedi, disk dolu...
        if state.get("yazici") is not None:
            state["yazici"].release()
            state["yazici"] = None
        return _bitir(state, {"hata": f"{type(e).__name__}: {e}"})
    return _bitir(state, {"hata": f"bilinmeyen iş: {tur or '(boş)'}"})


def _deneme(state: dict, image) -> str:
    from . import algilama

    fr = _goruntu(image)
    if fr is None:
        return "bekliyor: görüntü yok"
    algilama.tek_kare(_model(state), fr)
    return _bitir(state, {"ok": True, "surumler": algilama.surumler()})


def _tek_kare(state: dict, image, bitti: bool) -> str:
    from . import algilama

    fr = _goruntu(image)
    if fr is None:
        return _bitir(state, {"hata": "kare gelmedi"}) if bitti else "bekliyor: görüntü yok"
    H, W = fr.shape[:2]
    return _bitir(state, {"W": W, "H": H, "kisiler": algilama.tek_kare(_model(state), fr)})


def _video_bilgisi(state: dict) -> None:
    """fps, boyut ve toplam kare: 0.1.0'daki gibi videonun kendi bilgisinden."""
    cap = cv2.VideoCapture(os.environ.get(ORTAM_GIRDI, ""))
    try:
        state["fps"] = cap.get(cv2.CAP_PROP_FPS) or 24.0
        state["W"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        state["H"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        state["toplam"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        cap.release()
    state["adim"] = _sayi(ORTAM_ADIM, 2, 1, 1000)
    state["imgsz"] = _sayi(ORTAM_IMGSZ, 960, 160, 4096)


def _ilerleme(state: dict, i: int) -> None:
    try:
        json_yaz(os.environ.get(ORTAM_ILERLEME), {"i": i, "toplam": state["toplam"]})
    except OSError:
        pass


def _video(state: dict, image, sira, bitti: bool, kaynak_durum) -> str:
    from . import algilama

    if "fps" not in state:
        _video_bilgisi(state)
    if bitti:
        if "durduruldu" in str(kaynak_durum):
            return _bitir(state, {"hata": "durduruldu", "durduruldu": True})
        if not state["kareler"]:
            return _bitir(state, {"hata": "videodan kare okunamadı"})
        return _bitir(state, {"fps": state["fps"], "W": state["W"], "H": state["H"], "n": state["n"], "adim": state["adim"],
                              "kareler": state["kareler"]})
    fr = _goruntu(image)
    try:
        i = int(sira)
    except (TypeError, ValueError):
        i = -1
    if fr is None or i < 0:
        return "bekliyor: görüntü yok"
    state["n"] = i + 1
    if i % state["adim"] == 0:
        dets = algilama.takip_et(_model(state), fr, state["imgsz"])
        state["kareler"].append({"i": i, "t": round(i / state["fps"], 3), "d": dets})
        if len(state["kareler"]) % ILERLEME_ARALIGI == 0:
            _ilerleme(state, i)
    return f"ok algılama: {i} / {state['toplam']} kare"


def _kayit(state: dict, image, zaman, bitti: bool, kaynak_durum) -> str:
    """Canlı akışı sabit kare hızında kaydeder: duvar saatine göre eksik kareler son kareyle doldurulur, fazlası atılır.
    Böylece videodaki süre gerçek süreyle aynıdır (analiz süreleri saniye olarak doğru çıkar)."""
    try:
        t = float(zaman)
    except (TypeError, ValueError):
        t = 0.0
    fr = _goruntu(image)
    if fr is not None:
        if state.get("yazici") is None:
            yol = os.environ.get(ORTAM_KAYIT, "")
            if not yol:
                return _bitir(state, {"hata": "kayıt dosyası verilmedi"})
            h, w = fr.shape[:2]
            if w > KAYIT_GENISLIK:
                h, w = int(round(h * KAYIT_GENISLIK / w / 2)) * 2, KAYIT_GENISLIK
            state["boyut"] = (w, h)
            state["fps_k"] = 15.0
            state["yazici"] = cv2.VideoWriter(yol, cv2.VideoWriter_fourcc(*"mp4v"), state["fps_k"], (w, h))
            if not state["yazici"].isOpened():
                state["yazici"] = None
                return _bitir(state, {"hata": "kayıt dosyası açılamadı"})
            state["t_ilk"] = t
            state["yazilan"] = 0
        w, h = state["boyut"]
        if fr.shape[1] != w or fr.shape[0] != h:
            fr = cv2.resize(fr, (w, h), interpolation=cv2.INTER_AREA)
        state["son"] = fr
        hedef = int((t - state["t_ilk"]) * state["fps_k"]) + 1
        while state["yazilan"] < hedef:
            state["yazici"].write(fr)
            state["yazilan"] += 1
    if not bitti:
        return f"ok kayıt: {state.get('yazilan', 0)} kare" if state.get("yazici") is not None else str(kaynak_durum or "bekliyor")
    if state.get("yazici") is None:
        return _bitir(state, {"hata": _kaynak_hatasi(kaynak_durum) or "kameradan görüntü gelmedi"})
    # son kareyi bitiş anına kadar uzat
    hedef = int((t - state["t_ilk"]) * state["fps_k"])
    while state["yazilan"] < hedef and state.get("son") is not None:
        state["yazici"].write(state["son"])
        state["yazilan"] += 1
    state["yazici"].release()
    state["yazici"] = None
    w, h = state["boyut"]
    return _bitir(state, {"kare": state["yazilan"], "fps": state["fps_k"], "sure_sn": round(state["yazilan"] / state["fps_k"], 1),
                          "W": w, "H": h, "durduruldu": "durduruldu" in str(kaynak_durum)})
