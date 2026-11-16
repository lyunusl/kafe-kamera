"""Studio kurulum sözleşmesini gerçek kurucu çalıştırmadan sınar.

  .venv\\Scripts\\python egitim/dene_kurulum.py

Akış: resmî kurucuyu indir ve SHA-256 ile doğrula → Visual C++ yoksa Microsoft'tan indir, imzasını doğrula, kur → Studio'yu
sessizce kur, olmazsa resmî kurulum penceresini aç. Studio penceresi açılmaz (Kafe Kamera Studio'yu arayüzsüz kullanır);
lisans kodu Studio'nun kendi komutuyla (studio verify) arayüzsüz kaydedilir, saklanmaz. Kurulum dosyası (KafeKamera.iss)
ile studio_kurulum.py'nin aynı adres, özet ve adları kullandığı da denetlenir.
"""
import hashlib
import io
import os
import ssl
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from urllib.error import URLError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import studio_kurulum as kurulum


def yanit(icerik: bytes):
    """urlopen yanıtı gibi: okunur, bağlam yöneticisidir ve başlık taşır."""
    y = io.BytesIO(icerik)
    y.headers = {"Content-Length": str(len(icerik))}
    return y


@unittest.skipUnless(os.name == "nt", "Windows kurulum senaryosu")
class StudioKurulumTesti(unittest.TestCase):
    def setUp(self):
        gecici = self.enterContext(tempfile.TemporaryDirectory())
        self.veri = Path(gecici) / "veri"
        self.hedef = Path(gecici) / "Programlar" / "Studio"
        self.studio = self.hedef / kurulum.EXE
        self.is_ = SimpleNamespace(dur=threading.Event())
        self.enterContext(patch.dict(os.environ, {"PROCESSOR_ARCHITEW6432": "AMD64"}))
        self.enterContext(patch.object(kurulum.yollar, "VERI", self.veri))
        self.enterContext(patch.object(kurulum, "varsayilan_klasor", return_value=self.hedef))
        self.enterContext(patch.object(kurulum, "kurulu_studio", side_effect=self._bul))
        self.enterContext(patch.object(kurulum, "_kurulumu_bekle", side_effect=lambda *a: self._bul()))
        self.enterContext(patch.object(kurulum.time, "sleep"))
        self.enterContext(patch.object(kurulum, "studio_calisiyor", return_value=False))
        self.vc_var = True
        self.enterContext(patch.object(kurulum, "vc_kurulu", side_effect=lambda: self.vc_var))
        self.imza = self.enterContext(patch.object(kurulum, "microsoft_imzali", return_value=True))
        self.indir = self.enterContext(patch.object(kurulum.urllib.request, "urlopen"))
        self.calistir = self.enterContext(patch.object(kurulum, "_harici_program"))
        self.izinle = self.enterContext(patch.object(kurulum, "_izinle_calistir"))
        self.icerik = b"MZ test icin kurulum paketi"
        self.vc_icerik = b"MZ test icin visual c++ paketi"
        self.gercek_sha = kurulum.KURULUM_SHA256
        self.enterContext(patch.object(kurulum, "KURULUM_SHA256", hashlib.sha256(self.icerik).hexdigest()))
        self.indir.side_effect = lambda istek, **kw: yanit(self.vc_icerik if istek.full_url == kurulum.VC_URL else self.icerik)
        kurulum.DURUM.update(asama="bos", hata="")

    def _bul(self):
        return kurulum._studio_exe(self.hedef)

    def _studio_olustur(self, *_a, **_kw):
        self.hedef.mkdir(parents=True, exist_ok=True)
        self.studio.touch()
        python = self.hedef / "Python"
        paket = python / "Lib" / "site-packages" / "studio"
        paket.mkdir(parents=True, exist_ok=True)
        (python / "pythonw.exe").touch()
        (paket / "__init__.py").touch()
        return 0

    def _indirilenler(self):
        return [c.args[0].full_url for c in self.indir.call_args_list]

    def test_var_olan_kurulum_korunur(self):
        self._studio_olustur()
        self.assertEqual(kurulum.kur(self.is_), {"kurulu": True})
        self.indir.assert_not_called()
        self.izinle.assert_not_called()
        self.calistir.assert_not_called()  # Studio penceresi açılmaz

    def test_ilk_kurulum_sessiz_ve_pencere_acmaz(self):
        self.izinle.side_effect = self._studio_olustur
        self.assertEqual(kurulum.kur(self.is_), {"kurulu": True})
        self.assertEqual(self._indirilenler(), [kurulum.KURULUM_URL])
        tls = self.indir.call_args.kwargs["context"]
        self.assertTrue(tls.check_hostname)
        self.assertEqual(tls.verify_mode, ssl.CERT_REQUIRED)
        kurucu, parametre = self.izinle.call_args.args[:2]
        self.assertEqual(kurucu.parent, self.veri / "kurulum")
        self.assertIn("--silent", parametre)
        self.assertIn(f'--install-dir "{self.hedef}"', parametre)
        self.calistir.assert_not_called()  # ne kurulum penceresi ne Studio penceresi açıldı
        self.assertEqual(kurulum.DURUM["asama"], "bos")
        self.assertFalse(hasattr(kurulum, "ac"))

    def test_sessiz_kurulum_olmazsa_resmi_pencere_acilir(self):
        self.izinle.return_value = 1603
        pencere = MagicMock()
        pencere.__enter__.return_value = pencere
        pencere.wait.side_effect = self._studio_olustur
        self.calistir.return_value = pencere
        self.assertEqual(kurulum.kur(self.is_), {"kurulu": True})
        cagrilar = self.calistir.call_args_list
        self.assertEqual(len(cagrilar), 1)  # yalnızca resmî kurulum penceresi; Studio başlatılmadı
        self.assertEqual(cagrilar[0].kwargs, {"cwd": self.veri / "kurulum"})

    def test_visual_cpp_yoksa_imzasi_dogrulanip_kurulur(self):
        self.vc_var = False

        def calistir(program, parametre="", **kw):
            if program.name == "vc_redist.x64.exe":
                self.assertEqual(parametre, "/install /passive /norestart")
                self.vc_var = True
                return 3010  # yeniden başlatma gerekebilir: başarı sayılır
            return self._studio_olustur()

        self.izinle.side_effect = calistir
        self.assertEqual(kurulum.kur(self.is_), {"kurulu": True})
        self.assertEqual(self._indirilenler(), [kurulum.KURULUM_URL, kurulum.VC_URL])
        self.imza.assert_called_once()
        self.assertEqual([c.args[0].name for c in self.izinle.call_args_list][0], "vc_redist.x64.exe")

    def test_imzasi_dogrulanmayan_visual_cpp_calistirilmaz(self):
        self.vc_var = False
        self.imza.return_value = False
        with self.assertRaisesRegex(SystemExit, "Microsoft imzası doğrulanamadı"):
            kurulum.kur(self.is_)
        self.izinle.assert_not_called()
        self.calistir.assert_not_called()
        self.assertFalse((self.veri / "kurulum" / "vc_redist.x64.exe").exists())
        self.assertEqual(kurulum.DURUM["asama"], "hata")

    def test_windows_izni_verilmezse_anlasilir_hata(self):
        self.vc_var = False
        self.izinle.side_effect = OSError(None, "iptal", None, 1223)
        with self.assertRaisesRegex(SystemExit, "Windows izni verilmedi"):
            kurulum.kur(self.is_)

    def test_eksik_kurulumun_uzerine_yazilmaz(self):
        self.hedef.mkdir(parents=True)
        self.studio.touch()
        (self.hedef / "korunacak.txt").touch()
        with self.assertRaisesRegex(SystemExit, "klasörü dolu"):
            kurulum.kur(self.is_)
        self.indir.assert_not_called()
        self.calistir.assert_not_called()

    def test_dogrulanmamis_paket_calistirilmaz(self):
        self.indir.side_effect = lambda *a, **kw: yanit(b"MZ gecersiz")
        with self.assertRaisesRegex(SystemExit, "doğrulaması başarısız"):
            kurulum.kur(self.is_)
        self.izinle.assert_not_called()
        self.calistir.assert_not_called()
        self.assertFalse(list((self.veri / "kurulum").iterdir()))

    def test_exe_olmayan_indirme_calistirilmaz(self):
        self.indir.side_effect = lambda *a, **kw: yanit(b"<html>hata sayfasi</html>")
        with self.assertRaisesRegex(SystemExit, "eksik ya da bozuk"):
            kurulum.kur(self.is_)
        self.izinle.assert_not_called()

    def test_kurucu_basari_donse_bile_studio_yoksa_hata(self):
        self.izinle.return_value = 0
        self.calistir.return_value.__enter__.return_value.wait.return_value = 0
        with self.assertRaisesRegex(SystemExit, "kurulumu tamamlanmadı veya bulunamadı"):
            kurulum.kur(self.is_)
        self.calistir.assert_called_once()  # sessiz kurulum Studio bırakmadı: resmî pencere açıldı, yine yok
        self.assertEqual(kurulum.DURUM["asama"], "hata")

    def test_gecersiz_tls_ile_kurucu_calistirilmaz(self):
        self.indir.side_effect = URLError(ssl.SSLCertVerificationError("sertifika"))
        with self.assertRaisesRegex(SystemExit, "TLS sertifikası doğrulanamadı"):
            kurulum.kur(self.is_)
        self.izinle.assert_not_called()
        self.calistir.assert_not_called()

    def test_kurulumdan_sonra_acilan_studio_kapatilir(self):
        self.izinle.side_effect = self._studio_olustur
        kurulum.studio_calisiyor.return_value = True
        with patch.object(kurulum.subprocess, "run") as calistir:
            self.assertEqual(kurulum.kur(self.is_), {"kurulu": True})
        self.assertEqual(calistir.call_args.args[0][:3], ["taskkill", "/IM", kurulum.EXE])

    def test_lisans_kodu_arayuzsuz_kaydedilir_ve_saklanmaz(self):
        self._studio_olustur()
        kod = "ABCD-1234-EFGH-5678"
        with patch.object(kurulum.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")) as calistir:
            kurulum.lisans_kaydet(" " + kod + "\n")
        komut = calistir.call_args.args[0]
        self.assertEqual(komut[0], str(self.hedef / "Python" / "python.exe"))
        self.assertEqual(komut[1:], ["-c", kurulum.VERIFY])
        self.assertNotIn(kod, " ".join(komut))  # kod komut satırında görünmez
        self.assertEqual(calistir.call_args.kwargs["env"]["KAFE_LISANS_KODU"], kod)
        self.assertNotIn(kod, "".join(str(p) for p in self.veri.rglob("*")) if self.veri.exists() else "")

    def test_reddedilen_lisans_kodu_hata_metninde_gorunmez(self):
        self._studio_olustur()
        kod = "GECERSIZ-KOD-9999"
        cikti = SimpleNamespace(returncode=1, stdout="", stderr=f"Verification failed for {kod}: invalid code")
        with patch.object(kurulum.subprocess, "run", return_value=cikti):
            with self.assertRaises(SystemExit) as h:
                kurulum.lisans_kaydet(kod)
        self.assertNotIn(kod, str(h.exception.code))
        self.assertIn("kaydedilemedi", str(h.exception.code))

    def test_bicimsiz_lisans_kodu_studioya_verilmez(self):
        self._studio_olustur()
        with patch.object(kurulum.subprocess, "run") as calistir:
            for kod in ("", "kisa", "iki kelime kod", "--help"):
                with self.assertRaisesRegex(SystemExit, "geçersiz"):
                    kurulum.lisans_kaydet(kod)
        calistir.assert_not_called()

    def test_kurulum_dosyasi_ayni_studio_kurucusunu_kullanir(self):
        import re

        iss = (Path(__file__).resolve().parent.parent / "kurulum" / "KafeKamera.iss").read_text(encoding="utf-8")
        tanim = dict(re.findall(r'^#define (\w+) "([^"]*)"', iss, flags=re.M))
        self.assertEqual(tanim["StudioUrl"], kurulum.KURULUM_URL)
        self.assertEqual(tanim["StudioSha256"], self.gercek_sha)
        self.assertEqual(tanim["VcUrl"], kurulum.VC_URL)
        self.assertEqual(tanim["HesapUrl"], kurulum.HESAP_URL)
        self.assertEqual(tanim["StudioExe"], kurulum.EXE)

    def test_durum_paneli_icin(self):
        d = kurulum.durum()
        self.assertEqual(set(d), {"asama", "ne", "indirilen", "toplam", "hata", "gecen", "calisiyor"})


KOK = Path(__file__).resolve().parent.parent


class KurulumDosyasiTesti(unittest.TestCase):
    """KafeKamera.iss, studio_kurulum.py, yollar.py ve derleme dosyaları birbirine uyar."""

    def setUp(self):
        import re

        self.iss = (KOK / "kurulum" / "KafeKamera.iss").read_text(encoding="utf-8")
        self.tanim = dict(re.findall(r'^#define (\w+) "([^"]*)"', self.iss, flags=re.M))

    def test_surum_programla_ayni(self):
        self.assertEqual(self.tanim["Surum"], kurulum.yollar.SURUM)

    def test_lisans_kodu_ortamla_verilir_ve_ayni_komut(self):
        self.assertIn("KAFE_LISANS_KODU", kurulum.VERIFY)
        self.assertIn("OrtamYaz('KAFE_LISANS_KODU', Kod)", self.iss)
        self.assertIn("OrtamSil('KAFE_LISANS_KODU', 0)", self.iss)
        self.assertNotIn("SaveStringToFile(Isaret + '\\studio-lisans.txt', Kod", self.iss)  # işarete kod yazılmaz

    def test_veri_klasoru_ayni(self):
        self.assertIn("{localappdata}\\KafeKamera", self.iss)
        self.assertIn('"KafeKamera"', (KOK / "yollar.py").read_text(encoding="utf-8"))

    def test_kurulum_exe_si_derlemenin_ciktisi(self):
        derle = (KOK / "kurulum" / "derle.cmd").read_bytes()
        self.assertIn(b"\r\n", derle)
        self.assertNotIn(b"\n", derle.replace(b"\r\n", b""))  # CRLF
        self.assertIn(b"--distpath dist\\arayuzsuz", derle)
        self.assertEqual(self.tanim["Kaynak"], "..\\dist\\arayuzsuz\\KafeKamera.exe")

    def test_sahne_yoksa_derleme_anlasilir_hatayla_durur(self):
        spec = (KOK / "kurulum" / "KafeKamera.spec").read_text(encoding="utf-8")
        self.assertIn("raise SystemExit(f\"Hazır sahne yok", spec)
        self.assertIn(b"Hazir sahne yok", (KOK / "kurulum" / "derle.cmd").read_bytes())
        self.assertIn("*.pmod", (KOK / ".gitignore").read_text(encoding="utf-8").splitlines())

    def test_exe_torch_ve_ultralytics_icermez(self):
        spec = (KOK / "kurulum" / "KafeKamera.spec").read_text(encoding="utf-8")
        for ad in ("torch", "torchvision", "ultralytics"):
            self.assertIn(f'"{ad}"', spec.split("excludes=")[1].split("]")[0])
        self.assertNotIn("torch", (KOK / "requirements.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
