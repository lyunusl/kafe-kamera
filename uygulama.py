"""Kafe Kamera: çift tıklayınca veri klasörünü kurar, yerel sunucuyu (yalnızca 127.0.0.1) başlatır ve tarayıcıda açar.

Başlangıç sayfasından: örnek analiz, kamera ekleme, bağlantı denemesi, izleme ve panel.
"""
from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import re
import shutil
import socket
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import yollar

VARSAYILAN_PORT = 8770
KOD_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
TURLER = {
    ".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8", ".jpg": "image/jpeg",
    ".mp4": "video/mp4", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".png": "image/png", ".ico": "image/x-icon", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
}

# ---------------------------------------------------------------- arka plan işleri


class Is:
    """Arka planda çalışan bir iş (örnek analiz, bağlantı denemesi, izleme) ve ekrana yazdıkları."""

    sayac = 0

    def __init__(self, tur: str, baslik: str):
        Is.sayac += 1
        self.no = Is.sayac
        self.tur, self.baslik = tur, baslik
        self.satirlar: list[str] = []
        self._yarim = ""
        self.durum = "calisiyor"
        self.sonuc: dict = {}
        self.bas, self.bitis = time.time(), None
        self.dur = threading.Event()
        self.kilit = threading.Lock()

    def ekle(self, metin: str) -> None:
        with self.kilit:
            parca = (self._yarim + metin.replace("\r\n", "\n").replace("\r", "\n")).split("\n")
            self._yarim = parca.pop()
            for s in parca:
                s = s.rstrip()
                if not s:
                    continue
                # ilerleme satırları üst üste yazılsın
                if self.satirlar and s.startswith("  algılama:") and self.satirlar[-1].startswith("  algılama:"):
                    self.satirlar[-1] = s
                else:
                    self.satirlar.append(s)
            del self.satirlar[:-400]

    def ozet(self) -> dict:
        with self.kilit:
            satirlar = self.satirlar + ([self._yarim] if self._yarim.strip() else [])
        return {"no": self.no, "tur": self.tur, "baslik": self.baslik, "durum": self.durum, "satirlar": satirlar,
                "sonuc": self.sonuc, "sure": round((self.bitis or time.time()) - self.bas, 1), "durduruluyor": self.dur.is_set()}


class Yonlendirici(io.TextIOBase):
    """print() çıktısını, o anda hangi işin iş parçacığındaysa o işin kaydına da yazar."""

    def __init__(self, asil):
        self.asil = asil
        self.yerel = threading.local()

    @property
    def encoding(self):
        return "utf-8"

    def write(self, s):
        is_ = getattr(self.yerel, "is_", None)
        if is_ is not None:
            is_.ekle(s)
        if self.asil is not None:
            try:
                self.asil.write(s)
            except UnicodeEncodeError:
                self.asil.write(s.encode(getattr(self.asil, "encoding", None) or "ascii", "replace").decode(getattr(self.asil, "encoding", None) or "ascii"))
            except Exception:
                pass
        return len(s)

    def flush(self):
        if self.asil is not None:
            try:
                self.asil.flush()
            except Exception:
                pass

    def isatty(self):
        return False


YON_OUT = Yonlendirici(sys.stdout)
YON_ERR = Yonlendirici(sys.stderr)
AKTIF: Is | None = None
IS_KILIDI = threading.Lock()


def is_baslat(tur: str, baslik: str, fn, *args) -> tuple[bool, str]:
    global AKTIF
    with IS_KILIDI:
        if AKTIF is not None and AKTIF.durum == "calisiyor":
            return False, f"Şu an \"{AKTIF.baslik}\" çalışıyor. Bitmesini bekleyin ya da durdurun."
        is_ = Is(tur, baslik)
        AKTIF = is_

    def calis():
        YON_OUT.yerel.is_ = YON_ERR.yerel.is_ = is_
        try:
            sonuc = fn(is_, *args)
            is_.sonuc = sonuc or {}
            is_.durum = "hata" if is_.sonuc.get("hata") else ("durduruldu" if is_.dur.is_set() else "bitti")
        except SystemExit as e:
            if e.code not in (None, 0):
                if not isinstance(e.code, int):
                    print(str(e.code), flush=True)
                is_.durum = "hata"
            else:
                is_.durum = "bitti"
        except Exception as e:  # beklenmeyen hata: ayrıntı konsola, kısa mesaj ekrana
            traceback.print_exc(file=sys.__stderr__)
            print(f"Hata: {e}", flush=True)
            is_.durum = "hata"
        finally:
            YON_OUT.yerel.is_ = YON_ERR.yerel.is_ = None
            is_.bitis = time.time()

    threading.Thread(target=calis, name=f"is-{is_.no}", daemon=True).start()
    return True, ""


def ayar_yolu(kod: str) -> Path:
    return yollar.AYAR / f"{kod}.json"


def ayar_oku(kod: str) -> dict:
    yol = ayar_yolu(kod)
    if not yol.exists():
        raise SystemExit(f"Ayar bulunamadı: {kod}")
    return json.loads(yol.read_text(encoding="utf-8"))


def is_ornek(is_: Is) -> dict:
    import analiz
    import rapor

    for n, kod in enumerate(yollar.ORNEK_KODLAR, 1):
        if is_.dur.is_set():
            print("Durduruldu.", flush=True)
            return {}
        ayar = ayar_oku(kod)
        print(f"[{n}/{len(yollar.ORNEK_KODLAR)}] {ayar.get('ad', kod)} analiz ediliyor…", flush=True)
        t0 = time.time()
        analiz.calistir(yollar.VIDEOLAR / f"{kod}.mp4", ayar_yolu(kod), cikti_adi=kod)
        print(f"[{n}/{len(yollar.ORNEK_KODLAR)}] bitti ({time.time() - t0:.0f} sn).", flush=True)
    rapor.uret()
    return {"panel": "/cikti/panel.html"}


def is_test(is_: Is, kod: str, sifre: str | None) -> dict:
    import kamera

    ayar = ayar_oku(kod)
    r = kamera.test(ayar, ayar_yolu(kod), sifre)
    if r != 0:
        return {"hata": True}
    return {"kare": f"/ayar/_kare_{kamera.kod(ayar, ayar_yolu(kod))}.jpg?t={int(time.time())}", "kod": kod}


def is_izle(is_: Is, kod: str, sifre: str | None, dakika: float) -> dict:
    import kamera

    ayar = ayar_oku(kod)
    kamera.izle(ayar, ayar_yolu(kod), dakika, 0, False, sifre=sifre, dur=is_.dur)
    return {"panel": "/cikti/panel.html"}


def is_video(is_: Is, kod: str) -> dict:
    """Video dosyası türündeki kamerayı (ör. kayıt cihazından alınmış kayıt) baştan sona analiz eder."""
    import analiz
    import kamera
    import rapor

    ayar = ayar_oku(kod)
    if (ayar.get("kamera") or {}).get("tur") != "dosya":
        raise SystemExit("Bu kamera bir video dosyası değil. Canlı kamera için İzlemeyi başlat'ı kullanın.")
    yol, _ = kamera.kaynak(ayar)
    print(f"{Path(yol).name} analiz ediliyor…", flush=True)
    analiz.calistir(Path(yol), ayar_yolu(kod), cikti_adi=kamera.kod(ayar, ayar_yolu(kod)))
    rapor.uret()
    return {"panel": "/cikti/panel.html"}


def is_panel(is_: Is) -> dict:
    import rapor

    rapor.uret()
    return {"panel": "/cikti/panel.html"}


# ---------------------------------------------------------------- ayarlar


def sifreyi_temizle(ayar: dict) -> list[str]:
    """Ayar dosyasına şifre yazılmasın: şifre alanlarını siler, adresteki şifreyi {sifre} yapar."""
    notlar = []
    k = ayar.get("kamera")
    if isinstance(k, dict):
        for alan in list(k):
            if alan != "sifre_degiskeni" and re.search(r"sifre|şifre|password|pass$|parola", alan, re.I):
                del k[alan]
                notlar.append("Şifre alanı kaydedilmedi.")
        adres = k.get("adres")
        if isinstance(adres, str):
            m = re.search(r"://([^:/@]+):([^@]*)@", adres)
            if m and m.group(2) not in ("{sifre}", ""):
                k["adres"] = adres[:m.start(2)] + "{sifre}" + adres[m.end(2):]
                notlar.append("Adresteki şifre kaydedilmedi; yerine {sifre} yazıldı. Şifreyi çalışırken şifre kutusuna yazın.")
    ayar.pop("sifre", None)
    return notlar


def ayarlar() -> list[dict]:
    import kamera

    out = []
    for yol in sorted(yollar.AYAR.glob("*.json")):
        if yol.stem.startswith("_"):
            continue
        try:
            a = json.loads(yol.read_text(encoding="utf-8"))
        except Exception:
            continue
        k = a.get("kamera") or {}
        kare = yollar.AYAR / f"_kare_{kamera.kod(a, yol)}.jpg"
        out.append({"kod": yol.stem, "ad": a.get("ad", yol.stem), "tur": k.get("tur", "rtsp"), "sifre": kamera.sifre_gerekli(a),
                    "kare": f"/ayar/{kare.name}?t={int(kare.stat().st_mtime)}" if kare.exists() else None,
                    "ornek": yol.stem in yollar.ORNEK_KODLAR, "masa": len(a.get("masalar") or []), "bolge": len(a.get("bolgeler") or [])})
    out.sort(key=lambda x: (x["ornek"], yollar.ORNEK_KODLAR.index(x["kod"]) if x["ornek"] else 0, x["kod"]))
    return out


def durum() -> dict:
    return {
        "uygulama": "KafeKamera", "surum": yollar.SURUM, "veri": str(yollar.VERI),
        "panel": (yollar.CIKTI / "panel.html").exists(),
        "ornek_sonuc": any((yollar.CIKTI / k / "sonuc.json").exists() for k in yollar.ORNEK_KODLAR),
        "ayarlar": ayarlar(), "is": AKTIF.ozet() if AKTIF else None,
    }


# ---------------------------------------------------------------- HTTP


class Sunucu(ThreadingHTTPServer):
    allow_reuse_address = False  # Windows'ta aynı portu ikinci kez açmasın
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Istek(BaseHTTPRequestHandler):
    server_version = "KafeKamera"
    sys_version = ""

    def log_message(self, *a):  # konsolu istek satırlarıyla doldurma
        pass

    # --- yardımcılar
    def _izinli(self) -> bool:
        port = self.server.server_address[1]
        izinli = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host", "") not in izinli:
            return False
        koken = self.headers.get("Origin")
        if self.command == "POST" and koken is not None and koken not in {f"http://{h}" for h in izinli}:
            return False
        return True

    def _gonder(self, kod: int, govde: bytes, tur: str, ek: dict | None = None):
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (ek or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(govde)

    def _json(self, veri, kod: int = 200):
        self._gonder(kod, json.dumps(veri, ensure_ascii=False).encode("utf-8"), TURLER[".json"])

    def _hata_sayfasi(self, kod: int, baslik: str, metin: str):
        html = (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><link rel="icon" href="data:,"><title>{baslik}</title>'
                '<style>body{margin:0;background:#0b1020;color:#e8ecf5;font:16px/1.5 "Segoe UI",system-ui,sans-serif;padding:40px}'
                'a{color:#fde035}</style></head>'
                f'<body><h1>{baslik}</h1><p>{metin}</p><p><a href="/">Başlangıç sayfasına dön</a></p></body></html>')
        self._gonder(kod, html.encode("utf-8"), TURLER[".html"])

    def _dosya(self, yol: Path):
        if not yol.is_file():
            return self._hata_sayfasi(404, "Bulunamadı", "Bu dosya yok.")
        tur = TURLER.get(yol.suffix.lower()) or mimetypes.guess_type(yol.name)[0] or "application/octet-stream"
        boyut = yol.stat().st_size
        aralik = self.headers.get("Range")
        bas, son = 0, boyut - 1
        kod = 200
        m = re.match(r"bytes=(\d*)-(\d*)$", aralik or "")
        if m and boyut > 0 and (m.group(1) or m.group(2)):
            if m.group(1):
                bas = int(m.group(1))
                son = min(int(m.group(2)), boyut - 1) if m.group(2) else boyut - 1
            else:
                bas = max(0, boyut - int(m.group(2)))
            if bas > son or bas >= boyut:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{boyut}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            kod = 206
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(son - bas + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        if kod == 206:
            self.send_header("Content-Range", f"bytes {bas}-{son}/{boyut}")
        if yol.suffix.lower() == ".xlsx":
            self.send_header("Content-Disposition", f'attachment; filename="{yol.name}"')
        self.end_headers()
        if self.command == "HEAD":
            return
        try:
            with open(yol, "rb") as f:
                f.seek(bas)
                kalan = son - bas + 1
                while kalan > 0:
                    parca = f.read(min(1 << 16, kalan))
                    if not parca:
                        break
                    self.wfile.write(parca)
                    kalan -= len(parca)
        except (ConnectionError, OSError):
            pass

    def _govde(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 5_000_000:
            raise ValueError("istek çok büyük")
        veri = self.rfile.read(n) if n else b"{}"
        return json.loads(veri.decode("utf-8") or "{}")

    # --- GET
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self._izinli():
            return self._gonder(403, b"Forbidden", "text/plain")
        yol = unquote(urlparse(self.path).path)
        if yol in ("/", "/index.html", "/baslangic.html"):
            return self._dosya(yollar.WEB / "baslangic.html")
        if yol == "/bolge_ciz.html":
            return self._dosya(yollar.WEB / "bolge_ciz.html")
        if yol == "/favicon.ico":
            return self._dosya(yollar.WEB / "favicon.ico")
        if yol == "/api/durum":
            return self._json(durum())
        if yol.startswith("/api/ayar/"):
            kod = yol[len("/api/ayar/"):]
            if not KOD_RE.match(kod) or not ayar_yolu(kod).exists():
                return self._json({"hata": "Ayar bulunamadı."}, 404)
            return self._json(json.loads(ayar_yolu(kod).read_text(encoding="utf-8")))
        if yol.startswith("/ayar/"):
            ad = yol[len("/ayar/"):]
            if re.match(r"^_kare_[a-z0-9_-]{1,40}\.jpg$", ad):  # yalnızca yüzleri gizlenmiş kareler
                return self._dosya(yollar.AYAR / ad)
            return self._hata_sayfasi(404, "Bulunamadı", "Bu dosya yok.")
        if yol.startswith("/cikti/"):
            goreli = yol[len("/cikti/"):]
            hedef = (yollar.CIKTI / goreli).resolve()
            if yollar.CIKTI.resolve() not in hedef.parents:
                return self._hata_sayfasi(404, "Bulunamadı", "Bu dosya yok.")
            if goreli == "panel.html" and not hedef.exists():
                return self._hata_sayfasi(404, "Henüz panel yok",
                                          "Önce Başlangıç sayfasından <b>Örnek analizi çalıştır</b>'a basın ya da bir kamerayı izlemeye başlayın.")
            return self._dosya(hedef)
        return self._hata_sayfasi(404, "Bulunamadı", "Bu sayfa yok.")

    # --- POST
    def do_POST(self):
        if not self._izinli():
            return self._gonder(403, b"Forbidden", "text/plain")
        yol = urlparse(self.path).path
        try:
            g = self._govde()
        except Exception:
            return self._json({"hata": "İstek okunamadı."}, 400)
        try:
            return self._post(yol, g)
        except SystemExit as e:
            return self._json({"hata": str(e.code)}, 400)

    def _kod(self, g: dict) -> str:
        kod = str(g.get("kod", ""))
        if not KOD_RE.match(kod):
            raise SystemExit("Kısa kod yalnızca küçük harf (a-z), rakam, - ve _ içerebilir (ör. salon2).")
        return kod

    def _post(self, yol: str, g: dict):
        if yol == "/api/is/ornek":
            ok, m = is_baslat("ornek", "Örnek analiz", is_ornek)
        elif yol == "/api/is/panel":
            ok, m = is_baslat("panel", "Paneli yenile", is_panel)
        elif yol in ("/api/is/test", "/api/is/izle", "/api/is/video"):
            kod = self._kod(g)
            if not ayar_yolu(kod).exists():
                return self._json({"hata": f"Ayar bulunamadı: {kod}"}, 404)
            sifre = g.get("sifre")
            sifre = str(sifre) if sifre is not None else None
            ad = json.loads(ayar_yolu(kod).read_text(encoding="utf-8")).get("ad", kod)
            if yol == "/api/is/test":
                ok, m = is_baslat("test", f"Bağlantı denemesi · {ad}", is_test, kod, sifre)
            elif yol == "/api/is/video":
                ok, m = is_baslat("video", f"Video analizi · {ad}", is_video, kod)
            else:
                try:
                    dakika = min(240.0, max(0.25, float(g.get("dakika", 15))))
                except (TypeError, ValueError):
                    dakika = 15.0
                ok, m = is_baslat("izle", f"İzleme · {ad}", is_izle, kod, sifre, dakika)
        elif yol == "/api/is/durdur":
            if AKTIF is not None and AKTIF.durum == "calisiyor":
                AKTIF.dur.set()
                print(f"Durdurma istendi: {AKTIF.baslik}", flush=True)
            return self._json({"tamam": True})
        elif yol == "/api/ayar":
            ayar = g.get("ayar")
            if not isinstance(ayar, dict):
                return self._json({"hata": "Ayar okunamadı."}, 400)
            kod = self._kod({"kod": ayar.get("kod", "")})
            if kod in yollar.ORNEK_KODLAR:
                return self._json({"hata": f"\"{kod}\" örnek kameralara ait. Başka bir kısa kod yazın (ör. {kod}2)."}, 400)
            ayar["kod"] = kod
            notlar = sifreyi_temizle(ayar)
            yollar.AYAR.mkdir(parents=True, exist_ok=True)
            ayar_yolu(kod).write_text(json.dumps(ayar, ensure_ascii=False, indent=1), encoding="utf-8")
            return self._json({"tamam": True, "kod": kod, "notlar": notlar})
        elif yol == "/api/ayar/sil":
            kod = self._kod(g)
            if kod in yollar.ORNEK_KODLAR:
                return self._json({"hata": "Örnek kameraların ayarı silinmez."}, 400)
            if AKTIF is not None and AKTIF.durum == "calisiyor":
                return self._json({"hata": "Önce çalışan işi bitirin ya da durdurun."}, 409)
            ayar_yolu(kod).unlink(missing_ok=True)
            (yollar.AYAR / f"_kare_{kod}.jpg").unlink(missing_ok=True)
            shutil.rmtree(yollar.CIKTI / kod, ignore_errors=True)
            import rapor

            rapor.uret()
            return self._json({"tamam": True})
        elif yol == "/api/ornekleri-kaldir":
            if AKTIF is not None and AKTIF.durum == "calisiyor":
                return self._json({"hata": "Önce çalışan işi bitirin ya da durdurun."}, 409)
            for kod in yollar.ORNEK_KODLAR:
                shutil.rmtree(yollar.CIKTI / kod, ignore_errors=True)
            import rapor

            rapor.uret()
            return self._json({"tamam": True})
        elif yol == "/api/klasor":
            if hasattr(os, "startfile"):
                os.startfile(str(yollar.VERI))  # noqa: S606 - yalnızca kendi veri klasörümüz
            return self._json({"tamam": True})
        elif yol == "/api/kapat":
            self._json({"tamam": True})
            if AKTIF is not None:
                AKTIF.dur.set()
            threading.Thread(target=kapat, args=(self.server,), daemon=True).start()
            return None
        else:
            return self._json({"hata": "Bilinmeyen istek."}, 404)
        if not ok:
            return self._json({"hata": m}, 409)
        return self._json({"tamam": True, "is": AKTIF.ozet() if AKTIF else None})


def kapat(sunucu) -> None:
    time.sleep(0.4)
    print("Kafe Kamera kapatılıyor.", flush=True)
    sunucu.shutdown()


# ---------------------------------------------------------------- başlatma


def calisiyor_mu(port: int) -> bool:
    """Bu portta zaten bir Kafe Kamera çalışıyor mu?"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/durum", timeout=2) as r:
            return json.loads(r.read().decode("utf-8")).get("uygulama") == "KafeKamera"
    except Exception:
        return False


def splash_kapat() -> None:
    try:
        import pyi_splash  # yalnızca exe'de var

        pyi_splash.close()
    except Exception:
        pass


def isin() -> None:
    """Ağır kütüphaneleri arka planda yükle; ilk iş daha çabuk başlasın."""
    try:
        import analiz  # noqa: F401
        import kamera  # noqa: F401
        import rapor  # noqa: F401
    except Exception:
        traceback.print_exc(file=sys.__stderr__)


def main() -> None:
    ap = argparse.ArgumentParser(prog="KafeKamera", description="Kafe kamera analizi: yerel panel")
    ap.add_argument("--port", type=int, default=VARSAYILAN_PORT)
    ap.add_argument("--tarayici-yok", action="store_true", help="tarayıcıyı açma")
    a = ap.parse_args()

    if calisiyor_mu(a.port):
        splash_kapat()
        url = f"http://127.0.0.1:{a.port}/"
        print(f"Kafe Kamera zaten çalışıyor: {url}")
        if not a.tarayici_yok:
            webbrowser.open(url)
        time.sleep(2)
        return

    sys.stdout, sys.stderr = YON_OUT, YON_ERR
    print(f"Kafe Kamera {yollar.SURUM}")
    if yollar.hazirla():
        print("İlk kurulum: veri klasörü hazırlandı, örnek videolar kopyalandı.")
    # program izleme sırasında kapanmışsa yarım kalan ham kayıt parçaları (yüzler açık) silinsin
    for f in yollar.VIDEOLAR.glob("*.mp4"):
        if re.search(r"_\d{8}_\d{6}\.mp4$", f.name):
            f.unlink(missing_ok=True)
            (yollar.ONBELLEK / f"{f.stem}.json").unlink(missing_ok=True)

    sunucu = None
    for port in [a.port] + list(range(a.port + 1, a.port + 25)):
        try:
            sunucu = Sunucu(("127.0.0.1", port), Istek)
            break
        except OSError:
            if calisiyor_mu(port):
                splash_kapat()
                print(f"Kafe Kamera zaten çalışıyor: http://127.0.0.1:{port}/")
                if not a.tarayici_yok:
                    webbrowser.open(f"http://127.0.0.1:{port}/")
                time.sleep(2)
                return
    if sunucu is None:
        splash_kapat()
        print("Boş port bulunamadı.")
        time.sleep(5)
        raise SystemExit(1)
    port = sunucu.server_address[1]
    url = f"http://127.0.0.1:{port}/"
    print(f"  Panel   : {url}")
    print(f"  Veriler : {yollar.VERI}")
    print("Kapatmak için bu pencereyi kapatın (ya da sayfadaki Kapat düğmesine basın).\n", flush=True)
    threading.Thread(target=isin, daemon=True).start()
    splash_kapat()
    if not a.tarayici_yok:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        sunucu.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        sunucu.server_close()
    # izleme sürüyorsa kaydın düzgün kapanması için kısa bir süre tanı; analiz sürüyorsa beklenmez
    if AKTIF is not None and AKTIF.durum == "calisiyor":
        AKTIF.dur.set()
        for _ in range(10):
            if AKTIF.durum != "calisiyor":
                break
            time.sleep(0.3)
    os._exit(0)


if __name__ == "__main__":
    main()
