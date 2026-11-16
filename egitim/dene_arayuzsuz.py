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
elif tur == "canli":
    klasor = os.environ["KAFE_AKIS"]
    kosu = os.environ["KAFE_IS"].split("#")[1]
    with open(os.path.join(os.getcwd(), "sahte-canli.json"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"fps": os.environ.get("KAFE_ANALIZ_FPS"), "renk": os.environ.get("KAFE_RENKLER"),
                            "imgsz": os.environ.get("KAFE_IMGSZ"), "ip": os.environ.get("KAFE_IS_PARCACIGI"),
                            "omp": os.environ.get("OMP_NUM_THREADS"), "ip_dosya": os.environ.get("KAFE_IS_PARCACIGI_DOSYA"),
                            "kod": os.path.basename(klasor), "an": time.time()}) + "\n")
    os.makedirs(klasor, exist_ok=True)
    akis = open(os.path.join(klasor, f"akis-{kosu}-00001.jsonl"), "a", encoding="utf-8")
    k = [[640.0, 200.0, 0.9]] * 5 + [[600.0, 260.0, 0.9], [680.0, 260.0, 0.9]] + [[640.0, 330.0, 0.9]] * 10
    n = 0
    while True:
        an = time.time()
        if sahte != "canli_kop":
            n += 1
            akis.write(json.dumps({"z": an, "d": [{"id": 1, "b": [600.0, 180.0, 700.0, 420.0], "k": k, "o": 0.0},
                                                  {"id": 2, "b": [200.0, 180.0, 300.0, 420.0], "k": k, "o": 2.0}]}) + "\n")
            akis.flush()
        nabiz = {"an": an, "durum": "ok" if sahte != "canli_kop" else "bekliyor: Kameraya ya da kayıt cihazına ulaşılamıyor.",
                 "kare": n, "son_kare": an if sahte != "canli_kop" else an - 60, "W": 1280, "H": 720, "basladi": an - 100,
                 "hedef_fps": float(os.environ.get("KAFE_ANALIZ_FPS") or 3), "gercek_fps": 0.5 if sahte == "canli_yavas" else 3.0}
        with open(os.environ["KAFE_NABIZ"] + ".tmp", "w", encoding="utf-8") as f:
            json.dump(nabiz, f)
        os.replace(os.environ["KAFE_NABIZ"] + ".tmp", os.environ["KAFE_NABIZ"])
        with open(os.environ["KAFE_ONIZLEME"] + ".tmp", "wb") as f:
            f.write(b"\xff\xd8sahte-onizleme\xff\xd9")
        os.replace(os.environ["KAFE_ONIZLEME"] + ".tmp", os.environ["KAFE_ONIZLEME"])
        time.sleep(0.33)
elif tur == "kare" and sahte == "kare_bekle":  # kareyi hiç almaz, sonuç bırakmaz (askıda iş)
    while True:
        time.sleep(0.2)
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

    print("Kare sunucusu yarım istemcide takılmaz")
    import socket

    def askida_is(**kw):
        sonuc_ = {}

        def calis():
            bas_ = time.monotonic()
            try:
                studio.is_calistir("kare", {}, adim=3, girdi=b"x" * 1000, **kw)
                sonuc_["hata"] = None
            except Exception as e:  # noqa: BLE001
                sonuc_["hata"] = type(e).__name__
            sonuc_["sure"] = time.monotonic() - bas_
        onceki_ = len(ortamlar())
        th = threading.Thread(target=calis, daemon=True)
        th.start()
        url = None
        for _ in range(150):
            yeni_ = [r for r in ortamlar()[onceki_:] if r.get("girdi_url")]
            if yeni_:
                url = yeni_[-1]["girdi_url"]
                break
            time.sleep(0.1)
        port = int(url.split(":")[2].split("/")[0])
        bos_ = socket.create_connection(("127.0.0.1", port))  # bağlanır, hiçbir şey göndermez
        yarim = socket.create_connection(("127.0.0.1", port))
        yarim.sendall(b"GET /" + url.rsplit("/", 1)[1][:5].encode())  # yarım istek satırı
        return th, sonuc_, port, (bos_, yarim)

    sahte("kare_bekle")
    dur = threading.Event()
    th, sonuc_, port, soketler = askida_is(dur=dur)
    time.sleep(1.0)
    dur.set()
    th.join(40)
    denetle("yarım istemciler açıkken durdurulan tek kare işi sınırlı sürede biter",
            not th.is_alive() and sonuc_.get("hata") == "Durduruldu" and sonuc_["sure"] < 30)
    try:
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
        kapali = False
    except OSError:
        kapali = True
    denetle("iş bitince kare sunucusu kapalı", kapali)
    for s_ in soketler:
        s_.close()
    th, sonuc_, port, soketler = askida_is(sinir_sn=3)
    th.join(40)
    denetle("yarım istemciler açıkken süresi dolan tek kare işi sınırlı sürede hatayla biter",
            not th.is_alive() and sonuc_.get("hata") == "StudioHatasi" and sonuc_["sure"] < 20)
    for s_ in soketler:
        s_.close()
    dur = threading.Event()
    threading.Timer(2.0, dur.set).start()
    (yollar.AYAR / "_kare_dnm.jpg").unlink(missing_ok=True)
    try:
        kamera.test(ayar, yollar.AYAR / "dnm.json", dur=dur)
        iptal = "bitti"
    except SystemExit as e:
        iptal = str(e.code)
    denetle("bağlantı denemesi yarıda durdurulabilir, kare kaydedilmez", iptal == "Durduruldu." and not (yollar.AYAR / "_kare_dnm.jpg").exists())
    sahte(None)
    denetle("askıda işlerden sonra süreç kalmadı", not studio.KOSULAR)

    print("Kısa kullanıcı adı ve şifre de maskelenir")
    m = studio.maskeleyici("rtsp://a:bc@10.0.0.9:554/akis")
    denetle("1-2 karakterlik kimlik bilgisi ayrı sözcük, anahtar=değer ve adres içinde maskelenir",
            m("hata user=a pass=bc") == "hata user=**** pass=****" and m("kullanici: a sifre: bc") == "kullanici: **** sifre: ****"
            and m("giriş a bc reddedildi") == "giriş **** **** reddedildi" and "a:bc" not in m("rtsp://a:bc@10.0.0.9:554/akis"))
    denetle("kısa değerler sözcük içinde dokunulmaz (günlük parçalanmaz)", m("banana abc 12 kare") == "banana abc 12 kare")
    m2 = studio.maskeleyici("http://x%40:p%2F@10.0.0.9/v")
    denetle("yüzde kodlu ve çözülmüş biçim maskelenir", m2("u=x@ s=p/ ham x%40 p%2F") == "u=**** s=**** ham **** ****")

    print("Kapanışta ham parça: işi bekle, birkaç kez dene")
    yollar.KAYIT_GECICI.mkdir(parents=True, exist_ok=True)
    parca = yollar.KAYIT_GECICI / "acik_20260101_000000.mp4"
    tutuldu = threading.Event()

    def dosyayi_tutan_is(is_):  # kayıt gibi: parçayı kendisi yazar ve açık tutar
        with parca.open("wb") as f:
            f.write(b"ham")
            f.flush()
            tutuldu.set()
            while not is_.dur.is_set():
                time.sleep(0.1)
            time.sleep(2.0)  # durdurulduktan sonra da kısa süre dosyayı tutar (analiz bitiyor)
        return {}
    uygulama.is_baslat("izle", "Tutan iş", dosyayi_tutan_is)
    tutuldu.wait(5)
    try:
        parca.unlink()
        tutuluyor = False
    except OSError:
        tutuluyor = True
    kalan = uygulama.kapanis_temizligi(is_bekle_sn=10)
    denetle("kapanışta iş durdurulup beklenir, sonra (iş açıkken silinemeyen) ham parça silinir",
            tutuluyor and not kalan and not parca.exists() and uygulama.AKTIF.durum != "calisiyor")
    parca.write_bytes(b"ham")
    tutucu = parca.open("rb")
    satirlar3 = []
    asil_print = builtins.print
    builtins.print = lambda *a, **k: (satirlar3.append(" ".join(map(str, a))), asil_print(*a, **k))
    try:
        kalan = uygulama.kapanis_temizligi(is_bekle_sn=1)
    finally:
        builtins.print = asil_print
        tutucu.close()
    denetle("silinemeyen parça günlüğe yazılır ve açılıştaki temizliğe kalır",
            kalan == [parca] and any("silinemedi" in s for s in satirlar3) and not yollar.gecicileri_sil() and not parca.exists())

    print("Analiz hızı (saniyede kare)")
    sys.path.insert(0, str(kok / "motor"))
    sys.path.insert(0, str(kok))
    from kafe_motor import blok as motor_blok  # noqa: E402
    import canli  # noqa: E402

    for hedef_, beklenen in ((3, 30), (5, 50)):
        st = {"hedef": float(hedef_)}
        secilen = sum(motor_blok.kare_secilsin_mi(st, 1000.0 + j / 30.0) for j in range(300))  # 30 fps, 10 sn
        denetle(f"30 fps kaynaktan {hedef_} fps: 10 sn'de ~{beklenen} kare seçilir", abs(secilen - beklenen) <= 1)
    st = {"hedef": 3.0}
    secilen = sum(motor_blok.kare_secilsin_mi(st, 1000.0 + j / 2.0) for j in range(20))  # kaynak 2 fps (yavaş)
    denetle("kaynak hedeften yavaşsa her kare işlenir, kuyruk yok", secilen == 20)
    st = {}
    for j in range(31):
        st.setdefault("islem_anlari", []).append(1000.0 + j / 3)
    denetle("gerçek hız son 10 sn'den ölçülür", abs(motor_blok.gercek_fps(st, 1010.0) - 3.0) < 0.15)
    denetle("video dosyası adımı dosyanın fps'inden: 30/3=10, 24/5=5, 25/3=8, bilinmeyen fps=2",
            (analiz.video_adimi(30, 3), analiz.video_adimi(24, 5), analiz.video_adimi(25, 3), analiz.video_adimi(0, 3)) == (10, 5, 8, 2))
    denetle("analiz hızı: yoksa 3, değer okunur, sınırlanır",
            (canli.analiz_fps({}), canli.analiz_fps({"analiz_fps": 5}), canli.analiz_fps({"analiz_fps": "abc"}),
             canli.analiz_fps({"analiz_fps": 500})) == (3.0, 5.0, 3.0, 30.0))
    import tempfile as _tf

    sinir_dosya = Path(_tf.mkdtemp()) / "ip.json"
    sinir_dosya.write_text('{"n": 2}', encoding="utf-8")
    os.environ["KAFE_IS_PARCACIGI_DOSYA"] = str(sinir_dosya)
    st_ = {}
    motor_blok.is_parcacigi_uygula(st_)
    import torch  # noqa: E402

    ilk_ip = (st_.get("is_parcacigi"), torch.get_num_threads(), cv2.getNumThreads())
    sinir_dosya.write_text('{"n": 3}', encoding="utf-8")
    st_["ip_an"] = -1e9
    motor_blok.is_parcacigi_uygula(st_)
    denetle("motor sınırı torch ve OpenCV'ye uygular, sonradan değişince yeniden başlatmadan günceller",
            ilk_ip == (2, 2, 2) and (st_["is_parcacigi"], torch.get_num_threads(), cv2.getNumThreads()) == (3, 3, 3))
    del os.environ["KAFE_IS_PARCACIGI_DOSYA"]
    torch.set_num_threads(os.cpu_count() or 4)
    yol_ = motor_blok.izci_dosyasi(3.0)
    izci = Path(yol_).read_text(encoding="ascii")
    denetle("canlı izci ayarı hızla uyumlu (3 fps: kayıp iz 30 kare ~10 sn, gevşek eşleşme)",
            "track_buffer: 30" in izci and "match_thresh: 0.9" in izci and "track_buffer: 50" in Path(motor_blok.izci_dosyasi(10.0)).read_text())

    print("İş parçacığı sınırı ve sıralı başlatma")
    s_ = canli.is_parcacigi_siniri
    denetle("sınır: çekirdek / kamera, en az 1, en çok 4",
            (s_(1, 32, {}), s_(7, 32, {}), s_(7, 8, {}), s_(3, 8, {}), s_(2, 4, {}), s_(9, 4, {})) == (4, 4, 1, 2, 2, 1))
    denetle("kuruluma özel ayar sınırı geçersiz kılar (0 = sınırsız)", (s_(7, 8, {"is_parcacigi": 3}), s_(7, 8, {"is_parcacigi": 0})) == (3, 0))
    canli._SON_BASLATMA[0] = 0.0
    sira_ = [canli.baslatma_sirasi(100.0, 8.0), canli.baslatma_sirasi(100.5, 8.0), canli.baslatma_sirasi(101.0, 8.0),
             canli.baslatma_sirasi(300.0, 8.0)]
    denetle("birlikte başlatılan kameralar 8 sn arayla sıraya girer", sira_ == [100.0, 108.0, 116.0, 300.0])
    canli._SON_BASLATMA[0] = 0.0

    print("0.2.0 ayarları korunur")
    # 0.2.0'ın kaydettiği gibi: ayar dosyası (şifre yerine {sifre}), geçmiş, önbellek, Studio kaydı, lisans işareti
    import hashlib  # noqa: E402

    eski = {"ad": "D4 Mezzanine", "kod": "d4mez", "kamera": {"tur": "rtsp", "marka": "hikvision", "ip": "10.0.0.20", "port": 554,
                                                         "kullanici": "admin", "kanal": 4, "akis": "alt"},
            "calisan_renkleri": ["siyah", "turuncu"], "bekleme_uyari_sn": 240,
            "masalar": json.loads((yollar.AYAR / "salon.json").read_text(encoding="utf-8"))["masalar"],
            "bolgeler": [{"ad": "Kasa", "tur": "kuyruk", "poly": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.3]]}]}
    (yollar.AYAR / "d4mez.json").write_text(json.dumps(eski, ensure_ascii=False, indent=1), encoding="utf-8")
    (yollar.GECMIS / "d4mez").mkdir(parents=True, exist_ok=True)
    (yollar.GECMIS / "d4mez" / "d4mez_20261115_120000.json").write_text('{"ozet": {"oturum": 2}}', encoding="utf-8")
    (yollar.VERI / "studio-lisans.txt").write_text("2026-11-16 12:45:05", encoding="ascii")
    korunacak = [yollar.AYAR / "d4mez.json", yollar.GECMIS / "d4mez" / "d4mez_20261115_120000.json", yollar.VERI / "studio-lisans.txt"]
    once = {q: hashlib.sha256(q.read_bytes()).hexdigest() for q in korunacak}
    yollar.hazirla()
    liste = {a["kod"]: a for a in uygulama.ayarlar()}
    denetle("0.2.0 kamerası listelenir, şifre istenir, analiz hızı yoksa 3",
            "d4mez" in liste and liste["d4mez"]["sifre"] and canli.analiz_fps(eski) == 3.0)

    print("Canlı izleme (sahte Studio)")
    canli.PARCA_SN = 6.0
    canli.BASLATMA_ARALIGI = 0.5
    canli.baslat("d4mez", "GIZLI-sifre")
    k_ = None
    for _ in range(60):
        k_ = canli.api()["kameralar"][0]
        if k_["durum"] == "calisiyor" and k_["simdi"]["kisi"] is not None:
            break
        time.sleep(0.5)
    denetle("canlı kamera çalışıyor, anlık sayılar geldi", k_["durum"] == "calisiyor" and k_["simdi"]["kisi"] == 2
            and k_["simdi"]["calisan"] == 1)
    denetle("pano sözleşmesi: alanlar ve masa bölgeleri", set(k_) >= {"kod", "ad", "durum", "mesaj", "onizleme", "genislik", "yukseklik",
                                                                     "son_kare_sn", "simdi", "masalar", "kasa", "bugun", "saatlik",
                                                                     "uyarilar", "analiz_fps"}
            and k_["masalar"] and all(m["durum"] in ("bos", "dolu", "bekliyor", "kirli") for m in k_["masalar"])
            and k_["masalar"][0]["bolge"] == eski["masalar"][0]["poly"] and k_["kasa"] is not None)
    denetle("analiz hızı: hedef 3 (0.2.0 kamerası), gerçek ölçülür", k_["analiz_fps"] == {"hedef": 3.0, "gercek": 3.0})
    c_ = json.loads((studio.KOSU_KLASORU / "sahte-canli.json").read_text(encoding="utf-8").splitlines()[-1])
    denetle("motor kameranın hızını ve renklerini ortamdan alır", c_["fps"] == "3.0" and json.loads(c_["renk"]) == ["siyah", "turuncu"])
    o = [r for r in ortamlar() if (r.get("is") or "").startswith("canli#")][-1]
    denetle("canlı akış adresi yalnızca ortamda", "GIZLI-sifre" in (o["adres"] or "") and "GIZLI" not in " ".join(o["arg"])
            and "--on-fail" not in o["arg"])
    import urllib.request  # noqa: E402

    denetle("önizleme panelin dosyasından gelir", canli.onizleme("d4mez") is not None)
    time.sleep(8)  # parça (6 sn) kapanır: gecmis'e yazılır, gün toplamı oluşur
    k_ = canli.api()["kameralar"][0]
    denetle("parça kapanınca gün toplamı ve saatlik doluluk", k_["bugun"]["oturum"] is not None and k_["saatlik"]
            and list((yollar.GECMIS / "d4mez").glob("canli_*.json")))
    # Studio süreci ölürse panel yeniden başlatır
    kc = canli.KAMERALAR["d4mez"]
    ilk = kc.kosu.surec.pid
    import subprocess  # noqa: E402

    subprocess.run(["taskkill", "/PID", str(ilk), "/T", "/F"], capture_output=True)  # Studio çöktü: süreç ağacı ölür
    yeni_pid, yeni_idler = None, []
    for _ in range(100):
        time.sleep(0.5)
        k2_ = kc.kosu
        idler = [d["id"] for kr in list(kc.kareler)[-3:] for d in kr["d"]]
        if k2_ is not None and k2_.surec.pid != ilk and canli.api()["kameralar"][0]["durum"] == "calisiyor" and idler                 and max(idler) >= canli.ID_ARALIGI:
            yeni_pid, yeni_idler = k2_.surec.pid, idler
            break
    denetle("Studio süreci ölünce yeniden başlatılır, iz numaraları çakışmaz", yeni_pid is not None and kc.yeniden >= 1
            and yeni_idler and all(i >= canli.ID_ARALIGI for i in yeni_idler))
    canli.durdur("d4mez")
    denetle("durdurunca Studio süreci kapanır, canlı klasör silinir", not studio.KOSULAR and not canli.klasor("d4mez").exists()
            and canli.api()["kameralar"][0]["durum"] == "durdu" and canli.onizleme("d4mez") is None)
    denetle("canlı izlemede ham görüntü yok", not [q for q in (GECICI / "veri").rglob("*")
                                                  if q.suffix.lower() in (".mp4", ".png", ".avi") and "videolar" not in q.parts])
    denetle("şifre hiçbir dosyada yok", not any("GIZLI-sifre" in q.read_text(encoding="utf-8", errors="ignore")
                                                for q in (GECICI / "veri").rglob("*")
                                                if q.is_file() and q.name not in ("sahte-ortam.json",) and q.suffix != ".mp4"))
    denetle("0.2.0 dosyaları bayt bayt aynı", once == {q: hashlib.sha256(q.read_bytes()).hexdigest() for q in korunacak})

    print("İki kamera birlikte (sıralı başlatma, sınır)")
    (yollar.AYAR / "d4mez2.json").write_text(json.dumps({**eski, "ad": "Bar", "kod": "d4mez2"}, ensure_ascii=False), encoding="utf-8")
    canli.BASLATMA_ARALIGI = 3.0
    canli._SON_BASLATMA[0] = 0.0
    canli.baslat("d4mez", "GIZLI-sifre")
    canli.baslat("d4mez2", "GIZLI-sifre")
    time.sleep(0.8)
    k2 = {k["kod"]: k for k in canli.api()["kameralar"]}
    denetle("ikinci kamera 'sırada' (panoda baglaniyor ve açıklama)", k2["d4mez2"]["durum"] == "baglaniyor"
            and "Sırada" in (k2["d4mez2"]["mesaj"] or ""))
    for _ in range(60):
        k2 = {k["kod"]: k for k in canli.api()["kameralar"]}
        if all(k2[x]["durum"] == "calisiyor" for x in ("d4mez", "d4mez2")):
            break
        time.sleep(0.5)
    kayit_ = [json.loads(s) for s in (studio.KOSU_KLASORU / "sahte-canli.json").read_text(encoding="utf-8").splitlines()][-2:]
    beklenen_ = str(canli.is_parcacigi_siniri(2))
    denetle("iki kamera da çalışır; Studio süreçleri en az 3 sn arayla başlar", all(k2[x]["durum"] == "calisiyor" for x in ("d4mez", "d4mez2"))
            and abs(kayit_[1]["an"] - kayit_[0]["an"]) >= 2.5)
    denetle("iş parçacığı sınırı süreç başlamadan ortamda (OMP dahil) ve dosyada", all(r["ip"] == beklenen_ and r["omp"] == beklenen_
                                                                                     for r in kayit_)
            and json.loads(Path(kayit_[0]["ip_dosya"]).read_text())["n"] == int(beklenen_))
    canli.durdur("d4mez2")
    denetle("kamera durunca sınır dosyası kalan kameralara göre güncellenir",
            json.loads(Path(kayit_[0]["ip_dosya"]).read_text())["n"] == canli.is_parcacigi_siniri(1))
    canli.durdur_hepsi()
    canli.BASLATMA_ARALIGI = 0.5

    print("Kopuk akış ve yavaş bilgisayar")
    sahte("canli_kop")
    canli.baslat("d4mez", "GIZLI-sifre")
    for _ in range(40):
        k_ = canli.api()["kameralar"][0]
        if k_["durum"] == "koptu":
            break
        time.sleep(0.5)
    denetle("kopuk akış 'koptu' görünür, boş kafe değil (sayılar null)", k_["durum"] == "koptu"
            and "yeniden deneniyor" in k_["mesaj"] and k_["simdi"]["kisi"] is None and k_["analiz_fps"]["gercek"] is None)
    canli.durdur("d4mez")
    sahte("canli_yavas")
    canli.baslat("d4mez", "GIZLI-sifre")
    for _ in range(40):
        k_ = canli.api()["kameralar"][0]
        if k_["durum"] == "calisiyor" and "yetişemiyor" in (k_["mesaj"] or ""):
            break
        time.sleep(0.5)
    denetle("gerçek hız hedefin çok altındaysa uyarılır", "yetişemiyor" in (k_["mesaj"] or "") and k_["analiz_fps"]["gercek"] == 0.5)
    canli.durdur_hepsi()
    sahte(None)
    denetle("canlı işlerden sonra süreç kalmadı", not studio.KOSULAR)

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
