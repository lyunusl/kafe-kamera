"""AugeLab Studio köprüsü: arayüzsüz koşu.

Kafe Kamera, Studio'nun kodunu içermez ve Studio penceresini hiç açmaz. Her iş için kullanıcının kurduğu Studio'nun kendi
Python'uyla gizli bir süreç başlatır:

    "<Studio>/Python/python.exe" -m studio run kafe-kamera.pmod --json

kafe-kamera.pmod, programla gelen hazır sahnedir (sahne dosyası yalnızca Studio'dan kaydedilebildiği için bir kez Studio'da
kurulup kaydedilmiştir: kurulum/sablon.py):

    Kafe Kamera İşi ──┬──────────────────────────────┐
                      └─► Kafe Kaynak ─(görüntü, sıra, zaman, bitti, durum)─► Kafe Algılama ─► sonuç dosyası

Sahne her iş için aynıdır; işin ne olduğunu ortam değişkenlerinden öğrenir (kafe_motor.blok: KAFE_IS "tür#koşu",
KAFE_GIRDI, KAFE_CIKTI, KAFE_KAMERA_ADRES canlı akış adresi, KAFE_DUR durdurma dosyası). Panel önce bloklarını Studio'nun
özel blok klasörüne yazar ve motorunu (kafe_motor, model, ek kütüphaneler) yanına koyar; Studio'nun ortamına paket
kurulmaz. Model yalnızca Studio'nun içinde açılır; panel süreci modeli hiç yüklemez.

Geliştirme için:  python studio.py durum | dene
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

import studio_blok
import yollar

KAYNAK = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
MOTOR_KAYNAK = KAYNAK / "motor"
SABLON_KAYNAK = KAYNAK / "kurulum" / "sahne" / "kafe-kamera.pmod"
DURUM_DOSYASI = yollar.VERI / "studio.json"
LISANS_ISARETI = yollar.VERI / "studio-lisans.txt"  # kurulum dosyası lisans kodunu Studio'ya kaydedince bırakır (kodun kendisi değil)
KOSU_KLASORU = yollar.VERI / "studio"
PENCERESIZ = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
ORTAM_ONEKI = "KAFE_"  # motorun okuduğu ortam değişkenleri (kafe_motor.blok); panelin kendi ortamından devralınmaz


class StudioHatasi(RuntimeError):
    """Studio bir isteği reddetti ya da sahne çalışmadı."""


class StudioYok(StudioHatasi):
    """AugeLab Studio kurulu değil."""


class Durduruldu(StudioHatasi):
    """İş kullanıcının isteğiyle durduruldu."""


# ---------------------------------------------------------------- Studio'nun yerleri


def kurulu_klasor() -> Path | None:
    import studio_kurulum

    exe = studio_kurulum.kurulu_studio()
    return exe.parent if exe else None


def studio_python() -> Path:
    """Studio'nun kendi Python yorumlayıcısı (arayüzsüz koşu bununla yapılır)."""
    klasor = kurulu_klasor()
    if klasor is None:
        raise StudioYok("AugeLab Studio kurulu değil. Başlangıç sayfasındaki AugeLab Studio kurulum sihirbazıyla kurun.")
    py = klasor / "Python" / "python.exe"
    if not py.is_file():
        raise StudioHatasi(f"AugeLab Studio'nun Python'u bulunamadı ({yollar.gizle(str(py))}). Studio'yu resmî kurucuyla onarın.")
    return py


def marketplace() -> Path:
    """Studio'nun özel blok klasörünün bulunduğu yer (Studio bunu her kullanıcı için %APPDATA% altında tutar)."""
    return Path(os.environ.get("APPDATA", str(Path.home()))) / "AugeLab Studio" / "marketplace"


def surum() -> str | None:
    """Kurulu Studio'nun sürümü (paket bilgisinden; Studio çalıştırılmaz)."""
    klasor = kurulu_klasor()
    if klasor is None:
        return None
    for bilgi in sorted((klasor / "Python" / "Lib" / "site-packages").glob("studio-*.dist-info")):
        return bilgi.name[len("studio-"):-len(".dist-info")]
    return None


# ---------------------------------------------------------------- motor klasörü


def _dosyalar(klasor: Path) -> list[Path]:
    return sorted(p for p in klasor.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def _klasor_dosyalari(klasor: Path) -> dict[Path, Path]:
    """{göreli yol: kaynak yol}: klasördeki bütün dosyalar."""
    return {p.relative_to(klasor): p for p in _dosyalar(klasor)}


def _dosya_ozeti(p: Path) -> bytes:
    with p.open("rb") as dosya:
        return hashlib.file_digest(dosya, "sha256").digest()


def _parmak_izi(kaynaklar: dict[Path, Path]) -> str:
    """Kaynak dosyaların içerik imzası: göreli adlar ve içerik özetleri. Dosya tarihine bakılmaz: exe her açılışta
    dosyalarını geçici bir klasöre yeni tarihle açar; tarih imzaya girseydi motor her açılışta yeniden kopyalanırdı."""
    h = hashlib.sha256()
    for goreli in sorted(kaynaklar):
        h.update(goreli.as_posix().encode("utf-8") + b"\0" + _dosya_ozeti(kaynaklar[goreli]))
    return f"{len(kaynaklar)}:{h.hexdigest()[:40]}"


def _esitle(kaynaklar: dict[Path, Path], hedef: Path) -> int:
    """Hedef klasörü kaynak dosyaların aynısı yapar; yalnızca içeriği farklı olan dosyalara dokunur (Studio açıkken
    yüklediği kitaplıklar kilitlidir). Kaynakta artık olmayan dosyalar silinir. Dönüş: kopyalanan dosya sayısı."""
    hedef.mkdir(parents=True, exist_ok=True)
    kopya = 0
    for goreli, p in kaynaklar.items():
        h = hedef / goreli
        try:
            ayni = h.is_file() and h.stat().st_size == p.stat().st_size and _dosya_ozeti(h) == _dosya_ozeti(p)
        except OSError:
            ayni = False
        if ayni:
            continue
        h.parent.mkdir(parents=True, exist_ok=True)
        gecici = h.with_name(h.name + ".yeni")
        try:
            shutil.copyfile(p, gecici)
            os.replace(gecici, h)
        except OSError:
            try:
                gecici.unlink(missing_ok=True)
            except OSError:
                pass
            raise StudioHatasi(f"Motor dosyası güncellenemedi ({goreli.as_posix()}): dosya kullanımda olabilir. "
                               "Süren işi durdurup tekrar deneyin.") from None
        kopya += 1
    for h in _dosyalar(hedef):
        if h.relative_to(hedef) not in kaynaklar:
            try:
                h.unlink()
            except OSError:
                pass
    return kopya


ORTAK_MODULLER = ("renkler.py", "gizlilik.py", "rtsp_yokla.py", "gorunum.py", "gpu_ortak.py")  # motor bunları kafe_motor içinde kopya olarak taşır


def motor_kaynaklari() -> dict[str, dict[Path, Path]]:
    """Motor klasörüne giden dosyalar: {alt klasör: {göreli yol: kaynak yol}}."""
    if not (MOTOR_KAYNAK / "kafe_motor").is_dir():
        raise StudioHatasi(f"Motor kaynağı bulunamadı: {yollar.gizle(str(MOTOR_KAYNAK))}")
    if not yollar.MODEL.is_file():
        raise StudioHatasi(f"Model dosyası bulunamadı: {yollar.MODEL.name}")
    motor = _klasor_dosyalari(MOTOR_KAYNAK / "kafe_motor")
    for ad in ORTAK_MODULLER:  # panelle ortak modüller: kaynak koddan çalışırken kök klasörden (exe'de spec kopyalar)
        if Path(ad) not in motor and (KAYNAK / ad).is_file():
            motor[Path(ad)] = KAYNAK / ad
    eksik = [ad for ad in ORTAK_MODULLER if Path(ad) not in motor]
    if eksik:
        raise StudioHatasi(f"Motor dosyası eksik: {', '.join(eksik)}")
    modeller = {Path(yollar.MODEL.name): yollar.MODEL}
    for ad in ("yolo11s-pose.fp16.onnx", "yolo11s-pose.onnx"):  # ekran kartı modeli bunlardan bu bilgisayarda üretilir
        if (yollar.MODEL.parent / ad).is_file():
            modeller[Path(ad)] = yollar.MODEL.parent / ad
    out = {"kafe_motor": motor, "modeller": modeller}
    if (MOTOR_KAYNAK / "deps").is_dir():
        out["deps"] = _klasor_dosyalari(MOTOR_KAYNAK / "deps")
    return out


def motoru_yerlestir(hedef: Path) -> Path:
    """Motoru (kafe_motor, model, deps) Studio'nun özel blok klasörünün yanına kopyalar; değişmediyse dokunmaz."""
    hedef.mkdir(parents=True, exist_ok=True)
    imzalar = []
    for ad, kaynaklar in motor_kaynaklari().items():
        imza = _parmak_izi(kaynaklar)
        imzalar.append(f"{ad}={imza}")
        isaret = hedef / f"{ad}.surum"
        if (hedef / ad).is_dir() and isaret.exists() and isaret.read_text(encoding="ascii") == imza:
            continue
        _esitle(kaynaklar, hedef / ad)
        isaret.write_text(imza, encoding="ascii")
    surum_ = hedef / "surum.txt"  # yalnızca değiştiyse yazılır: bloklar bu dosyanın tarihine bakarak motoru yeniden yükler
    if not surum_.exists() or surum_.read_text(encoding="ascii") != "|".join(imzalar):
        surum_.write_text("|".join(imzalar), encoding="ascii")
    ayar = json.dumps({"veri": str(yollar.VERI)})
    if not (hedef / "ayar.json").is_file() or (hedef / "ayar.json").read_text(encoding="utf-8") != ayar:
        (hedef / "ayar.json").write_text(ayar, encoding="utf-8")
    return hedef


def bloklari_kur() -> Path:
    """Kafe bloklarını Studio'nun özel blok klasörüne yazar (yalnızca değiştiyse) ve motoru yanına yerleştirir.
    Dosyalar Studio'nun node.custom.create ile ürettiklerinin aynısıdır (studio_blok.dosya_metni). Dönüş: motor klasörü."""
    bloklar = marketplace() / "custom_blocks"
    bloklar.mkdir(parents=True, exist_ok=True)
    for tanim in studio_blok.TANIMLAR:
        hedef = bloklar / f"{tanim['opCode']}.py"
        metin = studio_blok.dosya_metni(tanim).replace("\n", "\r\n").encode("utf-8")
        try:
            if hedef.is_file() and hedef.read_bytes() == metin:
                continue
        except OSError:
            pass
        gecici = hedef.with_name(hedef.name + ".yeni")
        gecici.write_bytes(metin)
        os.replace(gecici, hedef)
    return motoru_yerlestir(marketplace() / studio_blok.MOTOR_KLASORU)


def sablon() -> Path:
    """Hazır sahnenin veri klasöründeki kopyası (exe her açılışta dosyalarını başka bir geçici klasöre açar)."""
    if not SABLON_KAYNAK.is_file():
        raise StudioHatasi("Hazır sahne (kafe-kamera.pmod) programla gelmemiş. Kafe Kamera'yı kurulum dosyasıyla yeniden kurun.")
    KOSU_KLASORU.mkdir(parents=True, exist_ok=True)
    hedef = KOSU_KLASORU / SABLON_KAYNAK.name
    if not hedef.is_file() or _dosya_ozeti(hedef) != _dosya_ozeti(SABLON_KAYNAK):
        shutil.copyfile(SABLON_KAYNAK, hedef)
    return hedef


# ---------------------------------------------------------------- arayüzsüz koşular


ANAHTAR_ADLARI = r"(?:user(?:name)?|usr|login|kullan[ıi]c[ıi](?:_?ad[ıi])?|pass(?:word|wd)?|pwd|[şs]ifre|parola|auth)"


def maskeleyici(adres: str = ""):
    """Studio'nun çıktısında akış adresi, kullanıcı adı ya da şifre geçerse gizleyen işlev. Panelin yazdığı ya da gösterdiği
    her Studio satırı önce bundan geçer: günlükte de hata metninde de maskesiz kopya kalmaz.

    Uzunluğu ne olursa olsun kullanıcı adı ve şifre maskelenir (yüzde kodlu ve çözülmüş biçimleriyle). Üç karakterden kısa
    değerler, günlüğü parçalamamak için yalnızca ayrı bir sözcük olarak, adresin kullanıcı kısmında ve "anahtar=değer" /
    "anahtar: değer" biçiminde aranır; uzunlar her yerde."""
    from urllib.parse import quote, unquote, urlsplit

    uzun, kisa = set(), set()
    if adres:
        uzun |= {adres, unquote(adres)}
        try:
            u = urlsplit(adres)
            for p in (u.username, u.password):
                if p:
                    for bicim in {p, unquote(p), quote(unquote(p), safe="")}:
                        (uzun if len(bicim) >= 3 else kisa).add(bicim)
        except ValueError:
            pass
    sirali = sorted((p for p in uzun if p), key=len, reverse=True)
    kisa_desenler = []
    for p in sorted(kisa, key=len, reverse=True):
        e = re.escape(p)
        kisa_desenler.append(re.compile(rf"(?i)(\b{ANAHTAR_ADLARI}\s*[=:]\s*['\"]?){e}(?![\w%])"))  # anahtar=değer
        kisa_desenler.append(re.compile(rf"(?<![\w%]){e}(?![\w%])"))  # ayrı sözcük

    def maskele(metin) -> str:
        metin = str(metin)
        for p in sirali:
            metin = metin.replace(p, "****")
        metin = re.sub(r"(://)[^/@\s]*@", r"\1****@", metin)  # adresin kullanıcı kısmı (her uzunlukta)
        for d in kisa_desenler:
            metin = d.sub(lambda m: (m.group(1) if m.groups() else "") + "****", metin)
        return metin
    return maskele


_GUNLUK_KILIDI = threading.Lock()


class Kosu:
    """Bir işin gizli `studio run` süreci. Studio'nun stdout'u (--json olayları) ve stderr'i bu süreçte okunur; stderr
    satırları maskelendikten sonra günlüğe yazılır (maskesiz kopya diske hiç gitmez)."""

    def __init__(self, ad: str, kosu: str, surec: subprocess.Popen, dur: Path, gunluk: Path, maskele=None):
        self.ad, self.kosu, self.surec, self.dur, self.gunluk = ad, kosu, surec, dur, gunluk
        self.anahtar = f"{ad}#{kosu}"
        self.maskele = maskele or maskeleyici()
        self.durum = "başlıyor"
        self.sonuc: dict | None = None
        self.son_satirlar: deque[str] = deque(maxlen=20)  # bu koşunun son stderr satırları (maskeli)
        self._okundu = threading.Event()
        self._hata_okundu = threading.Event()
        threading.Thread(target=self._oku, name=f"studio-{ad}", daemon=True).start()
        threading.Thread(target=self._hata_oku, name=f"studio-{ad}-hata", daemon=True).start()

    def _oku(self) -> None:
        """Studio'nun --json olaylarını okur (lifecycle / result)."""
        try:
            for satir in self.surec.stdout:
                try:
                    olay = json.loads(satir)
                except ValueError:
                    # Lisans yokken Studio'nun konsol istemi JSON sonuçla aynı satırda gelebilir.
                    bas = satir.find('{"type":')
                    if bas < 0:
                        continue
                    try:
                        olay = json.loads(satir[bas:])
                    except ValueError:
                        continue
                if not isinstance(olay, dict):
                    continue
                if olay.get("type") == "lifecycle":
                    self.durum = olay.get("state") or self.durum
                elif olay.get("type") == "result":
                    self.sonuc = olay
        finally:
            self._okundu.set()

    def _hata_oku(self) -> None:
        """Studio'nun stderr'i: her satır maskelenir, sonra günlüğe eklenir."""
        try:
            for satir in self.surec.stderr:
                temiz = self.maskele(satir.rstrip("\r\n"))
                if temiz.strip():
                    self.son_satirlar.append(temiz.strip()[:200])
                try:
                    with _GUNLUK_KILIDI, self.gunluk.open("a", encoding="utf-8") as g:
                        g.write(temiz + "\n")
                except OSError:
                    pass  # günlük yazılamazsa satır yalnızca bellekte (maskeli) kalır
        finally:
            self._hata_okundu.set()

    def calisiyor(self) -> bool:
        return self.surec.poll() is None

    def sorun(self) -> str | None:
        """Süreç kendiliğinden bittiyse ve başarısızsa nedeni (lisans, eksik blok, çökme...), sürüyorsa None."""
        if self.calisiyor():
            return None
        self._okundu.wait(2)
        self._hata_okundu.wait(2)
        r = self.sonuc or {}
        if r.get("success"):
            return None
        kod = self.surec.returncode
        if kod is not None and kod >= 2 ** 31:  # Windows çıkış kodu işaretsiz yazılır: 4294967295 = -1
            kod -= 2 ** 32
        neden = r.get("error") or r.get("failure_type")
        if not neden:
            neden = f"süreç sonuç bildirmeden kapandı, çıkış kodu {kod}"
            if self.son_satirlar:
                neden += f"; son satır: {self.son_satirlar[-1]}"
        neden = yollar.gizle(self.maskele(neden))
        if "EOF when reading a line" in neden:
            # Lisansı olmayan Studio arayüzsüz başlarken konsoldan lisans kodu ister; panel girdi vermediği için böyle biter.
            return ("AugeLab Studio bu bilgisayarda etkinleştirilmemiş: lisans kodu girilmemiş. "
                    "Başlangıç sayfasındaki AugeLab Studio sihirbazını açıp AugeLab hesabınızdaki lisans kodunu girin.")
        return (f"AugeLab Studio sahneyi çalıştıramadı ({neden}). Studio lisansınızı başlangıç sayfasındaki sihirbazdan "
                f"kontrol edin; ayrıntı: {yollar.gizle(str(self.gunluk))}")

    def bitir(self, bekle_sn: float = 3.0) -> None:
        """Önce akışı bitirir (bu koşunun durdurma dosyası), sonra süreç ağacını kapatır: sürekli kipte Studio kendiliğinden
        bitmez."""
        try:
            self.dur.touch()
        except OSError:
            pass
        son = time.monotonic() + bekle_sn
        while self.calisiyor() and time.monotonic() < son:
            time.sleep(0.2)
        if self.calisiyor():
            subprocess.run(["taskkill", "/PID", str(self.surec.pid), "/T", "/F"], capture_output=True, creationflags=PENCERESIZ)
            try:
                self.surec.wait(10)
            except subprocess.TimeoutExpired:
                self.surec.kill()
        try:
            self.dur.unlink(missing_ok=True)
        except OSError:
            pass


KOSULAR: dict[str, Kosu] = {}  # anahtar: "tür#koşu" (her koşunun kendi durdurma dosyası var)
_KILIT = threading.Lock()


def baslat(ad: str, kosu: str, ortam_ek: dict | None = None, adres: str = "", canli: bool = False, adim: int | None = None) -> Kosu:
    """Sahneyi arayüzsüz başlatır. `ortam_ek`: motorun ortam değişkenleri (KAFE_...). `adres`: canlı akış adresi (şifre
    içerebilir): yalnızca sürecin ortamına konur; komut satırına ve dosyaya yazılmaz, Studio'nun çıktısında geçerse
    maskelenir. `canli`: süreç çökerse Studio onu yeniden başlatır. `adim`: --step (deneme ve tek kare işleri kendiliğinden
    biter). Her koşunun durdurma dosyası kendinedir; aynı türden başka bir koşuya dokunulmaz."""
    py = studio_python()
    sahne = sablon()
    bloklari_kur()
    KOSU_KLASORU.mkdir(parents=True, exist_ok=True)
    dur = KOSU_KLASORU / f"{ad}-{kosu}.dur"
    dur.unlink(missing_ok=True)
    gunluk = KOSU_KLASORU / f"{ad}.log"
    ortam = {k: v for k, v in os.environ.items() if not k.startswith((ORTAM_ONEKI, "PYTHON", "_MEI", "TCL_", "TK_"))}
    import ekran_karti

    ortam.update({k: str(v) for k, v in ekran_karti.ortam().items()})  # cihaz seçimi (otomatik / işlemci / ekran kartı)
    ortam.update({k: str(v) for k, v in (ortam_ek or {}).items()})
    ortam.update(KAFE_IS=f"{ad}#{kosu}", KAFE_DUR=str(dur), PYTHONIOENCODING="utf-8")
    if adres:
        ortam["KAFE_KAMERA_ADRES"] = adres
    komut = [str(py), "-m", "studio", "run", str(sahne), "--json", "--verbosity", "30"]
    if canli:
        komut += ["--on-fail", "restart", "--max-restarts", "1000", "--restart-delay", "5"]
    if adim:
        komut += ["--step", str(int(adim))]
    import studio_kurulum

    with _KILIT:  # başlatma ve kayıt tek kilit bölümünde: durdur_hepsi() arada başlayan bir koşuyu kaçırmaz
        if f"{ad}#{kosu}" in KOSULAR:
            raise StudioHatasi("Aynı koşu iki kez başlatılamaz.")
        with studio_kurulum._temiz_dll_dizini():  # Studio, paketlenmiş Python'un DLL dizinini devralmasın
            surec = subprocess.Popen(komut, cwd=str(KOSU_KLASORU), env=ortam, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", creationflags=PENCERESIZ)
        yollar.cocuk_bagla(surec)  # program kapanırsa (pencere kapatılsa bile) Studio süreci de kapansın
        k = Kosu(ad, kosu, surec, dur, gunluk, maskeleyici(adres))
        KOSULAR[k.anahtar] = k
    return k


def durdur_hepsi() -> None:
    """Program kapanırken: süren bütün koşuları bitirir."""
    with _KILIT:
        kosular = list(KOSULAR.values())
        KOSULAR.clear()
    for k in kosular:
        k.bitir()


class _TekSeferlik:
    """Tek karelik işin görüntüsünü diske yazmadan Studio'ya verir: yalnızca 127.0.0.1'de, rastgele bir adreste ve bir kez
    yanıt veren küçük bir HTTP sunucusu. Her bağlantı ayrı bir iş parçacığında ve kısa bir zaman aşımıyla işlenir: yarım
    kalan ya da hiç veri göndermeyen bir istemci sunucuyu ve kapanışını bekletemez. kapat() hiçbir istemciyi beklemez."""

    ZAMAN_ASIMI = 3.0  # saniye: bir istemcinin isteğini göndermesi ve yanıtı alması için

    def __init__(self, veri: bytes):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        self.anahtar = secrets.token_urlsafe(24)
        self.verildi = threading.Event()
        dis = self

        class Istek(BaseHTTPRequestHandler):
            timeout = self.ZAMAN_ASIMI  # soket zaman aşımı: yarım istek bu sürede düşer

            def log_message(self, *a):
                pass

            def do_GET(self):
                with dis._kilit:
                    uygun = self.path == "/" + dis.anahtar and not dis.verildi.is_set()
                    if uygun:
                        dis.verildi.set()
                        govde, dis._veri = dis._veri, b""
                if not uygun:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(govde)))
                self.end_headers()
                self.wfile.write(govde)

        class Sunucu(ThreadingHTTPServer):
            daemon_threads = True
            block_on_close = False  # server_close() açık bağlantıları beklemez

        self._kilit = threading.Lock()
        self._veri = veri
        self.sunucu = Sunucu(("127.0.0.1", 0), Istek)
        self.sunucu.socket.settimeout(self.ZAMAN_ASIMI)
        self.adres = f"http://127.0.0.1:{self.sunucu.server_address[1]}/{self.anahtar}"
        self._is = threading.Thread(target=self.sunucu.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True, name="tek-kare")
        self._is.start()

    def kapat(self, en_cok_sn: float = 2.0) -> None:
        """Sunucuyu kapatır; hiçbir istemciyi beklemez ve en çok `en_cok_sn` sürer."""
        with self._kilit:
            self._veri = b""
            self.verildi.set()
        durdur = threading.Thread(target=self.sunucu.shutdown, daemon=True, name="tek-kare-kapat")
        durdur.start()
        durdur.join(en_cok_sn)
        try:
            self.sunucu.server_close()
        except OSError:
            pass


BOZUK_SONUC_SN = 5.0  # sonuç dosyası bu kadar süre okunamazsa iş hatayla biter


def is_calistir(tur: str, ortam_ek: dict | None = None, *, adres: str = "", adim: int | None = None,
                dur: threading.Event | None = None, ilerleme=None, sinir_sn: float | None = None, sure_sn: float | None = None,
                girdi: bytes | None = None) -> dict:
    """Bir motor işini (kafe_motor.blok: deneme | video | kare | kayit) arayüzsüz çalıştırır ve sonucunu döndürür.

    Sonuç dosyası gelince süreç kapatılır (sürekli kipte Studio kendiliğinden bitmez). `dur` işaretlenirse önce durdurma
    dosyası (motor elindekini yazar), sonra süreç kapatılır ve Durduruldu. `ilerleme(dict)`: video işinde motorun bıraktığı
    ilerleme. `sure_sn`: canlı kayıtta bu kadar sonra durdurma dosyası konur. `girdi`: tek karelik işin görüntüsü (PNG
    baytları); diske yazılmaz, motor onu bir kez 127.0.0.1'den alır. Studio reddederse, motor hata yazarsa ya da sonuç
    okunamazsa StudioHatasi (nedeniyle). Durdurma ve süre sınırı her durumda uygulanır."""
    kosu = secrets.token_hex(4)
    KOSU_KLASORU.mkdir(parents=True, exist_ok=True)
    cikti = KOSU_KLASORU / f"{tur}-{kosu}.json"
    ilerleme_yolu = KOSU_KLASORU / f"{tur}-{kosu}.ilerleme"
    ortam = dict(ortam_ek or {})
    ortam.update(KAFE_CIKTI=str(cikti), KAFE_ILERLEME=str(ilerleme_yolu))
    if adres:  # OpenCV / FFmpeg akış adresini çıktıya yazmasın (yazarsa da panel maskeler)
        ortam.update(OPENCV_LOG_LEVEL="SILENT", OPENCV_FFMPEG_LOGLEVEL="-8")
    tek = _TekSeferlik(girdi) if girdi is not None else None
    if tek is not None:
        ortam["KAFE_GIRDI_URL"] = tek.adres
    try:
        # İşler sonludur: Studio çökerse yeniden başlatılmaz (kayıt baştan başlayıp öncekinin üstüne yazardı); hata bildirilir.
        k = baslat(tur, kosu, ortam, adres=adres, canli=False, adim=adim)
    except BaseException:
        if tek is not None:
            tek.kapat()
        raise
    bas = time.monotonic()
    son_ilerleme = None
    sonuc = None
    durduruldu = False
    bas_dur = 0.0
    bozuk_bas = None
    try:
        while True:
            simdi = time.monotonic()
            if dur is not None and dur.is_set() and not durduruldu:
                durduruldu = True
                k.dur.touch()  # motor elindekini yazsın (kayıtta o ana kadarki video saklanır)
                bas_dur = simdi
            if durduruldu and simdi - bas_dur > 15:
                raise Durduruldu("Durduruldu.")
            if sinir_sn is not None and simdi - bas > sinir_sn:
                raise StudioHatasi("AugeLab Studio işi zamanında bitirmedi.")
            if sure_sn is not None and simdi - bas > sure_sn:
                k.dur.touch()
            if cikti.is_file():
                try:
                    sonuc = json.loads(cikti.read_text(encoding="utf-8"))
                    if not isinstance(sonuc, dict):
                        raise ValueError("sözlük değil")
                    break
                except (OSError, ValueError):
                    sonuc = None
                    bozuk_bas = bozuk_bas or simdi  # motor önce .tmp yazar; yine de kısa bir süre tanınır
                    if durduruldu:  # kullanıcı durdurdu: yarım ya da bozuk sonuç beklenmez
                        raise Durduruldu("Durduruldu.") from None
                    if simdi - bozuk_bas > BOZUK_SONUC_SN:
                        raise StudioHatasi("AugeLab Studio'daki motor okunamayan bir sonuç bıraktı; iş yarıda kaldı.") from None
            elif not k.calisiyor():
                time.sleep(0.3)
                if cikti.is_file():
                    continue
                raise StudioHatasi(k.sorun() or "AugeLab Studio işi sonuç bırakmadan bitirdi (Kafe blokları çalışmadı). "
                                   f"Ayrıntı: {yollar.gizle(str(k.gunluk))}")
            if ilerleme is not None and ilerleme_yolu.is_file():
                try:
                    d = json.loads(ilerleme_yolu.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    d = None
                if d is not None and d != son_ilerleme:
                    son_ilerleme = d
                    ilerleme(d)
            time.sleep(0.25)
    finally:
        # --step işleri (deneme, tek kare) sonucu ilk adımda yazar, Studio birkaç saniye sonra kendiliğinden çıkar: beklenir.
        # Sürekli kipteki işler (video, kayıt) kendiliğinden bitmez: sonuç gelince hemen kapatılır.
        if adim and sonuc is not None:
            try:
                k.surec.wait(15)
            except subprocess.TimeoutExpired:
                pass
        try:
            k.bitir(0 if sonuc is not None else 3.0)  # önce Studio süreci: kare sunucusu ne olursa olsun
        finally:
            if tek is not None:
                tek.kapat()  # sınırlı süre; istemci beklemez
        with _KILIT:
            if KOSULAR.get(k.anahtar) is k:
                KOSULAR.pop(k.anahtar)
        for p in (cikti, ilerleme_yolu, cikti.with_name(cikti.name + ".tmp"), ilerleme_yolu.with_name(ilerleme_yolu.name + ".tmp")):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
    if sonuc.get("durduruldu") and "hata" in sonuc:  # kayıt dışındaki işler durdurulunca yarım sonuç vermez
        raise Durduruldu("Durduruldu.")
    if "hata" in sonuc:
        raise StudioHatasi(f"AugeLab Studio'daki analiz çalışmadı: {yollar.gizle(k.maskele(sonuc['hata']))[:300]}")
    return sonuc


# ---------------------------------------------------------------- durum ve deneme


KONTROL_SURUMU = 2  # kontrolün sürümü: değişirse eski "hazır" kaydı geçersiz sayılır


def _kayitli() -> dict:
    try:
        return json.loads(DURUM_DOSYASI.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def kaydet(**degerler) -> None:
    d = _kayitli()
    d.update(degerler)
    DURUM_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
    DURUM_DOSYASI.write_text(json.dumps(d), encoding="utf-8")


def dene(sinir_sn: float = 300.0) -> dict:
    """Studio'nun arayüzsüz çalışabildiğini kısa bir koşuyla dener: Studio kurulu ve lisanslı, Kafe bloklarını yüklüyor,
    motor modeli açıp siyah bir kareyi işliyor. Sonuç saklanır; "Studio hazır" bu denemenin geçtiği demektir."""
    bas = time.monotonic()
    try:
        sonuc = is_calistir("deneme", adim=3, sinir_sn=sinir_sn)
    except StudioHatasi as e:
        kaydet(hazir=False, denendi=time.time(), hata=str(e)[:300], kontrol=KONTROL_SURUMU)
        raise
    kaydet(hazir=True, denendi=time.time(), surum=surum(), hata=None, kontrol=KONTROL_SURUMU, surumler=sonuc.get("surumler"))
    return {"hazir": True, "sure_sn": round(time.monotonic() - bas, 1)}


def durum() -> dict:
    """Panelin gösterdiği Studio durumu. Studio çalıştırılmaz ve ona bağlanılmaz: kurulu mu, deneme geçti mi."""
    if kurulu_klasor() is None:
        raise StudioYok("AugeLab Studio kurulu değil.")
    studio_python()
    k = _kayitli()
    hazir = k.get("hazir") if k.get("kontrol") == KONTROL_SURUMU else None
    return {"surum": surum(), "arayuzsuz": True, "hazir": hazir, "denendi": k.get("denendi"), "hata": k.get("hata"),
            "lisans_kaydedildi": bool(k.get("lisans") or LISANS_ISARETI.is_file()),
            "sablon": SABLON_KAYNAK.is_file(),
            "motor_calisiyor": any(x.calisiyor() for x in list(KOSULAR.values()))}


# ---------------------------------------------------------------- geliştirme komutları


def _komut(arg: list[str]) -> None:
    yollar.hazirla()
    if not arg or arg[0] == "durum":
        print(durum())
    elif arg[0] == "dene":
        print(dene())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    _komut(sys.argv[1:])
