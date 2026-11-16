"""cikti/*/sonuc.json dosyalarından tek sayfalık panel (panel.html) ve Excel raporu üretir."""
from __future__ import annotations

import json
from pathlib import Path

import yollar

HTML = r"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="data:,"><title>Raporlar · Kafe Kamera</title>
<style>__ORTAK_CSS__</style>
<script>__ORTAK_JS__</script>
<script>/* ortak dosyalar gömülemediyse: sade yedek yardımcılar ve kısa bir not */
if(!window.KK){window.KK={yedek:true,$:i=>document.getElementById(i),esc:s=>String(s??"").replace(/[&<>"']/g,c=>"&#"+c.charCodeAt(0)+";"),ik:()=>"",gezinme:()=>{},saatTik:()=>{}}}
if(KK.yedek||getComputedStyle(document.documentElement).getPropertyValue("--ortak").trim()!=="1")document.head.insertAdjacentHTML("beforeend","<style>body{margin:0;padding:0 12px;font:15px/1.5 Segoe UI,system-ui,sans-serif}.ik,svg.ik{width:1em;height:1em;vertical-align:-.125em;fill:none;stroke:currentColor}.gizli,[hidden]{display:none!important}header,main,section,aside{display:block;margin:10px 0}nav a{display:inline-block;margin-right:14px}img,video{max-width:100%;height:auto}.logo,.nokta{display:none}pre{white-space:pre-wrap}</style>");
addEventListener("DOMContentLoaded",()=>{if(KK.yedek||getComputedStyle(document.documentElement).getPropertyValue("--ortak").trim()!=="1"){const n=document.createElement("div");n.setAttribute("role","alert");n.style.cssText="margin:12px;padding:10px 14px;border:2px solid #b45309;border-radius:10px;background:#fff7e6;color:#5a3600;font:14px/1.4 Segoe UI,system-ui,sans-serif";n.textContent="Arayüz dosyaları rapora gömülemedi; rapor sade görünümde. Raporu Kafe Kamera'da yeniden üretin.";document.body.prepend(n)}});</script>
<style>
/* Rapora özgü görünüm */
.rapor{display:grid;gap:16px;grid-template-columns:repeat(2,minmax(0,1fr));align-items:start}
.rapor .tam{grid-column:1/-1}
.rapor .kart h2 .alt{font-weight:500;color:var(--soluk);font-size:13.5px}
.ozet-bas{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline;margin:0 0 12px}
.ozet-bas h2{margin:0;font-size:20px}
.ozet-bas span{color:var(--soluk);font-size:13.5px}
.kpi.rapor-kpi{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.kpi.rapor-kpi .tile .t-deger{font-size:clamp(26px,2.4vw,44px)}
video{width:100%;border-radius:10px;display:block;background:#000;aspect-ratio:16/9}
.cubuklu{display:flex;gap:8px;align-items:center;min-width:150px}
.cubuk2{flex:1;height:8px;border-radius:5px;background:var(--cizgi2);overflow:hidden;min-width:70px}
.cubuk2 i{display:block;height:100%;background:var(--s-dolu);border-radius:5px}
ul.liste-u,ul.liste-o{list-style:none;margin:0;padding:0;display:grid;gap:8px}
ul.liste-u li{display:grid;grid-template-columns:auto auto 1fr;gap:4px 10px;align-items:start;padding:9px 10px;border-radius:10px;border:1px solid color-mix(in srgb,var(--err) 35%,var(--cizgi));background:color-mix(in srgb,var(--err) 7%,var(--kart))}
ul.liste-u li[data-t]{cursor:pointer}
ul.liste-u li[data-t]:hover{border-color:var(--err)}
ul.liste-u li[data-k]{cursor:pointer}
ul.liste-u time{font-weight:700;color:var(--err);white-space:nowrap}
ul.liste-u .u-ik{color:var(--err)}
ul.liste-u small{display:block;color:var(--soluk);font-size:12.5px}
ul.liste-o li{display:flex;gap:10px;align-items:flex-start;padding:9px 12px;border-left:3px solid var(--vurgu);background:var(--kart2);border-radius:0 10px 10px 0}
ul.liste-o li .ik{color:var(--vurgu-yazi);margin-top:3px;flex:none}
ul.liste-o small{display:block;color:var(--soluk);font-size:12.5px}
.yok{color:var(--soluk)}
.harita{position:relative}
.harita img{width:100%;display:block;border-radius:10px;filter:brightness(.62);background:#0a0f1d;min-height:120px}
.harita svg{position:absolute;inset:0;width:100%;height:100%}
.aciklama{display:flex;gap:6px 16px;flex-wrap:wrap;color:var(--soluk);font-size:13px;margin-top:10px}
.aciklama span{display:inline-flex;align-items:center;gap:6px}
.aciklama i{display:inline-block;width:14px;height:12px;border-radius:3px}
.gantt{display:grid;grid-template-columns:minmax(64px,auto) 1fr;gap:6px 10px;align-items:center}
.gantt>span{font-weight:600;font-size:13.5px;white-space:nowrap}
.gantt .iz{position:relative;height:22px;background:var(--kart2);border:1px solid var(--cizgi2);border-radius:6px}
.gantt .iz i{position:absolute;top:2px;bottom:2px;border-radius:4px;background:var(--s-dolu)}
.gantt .iz i.b{background:var(--s-bek)}
.gantt .iz i.u{background:repeating-linear-gradient(45deg,var(--err) 0 3px,color-mix(in srgb,var(--err) 45%,transparent) 3px 6px)}
.gantt .iz em{position:absolute;top:-3px;bottom:-3px;width:3px;background:var(--yazi);border-radius:2px}
.l-oturum{background:var(--s-dolu)}.l-bek{background:var(--s-bek)}.l-u{background:repeating-linear-gradient(45deg,var(--err) 0 3px,color-mix(in srgb,var(--err) 45%,transparent) 3px 6px)}.l-tem{background:var(--yazi);width:4px!important}
.yig{display:flex;height:20px;border-radius:6px;overflow:hidden;background:var(--kart2);min-width:160px}
.yig i{display:block;height:100%}
.r-servis{background:var(--ok)}.r-tezgah{background:var(--s-bek)}.r-yurume{background:var(--s-dolu)}.r-bosta{background:repeating-linear-gradient(45deg,var(--s-bos) 0 2px,color-mix(in srgb,var(--s-bos) 45%,transparent) 2px 5px)}
.kuyruk-cizim{width:100%;height:130px;display:block}
.kuyruk-cizim .alan{fill:color-mix(in srgb,var(--s-kir) 25%,transparent)}
.kuyruk-cizim .cizgi{fill:none;stroke:var(--s-kir);stroke-width:.7}
.not-alt{color:var(--soluk);font-size:13px;padding:0 28px 30px;max-width:2200px;margin:0 auto}
.dosya-not{margin:0 0 14px}
@media(max-width:1100px){.rapor{grid-template-columns:minmax(0,1fr)}}
@media(max-width:860px){.not-alt{padding:0 16px 24px}.rapor-kpi{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style></head><body>
<header class="ust">
  <a class="marka" href="/canli.html" data-uygulama><div class="logo"><svg class="ik"><use href="#i-logo"/></svg></div>
    <div><div class="ad">Kafe Kamera Analizi</div><div class="alt">Raporlar</div></div></a>
  <nav class="ana-nav" aria-label="Bölümler">
    <a href="/canli.html" data-bolum="canli" data-uygulama><svg class="ik"><use href="#i-canli"/></svg>Canlı pano</a>
    <a href="panel.html" data-bolum="raporlar" aria-current="page"><svg class="ik"><use href="#i-rapor"/></svg>Raporlar</a>
    <a href="/#kameralar" data-bolum="kameralar" data-uygulama><svg class="ik"><use href="#i-kamera"/></svg>Kameralar</a>
    <a href="/#kurulum" data-bolum="kurulum" data-uygulama><svg class="ik"><use href="#i-ayar"/></svg>Kurulum</a>
  </nav>
  <div class="bosluk"></div>
  <div class="ust-sag">
    <span class="cip k-ok" title="Görüntülerde yüzler pikselleştirilir">Yüzler gizli · kimlik tanıma yok</span>
    <a class="dug" href="rapor.xlsx" download><svg class="ik"><use href="#i-indir"/></svg>Excel raporu</a>
    <div class="saat"><b id="saat">--:--:--</b><small id="tarih"></small></div>
  </div>
  <div class="ust-alt"><nav class="secici" id="nav" aria-label="Kamera seçimi"></nav></div>
</header>
<main>
<div class="serit bilgi dosya-not gizli" id="dosyaNot" style="margin:0 0 14px"><svg class="ik"><use href="#i-bilgi"/></svg><div>Bu rapor dosyadan açıldı. Canlı pano, Kameralar ve Kurulum bölümleri Kafe Kamera açıkken kullanılabilir.</div></div>
<div id="ana"></div>
</main>
<p class="not-alt" id="ornekNot" hidden>Örnek videolar 15–30 saniyelik olduğu için süreler saniye olarak görünür; gerçek kamera akışında aynı ölçümler dakika ve saat olarak birikir. Örnek görüntüler yapay zekâ ile üretildi, gerçek kişi yoktur.</p>
<script>
const V=__VERI__;
const esc=KK.esc,ik=KK.ik;
const saat=x=>{x=Math.round(x)%86400;return String(Math.floor(x/3600)).padStart(2,"0")+":"+String(Math.floor(x%3600/60)).padStart(2,"0")};
const sn=x=>x==null?"–":(x>=60?Math.floor(x/60)+" dk "+Math.round(x%60)+" sn":(Math.round(x*10)/10+" sn").replace(".",","));
const yz=x=>x==null?"–":("%"+String(Math.round(x*10)/10).replace(".",","));
const el=(h)=>{const d=document.createElement("div");d.innerHTML=h;return d.firstElementChild};
const tile=(deger,etiket,cls="",simge="")=>`<div class="tile ${cls}"><div class="t-bas">${simge?ik(simge):""}${etiket}</div><div class="t-deger">${deger}</div></div>`;
const bolum=(baslik,simge,ic,cls="")=>`<section class="kart ${cls}"><div class="kart-bas"><h2>${simge?ik(simge):""}${baslik}</h2></div>${ic}</section>`;
const cubuklu=v=>`<div class="cubuklu"><div class="cubuk2"><i style="width:${Math.max(0,Math.min(100,v))}%"></i></div>${yz(v)}</div>`;
const R={servis:"r-servis",tezgah:"r-tezgah",yurume:"r-yurume",bosta:"r-bosta"},A={servis:"masada servis",tezgah:"tezgâh / kasa",yurume:"yürüme",bosta:"boşta"};
const calisanLejant=`<div class="aciklama">${Object.keys(R).map(k=>`<span><i class="${R[k]}"></i>${A[k]}</span>`).join("")}</div>`;
const yig=p=>`<div class="yig">${Object.keys(R).map(k=>`<i class="${R[k]}" style="width:${p.toplam?p[k]/p.toplam*100:0}%" title="${A[k]}: ${sn(p[k])}"></i>`).join("")}</div>`;
function ciz(k){
  const c=V[k],o=c.ozet,ana=document.getElementById("ana");ana.innerHTML="";
  const masaVar=c.masalar.length>0,kuyrukVar=o.kuyruk_en_cok!=null;
  let kpi="";
  if(masaVar)kpi+=tile(o.oturum,"Masa oturumu","","masa")+tile(sn(o.ort_oturma),"Ortalama oturma","","saat")+tile(yz(o.doluluk),"Ortalama doluluk","","grafik")+tile(sn(o.ort_bekleme),"Oturma → ilk garson","sakin","zil");
  if(kuyrukVar)kpi+=tile(o.kuyruk_en_cok,"En uzun kuyruk (kişi)","","sira")+tile(sn(o.kuyruk_ort_bekleme),"Ortalama sıra bekleme","","saat")+tile(o.donen,"Sıraya girmeden çıkan","kotu","kapi");
  kpi+=tile(o.musteri,"İzlenen müşteri","","musteri")+tile(o.calisan,"Çalışan","","calisan")+tile(o.uyari,"Uyarı",o.uyari?"kotu":"","uyari");
  const r=el(`<div class="rapor"></div>`);ana.append(r);
  r.append(el(`<div class="tam"><div class="ozet-bas"><h2>${esc(c.ad)}</h2><span>Özet · ${sn(c.sure)} görüntü${c.saat_bas!=null?" ("+saat(c.saat_bas)+"–"+saat(c.saat_bas+c.sure)+")":""}${c.calisan_renkleri?` · çalışan rengi: ${esc(c.calisan_renkleri.join(", "))}`:""}</span></div><div class="kpi rapor-kpi" style="margin:0">${kpi}</div></div>`));
  r.append(el(bolum(`${esc(c.ad)} · işaretli görüntü`,"video",`<video id="vid" src="${esc(c.klasor)}/isaretli.mp4" controls muted loop autoplay playsinline></video>`)));
  // harita
  const mx=Math.max(1e-6,...c.isi.flat());let isi="";
  c.isi.forEach((s,y)=>s.forEach((v,x)=>{if(v>mx*0.06)isi+=`<rect x="${x/48*160}" y="${y/27*90}" width="${160/48}" height="${90/27}" fill="#fde035" opacity="${Math.min(.8,.18+.62*v/mx)}"/>`}));
  let pol=c.masalar.map(m=>{const p=m.poly.map(q=>q[0]*160+","+q[1]*90).join(" ");const cx=m.poly.reduce((a,q)=>a+q[0],0)/m.poly.length*160,cy=m.poly.reduce((a,q)=>a+q[1],0)/m.poly.length*90;
    return `<polygon points="${p}" fill="rgba(86,180,233,${.10+.4*m.doluluk/100})" stroke="#56b4e9" stroke-width=".5"/><text x="${cx}" y="${cy-1}" text-anchor="middle" font-size="5" font-weight="700" fill="#fff">${esc(m.ad)}</text><text x="${cx}" y="${cy+5}" text-anchor="middle" font-size="4.6" font-weight="700" fill="#fde035">${yz(m.doluluk)}</text>`}).join("");
  pol+=c.bolgeler.map(b=>`<polygon points="${b.poly.map(q=>q[0]*160+","+q[1]*90).join(" ")}" fill="rgba(220,140,196,.16)" stroke="#dc8cc4" stroke-width=".5" stroke-dasharray="2 1.2"/><text x="${b.poly[0][0]*160+2}" y="${b.poly[0][1]*90+7}" font-size="5" font-weight="700" fill="#fff">${esc(b.ad)}</text>`).join("");
  r.append(el(bolum("Yoğunluk haritası","harita",`<div class="harita"><img src="${esc(c.klasor)}/kare.jpg" alt="${esc(c.ad)} kamerasından kare (yüzler gizli)"><svg viewBox="0 0 160 90" preserveAspectRatio="none" aria-hidden="true">${isi}${pol}</svg></div><div class="aciklama"><span><i style="background:#fde035"></i>müşterilerin en çok durduğu yerler</span><span><i style="background:#56b4e9"></i>masa bölgesi ve doluluk</span>${c.bolgeler.length?'<span><i style="background:#dc8cc4"></i>tezgâh, kuyruk ve diğer bölgeler</span>':""}</div>`)));
  r.append(el(bolum("Öneriler","ampul",c.oneriler.length?`<ul class="liste-o">${c.oneriler.map(x=>`<li>${ik("ampul")}<span>${x}</span></li>`).join("")}</ul>`:'<div class="yok">Bu görüntü için öneri yok.</div>')));
  r.append(el(bolum("Uyarılar","uyari",c.uyarilar.length?`<ul class="liste-u">${c.uyarilar.map(u=>`<li data-t="${u.t}" title="Videoda bu ana git"><time>${sn(u.t)}</time><span class="u-ik">${ik("uyari")}</span><span>${esc(u.metin)}</span></li>`).join("")}</ul>`:`<div class="yok">Bu görüntüde uyarı yok.</div>`)));
  if(masaVar){
    const sira=[...c.masalar].sort((a,b)=>b.doluluk-a.doluluk);
    r.append(el(bolum("Masa talebi","masa",`<div class="tablo-kap"><table class="tablo"><thead><tr><th>Masa</th><th class="s">Oturum</th><th>Doluluk</th><th class="s">Ort. süre</th><th class="s">Kişi</th><th class="s">Kirli kaldı</th><th class="s">Temizlik</th></tr></thead><tbody>${sira.map(m=>`<tr><td><b>${esc(m.ad)}</b></td><td class="s">${m.oturum}</td><td>${cubuklu(m.doluluk)}</td><td class="s">${m.oturum?sn(m.ort_sure):"–"}</td><td class="s">${m.kisi}</td><td class="s">${m.kirli_sn>0?sn(m.kirli_sn):"–"}</td><td class="s">${m.temizlik_suresi!=null?sn(m.temizlik_suresi):"–"}</td></tr>`).join("")}</tbody></table></div>`,"tam")));
    const g=c.masalar.map(m=>{const b=c.oturumlar.filter(o=>o.masa==m.ad).map(o=>{const s=o.bas/c.sure*100,w=Math.max(.8,o.sure/c.sure*100);const cls=o.uyari&&o.ilk_temas==null?"u":(o.ilk_temas==null?"b":"");
      return `<i class="${cls}" style="left:${s}%;width:${w}%" title="${o.kisi} kişi · ${sn(o.sure)}"></i>`+(o.ilk_temas!=null?`<em style="left:${o.ilk_temas/c.sure*100}%" title="ilk garson teması"></em>`:"")}).join("");return `<span>${esc(m.ad)}</span><div class="iz">${b}</div>`}).join("");
    r.append(el(bolum("Oturum çizelgesi","liste",`<div class="gantt">${g}</div><div class="aciklama"><span><i class="l-oturum"></i>oturum, garson ilgilendi</span><span><i class="l-bek"></i>garson bekliyor</span><span><i class="l-u"></i>ilgilenilmedi</span><span><i class="l-tem"></i>ilk garson teması</span></div>`,"tam")));
    r.append(el(bolum("Oturumlar","saat",`<div class="tablo-kap"><table class="tablo"><thead><tr><th>No</th><th>Masa</th><th class="s">Kişi</th><th class="s">Başlangıç</th><th class="s">Bitiş</th><th class="s">Süre</th><th class="s">İlk garson</th><th>Not</th></tr></thead><tbody>${c.oturumlar.map(o=>`<tr><td>${o.no}</td><td><b>${esc(o.masa)}</b></td><td class="s">${o.kisi}</td><td class="s">${c.saat_bas!=null?saat(c.saat_bas+o.bas):sn(o.bas)}</td><td class="s">${o.devam?"sürüyor":(c.saat_bas!=null?saat(c.saat_bas+o.bitis):sn(o.bitis))}</td><td class="s">${sn(o.sure)}</td><td class="s">${c.masa_servisi===false?"self servis":(o.bekleme!=null?sn(o.bekleme):(o.ilk_temas!=null?"geldi":"gelmedi"))}</td><td class="soluk">${o.basta_dolu?"video başında oturuyordu":""}</td></tr>`).join("")}</tbody></table></div>`,"tam")));
  }
  if(c.calisanlar.length){
    r.append(el(bolum("Çalışan süre dağılımı","calisan",`<div class="tablo-kap"><table class="tablo"><thead><tr><th>Çalışan</th><th>Dağılım</th><th class="s">Görüntüde</th><th class="s">Aktif</th></tr></thead><tbody>${c.calisanlar.map(p=>`<tr><td><b>${esc(p.ad)}</b></td><td style="width:55%">${yig(p)}</td><td class="s">${sn(p.toplam)}</td><td class="s">${yz(p.aktif_yuzde)}</td></tr>`).join("")}</tbody></table></div>${calisanLejant}`,"tam")));
  }
  if(kuyrukVar){
    const s=c.kuyruk_seri,mxq=Math.max(1,...s.map(q=>q[1]));const pts=s.map(q=>(q[0]/c.sure*100)+","+(38-q[1]/mxq*34)).join(" ");
    r.append(el(bolum("Kasa kuyruğu (kişi)","sira",`<svg class="kuyruk-cizim" viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label="Kasa kuyruğu"><polyline class="alan" points="0,38 ${pts} 100,38" stroke="none"/><polyline class="cizgi" points="${pts}"/></svg><div class="aciklama"><span>en çok ${mxq} kişi · ortalama bekleme ${sn(o.kuyruk_ort_bekleme)}</span></div>`,"tam")));
  }
  document.querySelectorAll("li[data-t]").forEach(u=>u.onclick=()=>{const v=document.getElementById("vid");v.currentTime=Math.max(0,parseFloat(u.dataset.t)-1.5);v.play();v.scrollIntoView({behavior:"smooth",block:"center"})});
  sec(k+1);
}
function genel(){
  const ana=document.getElementById("ana");ana.innerHTML="";
  const T=(f)=>V.reduce((a,c)=>a+(f(c)||0),0);
  const masalar=V.flatMap(c=>c.masalar.map(m=>({...m,kamera:c.ad}))).sort((a,b)=>b.doluluk-a.doluluk||b.oturum-a.oturum);
  const uy=V.flatMap((c,i)=>c.uyarilar.map(u=>({...u,kamera:c.ad,k:i})));
  const on=V.flatMap(c=>c.oneriler.map(x=>`<li>${ik("ampul")}<span><small>${esc(c.ad)}</small>${x}</span></li>`));
  const r=el(`<div class="rapor"></div>`);ana.append(r);
  r.append(el(`<div class="tam"><div class="ozet-bas"><h2>Tüm kameralar</h2><span>${V.length} kamera, ${sn(T(c=>c.sure))} görüntü</span></div><div class="kpi rapor-kpi" style="margin:0">${tile(T(c=>c.ozet.oturum),"Masa oturumu","","masa")+tile(`${masalar.filter(m=>m.son_durum!="bos").length}<small>/ ${masalar.length}</small>`,"Masa şu an dolu ya da kirli","","grafik")+tile(T(c=>c.ozet.musteri),"İzlenen müşteri","","musteri")+tile(T(c=>c.ozet.calisan),"Çalışan","","calisan")+tile(Math.max(0,...V.map(c=>c.ozet.kuyruk_en_cok||0)),"En uzun kuyruk","","sira")+tile(uy.length,"Uyarı",uy.length?"kotu":"","uyari")}</div></div>`));
  r.append(el(bolum("Masa talebi sıralaması","masa",masalar.length?`<div class="tablo-kap"><table class="tablo"><thead><tr><th>Kamera</th><th>Masa</th><th class="s">Oturum</th><th>Doluluk</th><th class="s">Ort. süre</th></tr></thead><tbody>${masalar.map(m=>`<tr><td class="soluk">${esc(m.kamera)}</td><td><b>${esc(m.ad)}</b></td><td class="s">${m.oturum}</td><td>${cubuklu(m.doluluk)}</td><td class="s">${m.oturum?sn(m.ort_sure):"–"}</td></tr>`).join("")}</tbody></table></div>`:'<div class="yok">Masa tanımlı kamera yok.</div>')));
  const sag=el(`<div style="display:grid;gap:16px;align-content:start">${bolum("Uyarılar","uyari",uy.length?`<ul class="liste-u">${uy.map(u=>`<li data-k="${u.k}" title="Bu kameranın raporunu aç"><time>${sn(u.t)}</time><span class="u-ik">${ik("uyari")}</span><span><small>${esc(u.kamera)}</small>${esc(u.metin)}</span></li>`).join("")}</ul>`:'<div class="yok">Uyarı yok.</div>')}${bolum("Öneriler","ampul",on.length?`<ul class="liste-o">${on.join("")}</ul>`:'<div class="yok">Öneri yok.</div>')}</div>`);
  r.append(sag);sag.querySelectorAll("li[data-k]").forEach(u=>u.onclick=()=>git(+u.dataset.k));
  const cal=V.flatMap(c=>c.calisanlar.map(p=>({...p,kamera:c.ad})));
  if(cal.length)r.append(el(bolum("Çalışan süre dağılımı","calisan",`<div class="tablo-kap"><table class="tablo"><thead><tr><th>Kamera</th><th>Çalışan</th><th>Dağılım</th><th class="s">Görüntüde</th><th class="s">Aktif</th></tr></thead><tbody>${cal.map(p=>`<tr><td class="soluk">${esc(p.kamera)}</td><td><b>${esc(p.ad)}</b></td><td style="width:50%">${yig(p)}</td><td class="s">${sn(p.toplam)}</td><td class="s">${yz(p.aktif_yuzde)}</td></tr>`).join("")}</tbody></table></div>${calisanLejant}`,"tam")));
  sec(0);
}
function sec(i){document.querySelectorAll("#nav button").forEach((b,j)=>b.setAttribute("aria-pressed",String(j==i)))}
function git(i){
  try{history.replaceState(null,"",i<0?location.pathname:"#"+encodeURIComponent(V[i].klasor))}catch(e){}
  i<0?genel():ciz(i);window.scrollTo({top:0});
}
const nav=document.getElementById("nav");
{const b=document.createElement("button");b.type="button";b.innerHTML=ik("izgara")+"Genel bakış";b.onclick=()=>git(-1);nav.append(b)}
V.forEach((c,i)=>{const b=document.createElement("button");b.type="button";b.textContent=c.ad;b.onclick=()=>git(i);nav.append(b)});
{const h=decodeURIComponent(location.hash.slice(1)),i=V.findIndex(c=>c.klasor===h);i>=0?ciz(i):genel()}
document.getElementById("ornekNot").hidden=!V.some(c=>c.ornek);
if(location.protocol==="file:"){
  document.getElementById("dosyaNot").classList.remove("gizli");
  document.querySelectorAll("[data-uygulama]").forEach(a=>{a.removeAttribute("href");a.setAttribute("aria-disabled","true");a.style.opacity=".45";a.title="Kafe Kamera açıkken kullanılabilir"});
}
</script></body></html>
"""


def _ortak(ad: str) -> str:
    """Arayüzün ortak dosyası (web/ortak.css, web/ortak.js): rapor tek başına açılabilsin diye sayfaya gömülür."""
    try:
        return (yollar.WEB / ad).read_text(encoding="utf-8")
    except OSError:
        return ""  # sayfa yine çalışır; sade görünümde kısa bir not gösterir


def sayfa(veri: list[dict]) -> str:
    """panel.html: ortak görünüm gömülü, veriler JSON olarak sayfada; dış dosya gerekmez."""
    return (HTML.replace("__ORTAK_CSS__", _ortak("ortak.css").replace("</style", "<\\/style"))
            .replace("__ORTAK_JS__", _ortak("ortak.js").replace("</script", "<\\/script"))
            .replace("__VERI__", json.dumps(veri, ensure_ascii=False).replace("</", "<\\/")))


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
    (CIKTI / "panel.html").write_text(sayfa(veri), encoding="utf-8")
    try:
        excel(veri, CIKTI / "rapor.xlsx")
    except PermissionError:
        print("UYARI: rapor.xlsx şu an Excel'de açık olduğu için güncellenemedi. Excel'i kapatıp paneli yenileyin.", flush=True)
    print(f"Panel ve Excel raporu hazır ({len(veri)} kamera).", flush=True)
    return len(veri)


if __name__ == "__main__":
    yollar.hazirla()
    uret()
