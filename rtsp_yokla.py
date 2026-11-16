"""Kamera adresine ulaşılamadığında nedeni ayırır: ağ (ulaşılamıyor), kimlik (kullanıcı adı / şifre), yol (kanal ya da akış
yok) ya da görüntü biçimi (codec). Hem panelde (bağlantı denemesi) hem AugeLab Studio'daki motorda kullanılır.

Adres şifre içerebilir: bu modül adresi ve kimlik bilgisini hiçbir yere yazmaz; döndürdüğü metinde de bulunmaz.
RTSP için önce TCP bağlantısı, sonra DESCRIBE isteği denenir (Basic ve Digest kimlik doğrulaması: kayıt cihazlarının çoğu
Digest ister). HTTP için yalnızca bağlantı ve durum kodu.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import socket
from urllib.parse import unquote, urlsplit

ZAMAN_ASIMI = 4.0


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _istek(sock: socket.socket, satirlar: list[str]) -> tuple[int, dict]:
    sock.sendall(("\r\n".join(satirlar) + "\r\n\r\n").encode("utf-8"))
    veri = b""
    while b"\r\n\r\n" not in veri and len(veri) < 65536:
        parca = sock.recv(4096)
        if not parca:
            break
        veri += parca
    bas = veri.split(b"\r\n\r\n", 1)[0].decode("utf-8", "replace").split("\r\n")
    m = re.match(r"RTSP/1\.\d\s+(\d{3})", bas[0] if bas else "")
    basliklar = {}
    for s in bas[1:]:
        if ":" in s:
            k, v = s.split(":", 1)
            basliklar.setdefault(k.strip().lower(), []).append(v.strip())
    return (int(m.group(1)) if m else 0), basliklar


def _digest(baslik: str, kul: str, sif: str, yontem: str, uri: str) -> str | None:
    alan = dict(re.findall(r'(\w+)="?([^",]*)"?', baslik))
    if "nonce" not in alan:
        return None
    realm, nonce = alan.get("realm", ""), alan["nonce"]
    ha1, ha2 = _md5(f"{kul}:{realm}:{sif}"), _md5(f"{yontem}:{uri}")
    if "auth" in alan.get("qop", ""):
        nc, cnonce = "00000001", os.urandom(8).hex()
        yanit = _md5(f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}")
        return (f'Digest username="{kul}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{yanit}", '
                f'qop=auth, nc={nc}, cnonce="{cnonce}"')
    yanit = _md5(f"{ha1}:{nonce}:{ha2}")
    return f'Digest username="{kul}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{yanit}"'


def yokla(adres: str) -> tuple[str, str]:
    """Dönüş: (tür, Türkçe açıklama). tür: ulasilamiyor | kimlik | yol | acik (sunucu akışı veriyor; sorun görüntüde
    olabilir) | bilinmiyor. Açıklamada adres ya da kimlik bilgisi yoktur."""
    try:
        u = urlsplit(adres)
        host, port = u.hostname, u.port or (554 if u.scheme == "rtsp" else 80)
    except ValueError:
        return "bilinmiyor", "Kamera adresi okunamadı. Adresi kontrol edin."
    if not host:
        return "bilinmiyor", "Kamera adresi okunamadı. Adresi kontrol edin."
    try:
        sock = socket.create_connection((host, port), timeout=ZAMAN_ASIMI)
    except OSError:
        return "ulasilamiyor", (f"Kameraya ya da kayıt cihazına ulaşılamıyor ({host}:{port}). IP adresi ve port doğru mu, "
                                "bilgisayar aynı ağda mı, cihaz açık mı?")
    try:
        sock.settimeout(ZAMAN_ASIMI)
        if u.scheme != "rtsp":
            return "acik", "Cihaza bağlanılabiliyor."
        kul, sif = unquote(u.username or ""), unquote(u.password or "")
        uri = f"rtsp://{host}:{port}{u.path or '/'}" + (f"?{u.query}" if u.query else "")
        cseq = 1

        def describe(yetki: str | None):
            nonlocal cseq
            s = [f"DESCRIBE {uri} RTSP/1.0", f"CSeq: {cseq}", "Accept: application/sdp", "User-Agent: KafeKamera"]
            if yetki:
                s.append(f"Authorization: {yetki}")
            cseq += 1
            return _istek(sock, s)

        kod, b = describe(None)
        if kod == 401 and (kul or sif):
            yetki = None
            for w in b.get("www-authenticate", []):
                if w.lower().startswith("digest"):
                    yetki = _digest(w, kul, sif, "DESCRIBE", uri)
                    break
            if yetki is None:
                yetki = "Basic " + base64.b64encode(f"{kul}:{sif}".encode("utf-8")).decode("ascii")
            kod, b = describe(yetki)
        if kod == 200:
            return "acik", "Kayıt cihazı akışı veriyor."
        if kod == 401:
            return "kimlik", "Kayıt cihazı kullanıcı adını ya da şifreyi kabul etmedi. Kullanıcı adını ve şifreyi kontrol edin."
        if kod in (403,):
            return "kimlik", "Bu kullanıcının bu kanalı izleme izni yok (kayıt cihazında kullanıcı yetkilerini kontrol edin)."
        if kod in (404, 454):
            return "yol", "Kayıt cihazında bu kanal ya da akış bulunamadı. Kanal numarasını ve ana/alt akış seçimini kontrol edin."
        if kod == 0:
            return "bilinmiyor", "Cihaz bağlantıyı kabul etti ama RTSP yanıtı vermedi. Port numarası RTSP portu mu (genelde 554)?"
        return "bilinmiyor", f"Kayıt cihazı isteği reddetti (RTSP {kod})."
    except OSError:
        return "bilinmiyor", "Cihaz bağlantıyı kabul etti ama yanıt vermedi. Port numarasını kontrol edin."
    finally:
        sock.close()


def neden(adres: str, acildi: bool) -> str:
    """OpenCV akışı açamadığında (ya da açıp görüntü alamadığında) kullanıcıya gösterilecek Türkçe neden."""
    tur, metin = yokla(adres)
    if tur == "acik":
        return ("Akış açıldı ama görüntü çözülemedi: kayıt cihazının bu akışı desteklenmeyen bir biçimde (ör. H.265 ya da "
                "MJPEG alt akış) veriyor olabilir. Kanalın alt akışını H.264 yapın ya da ana akışı deneyin.") if acildi else (
                "Kayıt cihazı akışı veriyor ama görüntü açılamadı. Alt akışı H.264 yapıp yeniden deneyin.")
    return metin
