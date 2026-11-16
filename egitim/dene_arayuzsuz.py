"""Arayüzsüz Studio koşusunu (studio.py) gerçek Studio olmadan, sahte bir `python -m studio` ile sınar.

  .venv\\Scripts\\python egitim/dene_arayuzsuz.py

Sahte Studio, gerçeğinin --json çıktısını taklit eder (lifecycle satırları; --step verilirse sonuç satırıyla çıkış, verilmezse
kendiliğinden bitmez) ve motorun yapacağını yapar: KAFE_CIKTI'ya sonuç yazar. Denenenler: blok dosyalarının yazılması,
deneme koşusu ("Studio hazır"), video işinin sonucu ve ilerlemesi, durdurma, Studio'nun reddettiği koşunun nedeni, canlı
kaydın adresinin yalnızca ortamda kalması (komut satırında, dosyada ve günlükte yok), tek karelik işin yüzleri gizlemesi ve
başarısız tek karelik işin hiçbir kare bırakmaması, panelin torch / ultralytics yüklememesi.
"""
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

GECICI = Path(tempfile.mkdtemp(prefix="kafe-arayuzsuz-"))
os.environ["KAFE_KAMERA_VERI"] = str(GECICI / "veri")
for ad in [k for k in os.environ if k.startswith("SAHTE")]:
    del os.environ[ad]
kok = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(kok))
import studio  # noqa: E402
import studio_blok  # noqa: E402
import yollar  # noqa: E402

SAHTE = r'''
import json, os, sys, time
arg = sys.argv[1:]
def yaz(**o):
    print(json.dumps(o), flush=True)
def sonuc(veri):
    yol = os.environ["KAFE_CIKTI"]
    with open(yol + ".tmp", "w", encoding="utf-8") as f:
        json.dump(veri, f)
    os.replace(yol + ".tmp", yol)
def durdu():
    return os.path.exists(os.environ["KAFE_DUR"])
with open(os.path.join(os.getcwd(), "sahte-ortam.json"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"arg": arg, "is": os.environ.get("KAFE_IS"), "adres": os.environ.get("KAFE_KAMERA_ADRES"),
                        "girdi": os.environ.get("KAFE_GIRDI"), "girdi_url": os.environ.get("KAFE_GIRDI_URL"),
                        "dur": os.environ.get("KAFE_DUR")}) + "\n")
sahte = os.environ.get("SAHTE", "")
yaz(type="lifecycle", state="starting")
if sahte == "lisanssiz":  # gerçek Studio lisans yokken konsoldan kod ister; stdin kapalı olduğu için böyle biter
    print("Verification code: ", end="", flush=True)
    yaz(type="result", success=False, exit_code=2, error="EOF when reading a line")
    sys.exit(2)
if sahte == "reddet":
    yaz(type="result", success=False, exit_code=2, failure_type="license", error="License is not active")
    sys.exit(2)
yaz(type="lifecycle", state="started")
tur = os.environ["KAFE_IS"].split("#")[0]
adres = os.environ.get("KAFE_KAMERA_ADRES")
if adres:  # Studio / FFmpeg adresi stderr'e yazarsa panel günlüğe yazmadan önce maskeler
    from urllib.parse import unquote, urlsplit
    sys.stderr.write("ffmpeg: aciliyor " + adres + "\n")
    sys.stderr.write("yetki reddedildi: kullanici=" + unquote(urlsplit(adres).username) + " sifre=" + unquote(urlsplit(adres).password) + "\n")
    sys.stderr.flush()
    if sahte == "sizdir":  # sonuç bırakmadan çöker: son stderr satırı hata metnine girer
        sys.exit(3)
if sahte == "bozuk":  # okunamayan sonuç; süreç sürer (sürekli kip)
    with open(os.environ["KAFE_CIKTI"], "w", encoding="utf-8") as f:
        f.write("{bozuk")
    while True:
        time.sleep(0.2)
if sahte == "bozuk_olu":  # okunamayan sonuç bırakıp çıkar
    with open(os.environ["KAFE_CIKTI"], "w", encoding="utf-8") as f:
        f.write("[1, 2")
    sys.exit(0)
if tur == "deneme":
    sonuc({"hata": "ModuleNotFoundError: ultralytics"} if sahte == "model" else {"ok": True, "surumler": {"torch": "sahte"}})
elif tur == "kare":
    import urllib.request
    url = os.environ.get("KAFE_GIRDI_URL", "")
    acici = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    veri = acici.open(url, timeout=10).read() if url else b""
    try:
        acici.open(url, timeout=10).read()
        ikinci = "verdi"
    except Exception:
        ikinci = "vermedi"
    try:
        acici.open(url.rsplit("/", 1)[0] + "/yanlis", timeout=10).read()
        yanlis = "verdi"
    except Exception:
        yanlis = "vermedi"
    with open(os.path.join(os.getcwd(), "sahte-kare.json"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"bayt": len(veri), "png": veri[:4] == b"\x89PNG", "ikinci": ikinci, "yanlis": yanlis}) + "\n")
    if sahte == "bos":
        sonuc({"W": 64, "H": 48, "kisiler": []})
    elif sahte == "kare_hata":
        sonuc({"hata": "model açılamadı"})
    elif sahte != "kare_cokme":
        k = [[40.0, 20.0, 0.9]] * 5 + [[30.0, 40.0, 0.9], [50.0, 40.0, 0.9]] + [[40.0, 60.0, 0.9]] * 10
        sonuc({"W": 64, "H": 48, "kisiler": [{"b": [25.0, 10.0, 55.0, 47.0], "k": k}]})
elif tur == "video":
    if sahte == "video_bekle":
        while not durdu():
            time.sleep(0.1)
        sonuc({"hata": "durduruldu", "durduruldu": True})
    else:
        ilerleme = os.environ["KAFE_ILERLEME"]
        with open(ilerleme, "w", encoding="utf-8") as f:
            json.dump({"i": 4, "toplam": 10}, f)
        time.sleep(0.6)
        kareler = [{"i": i, "t": round(i / 10, 3), "d": [{"id": 1, "b": [10.0, 5.0, 30.0, 45.0], "k": [[20.0, 10.0, 0.9]] * 17, "o": 0.0}]}
                   for i in range(0, 10, 2)]
        sonuc({"fps": 10.0, "W": 64, "H": 48, "n": 10, "adim": 2, "kareler": kareler})
elif tur == "kayit":
    bas = time.monotonic()
    while not durdu() and time.monotonic() - bas < float(os.environ["KAFE_SURE_SN"]):
        time.sleep(0.1)
    with open(os.environ["KAFE_KAYIT"], "wb") as f:
        f.write(b"\0" * 20000)
    sonuc({"kare": 30, "fps": 15.0, "sure_sn": 2.0, "W": 64, "H": 48, "durduruldu": durdu()})
if "--step" in arg:
    time.sleep(0.2)
    yaz(type="result", success=True, exit_code=0, duration_ms=200)
    sys.exit(0)
while True:  # gerçek Studio gibi sürekli kipte kendiliğinden bitmez
    time.sleep(0.2)
'''

sonuclar = []


def denetle(ad, kosul):
    sonuclar.append((ad, bool(kosul)))
    print(("  geçti  " if kosul else "  KALDI  ") + ad, flush=True)


def sahte(deger: str | None):
    if deger:
        os.environ["SAHTE"] = deger
    else:
        os.environ.pop("SAHTE", None)


yollar.hazirla()
studio.SABLON_KAYNAK = GECICI / "kafe-kamera.pmod"
studio.SABLON_KAYNAK.write_bytes(b"sahte sahne")
studio.marketplace = lambda: GECICI / "marketplace"
studio.studio_python = lambda: Path(sys.executable)
paket = studio.KOSU_KLASORU / "studio"
paket.mkdir(parents=True)
(paket / "__init__.py").write_text("", encoding="utf-8")
(paket / "__main__.py").write_text(SAHTE, encoding="utf-8")


def ortamlar():
    yol = studio.KOSU_KLASORU / "sahte-ortam.json"
    return [json.loads(s) for s in yol.read_text(encoding="utf-8").splitlines()] if yol.exists() else []


try:
    print("Blok dosyaları ve motor")
    motor = studio.bloklari_kur()
    bloklar = GECICI / "marketplace" / "custom_blocks"
    denetle("iki blok dosyası yazıldı", sorted(p.name for p in bloklar.glob("*.py")) == sorted(t["opCode"] + ".py" for t in studio_blok.TANIMLAR))
    ham = (bloklar / "KafeKaynak.py").read_bytes()
    denetle("Studio'nun ürettiği gibi CRLF satır sonu", b"\r\n" in ham and b"\n" not in ham.replace(b"\r\n", b""))
    denetle("motor yanına yerleşti (kafe_motor, model, deps, ayar.json)",
            (motor / "kafe_motor" / "blok.py").exists() and (motor / "modeller" / "yolo11s-pose.pt").exists()
            and (motor / "ayar.json").exists() and ((motor / "deps").is_dir() or not (studio.MOTOR_KAYNAK / "deps").is_dir()))
    damgalar = {p: p.stat().st_mtime_ns for p in list(bloklar.glob("*.py")) + [motor / "surum.txt"]}
    time.sleep(0.05)
    studio.bloklari_kur()
    denetle("değişmeyen blok ve motor dosyalarına dokunulmaz", damgalar == {p: p.stat().st_mtime_ns for p in damgalar})
    for t in studio_blok.TANIMLAR:
        compile(studio_blok.dosya_metni(t), t["opCode"], "exec")
    denetle("üretilen blok dosyaları derlenebilir", True)

    print("Panel modeli yüklemez")
    import analiz  # noqa: E402
    import kamera  # noqa: E402
    import rapor  # noqa: E402,F401
    import renkler  # noqa: E402
    import uygulama  # noqa: E402,F401

    denetle("panelin modülleri torch / ultralytics yüklemez", not any(m in sys.modules for m in ("torch", "ultralytics", "kafe_motor")))

    print("Deneme koşusu (Studio hazır)")
    d = studio.dene(30)
    kayit = json.loads(studio.DURUM_DOSYASI.read_text())
    denetle("deneme geçti, hazır kaydedildi", d["hazir"] and kayit["hazir"] is True)
    denetle("deneme --step ile sınırlı ve iş ortamdan verilir", "--step" in ortamlar()[-1]["arg"] and ortamlar()[-1]["is"].startswith("deneme#"))
    denetle("durum: hazır (Studio'ya bağlanmadan)", studio.durum()["hazir"] is True) if studio.kurulu_klasor() else None
    sahte("model")
    try:
        studio.dene(30)
        denetle("motor modeli açamazsa deneme geçmez", False)
    except studio.StudioHatasi as e:
        denetle("motor modeli açamazsa deneme geçmez, neden yazılır", "ultralytics" in str(e))
    denetle("başarısız deneme hazır=False kaydeder", json.loads(studio.DURUM_DOSYASI.read_text())["hazir"] is False)
    sahte("lisanssiz")
    try:
        studio.dene(30)
        denetle("lisanssız Studio anlaşılır Türkçe nedenle reddedilir", False)
    except studio.StudioHatasi as e:
        denetle("lisanssız Studio anlaşılır Türkçe nedenle reddedilir", "lisans kodu girilmemiş" in str(e))
    sahte(None)
    studio.dene(30)
    denetle("sonra deneme yeniden geçer", json.loads(studio.DURUM_DOSYASI.read_text())["hazir"] is True)

    print("Video işi")
    import cv2  # noqa: E402
    import numpy as np  # noqa: E402

    video = yollar.VIDEOLAR / "dnm.mp4"
    yazici = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    for i in range(10):
        yazici.write(np.full((48, 64, 3), 20 * i, np.uint8))
    yazici.release()
    satirlar = []
    import builtins  # noqa: E402

    asil_print = builtins.print
    builtins.print = lambda *a, **k: (satirlar.append(" ".join(map(str, a))), asil_print(*a, **k))
    try:
        veri = analiz.algila(video, yollar.ONBELLEK / "dnm.json", 2, 960, "", renkler.coz(None))
    finally:
        builtins.print = asil_print
    denetle("video işinin sonucu 0.1.0 sözlüğü", set(veri) >= {"fps", "W", "H", "n", "adim", "kareler"} and len(veri["kareler"]) == 5)
    denetle("ilerleme 0.1.0 metniyle yazılır", any("algılama: 4 / 10 kare (%40)" in s for s in satirlar))
    denetle("algılama önbelleğe yazıldı", (yollar.ONBELLEK / "dnm.json").is_file())
    o = ortamlar()[-1]
    denetle("video yolu ve ayarlar ortamdan verilir, sürekli kip", o["girdi"] == str(video.resolve()) and "--step" not in o["arg"])
    denetle("sonuç gelince süreç kapatıldı", not any(k.calisiyor() for k in studio.KOSULAR.values()) and not studio.KOSULAR)
    denetle("iş dosyaları temizlendi", not list(studio.KOSU_KLASORU.glob("video-*")))

    print("Durdurma")
    sahte("video_bekle")
    dur = threading.Event()
    threading.Timer(1.5, dur.set).start()
    try:
        analiz.algila(video, yollar.ONBELLEK / "dnm2.json", 2, 960, "", renkler.coz(None), dur=dur)
        denetle("durdurulan video işi Durduruldu ile biter", False)
    except SystemExit as e:
        denetle("durdurulan video işi Durduruldu ile biter", str(e.code) == "Durduruldu.")
    denetle("durdurulan işin süreci kapandı, önbellek yazılmadı",
            not any(k.calisiyor() for k in studio.KOSULAR.values()) and not (yollar.ONBELLEK / "dnm2.json").exists())
    sahte(None)

    print("Studio reddederse")
    sahte("reddet")
    try:
        analiz.algila(video, yollar.ONBELLEK / "dnm3.json", 2, 960, "", renkler.coz(None))
        denetle("reddedilen işin nedeni iş kaydına gider", False)
    except SystemExit as e:
        denetle("reddedilen işin nedeni iş kaydına gider", "License is not active" in str(e.code))
    sahte(None)

    print("Tek kare (yüz gizleme)")
    ayar = {"kod": "dnm", "ad": "Deneme", "kamera": {"tur": "dosya", "yol": str(video)}}
    kare_yolu = yollar.AYAR / "_kare_dnm.jpg"
    for hata in ("kare_hata", "kare_cokme", "reddet"):
        sahte(hata)
        try:
            kamera.test(ayar, yollar.AYAR / "dnm.json")
            basarisiz = False
        except SystemExit:
            basarisiz = True
        denetle(f"başarısız tek kare işi ({hata}) kare bırakmaz", basarisiz and not kare_yolu.exists()
                and not list((GECICI / "veri").rglob("*.png")) and not list(yollar.AYAR.glob("_kare_*")))
    sahte(None)
    kod = kamera.test(ayar, yollar.AYAR / "dnm.json")
    kare = cv2.imread(str(kare_yolu))
    o = ortamlar()[-1]
    kayitlar = [json.loads(s) for s in (studio.KOSU_KLASORU / "sahte-kare.json").read_text(encoding="utf-8").splitlines()]
    denetle("tek kare işi --step ile; kare diske yazılmaz, 127.0.0.1'deki tek seferlik adresten gider",
            "--step" in o["arg"] and o["girdi"] is None and str(o["girdi_url"]).startswith("http://127.0.0.1:")
            and kayitlar[-1]["png"] and kayitlar[-1]["bayt"] > 0)
    denetle("adres bir kez yanıt verir, yanlış anahtar yanıt almaz", kayitlar[-1]["ikinci"] == "vermedi" and kayitlar[-1]["yanlis"] == "vermedi")
    denetle("başarılı tek kare kaydedilir, veri klasöründe ham kare yok", kod == 0 and kare is not None
            and not list((GECICI / "veri").rglob("*.png")))
    sahte("bos")
    ham = np.zeros((48, 64, 3), np.uint8)
    ham[:, :, 1] = np.indices((48, 64)).sum(0) % 2 * 255
    bulanik, kisi = analiz.yuzleri_gizle_bilgili(ham)
    denetle("kimse bulunamazsa kare tamamen bulanıklaştırılır (her bölge değişir, ince ayrıntı kalmaz)",
            kisi == 0 and np.abs(bulanik[:, :, 1].astype(int) - ham[:, :, 1].astype(int)).mean() > 100
            and float(np.abs(np.diff(bulanik[:, :, 1].astype(int), axis=1)).mean()) < 10)
    cap = cv2.VideoCapture(str(kok / "ornekler" / "videolar" / "salon.mp4"))
    _, sahne = cap.read()
    cap.release()
    b2, _ = analiz.yuzleri_gizle_bilgili(sahne)
    kucuk = cv2.resize(sahne, (160, 90), interpolation=cv2.INTER_AREA)
    denetle("bulanık karede oda düzeni kabaca kalır (160x90 ölçekte benzer)",
            float(np.abs(cv2.resize(b2, (160, 90), interpolation=cv2.INTER_AREA).astype(int) - kucuk.astype(int)).mean()) < 25)
    satirlar2 = []
    asil_print = builtins.print
    builtins.print = lambda *a, **k: (satirlar2.append(" ".join(map(str, a))), asil_print(*a, **k))
    try:
        kamera.test(ayar, yollar.AYAR / "dnm.json")
    finally:
        builtins.print = asil_print
    denetle("kimse bulunamayınca iş kaydı bunu söyler", any("kimse bulunamadı" in s for s in satirlar2))
    sahte(None)
    ham = np.zeros((48, 64, 3), np.uint8)  # dnm.mp4'ün ilk karesi siyah: pikselleme bunu değiştirmez; düz renkli kareyle sınanır
    desen = np.indices((48, 64)).sum(0) % 2 * 255
    ham[:, :, 1] = desen
    gizli = analiz.yuzleri_gizle(ham)
    denetle("yüz gizleme baş bölgesini pikseller, gövdeye dokunmaz",
            not np.array_equal(gizli[12:28, 32:48], ham[12:28, 32:48]) and np.array_equal(gizli[40:, :20], ham[40:, :20]))

    print("Canlı kayıt (adres yalnızca ortamda)")
    gizli_adres = "rtsp://admin:GIZLI-sifre@10.0.0.9:554/akis"
    hedef = yollar.KAYIT_GECICI / "kapi_20260101_000000.mp4"
    hedef.parent.mkdir(parents=True, exist_ok=True)
    dur = threading.Event()
    threading.Timer(1.0, dur.set).start()
    yol = kamera._kaydet_studio(gizli_adres, hedef, 60, dur)
    o = ortamlar()[-1]
    denetle("adres sürecin ortamında, komut satırında değil", o["adres"] == gizli_adres and "GIZLI" not in " ".join(o["arg"]))
    denetle("kayıt işi sonlu: yeniden başlatma yok", "--on-fail" not in o["arg"])
    denetle("durdurulan kayıt o ana kadarki dosyayla biter", yol == hedef and hedef.stat().st_size >= 10_000)
    denetle("adres hiçbir dosyaya ve günlüğe yazılmadı", not any("GIZLI" in p.read_text(encoding="utf-8", errors="ignore")
                                                                 for p in (GECICI / "veri").rglob("*")
                                                                 if p.is_file() and p.name != "sahte-ortam.json" and p.suffix != ".mp4"))
    denetle("koşu listesi boşaldı", not studio.KOSULAR)

    print("Kimlik bilgisi günlüğe ve hata metnine maskesiz gitmez")
    gunluk = studio.KOSU_KLASORU / "kayit.log"
    icerik = gunluk.read_text(encoding="utf-8") if gunluk.exists() else ""
    denetle("Studio'nun stderr'indeki adres, kullanıcı ve şifre günlükte maskeli",
            "ffmpeg: aciliyor" in icerik and "GIZLI" not in icerik and "admin" not in icerik and "****" in icerik)
    sahte("sizdir")
    try:
        kamera._kaydet_studio(gizli_adres, yollar.KAYIT_GECICI / "kapi_2.mp4", 60, None)
        denetle("çöken kaydın hata metni maskeli", False)
    except SystemExit as e:
        denetle("çöken kaydın hata metni maskeli (son satır var, şifre yok)", "son satır" in str(e.code) and "GIZLI" not in str(e.code)
                and "admin" not in str(e.code))
    sahte(None)
    denetle("adres yine hiçbir dosyada yok", not any("GIZLI" in p.read_text(encoding="utf-8", errors="ignore")
                                                   for p in (GECICI / "veri").rglob("*")
                                                   if p.is_file() and p.name != "sahte-ortam.json" and p.suffix != ".mp4"))

    print("Okunamayan sonuç")
    for hal in ("bozuk", "bozuk_olu"):
        sahte(hal)
        bas = time.monotonic()
        try:
            studio.is_calistir("video", {"KAFE_GIRDI": str(video)})
            denetle(f"okunamayan sonuç ({hal}) iş hatasıyla biter", False)
        except studio.StudioHatasi as e:
            denetle(f"okunamayan sonuç ({hal}) açık hatayla, sınırlı sürede biter",
                    "okunamayan" in str(e) and time.monotonic() - bas < studio.BOZUK_SONUC_SN + 10)
    sahte("bozuk")
    dur = threading.Event()
    dur.set()
    try:
        studio.is_calistir("video", {"KAFE_GIRDI": str(video)}, dur=dur)
    except studio.Durduruldu:
        denetle("okunamayan sonuç beklenirken durdurma işler", True)
    except studio.StudioHatasi:
        denetle("okunamayan sonuç beklenirken durdurma işler", False)
    sahte(None)
    denetle("okunamayan sonuçtan sonra süreç kalmadı", not studio.KOSULAR)

    print("Her koşunun kendi durdurma dosyası")
    k1 = studio.baslat("kayit", "aaaa1111", {"KAFE_KAYIT": str(yollar.KAYIT_GECICI / "a.mp4"), "KAFE_SURE_SN": 60,
                                              "KAFE_CIKTI": str(studio.KOSU_KLASORU / "a.json")})
    k2 = studio.baslat("kayit", "bbbb2222", {"KAFE_KAYIT": str(yollar.KAYIT_GECICI / "b.mp4"), "KAFE_SURE_SN": 60,
                                              "KAFE_CIKTI": str(studio.KOSU_KLASORU / "b.json")})
    denetle("aynı türden iki koşu ayrı durdurma dosyası alır, ikisi de sürer", k1.dur != k2.dur and k1.calisiyor() and k2.calisiyor())
    k1.bitir()
    denetle("birini durdurmak ötekini durdurmaz", not k1.calisiyor() and k2.calisiyor() and not k2.dur.exists())
    studio.durdur_hepsi()
    denetle("durdur_hepsi kalanı da kapatır", not k2.calisiyor())

    print("Ham parçalar ve geçici dosyalar")
    yollar.KAYIT_GECICI.mkdir(parents=True, exist_ok=True)
    kalinti = yollar.KAYIT_GECICI / "eski_20260101_000000.mp4"
    kalinti.write_bytes(b"ham")
    uygulama.is_baslat("deneme", "Temizlik denemesi", lambda is_: {})
    for _ in range(50):
        if uygulama.AKTIF.durum != "calisiyor":
            break
        time.sleep(0.1)
    denetle("yeni iş başlarken önceki işten kalan ham parça silinir", not kalinti.exists())

    print("Kullanıcı durdurunca iş hata sayılmaz")

    def durdurulan(is_):
        is_.dur.set()
        raise SystemExit("Durduruldu.")

    uygulama.is_baslat("deneme", "Durdurma denemesi", durdurulan)
    for _ in range(50):
        if uygulama.AKTIF.durum != "calisiyor":
            break
        time.sleep(0.1)
    denetle("durdurulan işin durumu 'durduruldu'", uygulama.AKTIF.durum == "durduruldu")
finally:
    studio.durdur_hepsi()
    import shutil

    shutil.rmtree(GECICI, ignore_errors=True)

kalan = [ad for ad, ok in sonuclar if not ok]
print(f"\n{len(sonuclar) - len(kalan)}/{len(sonuclar)} denetim geçti" + (f" · kalanlar: {kalan}" if kalan else ""))
sys.exit(1 if kalan else 0)
