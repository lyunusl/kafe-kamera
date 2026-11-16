"""Geliştirme aracı: bir videoyu döngüyle RTSP (H.264, TCP üzerinden) yayınlayan küçük, yerel bir deneme sunucusu.
Kayıt cihazı gibi Digest kimlik doğrulaması ister. Sistem hizmeti kurmaz; durdurunca hiçbir şey kalmaz.

  .venv\\Scripts\\python egitim\\rtsp_deneme_sunucusu.py <video> <port> <kullanıcı> <şifre> [--yol /Streaming/Channels/102]

Kodlamayı imageio-ffmpeg'in ffmpeg'i yapar (RTP paketlerini yerel bir UDP portuna gönderir); bu sunucu RTSP isteklerini
yanıtlar (OPTIONS, DESCRIBE, SETUP yalnızca TCP interleaved, PLAY, GET_PARAMETER, TEARDOWN) ve paketleri bağlı istemcilere
iletir. Yanlış yol 404, yanlış kimlik 401 döner (panelin hata ayrımı bununla denenir).
"""
from __future__ import annotations

import hashlib
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time


def md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


class Sunucu:
    def __init__(self, video: str, port: int, kul: str, sif: str, yol: str):
        self.port, self.kul, self.sif, self.yol = port, kul, sif, yol
        self.realm, self.nonce = "KafeDeneme", os.urandom(8).hex()
        self.istemciler: list[socket.socket] = []
        self.kilit = threading.Lock()
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind(("127.0.0.1", 0))
        udp_port = self.udp.getsockname()[1]
        self.gecici = tempfile.mkdtemp(prefix="kafe-rtsp-")
        sdp = os.path.join(self.gecici, "akis.sdp")
        import imageio_ffmpeg

        self.ffmpeg = subprocess.Popen(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-re", "-stream_loop", "-1", "-i", video, "-an",
             "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency", "-g", "12", "-pix_fmt", "yuv420p",
             "-f", "rtp", "-sdp_file", sdp, f"rtp://127.0.0.1:{udp_port}?pkt_size=1200"],
            stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for _ in range(100):
            if os.path.isfile(sdp) and os.path.getsize(sdp) > 0:
                break
            time.sleep(0.1)
        time.sleep(0.3)
        satirlar = [s for s in open(sdp, encoding="ascii").read().splitlines() if s and not s.startswith("a=control")]
        out = []
        for s in satirlar:
            if s.startswith("c="):
                s = "c=IN IP4 0.0.0.0"
            if s.startswith("m=video"):
                out.append("a=control:*")
                s = "m=video 0 RTP/AVP 96"
            out.append(s)
        out.append("a=control:trackID=0")
        self.sdp = "\r\n".join(out) + "\r\n"
        threading.Thread(target=self._dagit, daemon=True).start()

    def _dagit(self):
        while True:
            try:
                paket, _ = self.udp.recvfrom(65536)
            except OSError:
                return
            cerceve = b"$\x00" + len(paket).to_bytes(2, "big") + paket
            with self.kilit:
                for c in list(self.istemciler):
                    try:
                        c.sendall(cerceve)
                    except OSError:
                        self.istemciler.remove(c)

    def _yetkili(self, yontem: str, b: dict) -> bool:
        a = b.get("authorization", "")
        if not a.lower().startswith("digest"):
            return False
        al = dict(re.findall(r'(\w+)="?([^",]*)"?', a))
        ha1, ha2 = md5(f"{self.kul}:{self.realm}:{self.sif}"), md5(f"{yontem}:{al.get('uri', '')}")
        if al.get("qop"):
            beklenen = md5(f"{ha1}:{al.get('nonce')}:{al.get('nc')}:{al.get('cnonce')}:{al.get('qop')}:{ha2}")
        else:
            beklenen = md5(f"{ha1}:{al.get('nonce')}:{ha2}")
        return al.get("username") == self.kul and al.get("response") == beklenen

    def _istemci(self, c: socket.socket):
        oturum = os.urandom(4).hex()
        veri = b""
        try:
            while True:
                while b"\r\n\r\n" not in veri:
                    p = c.recv(4096)
                    if not p:
                        return
                    veri += p
                    while veri.startswith(b"$") and len(veri) >= 4:  # istemcinin RTCP paketleri
                        n = int.from_bytes(veri[2:4], "big")
                        if len(veri) < 4 + n:
                            break
                        veri = veri[4 + n:]
                bas, veri = veri.split(b"\r\n\r\n", 1)
                satirlar = bas.decode("utf-8", "replace").split("\r\n")
                yontem, url = satirlar[0].split(" ")[:2]
                b = {k.strip().lower(): v.strip() for k, v in (s.split(":", 1) for s in satirlar[1:] if ":" in s)}
                cseq = b.get("cseq", "0")

                def yanit(kod, ek="", govde=""):
                    metin = {200: "OK", 401: "Unauthorized", 404: "Not Found", 461: "Unsupported Transport"}.get(kod, "OK")
                    s = f"RTSP/1.0 {kod} {metin}\r\nCSeq: {cseq}\r\n{ek}"
                    if govde:
                        s += f"Content-Length: {len(govde)}\r\n"
                    c.sendall((s + "\r\n" + govde).encode())

                if yontem == "OPTIONS":
                    yanit(200, "Public: OPTIONS, DESCRIBE, SETUP, PLAY, TEARDOWN, GET_PARAMETER\r\n")
                    continue
                if not self._yetkili(yontem, b):
                    yanit(401, f'WWW-Authenticate: Digest realm="{self.realm}", nonce="{self.nonce}"\r\n')
                    continue
                yol = re.sub(r"^rtsp://[^/]+", "", url).split("?")[0].rstrip("/")
                if yontem in ("DESCRIBE", "SETUP", "PLAY") and not yol.startswith(self.yol.rstrip("/")):
                    yanit(404)
                    continue
                if yontem == "DESCRIBE":
                    yanit(200, f"Content-Base: {url.rstrip('/')}/\r\nContent-Type: application/sdp\r\n", self.sdp)
                elif yontem == "SETUP":
                    if "TCP" not in b.get("transport", ""):
                        yanit(461)
                        continue
                    yanit(200, f"Transport: RTP/AVP/TCP;unicast;interleaved=0-1\r\nSession: {oturum};timeout=60\r\n")
                elif yontem == "PLAY":
                    yanit(200, f"Session: {oturum}\r\nRange: npt=0.000-\r\n")
                    with self.kilit:
                        self.istemciler.append(c)
                elif yontem == "TEARDOWN":
                    yanit(200, f"Session: {oturum}\r\n")
                    return
                else:
                    yanit(200, f"Session: {oturum}\r\n")
        except (OSError, ValueError):
            pass
        finally:
            with self.kilit:
                if c in self.istemciler:
                    self.istemciler.remove(c)
            c.close()

    def calis(self):
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", self.port))
        s.listen(8)
        print(f"hazir rtsp://127.0.0.1:{self.port}{self.yol}", flush=True)
        try:
            while True:
                c, _ = s.accept()
                threading.Thread(target=self._istemci, args=(c,), daemon=True).start()
        finally:
            self.ffmpeg.terminate()
            self.ffmpeg.wait(10)
            import shutil

            shutil.rmtree(self.gecici, ignore_errors=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    yol = a[a.index("--yol") + 1] if "--yol" in a else "/Streaming/Channels/102"
    srv = Sunucu(a[0], int(a[1]), a[2], a[3], yol)
    try:
        srv.calis()
    except KeyboardInterrupt:
        pass
    finally:
        srv.ffmpeg.terminate()
