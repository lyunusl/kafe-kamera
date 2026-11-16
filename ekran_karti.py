"""Ekran kartı (NVIDIA) desteği, panel tarafı: kuruluma özel seçim, NVIDIA dosyalarının indirilmesi, ekran kartı
modelinin (TensorRT engine) hazırlanması ve motor işlerinin ortamı.

Dağıtım: NVIDIA dosyaları Kafe Kamera'nın exe'sinde, kurulum dosyasında ve deposunda YOKTUR. Kullanıcı isterse
(Kurulum → Ekran kartı) bu bilgisayara resmi dizinden (pypi.nvidia.com ve PyPI) indirilir; SHA-256 özetleri sabitlenmiştir
(gpu_ortak.PAKETLER). Paketlerden yalnızca gerekli dosyalar veri klasöründe gpu/dosyalar/ altına açılır; indirilen paketler
silinir. Studio'nun kendi paketlerine hiçbir şey kurulmaz: motor bu klasörü kendi sürecinde yoluna ekler.

Ayar (veri klasöründe ekran_karti.json): {"cihaz": "otomatik" | "islemci" | "ekran_karti", "hassasiyet": "fp16" | "fp32"}.
Dosyalar yoksa ya da ekran kartı kullanılamıyorsa her şey bugünkü gibi işlemcide çalışır.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

import gpu_ortak
import yollar

VARSAYILAN = {"cihaz": "otomatik", "hassasiyet": "fp16"}
HAZIRLAMA_SINIRI_SN = 1800.0
BOS_YER_PAYI = 600 * 2**20  # indirme + açma için paketlerin üstüne bırakılan boş yer


def ayar_dosyasi() -> Path:
    return yollar.VERI / "ekran_karti.json"


def ayar() -> dict:
    try:
        d = json.loads(ayar_dosyasi().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    out = dict(VARSAYILAN)
    if d.get("cihaz") in gpu_ortak.CIHAZLAR:
        out["cihaz"] = d["cihaz"]
    if d.get("hassasiyet") in gpu_ortak.HASSASIYETLER:
        out["hassasiyet"] = d["hassasiyet"]
    return out


def ayar_yaz(cihaz: str | None = None, hassasiyet: str | None = None) -> dict:
    a = ayar()
    if cihaz is not None:
        if cihaz not in gpu_ortak.CIHAZLAR:
            raise ValueError(f"cihaz: {', '.join(gpu_ortak.CIHAZLAR)}")
        a["cihaz"] = cihaz
    if hassasiyet is not None:
        if hassasiyet not in gpu_ortak.HASSASIYETLER:
            raise ValueError("hassasiyet: fp16 ya da fp32 (INT8 sunulmaz)")
        a["hassasiyet"] = hassasiyet
    ayar_dosyasi().parent.mkdir(parents=True, exist_ok=True)
    ayar_dosyasi().write_text(json.dumps(a), encoding="utf-8")
    beklenen_tazele()
    return a


def kok() -> Path:
    return yollar.VERI / "gpu"


def motorlar_klasoru() -> Path:
    return kok() / "motorlar"


_KART: dict = {"an": -1e9, "deger": None}


def kart(tazele: bool = False) -> dict | None:
    if tazele or time.monotonic() - _KART["an"] > 60:
        _KART.update(an=time.monotonic(), deger=gpu_ortak.kart_bilgisi())
    return _KART["deger"]


def dosyalar_klasoru(k: dict | None = None) -> Path | None:
    k = k if k is not None else kart()
    sm = gpu_ortak.sm_adi((k or {}).get("cc"))
    return kok() / "dosyalar" / f"{gpu_ortak.DOSYALAR_SURUM}-{sm}" if sm else None


def dosyalar_hazir(k: dict | None = None) -> tuple[bool, str | None]:
    """İndirilen klasör tam mı (bilgi dosyası ve listelenen dosyaların boyutları)."""
    d = dosyalar_klasoru(k)
    if d is None:
        return False, None
    try:
        bilgi = json.loads((d / gpu_ortak.BILGI_DOSYASI).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, "Ekran kartı dosyaları indirilmemiş."
    for goreli, boyut in (bilgi.get("dosyalar") or {}).items():
        p = d / goreli
        if not p.is_file() or p.stat().st_size != boyut:
            return False, "Ekran kartı dosyaları eksik ya da bozuk; yeniden indirin."
    return True, None


def motor_yolu(hw: tuple[int, int], hassasiyet: str, k: dict | None = None) -> Path | None:
    k = k if k is not None else kart()
    if not k:
        return None
    return motorlar_klasoru() / gpu_ortak.motor_adi(k, gpu_ortak.TRT_SURUM, hw, hassasiyet)


# ---------------------------------------------------------------- hangi giriş boyutları gerekli


def _istenen_dosyasi() -> Path:
    return kok() / "istenen.json"


def eksik_bildir(sekiller: list[str]) -> bool:
    """Motorların nabızda bildirdiği eksik boyutlar ("736x960"): bir sonraki hazırlamaya eklenir. Yeni bir boyut
    eklendiyse True."""
    mevcut = set(_istenenler())
    yeni = [s for s in sekiller if _hw(s) and s not in mevcut]
    if not yeni:
        return False
    kok().mkdir(parents=True, exist_ok=True)
    _istenen_dosyasi().write_text(json.dumps(sorted(mevcut | set(yeni))), encoding="utf-8")
    return True


_BOZUK_SILINEN: set = set()


def bozuk_bildir(sekiller: list[str], hassasiyet: str | None = None) -> bool:
    """Motorun açamadığı (bozuk ya da başka kart/TensorRT için) motor dosyaları silinir; bir sonraki hazırlama yeniden
    üretir. Aynı dosya bu çalışmada bir kez silinir (sürekli silip üretme döngüsü olmasın). Silindiyse True."""
    hassasiyet = hassasiyet or ayar()["hassasiyet"]
    sildi = False
    for s in sekiller:
        hw = _hw(s)
        p = motor_yolu(hw, hassasiyet) if hw else None
        if p is not None and p.is_file() and str(p) not in _BOZUK_SILINEN:
            _BOZUK_SILINEN.add(str(p))
            try:
                p.unlink()
                Path(str(p) + ".json").unlink(missing_ok=True)
                sildi = True
            except OSError:
                pass
    if sildi:
        beklenen_tazele()
    return sildi


def _istenenler() -> list[str]:
    try:
        return [s for s in json.loads(_istenen_dosyasi().read_text(encoding="utf-8")) if _hw(s)]
    except (OSError, ValueError, TypeError):
        return []


def _hw(s) -> tuple[int, int] | None:
    try:
        h, w = (int(v) for v in str(s).lower().split("x"))
        return (h, w) if 32 <= h <= 4096 and 32 <= w <= 4096 else None
    except ValueError:
        return None


def gerekli_sekiller() -> list[tuple[int, int]]:
    """16:9 görüntü (kayıt cihazlarının çoğu) her kullanılan imgsz için, ve motorların bildirdiği başka boyutlar."""
    imgszler = {960}
    try:
        for p in yollar.AYAR.glob("*.json"):
            try:
                imgszler.add(int(json.loads(p.read_text(encoding="utf-8")).get("imgsz") or 960))
            except (OSError, ValueError, TypeError):
                pass
    except OSError:
        pass
    out = [gpu_ortak.letterbox_hw(720, 1280, i) for i in sorted(imgszler)]
    for s in _istenenler():
        hw = _hw(s)
        if hw and hw not in out:
            out.append(hw)
    return out


def eksik_motorlar(hassasiyet: str | None = None, k: dict | None = None) -> list[tuple[int, int]]:
    hassasiyet = hassasiyet or ayar()["hassasiyet"]
    k = k if k is not None else kart()
    return [hw for hw in gerekli_sekiller() if not (motor_yolu(hw, hassasiyet, k) or Path("-")).is_file()]


# ---------------------------------------------------------------- durum ve motor ortamı


_BEKLENEN: dict = {"an": -1e9, "deger": None}


def beklenen() -> dict:
    """Panelin beklediği cihaz (gerçek cihazı motor nabızda bildirir): {"cihaz", "hassasiyet", "neden"}. 2 sn önbellek."""
    if time.monotonic() - _BEKLENEN["an"] < 2.0 and _BEKLENEN["deger"] is not None:
        return dict(_BEKLENEN["deger"])
    d = _beklenen()
    _BEKLENEN.update(an=time.monotonic(), deger=d)
    return dict(d)


def beklenen_tazele() -> None:
    _BEKLENEN.update(an=-1e9, deger=None)


def _beklenen() -> dict:
    a = ayar()
    if a["cihaz"] == "islemci":
        return {"cihaz": "islemci", "hassasiyet": None, "neden": None}
    k = kart()
    uygun, neden = gpu_ortak.kart_uygun_mu(k)
    if uygun:
        hazir, neden = dosyalar_hazir(k)
        if hazir and eksik_motorlar(a["hassasiyet"], k):
            neden = "Ekran kartı modeli hazırlanıyor." if IS.get("tur") == "hazirla" and not IS.get("bitti") else \
                "Ekran kartı modeli henüz hazırlanmadı."
        elif hazir:
            return {"cihaz": "ekran_karti", "hassasiyet": a["hassasiyet"], "neden": None}
    if a["cihaz"] == "otomatik" and k is None:
        neden = None  # kartı olmayan bilgisayarda "otomatik" sessizce işlemcidir
    return {"cihaz": "islemci", "hassasiyet": None, "neden": neden}


def ortam() -> dict:
    """Her motor işinin ortamı (studio.baslat ekler)."""
    a = ayar()
    out = {"KAFE_CIHAZ": a["cihaz"], "KAFE_GPU_HASSASIYET": a["hassasiyet"], "KAFE_GPU_MOTORLAR": str(motorlar_klasoru())}
    if a["cihaz"] != "islemci":
        k = kart()
        hazir, _ = dosyalar_hazir(k)
        if hazir:
            out["KAFE_GPU_DEPS"] = str(dosyalar_klasoru(k))
    return out


IS: dict = {}          # süren ya da son indirme / hazırlama işi (API'de "is")
_IS_KILIDI = threading.Lock()


def durum() -> dict:
    a = ayar()
    k = kart()
    uygun, kart_neden = gpu_ortak.kart_uygun_mu(k)
    hazir, dosya_neden = dosyalar_hazir(k) if uygun else (False, None)
    sekiller = gerekli_sekiller()
    motorlar = []
    for hw in sekiller:
        for h in gpu_ortak.HASSASIYETLER:
            p = motor_yolu(hw, h, k) if uygun else None
            motorlar.append({"boyut": f"{hw[0]}x{hw[1]}", "hassasiyet": h, "hazir": bool(p and p.is_file())})
    b = beklenen()
    return {
        "ayar": a,
        "kart": ({"ad": k.get("ad"), "surucu": k.get("surucu"), "bellek_mb": k.get("bellek_mb"), "uygun": uygun,
                  "neden": kart_neden} if k else None),
        "dosyalar": {"hazir": hazir, "neden": dosya_neden, "tensorrt": gpu_ortak.TRT_SURUM,
                     "indirme_mb": round(gpu_ortak.indirme_boyutu() / 2**20),
                     "disk_mb": round(_klasor_boyutu(dosyalar_klasoru(k)) / 2**20) if hazir else None},
        "motorlar": motorlar,
        "beklenen": b,
        "is": dict(IS) if IS else None,
    }


def _klasor_boyutu(d: Path | None) -> int:
    if d is None or not d.is_dir():
        return 0
    return sum(p.stat().st_size for p in d.rglob("*") if p.is_file())


def _is_baslat(tur: str, hedef, *arg) -> tuple[bool, str]:
    with _IS_KILIDI:
        if IS and not IS.get("bitti"):
            return False, "Ekran kartı için başka bir iş sürüyor."
        IS.clear()
        IS.update(tur=tur, asama="basliyor", bitti=False, hata=None, bas=time.time())
    threading.Thread(target=_is_sar, args=(hedef, *arg), daemon=True, name=f"ekran-karti-{tur}").start()
    return True, "başladı"


def _is_sar(hedef, *arg) -> None:
    try:
        hedef(*arg)
    except Exception as e:  # noqa: BLE001  (ileti kullanıcıya gösterilir)
        IS.update(hata=str(e)[:400] or type(e).__name__)
    finally:
        IS.update(bitti=True, sure_sn=round(time.time() - IS.get("bas", time.time()), 1))
        beklenen_tazele()


# ---------------------------------------------------------------- indirme


class IndirmeHatasi(RuntimeError):
    pass


INDIRME_DUR = threading.Event()


def indir_baslat() -> tuple[bool, str]:
    k = kart(tazele=True)
    uygun, neden = gpu_ortak.kart_uygun_mu(k)
    if not uygun:
        return False, neden
    INDIRME_DUR.clear()
    return _is_baslat("indir", _indir, k)


def _indir(k: dict) -> None:
    hedef = dosyalar_klasoru(k)
    gecici = kok() / "indirilen"
    gecici.mkdir(parents=True, exist_ok=True)
    toplam = gpu_ortak.indirme_boyutu()
    bos = shutil.disk_usage(gecici).free
    if bos < toplam + BOS_YER_PAYI:
        raise IndirmeHatasi(f"Diskte yer yok: {round((toplam + BOS_YER_PAYI) / 2**30, 1)} GB boş yer gerekir.")
    IS.update(asama="indiriliyor", bayt=0, toplam=toplam)
    onceki = 0
    for paket in gpu_ortak.PAKETLER:
        yol = gecici / paket["dosya"]
        _indir_dosya(paket, yol, onceki)
        onceki += paket["boyut"]
    IS.update(asama="aciliyor", bayt=toplam)
    yeni = hedef.with_name(hedef.name + ".yeni")
    shutil.rmtree(yeni, ignore_errors=True)
    yeni.mkdir(parents=True)
    dosyalar = {}
    sm = gpu_ortak.sm_adi(k.get("cc"))
    for paket in gpu_ortak.PAKETLER:
        dosyalar.update(_ac(gecici / paket["dosya"], [d.replace("{sm}", sm) for d in paket["al"]], yeni))
    gerekli = ["tensorrt_libs/nvinfer_11.dll", "tensorrt_libs/nvinfer_plugin_11.dll", "tensorrt_libs/nvonnxparser_11.dll",
               f"tensorrt_libs/nvinfer_builder_resource_{sm}_11.dll", "tensorrt_libs/__init__.py",
               "tensorrt_bindings/__init__.py", "nvidia/cu13/bin/x86_64/cudart64_13.dll"]
    eksik = [g for g in gerekli if g not in dosyalar]
    if eksik:
        shutil.rmtree(yeni, ignore_errors=True)
        raise IndirmeHatasi(f"İndirilen paketlerde beklenen dosyalar yok: {', '.join(eksik)}")
    (yeni / gpu_ortak.BILGI_DOSYASI).write_text(json.dumps({
        "tensorrt": gpu_ortak.TRT_SURUM, "cudart": gpu_ortak.CUDART_SURUM, "sm": sm, "an": time.time(),
        "kaynak": [{"ad": p["ad"], "surum": p["surum"], "url": p["url"], "sha256": p["sha256"]} for p in gpu_ortak.PAKETLER],
        "dosyalar": dosyalar}, ensure_ascii=False, indent=1), encoding="utf-8")
    if hedef.exists():
        shutil.rmtree(hedef, ignore_errors=True)
    os.replace(yeni, hedef)
    shutil.rmtree(gecici, ignore_errors=True)  # indirilen paketler silinir; yalnızca açılan dosyalar kalır
    IS.update(asama="indirildi")
    if ayar()["cihaz"] != "islemci" and eksik_motorlar(k=k):
        _hazirla(k)


def _indir_dosya(paket: dict, yol: Path, onceki: int) -> None:
    """Kaldığı yerden sürdürülebilir indirme (Range), sonra SHA-256 doğrulaması. Uyuşmazsa dosya silinir."""
    parca = yol.with_name(yol.name + ".part")
    if yol.is_file() and yol.stat().st_size == paket["boyut"] and _sha256(yol) == paket["sha256"]:
        IS.update(bayt=onceki + paket["boyut"])
        return
    var = parca.stat().st_size if parca.is_file() else 0
    if var > paket["boyut"]:
        parca.unlink()
        var = 0
    istek = urllib.request.Request(paket["url"], headers={"User-Agent": "KafeKamera"})
    if var:
        istek.add_header("Range", f"bytes={var}-")
    acici = urllib.request.build_opener()
    with acici.open(istek, timeout=60) as yanit:
        if var and yanit.status != 206:  # sunucu sürdürmeyi desteklemedi: baştan
            var = 0
        with open(parca, "ab" if var else "wb") as f:
            while True:
                if INDIRME_DUR.is_set():
                    raise IndirmeHatasi("İndirme durduruldu (kaldığı yerden sürdürülebilir).")
                blok = yanit.read(1 << 20)
                if not blok:
                    break
                f.write(blok)
                var += len(blok)
                IS.update(bayt=onceki + var)
    if var != paket["boyut"]:
        raise IndirmeHatasi(f"{paket['ad']} eksik indi ({var} / {paket['boyut']} bayt); yeniden deneyin.")
    IS.update(asama="dogrulaniyor")
    if _sha256(parca) != paket["sha256"]:
        parca.unlink(missing_ok=True)
        raise IndirmeHatasi(f"{paket['ad']} doğrulanamadı (SHA-256 tutmuyor); dosya silindi.")
    os.replace(parca, yol)
    IS.update(asama="indiriliyor")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def _ac(whl: Path, desenler: list[str], hedef: Path) -> dict:
    """Paketten yalnızca istenen dosyaları açar ("klasör/" ile biten desen: o klasörün hepsi). Dönüş: {göreli yol: boyut}."""
    out = {}
    with zipfile.ZipFile(whl) as z:
        for bilgi in z.infolist():
            ad = bilgi.filename
            if bilgi.is_dir() or ".." in Path(ad).parts or ad.startswith("/"):
                continue
            if not any(ad == d or (d.endswith("/") and ad.startswith(d)) for d in desenler):
                continue
            p = hedef / ad
            p.parent.mkdir(parents=True, exist_ok=True)
            with z.open(bilgi) as kaynak, open(p, "wb") as f:
                shutil.copyfileobj(kaynak, f, 1 << 20)
            out[ad] = p.stat().st_size
    return out


# ---------------------------------------------------------------- ekran kartı modelini hazırlama


def hazirla_baslat() -> tuple[bool, str]:
    k = kart(tazele=True)
    uygun, neden = gpu_ortak.kart_uygun_mu(k)
    if not uygun:
        return False, neden
    hazir, neden = dosyalar_hazir(k)
    if not hazir:
        return False, neden or "Ekran kartı dosyaları indirilmemiş."
    return _is_baslat("hazirla", _hazirla, k)


def _hazirla(k: dict) -> None:
    """Eksik motorları gizli bir Studio işiyle üretir; bitince ekran kartını bekleyip işlemcide çalışan canlı kameraları
    yeniden başlatır."""
    import studio

    a = ayar()
    sekiller = eksik_motorlar(a["hassasiyet"], k)
    IS.update(tur="hazirla", asama="hazirlaniyor", hassasiyet=a["hassasiyet"],
              sekiller=[f"{h}x{w}" for h, w in sekiller], i=0, toplam_motor=len(sekiller),
              mesaj="Ekran kartı için model hazırlanıyor (bir iki dakika sürer).")
    if not sekiller:
        IS.update(asama="hazir", mesaj="Ekran kartı modeli hazır.")
        return

    def ilerleme(d):
        IS.update(i=d.get("i", 0), hw=d.get("hw"))
    try:
        sonuc = studio.is_calistir("gpu", {"KAFE_GPU_SEKILLER": ",".join(f"{h}x{w}" for h, w in sekiller)}, adim=3,
                                   ilerleme=ilerleme, sinir_sn=HAZIRLAMA_SINIRI_SN)
    except studio.StudioHatasi as e:
        raise RuntimeError(f"Ekran kartı modeli hazırlanamadı: {e}") from None
    IS.update(asama="hazir", sonuc={x: sonuc.get(x) for x in ("uretilen", "vardi", "sure_sn", "kart", "tensorrt")},
              mesaj="Ekran kartı modeli hazır.")
    try:
        import canli

        canli.ekran_karti_hazir()
    except Exception:  # noqa: BLE001
        pass


def acilista() -> None:
    """Program açılınca: ekran kartı kullanılacaksa ve dosyalar hazırsa eksik modelleri arka planda hazırlar."""
    try:
        if ayar()["cihaz"] == "islemci":
            return
        k = kart(tazele=True)
        if not gpu_ortak.kart_uygun_mu(k)[0] or not dosyalar_hazir(k)[0]:
            return
        if eksik_motorlar(k=k):
            _is_baslat("hazirla", _hazirla, k)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- arayüz sözleşmesi (GET /api/durum "ekran_karti")


def api_durum() -> dict:
    """{durum: yok | indirilmedi | indiriliyor | hazirlaniyor | hazir | hata, kart, indirme_boyutu, indirilen, toplam,
    mesaj, secim, kullanilan, hassasiyet}. Dosyalar hazır ama model eksikse ve iş yoksa hazırlama burada başlatılır."""
    a = ayar()
    k = kart()
    uygun, kart_neden = gpu_ortak.kart_uygun_mu(k)
    out = {"durum": "yok", "kart": (k or {}).get("ad"), "indirme_boyutu": gpu_ortak.indirme_boyutu(),
           "indirilen": 0, "toplam": gpu_ortak.indirme_boyutu(), "mesaj": "", "secim": a["cihaz"],
           "kullanilan": None, "hassasiyet": None}
    is_ = dict(IS)
    calisiyor = bool(is_) and not is_.get("bitti")
    if is_.get("tur") == "indir":
        out.update(indirilen=int(is_.get("bayt") or 0), toplam=int(is_.get("toplam") or out["toplam"]))
    b = beklenen()
    out.update(kullanilan=b["cihaz"], hassasiyet=b["hassasiyet"])
    if k is None:
        out["mesaj"] = "NVIDIA ekran kartı bulunamadı; analiz işlemcide yapılır."
        return out
    if not uygun:
        out.update(durum="hata", mesaj=kart_neden)
        return out
    if calisiyor and is_.get("tur") == "indir":
        asama = {"aciliyor": "Dosyalar açılıyor…", "dogrulaniyor": "İndirilen dosya doğrulanıyor…"}.get(is_.get("asama"))
        out.update(durum="indiriliyor", mesaj=asama or "NVIDIA dosyaları indiriliyor…")
        if is_.get("asama") == "hazirlaniyor":
            out.update(durum="hazirlaniyor", mesaj=is_.get("mesaj") or "Ekran kartı için model hazırlanıyor.")
        return out
    if calisiyor and is_.get("tur") == "hazirla":
        out.update(durum="hazirlaniyor", mesaj=is_.get("mesaj") or "Ekran kartı için model hazırlanıyor (bir iki dakika).")
        return out
    hazir, dosya_neden = dosyalar_hazir(k)
    if is_.get("hata") and is_.get("bitti"):
        out.update(durum="hata", mesaj=is_["hata"])
        if not hazir:
            return out
    if not hazir:
        out.update(durum="indirilmedi", mesaj=dosya_neden or (
            f"Ekran kartıyla analiz için NVIDIA dosyaları indirilmeli ({round(gpu_ortak.indirme_boyutu() / 2**30, 2)} GB; "
            "diskte yaklaşık 0,7 GB kalır)."))
        return out
    if a["cihaz"] != "islemci" and eksik_motorlar(a["hassasiyet"], k):
        if not is_.get("hata"):
            _is_baslat("hazirla", _hazirla, k)
            out.update(durum="hazirlaniyor", mesaj="Ekran kartı için model hazırlanıyor (bir iki dakika).")
        return out
    if out["durum"] != "hata":
        out.update(durum="hazir", mesaj="Ekran kartı hazır." if a["cihaz"] != "islemci" else
                   "Ekran kartı hazır; seçim işlemci olduğu için kullanılmıyor.")
    return out
