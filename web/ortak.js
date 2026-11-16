/* Kafe Kamera · ortak yardımcılar (tüm sayfalar). window.KK altında toplanır.
   Bu dosya yüklenmezse her sayfanın kendi küçük yedeği (KK.yedek=true) devreye girer ve sayfa sade görünümde çalışır. */
"use strict";
(function(){
  const KK=window.KK={};
  KK.$=id=>document.getElementById(id);
  KK.esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  KK.ik=(ad,cls="")=>`<svg class="ik ${cls}" aria-hidden="true"><use href="#i-${ad}"/></svg>`;
  KK.sayi=v=>typeof v==="number"&&isFinite(v);
  KK.pad=n=>String(n).padStart(2,"0");
  /* Süre: "45 sn", "4 dk 12 sn", "1 sa 05 dk" */
  KK.sure=function(s){
    if(!KK.sayi(s))return "–";
    s=Math.max(0,Math.floor(s));
    if(s<60)return `${s} sn`;
    if(s<3600)return `${Math.floor(s/60)} dk ${KK.pad(s%60)} sn`;
    return `${Math.floor(s/3600)} sa ${KK.pad(Math.floor(s%3600/60))} dk`;
  };
  /* Kısa biçim (küçük kutular): "45 sn", "38 dk", "1 sa 05 dk" */
  KK.kisaSure=function(s){
    if(!KK.sayi(s))return "–";
    s=Math.max(0,Math.floor(s));
    if(s<60)return `${s} sn`;
    if(s<3600)return `${Math.floor(s/60)} dk`;
    return `${Math.floor(s/3600)} sa ${KK.pad(Math.floor(s%3600/60))} dk`;
  };
  KK.say=v=>KK.sayi(v)?Math.round(v).toLocaleString("tr-TR"):"–";
  KK.yuzde=v=>KK.sayi(v)?"%"+Math.round(v):"–";
  /* Analizin yapıldığı cihaz: "ekran_karti" | "islemci" (bilinmeyen değer gösterilmez) */
  KK.cihazAdi=c=>({ekran_karti:"Ekran kartı",islemci:"İşlemci"})[c]||"";
  KK.dogal=(a,b)=>String(a).localeCompare(String(b),"tr",{numeric:true});

  /* Tema: ?tema=acik|koyu sistem ayarını geçersiz kılar */
  const tema={acik:"light",koyu:"dark",light:"light",dark:"dark"}[new URLSearchParams(location.search).get("tema")];
  if(tema)document.documentElement.dataset.theme=tema;

  /* Saat: #saat ve #tarih varsa her saniye */
  const GUN=["Pazar","Pazartesi","Salı","Çarşamba","Perşembe","Cuma","Cumartesi"],AY=["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"];
  KK.saatTik=function(){
    const n=new Date(),s=KK.$("saat"),t=KK.$("tarih");
    if(s)s.textContent=`${KK.pad(n.getHours())}:${KK.pad(n.getMinutes())}:${KK.pad(n.getSeconds())}`;
    if(t)t.textContent=`${n.getDate()} ${AY[n.getMonth()]} ${GUN[n.getDay()]}`;
  };

  /* Gezinme: etkin bölümü işaretler (ad: canli | raporlar | kameralar | kurulum) */
  KK.gezinme=function(ad){
    document.querySelectorAll("nav.ana-nav a[data-bolum]").forEach(a=>{
      if(a.dataset.bolum===ad)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current");
    });
  };

  /* Sunucu çağrıları */
  KK.al=async function(yol,zaman=6000){
    const ac=new AbortController(),zt=setTimeout(()=>ac.abort(),zaman);
    try{const r=await fetch(yol,{cache:"no-store",signal:ac.signal});if(!r.ok)throw new Error("HTTP "+r.status);return await r.json()}
    finally{clearTimeout(zt)}
  };
  KK.gonder=async function(yol,govde){
    const r=await fetch(yol,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(govde||{})});
    let j={};try{j=await r.json()}catch(e){}
    return {ok:r.ok,durum:r.status,veri:j};
  };

  /* Simge kümesi: sayfaya bir kez eklenir */
  const S={
    logo:'<path d="M3 8.5a2 2 0 0 1 2-2h2.2l1.4-2h6.8l1.4 2H19a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><circle cx="12" cy="13" r="3.6"/>',
    musteri:'<circle cx="9" cy="8" r="3.3"/><path d="M3 20c0-3.6 2.7-6 6-6s6 2.4 6 6"/><circle cx="17" cy="9" r="2.6"/><path d="M16.5 14.2c2.6.2 4.5 2.4 4.5 5.3"/>',
    calisan:'<circle cx="12" cy="7" r="3.3"/><path d="M5 21c0-4 3.1-7 7-7s7 3 7 7"/><path d="M9.5 14.6 12 19l2.5-4.4"/>',
    masa:'<path d="M3 9h18"/><path d="M5 9l1-3h12l1 3"/><path d="M7 9v11M17 9v11M7 15h10"/>',
    saat:'<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    zil:'<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.6 1.8H4.4z"/><path d="M10 21a2.2 2.2 0 0 0 4 0"/>',
    sira:'<circle cx="5" cy="8" r="2"/><circle cx="12" cy="8" r="2"/><circle cx="19" cy="8" r="2"/><path d="M2.5 17c0-2.4 1.1-4 2.5-4s2.5 1.6 2.5 4M9.5 17c0-2.4 1.1-4 2.5-4s2.5 1.6 2.5 4M16.5 17c0-2.4 1.1-4 2.5-4s2.5 1.6 2.5 4"/><path d="M3 21h18"/>',
    bos:'<circle cx="12" cy="12" r="7" stroke-dasharray="3 3"/>',
    dolu:'<circle cx="12" cy="8" r="3.5"/><path d="M5 20c0-3.9 3.1-7 7-7s7 3.1 7 7"/>',
    kirli:'<path d="M20 3l-7.5 7.5"/><path d="M8.6 10.4l5 5-2.3 2.3C9.4 19.6 5.6 20.6 3 21c.4-2.6 1.4-6.4 3.3-8.3z"/><path d="M6.5 16.5l2 2"/>',
    ara:'<path d="M4 9h12v4.5A5.5 5.5 0 0 1 10.5 19h-1A5.5 5.5 0 0 1 4 13.5z"/><path d="M16 11h1.5a2.5 2.5 0 0 1 0 5H16"/><path d="M8 3.5c0 1.2 1 1.3 1 2.5M12 3.5c0 1.2 1 1.3 1 2.5"/>',
    yonga:'<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5" rx=".5"/><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3"/>',
    kapi:'<path d="M13 4H6v16h7"/><path d="M10 12h10M17 9l3 3-3 3"/>',
    bilgi:'<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.6v.2"/>',
    "kamera-yok":'<path d="M3 3l18 18"/><path d="M10.5 6H15l1.4 2H19a2 2 0 0 1 2 2v7.5M18 20H5a2 2 0 0 1-2-2V10a2 2 0 0 1 2-2h1"/><path d="M9.3 11.3a3.5 3.5 0 0 0 4.9 4.9"/>',
    geri:'<path d="M15 5l-7 7 7 7"/>',
    uyari:'<path d="M12 3.5 2.5 20h19z"/><path d="M12 10v4.5M12 17.2v.2"/>',
    durdu:'<circle cx="12" cy="12" r="8.5"/><path d="M9.5 9v6M14.5 9v6"/>',
    izgara:'<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
    grafik:'<path d="M4 20h16"/><path d="M7 16v-4M12 16V7M17 16v-6"/>',
    canli:'<circle cx="12" cy="12" r="2.5"/><path d="M7.8 7.8a6 6 0 0 0 0 8.4M16.2 7.8a6 6 0 0 1 0 8.4M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14"/>',
    rapor:'<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5"/><path d="M9 17v-3M12 17v-6M15 17v-4"/>',
    kamera:'<rect x="3" y="7" width="13" height="10" rx="2"/><path d="M16 11l5-3v8l-5-3"/>',
    ayar:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    indir:'<path d="M12 4v11M7 10l5 5 5-5"/><path d="M4 19h16"/>',
    oynat:'<path d="M7 5l12 7-12 7z"/>',
    duraklat:'<path d="M8 5v14M16 5v14"/>',
    kilit:'<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    klasor:'<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    guc:'<path d="M12 3v8"/><path d="M6.3 7.3a8 8 0 1 0 11.4 0"/>',
    ekle:'<path d="M12 5v14M5 12h14"/>',
    duzenle:'<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    sil:'<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
    yenile:'<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
    tamam:'<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    kalem:'<path d="M4 20l4-1 11-11-3-3L5 16z"/>',
    harita:'<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
    kalkan:'<path d="M12 3l8 3v6c0 4.5-3.4 8.2-8 9-4.6-.8-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    video:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M10 9l5 3-5 3z"/>',
    liste:'<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
    ampul:'<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
    terminal:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3M12 15h5"/>',
  };
  KK.simgeler=S;
  function simgeEkle(){
    if(document.getElementById("kk-simgeler"))return;
    const d=document.createElement("div");
    d.innerHTML=`<svg id="kk-simgeler" width="0" height="0" style="position:absolute" aria-hidden="true">${Object.entries(S).map(([k,v])=>`<symbol id="i-${k}" viewBox="0 0 24 24">${v}</symbol>`).join("")}</svg>`;
    document.body.prepend(d.firstChild);
  }
  if(document.body)simgeEkle();else document.addEventListener("DOMContentLoaded",simgeEkle);
  document.addEventListener("DOMContentLoaded",()=>{KK.saatTik();setInterval(KK.saatTik,1000)});
})();
