"""Örnek videolarda iki ölçüm (geliştirme aracı):
  1. yüz büyüklüğü: algılanan kişilerin yüzü kaç piksel (yüz eşleştirmenin işe yarayıp yaramayacağını görmek için;
     yaygın yüz özeti modelleri en az ~64 px yüz ister). Yüz özeti HESAPLANMAZ; yalnızca iskelet noktalarından genişlik.
  2. kıyafet rengi özetinin ayırt ediciliği: aynı izin iki yarısı ile farklı izler arasındaki benzerlik dağılımı.

  .venv\\Scripts\\python egitim\\olc_gorunum_yuz.py <algılama önbellek klasörü>   (veri\\onbellek: örnek analizden sonra)
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

kok = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(kok))
import analiz  # noqa: E402
import gorunum  # noqa: E402

onbellek = Path(sys.argv[1])
yuz, ayni, farkli = [], [], []
for kod in ("salon", "teras", "kasa", "bahce"):
    veri = json.loads((onbellek / f"{kod}.json").read_text(encoding="utf-8"))
    video = kok / "ornekler" / "videolar" / f"{kod}.mp4"
    for kr in veri["kareler"]:
        for d in kr["d"]:
            k = d["k"]
            if k[3][2] > 0.35 and k[4][2] > 0.35:
                yuz.append(abs(k[3][0] - k[4][0]))
            elif k[1][2] > 0.35 and k[2][2] > 0.35:
                yuz.append(2.3 * abs(k[1][0] - k[2][0]))
    analiz.gorunum_ekle(video, veri)
    izler = defaultdict(list)
    for kr in veri["kareler"]:
        for d in kr["d"]:
            if d.get("g") is not None:
                izler[d["id"]].append(d["g"])
    yarim = {}
    for pid, gs in izler.items():
        if len(gs) >= 10:
            h = len(gs) // 2
            a, b = gorunum.Ortalama(100), gorunum.Ortalama(100)
            for g in gs[:h]:
                a.ekle(g)
            for g in gs[h:]:
                b.ekle(g)
            yarim[pid] = (a.deger(), b.deger())
            ayni.append(gorunum.benzerlik(*yarim[pid]))
    ids = list(yarim)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            farkli.append(gorunum.benzerlik(yarim[ids[i]][1], yarim[ids[j]][0]))

yuz = np.array(yuz)
print(f"yüz genişliği (iskelet noktalarından; 720p): n={len(yuz)}, ortanca {np.median(yuz):.0f} px, "
      f">=32 px %{100 * np.mean(yuz >= 32):.1f}, >=64 px %{100 * np.mean(yuz >= 64):.1f}, >=112 px %{100 * np.mean(yuz >= 112):.1f}")
ayni, farkli = np.array(ayni), np.array(farkli)
print(f"aynı iz (iki yarı): n={len(ayni)}, ortanca {np.median(ayni):.3f}, %10 {np.percentile(ayni, 10):.3f}, en az {ayni.min():.3f}")
print(f"farklı izler: n={len(farkli)}, ortanca {np.median(farkli):.3f}, %90 {np.percentile(farkli, 90):.3f}, en çok {farkli.max():.3f}")
for e in (0.7, 0.75, 0.8, 0.85, 0.9):
    print(f"  eşik {e}: aynı kişiyi tanıma %{100 * np.mean(ayni >= e):.0f}, farklı kişiyi karıştırma %{100 * np.mean(farkli >= e):.1f}")
