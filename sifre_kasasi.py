"""Kamera şifresi için isteğe bağlı saklama: yalnızca kamera ayarında "Şifreyi bu bilgisayarda sakla" açıksa.

Şifre Windows DPAPI ile, bu Windows kullanıcısına bağlı olarak şifrelenir ve veri klasöründeki sifreler/<kod>.dpapi
dosyasına yazılır. Kamera ayar dosyasına, günlüğe, komut satırına ve API yanıtlarına hiç yazılmaz. Seçenek kapatılınca ya da
kamera silinince dosya silinir. Başka bir Windows kullanıcısı ya da başka bir bilgisayar dosyayı çözemez.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

import yollar

_ENTROPI = b"KafeKamera kamera sifresi v1"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(veri: bytes) -> _Blob:
    tampon = ctypes.create_string_buffer(veri, len(veri))
    b = _Blob(len(veri), ctypes.cast(tampon, ctypes.POINTER(ctypes.c_char)))
    b._tampon = tampon  # çöp toplamaya karşı
    return b


def _cagir(islev: str, veri: bytes) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    giris, cikis, ent = _blob(veri), _Blob(), _blob(_ENTROPI)
    f = getattr(crypt32, islev)
    if islev == "CryptProtectData":
        ok = f(ctypes.byref(giris), None, ctypes.byref(ent), None, None, 0x1, ctypes.byref(cikis))  # UI yok
    else:
        ok = f(ctypes.byref(giris), None, ctypes.byref(ent), None, None, 0x1, ctypes.byref(cikis))
    if not ok:
        raise OSError(ctypes.get_last_error(), "DPAPI")
    try:
        return ctypes.string_at(cikis.pbData, cikis.cbData)
    finally:
        kernel32.LocalFree(cikis.pbData)


def klasor() -> Path:
    return yollar.VERI / "sifreler"


def _yol(kod: str) -> Path:
    return klasor() / f"{kod}.dpapi"


def sakla(kod: str, sifre: str) -> None:
    if os.name != "nt":
        raise OSError("Şifre saklama yalnızca Windows'ta")
    klasor().mkdir(parents=True, exist_ok=True)
    veri = _cagir("CryptProtectData", sifre.encode("utf-8"))
    gecici = _yol(kod).with_suffix(".tmp")
    gecici.write_bytes(veri)
    os.replace(gecici, _yol(kod))


def oku(kod: str) -> str | None:
    p = _yol(kod)
    if os.name != "nt" or not p.is_file():
        return None
    try:
        return _cagir("CryptUnprotectData", p.read_bytes()).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def sil(kod: str) -> None:
    try:
        _yol(kod).unlink(missing_ok=True)
    except OSError:
        pass


def var_mi(kod: str) -> bool:
    return _yol(kod).is_file()
