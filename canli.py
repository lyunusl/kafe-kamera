"""Canlı izleme: her kamera için bir uzun ömürlü, gizli AugeLab Studio süreci (kafe_motor.blok, iş "canli").

Nasıl çalışır:
  - Studio akışı sürekli okur (son kare; kopunca yeniden bağlanır), saniyede birkaç kare kişi izler (izci koşu boyunca
    yaşar), çalışan kıyafet rengi puanını kendi içinde hesaplar ve her analiz edilen kareyi veri/canli/<kod>/ altına JSON
    satırı olarak ekler; saniyede bir durum dosyası ve yüzleri gizlenmiş küçük bir önizleme yazar. Ham görüntü diske yazılmaz.
  - Panel bu satırları birkaç saniyede bir okur ve 0.1.0'daki masa / oturum / çalışan / kuyruk kurallarını (analiz.analiz,
    videosuz) içinde bulunulan parçanın algılamaları üzerinde yeniden çalıştırır. Parça PARCA_SN'de bir kapanır: sonucu
    gecmis/ altına yazılır (gün toplamları ve Excel raporu buradan), yeni parça başlar. Izci ve Studio süreci parçadan
    etkilenmez.
  - Akış koparsa kamera "koptu" görünür (boş kafe değil); Studio süreci ölürse panel onu bekleyerek yeniden başlatır.
  - Kamera şifresi yalnızca bellekte ve Studio sürecinin ortamında durur (studio.baslat: dosyaya ve komut satırına yazılmaz).
"""
from __future__ import annotations

import datetime as dt
import json
import secrets
import shutil
import threading
import time
from pathlib import Path

import yollar

PARCA_SN = 900            # canlı analizin parça süresi (gün toplamı parçalardan oluşur; 0.2.0'daki 15 dk'lık kayıtla aynı)
YENILE_SN = 2.0           # panelin canlı ölçümleri yeniden hesaplama aralığı (en az)
KOPTU_SN = 6.0            # bu kadar süre yeni kare gelmezse akış "koptu" sayılır
VARSAYILAN_FPS = 3.0      # kamera ayarında analiz_fps yoksa (0.2.0'dan kalan kameralar): saniyede analiz edilen kare
DUSUK_HIZ_ORANI = 0.7     # gerçek hız hedefin bu oranının altında kalırsa uyarı
ID_ARALIGI = 1_000_000    # Studio yeniden başlarsa iz numaraları çakışmasın
PANEL_ADRES = None        # uygulama.py sunucuyu açınca yazar (motorun görünüm özetlerini göndereceği yer)
BASLATMA_ARALIGI = 8.0    # birlikte başlatılan kameralar bu kadar arayla açılır (model yüklemesi üst üste binmesin)
EN_COK_IS_PARCACIGI = 4   # bir canlı kameranın Studio sürecine verilen en çok işlemci iş parçacığı
GPU_IS_PARCACIGI = 2      # ekran kartı kullanılırken: ağır iş kartta; süreç başına az iş parçacığı yeter (ölçüldü)
GPU_BASLATMA_ARALIGI = 3.0  # ekran kartında model yüklemesi kısa sürer (ölçüldü)


def ayarlar_dosyasi() -> Path:
    """Bu kuruluma özel canlı izleme ayarı (isteğe bağlı): {"is_parcacigi": n}. 0 = sınır yok."""
    return yollar.VERI / "canli.json"


def is_parcacigi_siniri(kamera_sayisi: int, cekirdek: int | None = None, ayar: dict | None = None) -> int:
    """Bir canlı kameranın iş parçacığı sınırı: çekirdek sayısı / canlı kamera sayısı, en az 1, en çok 4. Kuruluma özel
    ayar (canli.json "is_parcacigi") varsa o kullanılır; 0 sınır yok demektir (Studio'nun kendi varsayılanı)."""
    import os

    if ayar is None:
        try:
            ayar = json.loads(ayarlar_dosyasi().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            ayar = {}
    if isinstance(ayar, dict) and ayar.get("is_parcacigi") is not None:
        try:
            return max(0, int(ayar["is_parcacigi"]))
        except (TypeError, ValueError):
            pass
    cekirdek = cekirdek or os.cpu_count() or 4
    if _ekran_karti_bekleniyor():
        return max(1, min(GPU_IS_PARCACIGI, cekirdek // max(1, kamera_sayisi)))
    return max(1, min(EN_COK_IS_PARCACIGI, cekirdek // max(1, kamera_sayisi)))


def _ekran_karti_bekleniyor() -> bool:
    try:
        import ekran_karti

        return ekran_karti.beklenen()["cihaz"] == "ekran_karti"
    except Exception:  # noqa: BLE001
        return False


def _sinir_dosyasi() -> Path:
    return yollar.VERI / "canli" / "is_parcacigi.json"


def siniri_guncelle() -> int:
    """Çalışan canlı kamera sayısına göre sınırı hesaplar ve motorların okuduğu dosyaya yazar (süreçler yeniden
    başlatılmadan 5 sn içinde uyar). Dönüş: sınır."""
    n = is_parcacigi_siniri(len(calisanlar()))
    p = _sinir_dosyasi()
    p.parent.mkdir(parents=True, exist_ok=True)
    gecici = p.with_suffix(".tmp")
    gecici.write_text(json.dumps({"n": n}), encoding="utf-8")
    import os

    os.replace(gecici, p)
    return n


_SIRA_KILIDI = threading.Lock()
_SON_BASLATMA = [0.0]


def baslatma_sirasi(simdi: float | None = None, aralik: float | None = None) -> float:
    """Bu kameranın Studio sürecini başlatacağı an: bir öncekinden en az BASLATMA_ARALIGI sonra."""
    simdi = time.monotonic() if simdi is None else simdi
    if aralik is None:
        try:  # kuruluma özel (canli.json "baslatma_araligi", saniye)
            aralik = float(json.loads(ayarlar_dosyasi().read_text(encoding="utf-8"))["baslatma_araligi"])
        except (OSError, ValueError, KeyError, TypeError):
            aralik = GPU_BASLATMA_ARALIGI if _ekran_karti_bekleniyor() else BASLATMA_ARALIGI
    with _SIRA_KILIDI:
        an = max(simdi, _SON_BASLATMA[0] + aralik)
        _SON_BASLATMA[0] = an
        return an


def klasor(kod: str) -> Path:
    return yollar.VERI / "canli" / kod


def analiz_fps(ayar: dict) -> float:
    """Kameranın seçili analiz hızı (saniyede kare); yoksa ya da geçersizse VARSAYILAN_FPS. 0.2 ile 30 arasında."""
    try:
        f = float(ayar.get("analiz_fps") or VARSAYILAN_FPS)
    except (TypeError, ValueError):
        f = VARSAYILAN_FPS
    return max(0.2, min(30.0, f))


def _ayar(kod: str) -> dict:
    return json.loads((yollar.AYAR / f"{kod}.json").read_text(encoding="utf-8"))


class CanliKamera:
    def __init__(self, kod: str, sifre: str | None):
        self.kod = kod
        self._sifre = sifre  # yalnızca bellekte; Studio sürecine ortam değişkeniyle gider
        self.dur = threading.Event()
        self.kilit = threading.Lock()
        self.durum, self.mesaj = "baglaniyor", "AugeLab Studio başlatılıyor"
        self.kosu = None          # studio.Kosu
        self.nabiz: dict = {}
        self.yeniden = 0          # Studio'nun kaçıncı kez başlatıldığı (iz numarası ofseti)
        self.kareler: list[dict] = []
        self.parca_bas: float | None = None
        self.sonuc: dict | None = None
        self.okunan: dict[str, int] = {}  # akış dosyası -> okunan bayt
        self.gorunum_anahtari = secrets.token_urlsafe(18)
        self._gorunum: dict[float, dict] = {}  # kare zamanı -> {iz: görünüm özeti}; yalnızca bellekte
        self.renk_imza = None
        self.yeniden_istek = threading.Event()  # panel istedi (ör. ekran kartı modeli hazırlandı, cihaz seçimi değişti)
        self.bitti = threading.Event()
        self.is_parcacigi = threading.Thread(target=self._calis, name=f"canli-{kod}", daemon=True)

    # ------------------------------------------------------------ Studio süreci
    def _studio_baslat(self) -> None:
        import kamera
        import studio

        ayar = _ayar(self.kod)
        adres, _ = kamera.kaynak(ayar, self._sifre)
        if isinstance(adres, int):  # USB kamera: motor numarayla açar
            adres = str(adres)
        if not isinstance(adres, str) or not (adres.startswith(("rtsp", "http")) or adres.isdigit()):
            raise SystemExit("Canlı izleme IP kamera (RTSP), HTTP akışı ve USB kamera içindir.")
        k = klasor(self.kod)
        for p in k.glob("akis-*.jsonl"):
            p.unlink(missing_ok=True)
        self.okunan.clear()
        self.renk_imza = _imza(ayar)
        ortam = {"KAFE_AKIS": str(k), "KAFE_NABIZ": str(k / "nabiz.json"), "KAFE_ONIZLEME": str(k / "onizleme.jpg"),
                 "KAFE_RENKLER": json.dumps(ayar.get("calisan_renkleri")), "KAFE_IMGSZ": int(ayar.get("imgsz", 960)),
                 "KAFE_ANALIZ_FPS": analiz_fps(ayar), "OPENCV_LOG_LEVEL": "SILENT", "OPENCV_FFMPEG_LOGLEVEL": "-8"}
        (k / "nabiz.json").unlink(missing_ok=True)
        # sıralı başlatma: birlikte açılan kameraların model yüklemesi üst üste binmesin
        an = baslatma_sirasi()
        while not self.dur.is_set() and time.monotonic() < an:
            self.durum = "sirada"
            self.mesaj = f"Sırada: {int(an - time.monotonic()) + 1} sn sonra başlatılacak (kameralar art arda açılıyor)"
            self.dur.wait(min(1.0, max(0.05, an - time.monotonic())))
        if self.dur.is_set():
            raise SystemExit("Durduruldu.")
        sinir = siniri_guncelle()
        if sinir > 0:  # kütüphaneler yüklenmeden önce: süreç ortamı
            for d in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
                ortam[d] = sinir
            ortam["KAFE_IS_PARCACIGI"] = sinir
        ortam["KAFE_IS_PARCACIGI_DOSYA"] = str(_sinir_dosyasi())
        if PANEL_ADRES:
            ortam["KAFE_GORUNUM_URL"] = f"{PANEL_ADRES}/api/canli/gorunum/{self.kod}?a={self.gorunum_anahtari}"
        self._gorunum.clear()
        self.durum, self.mesaj = "baglaniyor", "AugeLab Studio başlatılıyor"
        self.kosu = studio.baslat("canli", f"{self.kod}-{secrets.token_hex(3)}", ortam, adres=adres, canli=False)
        self.kosu_bas = time.time()
        del adres

    def _studio_durdur(self) -> None:
        if self.kosu is not None:
            import studio

            k = self.kosu
            self.kosu = None
            k.bitir(2.0)
            with studio._KILIT:
                if studio.KOSULAR.get(k.anahtar) is k:
                    studio.KOSULAR.pop(k.anahtar)

    # ------------------------------------------------------------ akış
    def _oku(self) -> int:
        """Yeni analiz satırlarını okur; tamamen okunmuş eski dosyaları siler. Dönüş: yeni kare sayısı."""
        yeni = 0
        dosyalar = sorted(klasor(self.kod).glob("akis-*.jsonl"))
        for n, p in enumerate(dosyalar):
            try:
                with p.open("rb") as f:
                    f.seek(self.okunan.get(p.name, 0))
                    veri = f.read()
            except OSError:
                continue
            son = veri.rfind(b"\n")
            if son < 0:
                continue
            self.okunan[p.name] = self.okunan.get(p.name, 0) + son + 1
            for satir in veri[:son].splitlines():
                try:
                    s = json.loads(satir)
                except ValueError:
                    continue
                z = float(s.get("z", 0))
                if self.parca_bas is None:
                    self.parca_bas = z
                ofset = self.yeniden * ID_ARALIGI
                for d in s.get("d") or []:
                    d["id"] = int(d["id"]) + ofset
                self.kareler.append({"i": len(self.kareler), "t": round(z - self.parca_bas, 3), "d": s.get("d") or [],
                                     "z": round(z, 3), "ofset": ofset})
                yeni += 1
            if n < len(dosyalar) - 1:  # motor yeni dosyaya geçti: bu dosya bitti
                try:
                    p.unlink()
                    self.okunan.pop(p.name, None)
                except OSError:
                    pass
        return yeni

    def _nabiz_oku(self) -> None:
        try:
            self.nabiz = json.loads((klasor(self.kod) / "nabiz.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

    # ------------------------------------------------------------ analiz
    def _hesapla(self) -> dict | None:
        """İçinde bulunulan parçanın algılamaları üzerinde masa / çalışan / kuyruk kurallarını çalıştırır (videosuz)."""
        import analiz

        if len(self.kareler) < 2:
            return None
        ayar = _ayar(self.kod)
        self._gorunum_ekle()
        kareler = json.loads(json.dumps(self.kareler))
        sure = max(1e-3, kareler[-1]["t"] - kareler[0]["t"])
        fps = max(0.2, (len(kareler) - 1) / sure)
        W, H = self.nabiz.get("W") or 1280, self.nabiz.get("H") or 720
        veri = {"fps": fps, "W": int(W), "H": int(H), "n": max(len(kareler), int(round(kareler[-1]["t"] * fps)) + 1), "adim": 1,
                "kareler": kareler}
        veri = analiz.izleri_birlestir(veri)
        s = analiz.analiz(None, ayar, veri, yollar.CIKTI / self.kod)
        s["bas_epoch"] = self.parca_bas
        s["bas_zaman"] = dt.datetime.fromtimestamp(self.parca_bas).isoformat(timespec="seconds")
        s["canli"] = True
        (yollar.CIKTI / self.kod / "sonuc.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        return s

    def gorunum_al(self, veri: dict) -> None:
        """Motorun gönderdiği görünüm özetleri (yalnızca bellekte; en çok 2 dakika tutulur)."""
        try:
            z = round(float(veri["z"]), 3)
            g = {str(k): v for k, v in (veri.get("g") or {}).items() if isinstance(v, list) and len(v) <= 64}
        except (KeyError, TypeError, ValueError):
            return
        with self.kilit:
            self._gorunum[z] = g
            for eski in [k for k in self._gorunum if k < z - 120]:
                del self._gorunum[eski]

    def _gorunum_ekle(self) -> None:
        with self.kilit:
            for kr in self.kareler:
                g = self._gorunum.pop(kr.get("z"), None)
                if not g:
                    continue
                for d in kr["d"]:
                    oz = g.get(str(d["id"] - kr.get("ofset", 0)))
                    if oz is not None:
                        d["g"] = oz

    def _parcayi_kapat(self) -> None:
        """Parçanın sonucu gecmis/'e yazılır (gün toplamı, Excel), panel yenilenir; yeni parça başlar."""
        import rapor

        s = self._hesapla()
        if s is not None:
            g = yollar.GECMIS / self.kod
            g.mkdir(parents=True, exist_ok=True)
            ad = dt.datetime.fromtimestamp(self.parca_bas).strftime("%Y%m%d_%H%M%S")
            (g / f"canli_{ad}.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
            try:
                rapor.uret()
            except Exception as e:  # noqa: BLE001
                print(f"Panel yenilenemedi: {e}", flush=True)
        son = self.kareler[-1]["t"] + (self.parca_bas or 0) if self.kareler else None
        self.kareler, self.parca_bas, self.sonuc = [], son, None  # parçanın görünüm özetleri de bellekten gider

    # ------------------------------------------------------------ döngü
    def _calis(self) -> None:
        bekle, son_hesap = 5.0, 0.0
        try:
            while not self.dur.is_set():
                try:
                    if self.kosu is None:
                        self._studio_baslat()
                    self._nabiz_oku()
                    yeni = self._oku()
                    if not self.kosu.calisiyor():
                        sorun = self.kosu.sorun() or "AugeLab Studio süreci kapandı"
                        self._studio_durdur()
                        self.yeniden += 1
                        self.durum, self.mesaj = "hata", f"{sorun} Yeniden deneniyor."
                        self.dur.wait(bekle)
                        bekle = min(60.0, bekle * 2)
                        continue
                    self._durum_guncelle()
                    if self.durum == "calisiyor":
                        bekle = 5.0

                    a_ = _ayar(self.kod)
                    if _imza(a_) != self.renk_imza or self.yeniden_istek.is_set():
                        print(f"{self.kod}: çalışan renkleri, analiz hızı, algılama çözünürlüğü ya da cihaz değişti; "
                              "analiz yeniden başlatılıyor.", flush=True)
                        self.yeniden_istek.clear()
                        self._studio_durdur()
                        self.yeniden += 1
                        continue
                    self._ekran_karti_eksigi()
                    simdi = time.time()
                    if yeni and simdi - son_hesap >= YENILE_SN:
                        try:
                            s = self._hesapla()
                        except Exception as e:  # noqa: BLE001  (ölçüm hatası Studio'yu durdurmaz)
                            import traceback

                            traceback.print_exc()
                            print(f"{self.kod}: canlı ölçüm hesaplanamadı ({type(e).__name__}).", flush=True)
                            s = self.sonuc
                        son_hesap = time.time()
                        with self.kilit:
                            self.sonuc = s
                    if self.parca_bas is not None and self.kareler and self.kareler[-1]["t"] >= PARCA_SN:
                        self._parcayi_kapat()
                except SystemExit as e:
                    self.durum, self.mesaj = "hata", str(e.code)
                    self._studio_durdur()
                    self.dur.wait(bekle)
                    bekle = min(60.0, bekle * 2)
                    continue
                except Exception as e:  # noqa: BLE001
                    import studio

                    self.durum = "hata"
                    self.mesaj = str(e) if isinstance(e, studio.StudioHatasi) else f"Canlı analiz hatası: {type(e).__name__}"
                    self._studio_durdur()
                    self.dur.wait(bekle)
                    bekle = min(60.0, bekle * 2)
                    continue
                self.dur.wait(1.0)
        finally:
            self._studio_durdur()
            try:
                self._oku()
                if self.kareler:
                    self._parcayi_kapat()
            except Exception:  # noqa: BLE001
                pass
            self._temizle()
            with self.kilit:
                self._gorunum.clear()
            self.kareler = []
            self.durum, self.mesaj = "durdu", "Canlı izleme durduruldu"
            self._sifre = None
            self.bitti.set()
            try:
                siniri_guncelle()  # kalan kameralar daha çok iş parçacığı kullanabilir
            except OSError:
                pass

    def _ekran_karti_eksigi(self) -> None:
        """Motor bir görüntü boyutu için ekran kartı modeli bulamadıysa (ör. 4:3 kamera) hazırlatılır; hazır olunca
        kamera yeniden başlatılır (ekran_karti._hazirla -> ekran_karti_hazir)."""
        c = self.nabiz.get("cihaz") or {}
        if c.get("eksik") or c.get("bozuk"):
            try:
                import ekran_karti

                yeni = ekran_karti.eksik_bildir(list(c.get("eksik") or []))
                if c.get("bozuk") and ekran_karti.bozuk_bildir(list(c["bozuk"]), c.get("hassasiyet_istenen")):
                    yeni = True
                if yeni:
                    ekran_karti.hazirla_baslat()
            except Exception:  # noqa: BLE001
                pass

    def _cihaz(self) -> dict:
        """Panoda gösterilen cihaz: motor nabızda bildirdiyse o, yoksa panelin beklediği."""
        c = self.nabiz.get("cihaz") or {}
        if c.get("cihaz") in ("ekran_karti", "islemci"):
            return {"cihaz": c["cihaz"], "hassasiyet": c.get("hassasiyet") if c["cihaz"] == "ekran_karti" else None,
                    "neden": c.get("neden"), "istenen": c.get("istenen"), "kart_yok": c.get("kart_yok")}
        return _beklenen_cihaz()

    def _temizle(self) -> None:
        k = klasor(self.kod)  # yalnızca bu kameranın klasörü (ortak sınır dosyası canli/ altında kalır)
        if k.is_dir():
            shutil.rmtree(k, ignore_errors=True)

    def _durum_guncelle(self) -> None:
        n = self.nabiz
        simdi = time.time()
        kaynak = str(n.get("durum") or "")
        son_kare = float(n.get("son_kare") or 0)
        if not n or simdi - float(n.get("an") or 0) > 20:
            self.durum, self.mesaj = "baglaniyor", "AugeLab Studio başlatılıyor"
        elif son_kare and simdi - son_kare <= KOPTU_SN:
            self.durum, self.mesaj = "calisiyor", ""
            c = self._cihaz()
            if c["cihaz"] == "islemci" and c.get("neden") and c.get("istenen") not in (None, "islemci") and not (
                    c.get("istenen") == "otomatik" and c.get("kart_yok")):
                self.mesaj = f"İşlemcide analiz ediliyor: {c['neden']}"
            hedef, gercek = n.get("hedef_fps"), n.get("gercek_fps")
            if hedef and gercek is not None and simdi - float(n.get("basladi") or simdi) > 20 and gercek < DUSUK_HIZ_ORANI * hedef:
                self.mesaj = (f"Bilgisayar yetişemiyor: saniyede {hedef:g} kare isteniyor, {gercek:g} kare analiz ediliyor. "
                              "Analiz hızını düşürün ya da alt akışı kullanın.")
        elif son_kare:
            neden = kaynak[len("bekliyor:"):].strip() if kaynak.startswith("bekliyor:") else ""
            self.durum, self.mesaj = "koptu", "Bağlantı koptu, yeniden deneniyor." + (f" {neden}" if neden and "bağlanılıyor" not in neden else "")
        else:
            neden = kaynak[len("bekliyor:"):].strip() if kaynak.startswith("bekliyor:") else ""
            self.durum, self.mesaj = "baglaniyor", neden or "Kameraya bağlanılıyor"

    # ------------------------------------------------------------ pano verisi
    def pano(self) -> dict:
        return {**self._pano(), "izlemeye_dahil": True, "sifre_bekleniyor": False, "baglanti": None}

    def _pano(self) -> dict:
        ayar = {}
        try:
            ayar = _ayar(self.kod)
        except (OSError, ValueError):
            pass
        n = self.nabiz
        with self.kilit:
            s = self.sonuc
        son_kare = float(n.get("son_kare") or 0)
        canli = self.durum == "calisiyor"
        a = (s or {}).get("anlik") or {}
        durumlar = {m["ad"]: m for m in a.get("masalar") or []}
        masalar = []
        for m in ayar.get("masalar") or []:
            d = durumlar.get(m["ad"])
            if d is None:
                masalar.append({"ad": m["ad"], "durum": None, "kisi": None, "sure_sn": None, "bolge": m["poly"], "uyeler": None,
                                "ara_verdi": None, "ara_sn": None})
                continue
            ic = d["durum"]
            durum = {"bos": "bos", "dolu": "dolu", "bekliyor": "dolu", "uyari": "bekliyor", "kirli": "kirli",
                     "temizleniyor": "kirli", "ara": "dolu"}.get(ic, ic)
            sure = (d.get("ara_oturum_sn") if ic == "ara" else d.get("oturum_sn")) if durum in ("dolu", "bekliyor") else (
                d.get("kirli_sn") if durum == "kirli" else d.get("sure_sn"))
            masalar.append({"ad": m["ad"], "durum": durum, "kisi": d.get("kisi"), "sure_sn": round(sure) if sure is not None else None,
                            "bolge": m["poly"], "uyeler": d.get("uyeler") or {"masada": 0, "ara_verdi": 0},
                            "ara_verdi": ic == "ara", "ara_sn": round(d["ara_sn"]) if d.get("ara_sn") is not None else None})
        kasa = a.get("kuyruk")
        c = self._cihaz()
        return {
            "kod": self.kod, "ad": ayar.get("ad", self.kod), "durum": "baglaniyor" if self.durum == "sirada" else self.durum,
            "mesaj": self.mesaj, "cihaz": c["cihaz"], "hassasiyet": c.get("hassasiyet"),
            "onizleme": f"/api/canli/onizleme/{self.kod}", "genislik": n.get("W"), "yukseklik": n.get("H"),
            "son_kare_sn": round(time.time() - son_kare, 1) if son_kare else None,
            "analiz_fps": {"hedef": analiz_fps(ayar) if ayar else None, "gercek": n.get("gercek_fps") if self.durum == "calisiyor" else None},
            "simdi": ({"kisi": a.get("kisi"), "musteri": a.get("musteri"), "calisan": a.get("calisan")} if canli and a
                      else {"kisi": None, "musteri": None, "calisan": None}),
            "masalar": masalar,
            "kasa": ({"sira": kasa["sira"], "bekleme_sn": round(kasa["bekleme_sn"])} if canli and kasa else None),
            **gun_ozeti(self.kod, s),
        }


def _bugunku_parcalar(kod: str, acik: dict | None) -> list[dict]:
    bugun = dt.date.today()
    out = []
    g = yollar.GECMIS / kod
    for p in sorted(g.glob("canli_*.json")) if g.is_dir() else []:
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if s.get("bas_epoch") and dt.date.fromtimestamp(s["bas_epoch"]) == bugun:
            out.append(s)
    if acik and acik.get("bas_epoch") and dt.date.fromtimestamp(acik["bas_epoch"]) == bugun:
        out.append(acik)
    return out


def gun_ozeti(kod: str, acik: dict | None) -> dict:
    """Bugünün parçalarından toplamlar, saatlik doluluk ve son uyarılar. Hesaplanamayan değer None."""
    parcalar = _bugunku_parcalar(kod, acik)
    if not parcalar:
        return {"bugun": {"oturum": None, "ort_kalis_sn": None, "doluluk_yuzde": None, "musteri": None, "terk": None},
                "saatlik": [], "uyarilar": []}
    oturum = sum(p["ozet"]["oturum"] for p in parcalar)
    kalis = [(p["ozet"]["ort_oturma"], p["ozet"]["oturum"]) for p in parcalar if p["ozet"].get("ort_oturma") is not None]
    dol = [(p["ozet"]["doluluk"], p["sure"]) for p in parcalar if p["ozet"].get("doluluk") is not None]
    terk = [p["ozet"]["donen"] for p in parcalar if p["ozet"].get("donen") is not None]
    bugun = {
        "oturum": oturum,
        "ort_kalis_sn": round(sum(a * b for a, b in kalis) / sum(b for _, b in kalis)) if kalis and sum(b for _, b in kalis) else None,
        "doluluk_yuzde": round(sum(a * b for a, b in dol) / sum(b for _, b in dol), 1) if dol and sum(b for _, b in dol) else None,
        "musteri": sum(p["ozet"]["musteri"] for p in parcalar),
        "terk": sum(terk) if terk else None,
    }
    saat: dict[int, dict] = {}
    for p in parcalar:
        masa_say = len(p.get("masalar") or [])
        for t, dolu in p.get("doluluk_seri") or []:
            h = dt.datetime.fromtimestamp(p["bas_epoch"] + t).hour
            s = saat.setdefault(h, {"dol": [], "musteri": 0})
            if masa_say:
                s["dol"].append(100.0 * dolu / masa_say)
        for iz in p.get("izler") or []:
            h = dt.datetime.fromtimestamp(p["bas_epoch"] + iz["ilk"]).hour
            saat.setdefault(h, {"dol": [], "musteri": 0})["musteri"] += 1
    saatlik = [{"saat": h, "doluluk_yuzde": round(sum(v["dol"]) / len(v["dol"]), 1) if v["dol"] else None, "musteri": v["musteri"]}
               for h, v in sorted(saat.items())]
    uyarilar = []
    for p in parcalar:
        for u in p.get("uyarilar") or []:
            an = p["bas_epoch"] + float(u.get("t") or 0)
            uyarilar.append((an, {"zaman": dt.datetime.fromtimestamp(an).strftime("%H:%M"), "tur": u.get("tur"),
                                  "metin": str(u.get("metin") or "").replace("video başından", "izleme başından"),
                                  "masa": u.get("masa") or None}))
    uyarilar.sort(key=lambda x: -x[0])
    return {"bugun": bugun, "saatlik": saatlik, "uyarilar": [u for _, u in uyarilar[:20]]}


# ---------------------------------------------------------------- yönetici

KAMERALAR: dict[str, CanliKamera] = {}
_KILIT = threading.Lock()


def baslat(kod: str, sifre: str | None) -> None:
    with _KILIT:
        eski = KAMERALAR.get(kod)
        if eski is not None and not eski.bitti.is_set():
            raise SystemExit("Bu kamera zaten canlı izleniyor.")
        klasor(kod).mkdir(parents=True, exist_ok=True)
        k = CanliKamera(kod, sifre)
        KAMERALAR[kod] = k
        k.is_parcacigi.start()


def durdur(kod: str, bekle_sn: float = 30.0) -> None:
    with _KILIT:
        k = KAMERALAR.get(kod)
    if k is None:
        return
    k.dur.set()
    k.bitti.wait(bekle_sn)


def durdur_hepsi(bekle_sn: float = 30.0) -> None:
    with _KILIT:
        kameralar = list(KAMERALAR.values())
    for k in kameralar:
        k.dur.set()
    son = time.monotonic() + bekle_sn
    for k in kameralar:
        k.bitti.wait(max(0.1, son - time.monotonic()))


def calisanlar() -> list[str]:
    return [kod for kod, k in KAMERALAR.items() if not k.bitti.is_set()]


def api() -> dict:
    """Canlı pano verisi: izlenen kameralar (çalışan, sırada, şifre bekleyen) ve izlemeye dahil olmayanlar."""
    with _KILIT:
        kameralar = {kod: k for kod, k in KAMERALAR.items() if not k.bitti.is_set()}
    out = [k.pano() for k in kameralar.values()]
    for kod, a in _canli_ayarlar().items():
        if kod in kameralar:
            continue
        bekleyen = _BEKLEYEN.get(kod)
        if bekleyen is not None:
            out.append(_bos_pano(kod, a, "baglaniyor", "Şifre bekleniyor: kameranın (ya da kayıt cihazının) şifresini girin.",
                                 sifre_bekleniyor=True, baglanti=bekleyen))
        elif not izlemede_mi(a):
            out.append(_bos_pano(kod, a, "durdu", "İzleme duraklatıldı." if duraklatildi() else "Bu kamera izlemeye dahil değil.",
                                 izlemeye_dahil=a.get("izlemeye_dahil", True) is not False))
        else:
            out.append(_bos_pano(kod, a, "durdu", "Canlı izleme durduruldu." if kod in KAMERALAR else "Henüz başlatılmadı."))
    return {"zaman": dt.datetime.now().isoformat(timespec="seconds"), "duraklatildi": duraklatildi(), "kameralar": out}


def _bos_pano(kod: str, a: dict, durum: str, mesaj: str, sifre_bekleniyor: bool = False, baglanti=None,
              izlemeye_dahil: bool = True) -> dict:
    return {"kod": kod, "ad": a.get("ad", kod), "durum": durum, "mesaj": mesaj, "onizleme": f"/api/canli/onizleme/{kod}",
            "genislik": None, "yukseklik": None, "son_kare_sn": None,
            "analiz_fps": {"hedef": analiz_fps(a), "gercek": None},
            "simdi": {"kisi": None, "musteri": None, "calisan": None},
            "masalar": [{"ad": m["ad"], "durum": None, "kisi": None, "sure_sn": None, "bolge": m["poly"], "uyeler": None,
                         "ara_verdi": None, "ara_sn": None} for m in a.get("masalar") or []],
            "kasa": None, **gun_ozeti(kod, None), "izlemeye_dahil": izlemeye_dahil, "sifre_bekleniyor": sifre_bekleniyor,
            "baglanti": baglanti, "cihaz": _beklenen_cihaz()["cihaz"], "hassasiyet": _beklenen_cihaz()["hassasiyet"]}


def _imza(a: dict):
    import renkler

    return (renkler.imza(renkler.coz(a.get("calisan_renkleri"))), analiz_fps(a), int(a.get("imgsz") or 960))


def _beklenen_cihaz() -> dict:
    try:
        import ekran_karti

        return ekran_karti.beklenen()
    except Exception:  # noqa: BLE001
        return {"cihaz": "islemci", "hassasiyet": None, "neden": None}


def yeniden_baslat(yalniz_islemcide: bool = False) -> list[str]:
    """Çalışan kameraların Studio süreçleri yerinde yeniden başlatılır (izleme kesilmez, gün toplamı korunur).
    `yalniz_islemcide`: yalnızca ekran kartı beklenirken işlemcide çalışanlar."""
    out = []
    with _KILIT:
        kameralar = [k for k in KAMERALAR.values() if not k.bitti.is_set()]
    for k in kameralar:
        if yalniz_islemcide and (k.nabiz.get("cihaz") or {}).get("cihaz") == "ekran_karti":
            continue
        k.yeniden_istek.set()
        out.append(k.kod)
    return out


def ekran_karti_hazir() -> list[str]:
    """Ekran kartı modeli hazırlandı: ekran kartı bekleyen ama işlemcide çalışan kameralar yeniden başlatılır."""
    return yeniden_baslat(yalniz_islemcide=True) if _beklenen_cihaz()["cihaz"] == "ekran_karti" else []


def gorunum_al(kod: str, anahtar: str, veri: dict) -> bool:
    k = KAMERALAR.get(kod)
    if k is None or k.bitti.is_set() or not secrets.compare_digest(str(anahtar), k.gorunum_anahtari):
        return False
    k.gorunum_al(veri)
    return True


def onizleme(kod: str) -> Path | None:
    k = KAMERALAR.get(kod)
    p = klasor(kod) / "onizleme.jpg"
    return p if k is not None and not k.bitti.is_set() and p.is_file() else None


# ---------------------------------------------------------------- otomatik izleme
# Kaydedilen her canlı kamera (IP kamera, HTTP akışı, USB) izlenir: program açılınca, kamera eklenince ya da değişince
# başlar (sıralı, iş parçacığı sınırıyla). Kamera başına "izlemeye_dahil" (varsayılan açık) ve genel duraklatma kalıcıdır.
# Şifre: yalnızca bellekte (bu çalışma için, aynı kayıt cihazı + kullanıcı için bir kez girilir) ya da kamera ayarında
# "sifre_sakla" açıksa Windows DPAPI ile şifreli (sifre_kasasi). Şifre gerekip bilinmiyorsa kamera "şifre bekleniyor"da kalır.

CANLI_TURLER = ("rtsp", "http", "usb")
_SIFRELER: dict[str, str] = {}      # "host:port|kullanıcı" -> şifre (yalnızca bellekte)
_BEKLEYEN: dict[str, dict] = {}     # kod -> {"host", "kullanici"}: şifre bekleyen kameralar
_PARMAK: dict[str, str] = {}        # kod -> çalışan kameranın bağlantı ayarlarının özeti (değişirse yeniden başlar)
_ESITLE_KILIDI = threading.Lock()


def genel_ayar() -> dict:
    try:
        d = json.loads(ayarlar_dosyasi().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _genel_yaz(**degerler) -> None:
    d = genel_ayar()
    d.update(degerler)
    yollar.VERI.mkdir(parents=True, exist_ok=True)
    ayarlar_dosyasi().write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def duraklatildi() -> bool:
    return bool(genel_ayar().get("duraklat"))


def _canli_ayarlar() -> dict[str, dict]:
    out = {}
    for p in sorted(yollar.AYAR.glob("*.json")) if yollar.AYAR.is_dir() else []:
        if p.stem.startswith("_"):
            continue
        try:
            a = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (a.get("kamera") or {}).get("tur", "rtsp") in CANLI_TURLER:
            out[p.stem] = a
    return out


def izlemede_mi(a: dict) -> bool:
    return (a.get("kamera") or {}).get("tur", "rtsp") in CANLI_TURLER and a.get("izlemeye_dahil", True) is not False \
        and not duraklatildi()


def baglanti(a: dict) -> dict | None:
    """Şifrenin paylaşıldığı birim: kayıt cihazının adresi ve kullanıcı adı (aynı NVR'nin kanalları tek şifreyle açılır)."""
    from urllib.parse import urlsplit

    k = a.get("kamera") or {}
    tur = k.get("tur", "rtsp")
    if tur == "usb":
        return None
    kul = k.get("kullanici", "admin")
    if k.get("adres"):
        try:
            u = urlsplit(k["adres"].replace("{kullanici}", "u").replace("{sifre}", "p"))
            host = f"{u.hostname}:{u.port or (554 if u.scheme == 'rtsp' else 80)}"
        except ValueError:
            return None
    else:
        host = f"{k.get('ip', '')}:{k.get('port', 554)}"
    return {"host": host, "kullanici": kul}


def _anahtar(b: dict) -> str:
    return f"{b['host']}|{b['kullanici']}"


def _sifre(kod: str, a: dict) -> str | None:
    """Kameranın şifresi: gerekmiyorsa "", bellekte ya da (sakla açıksa) DPAPI kasasında varsa o; yoksa None."""
    import kamera

    if not kamera.sifre_gerekli(a):
        return ""
    b = baglanti(a)
    if b is None:
        return ""
    s = _SIFRELER.get(_anahtar(b))
    if s is None and a.get("sifre_sakla"):
        import sifre_kasasi

        s = sifre_kasasi.oku(kod)
        if s is not None:
            _SIFRELER[_anahtar(b)] = s
    return s


def _parmak(a: dict) -> str:
    import hashlib

    return hashlib.sha256(json.dumps(a.get("kamera") or {}, sort_keys=True).encode("utf-8")).hexdigest()


def esitle() -> dict:
    """İstenen durumla çalışanı eşitler: izlenmesi gereken kameraları başlatır, kalanları durdurur, bağlantı ayarı
    değişenleri yeniden başlatır. Dönüş: {"baslatilan", "durdurulan", "sifre_bekleyen"}."""
    with _ESITLE_KILIDI:
        istenen = {kod: a for kod, a in _canli_ayarlar().items() if izlemede_mi(a)}
        sonuc = {"baslatilan": [], "durdurulan": [], "sifre_bekleyen": []}
        for kod in [k for k in calisanlar() if k not in istenen or _PARMAK.get(k) != _parmak(istenen[k])]:
            durdur(kod)
            sonuc["durdurulan"].append(kod)
        for kod in list(_BEKLEYEN):
            if kod not in istenen:
                _BEKLEYEN.pop(kod, None)
        calisan = set(calisanlar())
        for kod, a in istenen.items():
            if kod in calisan:
                continue
            s = _sifre(kod, a)
            if s is None:
                _BEKLEYEN[kod] = baglanti(a)
                sonuc["sifre_bekleyen"].append(kod)
                continue
            _BEKLEYEN.pop(kod, None)
            _PARMAK[kod] = _parmak(a)
            baslat(kod, s)
            sonuc["baslatilan"].append(kod)
        return sonuc


def esitle_arkada() -> None:
    threading.Thread(target=esitle, daemon=True, name="canli-esitle").start()


def izlemeye_dahil(kod: str, evet: bool) -> None:
    p = yollar.AYAR / f"{kod}.json"
    a = json.loads(p.read_text(encoding="utf-8"))
    a["izlemeye_dahil"] = bool(evet)
    p.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")


def duraklat(evet: bool) -> None:
    _genel_yaz(duraklat=bool(evet))


def sifre_ver(sifre: str, kod: str | None = None, host: str | None = None, kullanici: str | None = None,
              sakla: bool | None = None) -> list[str]:
    """Bir kayıt cihazının (host + kullanıcı) şifresi: bu çalışma için bellekte tutulur ve aynı cihazın bütün kameralarını
    açar. `sakla` True ise bu kameraların "sifre_sakla" seçeneği açılır ve şifre DPAPI ile saklanır; False ise kapatılır ve
    saklanan şifre silinir. Dönüş: bu şifreyi kullanan kameralar."""
    import sifre_kasasi

    ayarlar = _canli_ayarlar()
    if kod is not None:
        b = baglanti(ayarlar[kod]) if kod in ayarlar else None
    else:
        b = {"host": host, "kullanici": kullanici}
    if not b or not b.get("host"):
        raise SystemExit("Kamera bulunamadı.")
    anahtar = _anahtar(b)
    _SIFRELER[anahtar] = str(sifre)
    ortak = [k for k, a in ayarlar.items() if baglanti(a) and _anahtar(baglanti(a)) == anahtar]
    for k in ortak:
        if sakla is not None:
            sifre_sakla(k, bool(sakla), _sifre_bilinen=str(sifre))
        elif ayarlar[k].get("sifre_sakla"):
            sifre_kasasi.sakla(k, str(sifre))
        if k in calisanlar():  # yanlış şifreyle bağlanamayan kamera yeni şifreyle yeniden başlar
            durdur(k)
    return ortak


def sifre_sakla(kod: str, evet: bool, _sifre_bilinen: str | None = None) -> None:
    """Kameranın "Şifreyi bu bilgisayarda sakla" seçeneği. Açılınca şifre (bu çalışmada biliniyorsa) DPAPI ile saklanır;
    kapatılınca saklanan şifre silinir."""
    import sifre_kasasi

    p = yollar.AYAR / f"{kod}.json"
    a = json.loads(p.read_text(encoding="utf-8"))
    a["sifre_sakla"] = bool(evet)
    p.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    if not evet:
        sifre_kasasi.sil(kod)
        return
    s = _sifre_bilinen
    if s is None:
        b = baglanti(a)
        s = _SIFRELER.get(_anahtar(b)) if b else None
    if s:
        sifre_kasasi.sakla(kod, s)


def kamera_silindi(kod: str) -> None:
    import sifre_kasasi

    sifre_kasasi.sil(kod)
    _BEKLEYEN.pop(kod, None)
    _PARMAK.pop(kod, None)


def izleme_listesi() -> dict:
    """Kurulum sayfası için: canlı izlenebilen kameralar, anahtarları ve durumları (şifre hiç yer almaz)."""
    import kamera
    import sifre_kasasi

    canli_ = {k["kod"]: k for k in api()["kameralar"]}
    out = []
    for kod, a in _canli_ayarlar().items():
        k = canli_.get(kod) or {}
        out.append({"kod": kod, "ad": a.get("ad", kod), "tur": (a.get("kamera") or {}).get("tur", "rtsp"),
                    "izlemeye_dahil": a.get("izlemeye_dahil", True) is not False, "durum": k.get("durum", "durdu"),
                    "mesaj": k.get("mesaj", ""), "sifre_gerekli": kamera.sifre_gerekli(a),
                    "sifre_bekleniyor": kod in _BEKLEYEN, "sifre_saklaniyor": bool(a.get("sifre_sakla")) and sifre_kasasi.var_mi(kod),
                    "sifre_sakla": bool(a.get("sifre_sakla")), "baglanti": baglanti(a), "analiz_fps": analiz_fps(a),
                    "cihaz": k.get("cihaz") or _beklenen_cihaz()["cihaz"], "hassasiyet": k.get("hassasiyet"),
                    "imgsz": int(a.get("imgsz") or 960)})
    return {"duraklatildi": duraklatildi(), "kameralar": out}
