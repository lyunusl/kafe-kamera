"""cikti/*/sonuc.json dosyalarından tek sayfalık panel (panel.html) ve Excel raporu üretir."""
from __future__ import annotations

import json
from pathlib import Path

import yollar

HTML = r"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:,"><title>Kafe Kamera Analizi</title>
<style>
:root{--bg:#0b1020;--kart:#141b30;--cizgi:#26304d;--yazi:#e8ecf5;--soluk:#93a0bd;--sari:#fde035;--yesil:#22c55e;--mavi:#3ec6d8;--turuncu:#ff8c28;--kirmizi:#f0463c;--mor:#c878c8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--yazi);font:15px/1.45 "Segoe UI",system-ui,sans-serif}
header{padding:22px 28px 10px;display:flex;align-items:flex-end;gap:18px;flex-wrap:wrap}
h1{margin:0;font-size:26px;letter-spacing:-.3px}header p{margin:0;color:var(--soluk)}
.baglanti{color:var(--yazi);text-decoration:none;border:1.5px solid var(--cizgi);background:var(--kart);border-radius:999px;padding:6px 14px;font-weight:600;font-size:13px}.baglanti:first-of-type{margin-left:auto}
.rozet{padding:6px 14px;border-radius:999px;border:1.5px solid var(--yesil);color:var(--yesil);font-weight:600;font-size:13px}
nav{display:flex;gap:8px;padding:8px 28px 0;flex-wrap:wrap}
nav button{background:var(--kart);color:var(--soluk);border:1.5px solid var(--cizgi);border-radius:10px;padding:9px 18px;font:600 15px inherit;cursor:pointer}
nav button.sec{color:#111;background:var(--sari);border-color:var(--sari)}
main{padding:16px 28px 40px;display:grid;gap:16px;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr)}
.kart{background:var(--kart);border:1px solid var(--cizgi);border-radius:16px;padding:16px;min-width:0}
.kart h2{margin:0 0 12px;font-size:13px;letter-spacing:1.2px;text-transform:uppercase;color:var(--soluk)}
.tam{grid-column:1/-1}video{width:100%;border-radius:10px;display:block;background:#000}
.kpi{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.kpi div{background:#0f1528;border:1px solid var(--cizgi);border-radius:12px;padding:12px 14px}
.kpi b{display:block;font-size:30px;line-height:1.1;font-variant-numeric:tabular-nums}.kpi span{color:var(--soluk);font-size:13px}
.kpi .u b{color:var(--kirmizi)}.kpi .i b{color:var(--yesil)}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th{color:var(--soluk);font-weight:600;font-size:12px;letter-spacing:.8px;text-transform:uppercase;text-align:left;padding:6px 8px;border-bottom:1px solid var(--cizgi)}
td{padding:8px;border-bottom:1px solid #1c2440}td b{white-space:nowrap}td.s,th.s{text-align:right}
.cubuk{height:10px;border-radius:5px;background:#0f1528;overflow:hidden;min-width:90px}.cubuk i{display:block;height:100%;background:var(--sari);border-radius:5px}
.uy{display:flex;gap:10px;align-items:center;padding:9px 12px;border-radius:10px;background:rgba(240,70,60,.12);border:1px solid rgba(240,70,60,.45);margin-bottom:8px;cursor:pointer}
.on{padding:9px 12px 9px 14px;border-left:3px solid var(--sari);background:#0f1528;border-radius:0 10px 10px 0;margin-bottom:8px}
.uy b{color:var(--kirmizi);font-variant-numeric:tabular-nums}.yok{color:var(--soluk)}
.harita{position:relative}.harita img{width:100%;display:block;border-radius:10px;filter:brightness(.62)}.harita svg{position:absolute;inset:0;width:100%;height:100%}
.gantt{display:grid;grid-template-columns:76px 1fr;gap:6px 10px;align-items:center}.gantt .iz{position:relative;height:22px;background:#0f1528;border-radius:6px}
.gantt .iz i{position:absolute;top:2px;bottom:2px;border-radius:5px;background:var(--mavi)}.gantt .iz i.b{background:var(--sari)}.gantt .iz i.u{background:var(--kirmizi)}.gantt .iz em{position:absolute;top:-2px;bottom:-2px;width:3px;background:var(--turuncu);border-radius:2px}
.yig{display:flex;height:22px;border-radius:6px;overflow:hidden;background:#0f1528}.yig i{display:block;height:100%}
.aciklama{display:flex;gap:14px;flex-wrap:wrap;color:var(--soluk);font-size:13px;margin-top:10px}.aciklama i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.not{color:var(--soluk);font-size:13px;padding:0 28px 30px}
@media(max-width:980px){main{grid-template-columns:1fr}}
</style></head><body>
<header><div><h1>Kafe Kamera Analizi</h1><p>Güvenlik kamerasından masa, müşteri ve çalışan ölçümleri</p></div><a class="baglanti" href="/">Başlangıç</a><a class="baglanti" href="/bolge_ciz.html">Kamera ekle / ayarla</a><a class="baglanti" href="rapor.xlsx" download>Excel raporu</a><div class="rozet">Yüzler gizli · kimlik tanıma yok</div></header>
<nav id="nav"></nav><main id="ana"></main>
<p class="not" id="ornekNot" hidden>Örnek videolar 15–30 saniyelik olduğu için süreler saniye olarak görünür; gerçek kamera akışında aynı ölçümler dakika ve saat olarak birikir. Örnek görüntüler yapay zekâ ile üretildi, gerçek kişi yoktur.</p>
<script>
const V=__VERI__;
const saat=x=>{x=Math.round(x)%86400;return String(Math.floor(x/3600)).padStart(2,"0")+":"+String(Math.floor(x%3600/60)).padStart(2,"0")};
const sn=x=>x==null?"–":(x>=60?Math.floor(x/60)+" dk "+Math.round(x%60)+" sn":(Math.round(x*10)/10+" sn").replace(".",","));
const yz=x=>x==null?"–":("%"+String(Math.round(x*10)/10).replace(".",","));
const el=(h)=>{const d=document.createElement("div");d.innerHTML=h;return d.firstElementChild};
function ciz(k){
  const c=V[k],o=c.ozet,ana=document.getElementById("ana");ana.innerHTML="";
  const masaVar=c.masalar.length>0,kuyrukVar=o.kuyruk_en_cok!=null;
  let kpi="";
  if(masaVar)kpi+=`<div><b>${o.oturum}</b><span>masa oturumu</span></div><div><b>${sn(o.ort_oturma)}</b><span>ortalama oturma</span></div><div><b>${yz(o.doluluk)}</b><span>ortalama doluluk</span></div><div class="i"><b>${sn(o.ort_bekleme)}</b><span>oturma → ilk garson</span></div>`;
  if(kuyrukVar)kpi+=`<div><b>${o.kuyruk_en_cok}</b><span>en uzun kuyruk (kişi)</span></div><div><b>${sn(o.kuyruk_ort_bekleme)}</b><span>ortalama sıra bekleme</span></div><div class="u"><b>${o.donen}</b><span>sıraya girmeden çıkan</span></div>`;
  kpi+=`<div><b>${o.musteri}</b><span>izlenen müşteri</span></div><div><b>${o.calisan}</b><span>çalışan</span></div><div class="u"><b>${o.uyari}</b><span>uyarı</span></div>`;
  ana.append(el(`<section class="kart"><h2>${c.ad} · işaretli görüntü</h2><video id="vid" src="${c.klasor}/isaretli.mp4" controls muted loop autoplay playsinline></video></section>`));
  ana.append(el(`<section class="kart"><h2>Özet · ${sn(c.sure)} görüntü${c.saat_bas!=null?" ("+saat(c.saat_bas)+"–"+saat(c.saat_bas+c.sure)+")":""}${c.calisan_renkleri?` · çalışan rengi: ${c.calisan_renkleri.join(", ")}`:""}</h2><div class="kpi">${kpi}</div></section>`));
  const uy=c.uyarilar.length?c.uyarilar.map(u=>`<div class="uy" data-t="${u.t}"><b>${sn(u.t)}</b><span>${u.metin}</span></div>`).join(""):`<div class="yok">Bu görüntüde uyarı yok.</div>`;
  ana.append(el(`<section class="kart"><h2>Öneriler</h2>${c.oneriler.map(x=>`<div class="on">${x}</div>`).join("")||'<div class="yok">Bu görüntü için öneri yok.</div>'}</section>`));
  ana.append(el(`<section class="kart"><h2>Uyarılar</h2>${uy}</section>`));
  // harita
  const mx=Math.max(1e-6,...c.isi.flat());let isi="";
  c.isi.forEach((s,y)=>s.forEach((v,x)=>{if(v>mx*0.06)isi+=`<rect x="${x/48*160}" y="${y/27*90}" width="${160/48}" height="${90/27}" fill="#fde035" opacity="${Math.min(.8,.18+.62*v/mx)}"/>`}));
  let pol=c.masalar.map(m=>{const p=m.poly.map(q=>q[0]*160+","+q[1]*90).join(" ");const cx=m.poly.reduce((a,q)=>a+q[0],0)/m.poly.length*160,cy=m.poly.reduce((a,q)=>a+q[1],0)/m.poly.length*90;
    return `<polygon points="${p}" fill="rgba(62,198,216,${.10+.4*m.doluluk/100})" stroke="#3ec6d8" stroke-width=".5"/><text x="${cx}" y="${cy-1}" text-anchor="middle" font-size="5" font-weight="700" fill="#fff">${m.ad}</text><text x="${cx}" y="${cy+5}" text-anchor="middle" font-size="4.6" font-weight="700" fill="#fde035">${yz(m.doluluk)}</text>`}).join("");
  pol+=c.bolgeler.map(b=>`<polygon points="${b.poly.map(q=>q[0]*160+","+q[1]*90).join(" ")}" fill="rgba(200,120,200,.14)" stroke="#c878c8" stroke-width=".5"/><text x="${b.poly[0][0]*160+2}" y="${b.poly[0][1]*90+7}" font-size="5" font-weight="700" fill="#fff">${b.ad}</text>`).join("");
  ana.append(el(`<section class="kart"><h2>Yoğunluk haritası</h2><div class="harita"><img src="${c.klasor}/kare.jpg"><svg viewBox="0 0 160 90" preserveAspectRatio="none">${isi}${pol}</svg></div><div class="aciklama"><span><i style="background:#fde035"></i>müşterilerin en çok durduğu yerler</span><span><i style="background:#3ec6d8"></i>masa bölgesi ve doluluk</span></div></section>`));
  if(masaVar){
    const sira=[...c.masalar].sort((a,b)=>b.doluluk-a.doluluk);
    ana.append(el(`<section class="kart"><h2>Masa talebi</h2><table><tr><th>Masa</th><th class="s">Oturum</th><th>Doluluk</th><th class="s">Ort. süre</th><th class="s">Kişi</th><th class="s">Kirli kaldı</th><th class="s">Temizlik</th></tr>${sira.map(m=>`<tr><td><b>${m.ad}</b></td><td class="s">${m.oturum}</td><td><div style="display:flex;gap:8px;align-items:center"><div class="cubuk" style="flex:1"><i style="width:${m.doluluk}%"></i></div>${yz(m.doluluk)}</div></td><td class="s">${m.oturum?sn(m.ort_sure):"–"}</td><td class="s">${m.kisi}</td><td class="s">${m.kirli_sn>0?sn(m.kirli_sn):"–"}</td><td class="s">${m.temizlik_suresi!=null?sn(m.temizlik_suresi):"–"}</td></tr>`).join("")}</table></section>`));
    const g=c.masalar.map(m=>{const b=c.oturumlar.filter(o=>o.masa==m.ad).map(o=>{const s=o.bas/c.sure*100,w=Math.max(.8,o.sure/c.sure*100);const cls=o.uyari&&o.ilk_temas==null?"u":(o.ilk_temas==null?"b":"");
      return `<i class="${cls}" style="left:${s}%;width:${w}%" title="${o.kisi} kişi · ${sn(o.sure)}"></i>`+(o.ilk_temas!=null?`<em style="left:${o.ilk_temas/c.sure*100}%" title="ilk garson teması"></em>`:"")}).join("");return `<span>${m.ad}</span><div class="iz">${b}</div>`}).join("");
    ana.append(el(`<section class="kart tam"><h2>Oturum çizelgesi</h2><div class="gantt">${g}</div><div class="aciklama"><span><i style="background:#3ec6d8"></i>oturum, garson ilgilendi</span><span><i style="background:#fde035"></i>garson bekliyor</span><span><i style="background:#f0463c"></i>ilgilenilmedi</span><span><i style="background:#ff8c28"></i>ilk garson teması</span></div></section>`));
    ana.append(el(`<section class="kart tam"><h2>Oturumlar</h2><table><tr><th>No</th><th>Masa</th><th class="s">Kişi</th><th class="s">Başlangıç</th><th class="s">Bitiş</th><th class="s">Süre</th><th class="s">İlk garson</th><th>Not</th></tr>${c.oturumlar.map(o=>`<tr><td>${o.no}</td><td><b>${o.masa}</b></td><td class="s">${o.kisi}</td><td class="s">${c.saat_bas!=null?saat(c.saat_bas+o.bas):sn(o.bas)}</td><td class="s">${o.devam?"sürüyor":(c.saat_bas!=null?saat(c.saat_bas+o.bitis):sn(o.bitis))}</td><td class="s">${sn(o.sure)}</td><td class="s">${c.masa_servisi===false?"self servis":(o.bekleme!=null?sn(o.bekleme):(o.ilk_temas!=null?"geldi":"gelmedi"))}</td><td class="yok">${o.basta_dolu?"video başında oturuyordu":""}</td></tr>`).join("")}</table></section>`));
  }
  if(c.calisanlar.length){
    const R={servis:"#22c55e",tezgah:"#ff8c28",yurume:"#3ec6d8",bosta:"#5b667a"},A={servis:"masada servis",tezgah:"tezgâh / kasa",yurume:"yürüme",bosta:"boşta"};
    ana.append(el(`<section class="kart tam"><h2>Çalışan süre dağılımı</h2><table><tr><th>Çalışan</th><th>Dağılım</th><th class="s">Görüntüde</th><th class="s">Aktif</th></tr>${c.calisanlar.map(p=>`<tr><td><b>${p.ad}</b></td><td style="width:55%"><div class="yig">${Object.keys(R).map(k=>`<i style="width:${p[k]/p.toplam*100}%;background:${R[k]}" title="${A[k]}: ${sn(p[k])}"></i>`).join("")}</div></td><td class="s">${sn(p.toplam)}</td><td class="s">${yz(p.aktif_yuzde)}</td></tr>`).join("")}</table><div class="aciklama">${Object.keys(R).map(k=>`<span><i style="background:${R[k]}"></i>${A[k]}</span>`).join("")}</div></section>`));
  }
  if(kuyrukVar){
    const s=c.kuyruk_seri,mxq=Math.max(1,...s.map(q=>q[1]));const pts=s.map(q=>(q[0]/c.sure*100)+","+(38-q[1]/mxq*34)).join(" ");
    ana.append(el(`<section class="kart tam"><h2>Kasa kuyruğu (kişi)</h2><svg viewBox="0 0 100 40" preserveAspectRatio="none" style="width:100%;height:120px"><polyline points="0,38 ${pts} 100,38" fill="rgba(200,120,200,.25)" stroke="none"/><polyline points="${pts}" fill="none" stroke="#c878c8" stroke-width=".7"/></svg><div class="aciklama"><span>en çok ${mxq} kişi · ortalama bekleme ${sn(o.kuyruk_ort_bekleme)}</span></div></section>`));
  }
  document.querySelectorAll(".uy").forEach(u=>u.onclick=()=>{const v=document.getElementById("vid");v.currentTime=Math.max(0,parseFloat(u.dataset.t)-1.5);v.play();window.scrollTo({top:0,behavior:"smooth"})});
  document.querySelectorAll("nav button").forEach((b,i)=>b.classList.toggle("sec",i==k+1));
}
function genel(){
  const ana=document.getElementById("ana");ana.innerHTML="";
  const T=(f)=>V.reduce((a,c)=>a+(f(c)||0),0);
  const masalar=V.flatMap(c=>c.masalar.map(m=>({...m,kamera:c.ad}))).sort((a,b)=>b.doluluk-a.doluluk||b.oturum-a.oturum);
  const uy=V.flatMap((c,i)=>c.uyarilar.map(u=>({...u,kamera:c.ad,k:i})));
  const on=V.flatMap(c=>c.oneriler.map(x=>`<div class="on"><span class="yok">${c.ad}</span><br>${x}</div>`));
  ana.append(el(`<section class="kart tam"><h2>Tüm kameralar · ${V.length} kamera, ${sn(T(c=>c.sure))} görüntü</h2><div class="kpi" style="grid-template-columns:repeat(6,minmax(0,1fr))"><div><b>${T(c=>c.ozet.oturum)}</b><span>masa oturumu</span></div><div><b>${masalar.filter(m=>m.son_durum!="bos").length}/${masalar.length}</b><span>masa şu an dolu ya da kirli</span></div><div><b>${T(c=>c.ozet.musteri)}</b><span>izlenen müşteri</span></div><div><b>${T(c=>c.ozet.calisan)}</b><span>çalışan</span></div><div><b>${Math.max(0,...V.map(c=>c.ozet.kuyruk_en_cok||0))}</b><span>en uzun kuyruk</span></div><div class="u"><b>${uy.length}</b><span>uyarı</span></div></div></section>`));
  ana.append(el(`<section class="kart"><h2>Masa talebi sıralaması</h2><table><tr><th>Kamera</th><th>Masa</th><th class="s">Oturum</th><th>Doluluk</th><th class="s">Ort. süre</th></tr>${masalar.map(m=>`<tr><td class="yok">${m.kamera}</td><td><b>${m.ad}</b></td><td class="s">${m.oturum}</td><td><div style="display:flex;gap:8px;align-items:center"><div class="cubuk" style="flex:1"><i style="width:${m.doluluk}%"></i></div>${yz(m.doluluk)}</div></td><td class="s">${m.oturum?sn(m.ort_sure):"–"}</td></tr>`).join("")}</table></section>`));
  const sag=el(`<section class="kart"><h2>Uyarılar</h2>${uy.length?uy.map(u=>`<div class="uy" data-k="${u.k}"><b>${sn(u.t)}</b><span><span class="yok">${u.kamera}</span><br>${u.metin}</span></div>`).join(""):'<div class="yok">Uyarı yok.</div>'}<h2 style="margin-top:18px">Öneriler</h2>${on.join("")}</section>`);
  ana.append(sag);sag.querySelectorAll(".uy").forEach(u=>u.onclick=()=>ciz(+u.dataset.k));
  const cal=V.flatMap(c=>c.calisanlar.map(p=>({...p,kamera:c.ad})));
  const R={servis:"#22c55e",tezgah:"#ff8c28",yurume:"#3ec6d8",bosta:"#5b667a"},A={servis:"masada servis",tezgah:"tezgâh / kasa",yurume:"yürüme",bosta:"boşta"};
  if(cal.length)ana.append(el(`<section class="kart tam"><h2>Çalışan süre dağılımı</h2><table><tr><th>Kamera</th><th>Çalışan</th><th>Dağılım</th><th class="s">Görüntüde</th><th class="s">Aktif</th></tr>${cal.map(p=>`<tr><td class="yok">${p.kamera}</td><td><b>${p.ad}</b></td><td style="width:50%"><div class="yig">${Object.keys(R).map(k=>`<i style="width:${p[k]/p.toplam*100}%;background:${R[k]}" title="${A[k]}: ${sn(p[k])}"></i>`).join("")}</div></td><td class="s">${sn(p.toplam)}</td><td class="s">${yz(p.aktif_yuzde)}</td></tr>`).join("")}</table><div class="aciklama">${Object.keys(R).map(k=>`<span><i style="background:${R[k]}"></i>${A[k]}</span>`).join("")}</div></section>`));
  document.querySelectorAll("nav button").forEach((b,i)=>b.classList.toggle("sec",i==0));
}
const nav=document.getElementById("nav");{const b=document.createElement("button");b.textContent="Genel bakış";b.onclick=genel;nav.append(b)}
V.forEach((c,i)=>{const b=document.createElement("button");b.textContent=c.ad;b.onclick=()=>ciz(i);nav.append(b)});genel();
document.getElementById("ornekNot").hidden=!V.some(c=>c.ornek);
</script></body></html>
"""


def excel(veri: list[dict], yol: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()

    def sayfa(ad, basliklar, satirlar, ilk=False):
        ws = wb.active if ilk else wb.create_sheet()
        ws.title = ad
        ws.append(basliklar)
        for h in ws[1]:
            h.font = Font(bold=True, color="FFFFFF")
            h.fill = PatternFill("solid", fgColor="1F2A44")
        for s in satirlar:
            ws.append(s)
        for n, b in enumerate(basliklar, 1):
            ws.column_dimensions[get_column_letter(n)].width = max(12, len(str(b)) + 4)
        ws.freeze_panes = "A2"

    sayfa("Özet", ["Kamera", "Görüntü (sn)", "Oturum", "Ort. oturma (sn)", "Ort. doluluk %", "Ort. ilk garson (sn)", "Müşteri", "Çalışan", "Uyarı", "En uzun kuyruk", "Sıraya girmeden çıkan"],
          [[c["ad"], c["sure"], c["ozet"]["oturum"], c["ozet"]["ort_oturma"], c["ozet"]["doluluk"], c["ozet"]["ort_bekleme"], c["ozet"]["musteri"], c["ozet"]["calisan"], c["ozet"]["uyari"], c["ozet"]["kuyruk_en_cok"], c["ozet"]["donen"]] for c in veri], ilk=True)
    sayfa("Masalar", ["Kamera", "Masa", "Oturum", "Doluluk %", "Dolu (sn)", "Ort. süre (sn)", "Kişi", "Temizlenmeden (sn)"],
          [[c["ad"], m["ad"], m["oturum"], m["doluluk"], m["dolu_sn"], m["ort_sure"], m["kisi"], m["kirli_sn"]] for c in veri for m in c["masalar"]])
    sayfa("Oturumlar", ["Kamera", "No", "Masa", "Kişi", "Başlangıç (sn)", "Bitiş (sn)", "Süre (sn)", "İlk garson (sn)", "Garson bekleme (sn)", "Not"],
          [[c["ad"], o["no"], o["masa"], o["kisi"], o["bas"], o["bitis"], o["sure"], o["ilk_temas"], o["bekleme"],
            "video başında oturuyordu" if o["basta_dolu"] else ("sürüyor" if o["devam"] else "")] for c in veri for o in c["oturumlar"]])
    sayfa("Çalışanlar", ["Kamera", "Çalışan", "Görüntüde (sn)", "Masada servis (sn)", "Tezgâh/kasa (sn)", "Yürüme (sn)", "Boşta (sn)", "Aktif %"],
          [[c["ad"], p["ad"], p["toplam"], p["servis"], p["tezgah"], p["yurume"], p["bosta"], p["aktif_yuzde"]] for c in veri for p in c["calisanlar"]])
    sayfa("Uyarılar", ["Kamera", "Zaman (sn)", "Masa", "Tür", "Açıklama"],
          [[c["ad"], u["t"], u["masa"], u["tur"], u["metin"]] for c in veri for u in c["uyarilar"]])
    wb.save(yol)


def oneriler(c: dict) -> list[str]:
    o, out = c["ozet"], []
    ms = c["masalar"]
    if ms:
        dolu = sorted([m for m in ms if m["oturum"]], key=lambda m: -m["doluluk"])
        bos = [m["ad"] for m in ms if not m["oturum"] and m["kirli_sn"] == 0]
        if dolu:
            ek = " Rezervasyon ve servis önceliğini bu masalara verin." if c.get("masa_servisi", True) else " Bu düzendeki oturma alanını çoğaltmayı değerlendirin."
            out.append(f"En çok talep gören: <b>{', '.join(m['ad'] for m in dolu[:3])}</b>." + ek)
        if bos:
            out.append(f"<b>{', '.join(bos)}</b> bu görüntüde hiç kullanılmadı. Konumunu ya da düzenini gözden geçirin.")
        for u in c["uyarilar"]:
            if u["tur"] == "ilgilenilmedi":
                ot = next((x for x in c["oturumlar"] if x["masa"] == u["masa"] and x["ilk_temas"] is None), None)
                if ot:
                    out.append(f"<b>{u['masa']}</b> {int(ot['sure'])} sn boyunca garson görmedi. Bu bölgeye bir çalışan atayın ya da uyarıyı garson ekranına düşürün.")
        for m in ms:
            if m["temizlik_suresi"]:
                out.append(f"<b>{m['ad']}</b> {str(m['temizlik_suresi']).replace('.', ',')} sn'de temizlendi; bu sürede masa satışa kapalıydı.")
        if o["ort_bekleme"] is not None:
            out.append(f"Yeni oturan müşteriyle ilk temas ortalama <b>{str(o['ort_bekleme']).replace('.', ',')} sn</b>.")
    if o["kuyruk_en_cok"]:
        out.append(f"Kasada kuyruk <b>{o['kuyruk_en_cok']} kişiye</b> çıktı" + (f", <b>{o['donen']} müşteri</b> sıraya girmeden çıktı" if o["donen"] else "") + ". Yoğun saatte ikinci kasayı açın.")
    if o.get("calisan") and o.get("calisan_ort") is not None:
        out.append(f"Görüntüde ortalama <b>{str(round(o['calisan_ort'], 1)).replace('.', ',')} çalışan</b> vardı (aynı anda en çok {o['calisan']}).")
    for p in c["calisanlar"]:
        if p["aktif_yuzde"] < 60 and p["toplam"] >= 5:
            out.append(f"<b>{p['ad']}</b> görüntüde kaldığı sürenin %{int(100 - p['aktif_yuzde'])}'inde boştaydı.")
    return out


def uret() -> int:
    """Paneli ve Excel raporunu yeniden üretir. Dönüş: paneldeki kamera sayısı."""
    CIKTI = yollar.CIKTI
    CIKTI.mkdir(parents=True, exist_ok=True)
    veri = []
    for d in sorted(CIKTI.iterdir()):
        s = d / "sonuc.json"
        if d.is_dir() and s.exists():
            c = json.loads(s.read_text(encoding="utf-8"))
            c["klasor"] = d.name
            c["ornek"] = d.name in yollar.ORNEK_KODLAR and c.get("video") == f"{d.name}.mp4"
            c["oneriler"] = oneriler(c)
            c.pop("izler", None)
            veri.append(c)
    # önce kullanıcının kameraları, sonra örnekler
    veri.sort(key=lambda c: (c["ornek"], yollar.ORNEK_KODLAR.index(c["klasor"]) if c["ornek"] else 0, c["klasor"]))
    if not veri:
        for ad in ("panel.html", "rapor.xlsx"):
            (CIKTI / ad).unlink(missing_ok=True)
        print("Panel için analiz sonucu yok.", flush=True)
        return 0
    (CIKTI / "panel.html").write_text(HTML.replace("__VERI__", json.dumps(veri, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
    try:
        excel(veri, CIKTI / "rapor.xlsx")
    except PermissionError:
        print("UYARI: rapor.xlsx şu an Excel'de açık olduğu için güncellenemedi. Excel'i kapatıp paneli yenileyin.", flush=True)
    print(f"Panel ve Excel raporu hazır ({len(veri)} kamera).", flush=True)
    return len(veri)


if __name__ == "__main__":
    yollar.hazirla()
    uret()
