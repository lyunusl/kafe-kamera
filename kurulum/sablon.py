"""Geliştirici aracı: programla gelen hazır sahneyi (kurulum/sahne/kafe-kamera.pmod) yeniden üretir.

Sahne dosyası yalnızca Studio penceresindeki Dosya → Farklı Kaydet ile kaydedilir. Bu yüzden sahne bir kez, geliştirici
bilgisayarında açık Studio'da kurulur:

    1. AugeLab Studio'yu açın (MCP varsayılan 127.0.0.1:8765 adresinde açık olmalı).
    2. python kurulum/sablon.py      → Kafe bloklarını Studio'ya kaydeder ve sahneyi YENİ bir sekmede kurar
       (mcp paketi gerekir: requirements-gelistirme.txt). Açık diğer belgelere dokunulmaz.
    3. Studio'da o sekmeyi Dosya → Farklı Kaydet ile kurulum/sahne/kafe-kamera.pmod olarak kaydedin.

Sahne: "Kafe Kamera İşi" metin girişi → Kafe Kaynak → Kafe Algılama. Metin girişinin değeri arayüzsüz koşuda yok sayılır
(iş ortam değişkeninden gelir: kafe_motor.blok.ORTAM_IS).

Blok tanımları (studio_blok.py) değiştiğinde sahneyi yeniden üretmek gerekmez: bloklar sahneye adlarıyla bağlıdır ve panel
blok dosyalarını her çalıştırmada günceller. Yalnızca giriş/çıkış sayısı ya da sırası değişirse yeniden üretin.
Kullanıcı bilgisayarında bu araç çalışmaz; orada sahne Studio penceresi açılmadan çalıştırılır (studio.py).
"""
from __future__ import annotations

import asyncio
import json
import secrets
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import studio_blok  # noqa: E402

ADRES = "http://127.0.0.1:8765/mcp"
OP_METIN = "119"  # String Input
IS_BASLIGI = "Kafe Kamera İşi"
SAHNE_ISI = "KAFE"  # arayüzsüz koşuda yok sayılır: iş ortam değişkeninden gelir (kafe_motor.blok.ORTAM_IS)
HEDEF = Path(__file__).resolve().parent / "sahne" / "kafe-kamera.pmod"


def _anahtar() -> str:
    return "kafe-" + secrets.token_hex(12)


async def cagir(arac: str, arg: dict[str, Any]) -> dict[str, Any]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with streamable_http_client(ADRES) as (oku, yaz, *_):
        async with ClientSession(oku, yaz) as oturum:
            await oturum.initialize()
            sonuc = await oturum.call_tool(arac, arg)
    yuk = getattr(sonuc, "structuredContent", None) or getattr(sonuc, "structured_content", None) or {}
    if not yuk and sonuc.content:
        try:
            yuk = json.loads(getattr(sonuc.content[0], "text", "") or "{}")
        except ValueError:
            yuk = {"error": getattr(sonuc.content[0], "text", "")}
    if getattr(sonuc, "isError", False) or getattr(sonuc, "is_error", False) or yuk.get("error"):
        raise SystemExit(f"{arac}: {json.dumps(yuk.get('error') or yuk, ensure_ascii=False)[:500]}")
    veri = dict(yuk.get("data") or {})
    if yuk.get("operation") and "operation" not in veri:
        veri["operation"] = yuk["operation"]
    return veri


async def bekle(veri: dict[str, Any], sinir_sn: float) -> dict[str, Any]:
    is_ = veri.get("operation") or veri
    bas = time.monotonic()
    while is_.get("state") in ("queued", "running") and time.monotonic() - bas < sinir_sn:
        dahasi = await cagir("operation.get", {"operationId": is_["id"], "waitTimeoutMs": 15000, "updateLimit": 1})
        is_ = dahasi.get("operation") or dahasi
    return is_


def sahne_kaynagi() -> str:
    b = studio_blok
    return "\n".join([
        f"is_ = node('{OP_METIN}', title='{IS_BASLIGI}')",
        f"kaynak = node('{b.KAYNAK_OP}', title='{b.KAYNAK_BASLIK}')",
        f"algila = node('{b.ALGILA_OP}', title='{b.ALGILA_BASLIK}')",
        f"is_.params['threshold'] = '{SAHNE_ISI}'",
        "connect(is_.out[0], kaynak.in_[0])",       # Is
        "connect(kaynak.out[0], algila.in_[0])",    # Image
        "connect(is_.out[0], algila.in_[1])",       # Is
        "connect(kaynak.out[1], algila.in_[2])",    # Sira
        "connect(kaynak.out[2], algila.in_[3])",    # Zaman
        "connect(kaynak.out[3], algila.in_[4])",    # Bitti
        "connect(kaynak.out[4], algila.in_[5])",    # Kaynak (Durum)
    ]) + "\n"


async def main() -> None:
    is_ = await bekle(await cagir("node.custom.create", {"specifications": studio_blok.TANIMLAR, "replaceExisting": True,
                                                          "idempotencyKey": _anahtar()}), 120)
    if is_.get("state") != "succeeded":
        raise SystemExit(f"Kafe blokları Studio'ya eklenemedi: {is_.get('error') or is_.get('state')}")
    veri = await cagir("graph.program", {"target": "create_new", "expectedRevision": "none", "idempotencyKey": _anahtar(),
                                         "source": sahne_kaynagi()})
    print(json.dumps({k: veri.get(k) for k in ("scene", "document", "documentId", "revision", "title") if k in veri},
                     ensure_ascii=False))
    print("Sahne Studio'da yeni bir sekmede kuruldu. Studio'da bu sekmeyi Dosya → Farklı Kaydet ile şuraya kaydedin:\n"
          "  kurulum/sahne/kafe-kamera.pmod")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
