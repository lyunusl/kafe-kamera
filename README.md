# Kafe Kamera

Kafe ve restoranın mevcut güvenlik kamerasından masa, müşteri ve çalışan ölçümleri: hangi masa ne kadar dolu kaldı, garson kaç saniyede geldi, kasada kaç kişi bekledi, gün sonunda Excel raporu ve öneriler.

<p align="center">
  <a href="https://github.com/lyunusl/kafe-kamera/releases/latest/download/KafeKamera.exe">
    <img src="https://img.shields.io/badge/Windows%20i%C3%A7in%20indir-KafeKamera.exe-0078D4?style=for-the-badge&logo=windows&logoColor=white" alt="Windows için indir: KafeKamera.exe" height="56">
  </a>
  <br>
  <sub><b>Ücretsiz</b> · Windows 10/11 (64 bit) · Kurulum ve Python gerekmez · <a href="https://github.com/lyunusl/kafe-kamera/releases/latest">Sürüm notları</a></sub>
</p>

> **İndirdikten sonra:** `KafeKamera.exe`'yi çift tıklayın. Gereken her şey exe'nin içinde; ilk açılışta veri klasörü kurulur, örnek videolar kopyalanır ve tarayıcıda Başlangıç sayfası açılır.
> Windows "tanınmayan uygulama" uyarısı verirse **Ek bilgi → Yine de çalıştır**'a basın (exe imzalı değil).
>
> Exe yaklaşık 360 MB (yapay zekâ modeli, PyTorch ve video araçları içinde); her açılışta kendini geçici klasöre açtığı için başlaması 10 saniye kadar sürer.

Her şey kendi bilgisayarınızda çalışır, internet gerekmez. Görüntü hiçbir yere gönderilmez; yüzler her karede gizlenir, kimlik tanıma yapılmaz.

## Ne ölçer

- **Masa süresi:** hangi masa, kaç kişi, ne zaman oturdu, ne zaman kalktı, kaç dakika sürdü.
- **En çok istenen masa:** masa başına doluluk, oturum sayısı, ortalama süre; hiç kullanılmayan masalar.
- **Garson uyarısı:** oturma → ilk garson teması süresi; eşik aşılırsa "ilgilenilmedi" uyarısı.
- **Kirli masa:** müşteri kalktıktan sonra masanın temizlenmeden kaldığı süre ve temizlik süresi.
- **Kasa kuyruğu:** kuyruk uzunluğu, sırada bekleme süresi, kuyruğu görüp sıraya girmeden çıkan müşteri.
- **Çalışan süresi:** masada servis, tezgâh/kasa, yürüme ve boşta geçen süre.
- **Çalışan ayrımı:** kıyafet rengiyle (önlük, tişört; birden fazla renk seçilebilir). Üniforma yoksa tezgâh arkası gibi bir **çalışan alanı** çizilir.
- **Yüzler gizli:** kaydedilen her karede ve işaretli videoda yüzler pikselleştirilir; kimlik tanıma yok.
- **Mevcut kamera ya da kayıt:** IP kamera / kayıt cihazı (RTSP), HTTP akışı, USB kamera ya da video dosyası.
- **Gün sonu Excel raporu** (özet, masalar, oturumlar, çalışanlar, uyarılar), yoğunluk haritası ve düz yazıyla öneriler.

## İlk kullanım

1. **`KafeKamera.exe`'yi çift tıklayın.** Siyah bir pencere açılır (programın kendisi; kapatınca program da kapanır) ve tarayıcıda Başlangıç sayfası gelir: `http://127.0.0.1:8770`. Sayfa yalnızca bu bilgisayardan açılır.
2. **Örnek analizi çalıştır.** Dört örnek video (salon, teras, kasa, bahçe) analiz edilir; panel ve `rapor.xlsx` çıkar. İlk seferde bilgisayarın hızına göre birkaç dakika sürer, sonra saniyeler.
3. **Kamera ekle / ayarla.** Bağlantı türü, marka, IP adresi, kanal ve kullanıcı adı; çalışanların kıyafet rengi. **Kaydet**'e basın. Şifre bu sayfaya yazılmaz.
4. **Bağlantıyı dene.** Başlangıç sayfasında kamerayı seçin, şifreyi şifre kutusuna yazın. Program kameraya bağlanır, bir kare alır ve yüzleri gizleyip kaydeder. Ulaşılamayan adreste 8 saniyede vazgeçer ve neyi kontrol etmeniz gerektiğini yazar.
5. **Masaları çiz.** Alınan karede her masanın (sandalyeleriyle) köşelerine tıklayıp **Bölgeyi kapat**; gerekirse tezgâh/kasa, kuyruk ve çalışan alanı da çizilir. **Kaydet**.
6. **İzlemeyi başlat.** Görüntü parça parça (varsayılan 15 dakika) kaydedilir, her parça analiz edilir, panel yenilenir ve ham kayıt silinir. Kamera bir video dosyasıysa **Videoyu analiz et** görünür.
7. **Paneli aç / Excel raporu.** Bütün kameralar tek panelde; uyarıya tıklayınca işaretli videoda o ana gider.

Ayarlar, kareler ve çıktılar `%LOCALAPPDATA%\KafeKamera` klasöründedir (Başlangıç sayfasında **Veri klasörü**). Programı kaldırmak için exe'yi ve bu klasörü silmeniz yeterli.

## Kameralar

Hazır adres şablonları: **Hikvision / HiLook, Dahua / Imou, Uniview (UNV), Reolink, TP-Link Tapo / VIGI, Axis, EZVIZ**.
Listede yoksa **Diğer**'i seçip tam RTSP adresini yazın; şifre yerine `{sifre}` bırakın. Adresler markaların yaygın şablonlarıdır; bazı modellerde farklı olabilir, o zaman tam adres kullanılır.
Analiz için kameranın **alt akışı** (genelde 640p–720p) yeterlidir ve çok daha hızlıdır.

Ayrıca: HTTP (MJPEG) akışı, USB kamera ve video dosyası (ör. kayıt cihazından dışa aktarılmış kayıt).

## Çalışan kıyafet rengi

- Hazır renkler: turuncu, kırmızı, bordo, sarı, yeşil, turkuaz, mavi, lacivert, mor, pembe, siyah, beyaz. Birden fazlası seçilebilir (ör. garson siyah, mutfak beyaz).
- Siyah, beyaz ve lacivert müşterilerde de çok görülür; tek başına güvenilmez. Mümkünse renkli önlük önerin.
- **Kareden seç:** karede bir çalışanın kıyafetine tıklayarak özel renk eklenir.
- Yanlış "çalışan" sayımına karşı: arka planda zaten o renkte olan pikseller (masa, sandalye, duvar) ve dağınık küçük lekeler sayılmaz; oturan ya da masada baştan sona kıpırdamayan kişi, rengi ne olursa olsun müşteri sayılır.
- Çalışan alanına (tezgâh arkası, mutfak) giren kişi kıyafetinden bağımsız çalışan sayılır.

## Gizlilik

- Program yalnızca bu bilgisayarda çalışır; yerel sunucu yalnızca `127.0.0.1` adresini dinler, ağdaki başka cihazlar erişemez. İnternet bağlantısı kullanılmaz.
- Kaydedilen her karede ve işaretli videoda yüzler pikselleştirilir. Kimlik tanıma yoktur; çalışan ile müşteri yalnızca kıyafet rengi ve konumla ayrılır.
- **Kamera şifresi kaydedilmez.** Bağlanırken şifre kutusuna yazılır, yalnızca o oturumda bellekte tutulur; ekranda ve kayıtlarda `****` görünür. Adres içine yazılmış bir şifre de ayar dosyasına yazılmaz.
- İzlemede ham kayıt her parça analiz edildikten sonra silinir; kalan işaretli video yüzleri gizlenmiş haldedir.

## Sınırlar

- Örnek videolar yapay zekâ ile üretildi (15–30 sn); gerçek kişi yoktur. Bu yüzden panelde süreler saniye olarak görünür; gerçek kamerada aynı ölçümler dakika ve saat olarak birikir.
- RTSP bağlantısı gerçek bir kamerayla denenmedi; yalnızca ulaşılamayan adreste hata mesajı ve video dosyasından kayıt/izleme denendi.
- İzleme canlı değil, parça parça çalışır: sonuçlar her parça bittikten sonra gelir. Analiz işlemcide (CPU) yapılır ve görüntünün kendisinden uzun sürer: 30 saniyelik 720p örnek videonun analizi test bilgisayarında yaklaşık 1 dakika sürdü. Analiz sürerken kayıt yapılmaz, yani 15 dakikalık bir parçanın analizi sürerken gelen görüntü ölçülmez.
- Turuncu dışındaki hazır renkler, o rengi giyen çalışanların olduğu bir videoda denenmedi.
- Kişi takibi kopabildiği için "izlenen müşteri" sayısı gerçek kişi sayısından fazla çıkabilir.
- Kıyafet rengi seçilmeyen ya da renksiz giyinen çalışan müşteri sayılır. Kimlik tanıma olmadığı için çalışan sayısı "aynı anda görünen en çok kişi" olarak hesaplanır; kişiler birbirinden ayrılamazsa çalışan süresi tek "tüm çalışanlar" satırı olarak verilir.
- Tezgâh arkasında durmak "tezgâh" sayıldığı için oradaki "aktif %" boşta bekleyeni ayırt etmez.
- Masadaki kişi sayısı, kişi kapandığında ya da algılanmadığında eksik çıkabilir.
- Algılanmayan bir kişinin yüzü gizlenmez; algılama oranı kamera açısına bağlıdır.
- Adisyon/ciro eşleştirmesi ve saatlik personel planı yok.
- Yalnızca Windows 10/11 (64 bit) için hazır exe var.

## Kaynak koddan çalıştırma

Python 3.12 ile:

    py -3.12 -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt
    .venv\Scripts\python uygulama.py

Kaynak koddan çalışırken veriler proje içindeki `veri/` klasörüne yazılır (`KAFE_KAMERA_VERI` ortam değişkeniyle değiştirilebilir).
Exe'yi üretmek için `build.cmd` (sonuç: `dist\KafeKamera.exe`).

## Lisans

[GNU AGPL-3.0](LICENSE). Kişi ve duruş algılama Ultralytics YOLO11 (`yolo11s-pose.pt`) ile, kişi takibi Ultralytics içindeki ByteTrack ile yapılır; Ultralytics ve model ağırlıkları AGPL-3.0 lisanslı olduğu için bu proje de AGPL-3.0'dır.
Exe ayrıca PyTorch (BSD), OpenCV (Apache-2.0), openpyxl (MIT), Pillow ve ffmpeg (imageio-ffmpeg derlemesi, GPL; kaynak kodu ffmpeg.org) içerir.
