# Kafe Kamera

Kafe ve restoranın mevcut güvenlik kamerasından masa, müşteri ve çalışan ölçümleri: hangi masa ne kadar dolu kaldı, garson kaç saniyede geldi, kasada kaç kişi bekledi, gün sonunda Excel raporu ve öneriler.

<p align="center">
  <a href="https://github.com/lyunusl/kafe-kamera/releases/latest/download/KafeKamera-Kurulum-0.2.0.exe">
    <img src="https://img.shields.io/badge/Windows%20i%C3%A7in%20indir-KafeKamera--Kurulum.exe-0078D4?style=for-the-badge&logo=windows&logoColor=white" alt="Windows için indir: Kafe Kamera kurulum dosyası" height="56">
  </a>
  <br>
  <sub><b>Ücretsiz</b> · Windows 10/11 (64 bit) · AugeLab Studio gerekir (kurulum dosyası onu da kurar) · <a href="https://github.com/lyunusl/kafe-kamera/releases/latest">Sürüm notları</a></sub>
</p>

Kafe Kamera, kişileri bu bilgisayardaki **AugeLab Studio** ile algılar. Studio arka planda, penceresi açılmadan çalışır; görüntü hiçbir yere gönderilmez. Yüzler her karede gizlenir, kimlik tanıma yapılmaz.

## Kurulum

`KafeKamera-Kurulum-0.2.0.exe`'yi çalıştırın (0.3.0 için kurulum dosyası yok: kurulu programın `KafeKamera.exe` dosyası değiştirilir, aşağıya bakın). Kurulum adım adım ilerler:

1. **Kafe Kamera** bu kullanıcı için kurulur (`%LOCALAPPDATA%\Programs\KafeKamera`); yönetici izni gerekmez.
2. **AugeLab Studio** kurulu değilse AugeLab'in resmî kurulum dosyası indirilir ve SHA-256 özetiyle doğrulanır. Microsoft Visual C++ çalışma kitaplığı eksikse Microsoft'tan indirilir, Microsoft imzası doğrulanır ve kurulur (Windows izin sorabilir). Studio sessizce kurulur; olmazsa Studio'nun kendi kurulum penceresi açılır.
3. **AugeLab hesabı:** hesabınız yoksa düğmeyle tarayıcıda oluşturun. Ücretsiz Community planı yeterlidir.
4. **Lisans kodu:** AugeLab hesabınızdaki kodu yapıştırın. Kod yalnızca Studio'nun kendi `verify` komutuna verilir; Kafe Kamera onu saklamaz, ekrana ve günlüğe yazmaz. Boş bırakırsanız programdaki sihirbazdan girersiniz.

Windows "tanınmayan uygulama" uyarısı verirse **Ek bilgi → Yine de çalıştır**'a basın (dosyalar imzalı değil).

Program açılınca Başlangıç sayfası tarayıcıda gelir. Sağ üstteki **AugeLab Studio** göstergesi "hazır" değilse aynı dört adımlı sihirbaz açılır. "Hazır", Studio'nun arka planda kısa bir deneme koşusunu geçtiği anlamına gelir: Studio kurulu ve lisanslı, Kafe blokları yükleniyor ve model açılıyor.

## Ne ölçer

- **Masa süresi:** hangi masa, kaç kişi, ne zaman oturdu, ne zaman kalktı, kaç dakika sürdü.
- **En çok istenen masa:** masa başına doluluk, oturum sayısı, ortalama süre; hiç kullanılmayan masalar.
- **Garson uyarısı:** oturma → ilk garson teması süresi; eşik aşılırsa "ilgilenilmedi" uyarısı.
- **Kirli masa:** müşteri kalktıktan sonra masanın temizlenmeden kaldığı süre ve temizlik süresi.
- **Kasa kuyruğu:** kuyruk uzunluğu, sırada bekleme süresi, kuyruğu görüp sıraya girmeden çıkan müşteri.
- **Çalışan süresi:** masada servis, tezgâh/kasa, yürüme ve boşta geçen süre.
- **Çalışan ayrımı:** kıyafet rengiyle (önlük, tişört; birden fazla renk seçilebilir). Üniforma yoksa tezgâh arkası gibi bir **çalışan alanı** çizilir.
- **Mevcut kamera ya da kayıt:** IP kamera / kayıt cihazı (RTSP), HTTP akışı, USB kamera ya da video dosyası.
- **Gün sonu Excel raporu** (özet, masalar, oturumlar, çalışanlar, uyarılar), yoğunluk haritası ve düz yazıyla öneriler.

## İlk kullanım

1. **Kafe Kamera'yı açın.** Siyah bir pencere açılır (programın kendisi; kapatınca program da kapanır) ve tarayıcıda Başlangıç sayfası gelir: `http://127.0.0.1:8770`. Sayfa yalnızca bu bilgisayardan açılır.
2. **Örnek analizi çalıştır.** Dört örnek video (salon, teras, kasa, bahçe) AugeLab Studio'da analiz edilir; panel ve `rapor.xlsx` çıkar. İlk seferde bilgisayarın hızına göre birkaç dakika sürer. Algılama sonuçları saklanır: aynı video yeniden raporlanırken (ör. kıyafet rengi değişince) Studio gerekmez.
3. **Kamera ekle / ayarla.** Bağlantı türü, marka, IP adresi, kanal ve kullanıcı adı; çalışanların kıyafet rengi. **Kaydet**'e basın. Şifre bu sayfaya yazılmaz.
4. **Bağlantıyı dene.** Kamerayı seçin, şifreyi şifre kutusuna yazın. Program kameraya bağlanır, bir kare alır, kişileri Studio'da bulup yüzleri gizler ve kareyi kaydeder. Karede kimse bulunamazsa kare tamamen bulanıklaştırılır (masalar kabaca görünür) ve iş kaydı bunu söyler. Studio çalışmazsa kare kaydedilmez.
5. **Masaları çiz.** Alınan karede her masanın (sandalyeleriyle) köşelerine tıklayıp **Bölgeyi kapat**; gerekirse tezgâh/kasa, kuyruk ve çalışan alanı da çizilir. **Kaydet**.
6. **İzlemeyi başlat.** IP kamera (RTSP) ve HTTP akışı **canlı** analiz edilir: AugeLab Studio görüntüyü sürekli işler, **Canlı pano** (`http://127.0.0.1:8770/canli`) birkaç saniyede bir güncellenir, ham kayıt alınmaz. Kamera ayarında **saniyede analiz edilen kare** seçilir (1, 2, 3, 5, 10 ya da özel; varsayılan 3): kamera 25-30 fps gönderse de yalnızca bu kadarı işlenir. USB kamera ve video dosyası eskisi gibi parça parça kaydedilip analiz edilir.
7. **Paneli aç / Excel raporu.** Bütün kameralar tek panelde; uyarıya tıklayınca işaretli videoda o ana gider.

Ayarlar, kareler ve çıktılar `%LOCALAPPDATA%\KafeKamera` klasöründedir (Başlangıç sayfasında **Veri klasörü**). Program kaldırılınca bu klasör yerinde kalır.

## AugeLab Studio ile nasıl çalışır

- Kafe Kamera, Studio'nun kodunu içermez ve Studio penceresini hiç açmaz. Her iş (örnek ya da kamera videosunun analizi, bağlantı denemesindeki tek kare, canlı kameranın bir parçasının kaydı) için Studio'nun kendi Python'uyla gizli bir süreç başlatır: `python -m studio run kafe-kamera.pmod --json`. İş bitince süreç kapanır.
- `kafe-kamera.pmod` programla gelen hazır sahnedir: **Kafe Kaynak** (video, tek kare ya da canlı akış) → **Kafe Algılama** (YOLO11s-pose ile kişi ve iskelet noktaları, ByteTrack ile takip). İşin ne olduğu sahneye yazılmaz; sürecin ortam değişkenleriyle verilir.
- Kafe Kamera iki blok dosyasını Studio'nun özel blok klasörüne (`%APPDATA%\AugeLab Studio\marketplace\custom_blocks`) ve motorunu yanına (`marketplace\kafe_engine`: model, `kafe_motor`, `ultralytics` ve `lap`) yazar. Studio'nun kendi Python ortamına paket kurulmaz; torch, numpy ve OpenCV Studio'nunkilerdir.
- Algılama ayarları 0.1.0 ile aynıdır (`conf 0.2`, `iou 0.6`, ByteTrack, varsayılan her 2 karede bir, giriş 960 piksel). Studio 3.12.0'da `salon.mp4` için motorun sonucu 0.1.0'ın programın içinde yaptığı algılamayla karşılaştırıldı: 361 karenin 361'inde aynı izler, aynı kutular ve noktalar (en büyük fark 0 piksel).
- Studio'nun MCP sunucusu kullanılmaz; Studio penceresinin açık olması gerekmez.
- Programın kendisi (KafeKamera.exe) artık PyTorch ve Ultralytics içermez (yaklaşık 150 MB; 0.1.0'da 360 MB).

## Canlı izleme nasıl çalışır (0.3.0)

Her canlı kamera için AugeLab Studio'da gizli, uzun süreli bir süreç çalışır. Akışı sürekli okur (yalnızca en son kare; kopunca kısa aralıklarla yeniden bağlanır), seçilen hızda kareleri zamana göre seçip kişileri izler (iz numaraları koşu boyunca sürer) ve çalışanın kıyafet rengini orada hesaplar. Panel bu algılamaları birkaç saniyede bir okur ve masa, oturum, garson, temizlik ve kuyruk kurallarını aynen uygular. Akış koparsa pano kamerayı "bağlantı koptu, yeniden deneniyor" olarak gösterir; sayıları sıfır göstermez. Bilgisayar seçilen hıza yetişemezse daha az kare işlenir ve pano bunu yazar.

Kayıt cihazı (NVR) bağlantısı: RTSP TCP üzerinden açılır, 8 saniyelik bağlantı ve okuma sınırı vardır, alt akış önerilir. Bağlanılamazsa neden ayrılır: cihaza ulaşılamıyor, kullanıcı adı / şifre kabul edilmedi, kanal ya da akış yok, ya da görüntü biçimi çözülemedi (ör. H.265 alt akış: H.264 yapın).

## Ne denendi (0.2.0)

- **Temiz Windows (Windows Sandbox, Windows 11):** kurulum dosyası Visual C++ çalışma kitaplığını ve AugeLab Studio 3.12.0'ı indirip doğruladı ve kendisi kurdu (yaklaşık 13 dakika), lisans kodunu kurulum adımında Studio'ya kaydetti ve programı açtı. Studio denemesi yarım dakikada geçti; dört örnek videonun analizi (yaklaşık 6 dakika) bu geliştirme bilgisayarındakiyle aynı sayıları verdi; bağlantı denemesindeki karede yüzler gizlendi. Kurulum ve analiz boyunca hiçbir AugeLab Studio penceresi görünmedi ve Studio'nun MCP portu (8765) hiç açılmadı.
- **Üstüne kurma (aynı Sandbox):** program açıkken yeni derleme kuruldu: kurulum açık paneli kapattı, Studio'nun kurulu olduğunu gördü, lisans sayfası boş geçildi (Studio zaten etkindi) ve yeni programı açtı. Studio denemesi, dört örnek (aynı sayılar) ve bağlantı denemesi yine geçti; Studio penceresi görünmedi, 8765 açılmadı.
- **Geliştirme bilgisayarı:** dört örnek videonun bütün sonuçları (`sonuc.json`) 0.1.0'ınkilerle aynı çıktı. Canlı kayıt, kullanıcı adı ve şifre isteyen yerel bir HTTP (MJPEG) deneme akışıyla denendi: parça kaydedilip analiz edildi; şifre hiçbir komut satırında, dosyada ve günlükte görülmedi.

## 0.2.0'dan 0.3.0'a güncelleme (kurulum gerekmez)

1. Kafe Kamera'yı **Kapat** düğmesiyle kapatın (canlı izleme ve Studio süreçleri durur).
2. `%LOCALAPPDATA%\Programs\KafeKamera\KafeKamera.exe` dosyasının üstüne yeni `KafeKamera.exe`'yi kopyalayın.
3. Kafe Kamera'yı açın. Program açılışta Studio'daki Kafe bloklarını ve motorunu kendisi yeniler ve AugeLab Studio'yu bir kez kısa bir denemeyle yeniden kontrol eder (lisans kodu istemez). Kameralar, bölgeler, renkler ve geçmiş sonuçlar (`%LOCALAPPDATA%\KafeKamera`) olduğu gibi kalır; canlı izlemeyi başlatırken yalnızca kamera şifresi yeniden girilir (şifre hiç kaydedilmez).

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

## Gizlilik: ne yerelde kalır

- Analiz yalnızca bu bilgisayarda yapılır; yerel sunucu yalnızca `127.0.0.1` adresini dinler. İnternet yalnızca AugeLab Studio'nun kurulumu ve lisans kodunun kaydı için kullanılır (Studio'nun kendisi lisans için AugeLab'e bağlanabilir).
- Kaydedilen her karede ve işaretli videoda yüzler pikselleştirilir. Kimlik tanıma yoktur; çalışan ile müşteri yalnızca kıyafet rengi ve konumla ayrılır. Studio bloklarının görüntü çıkışı yoktur.
- Bağlantı denemesindeki kare diske yazılmadan Studio'ya verilir: Studio onu bu bilgisayardaki (127.0.0.1) tek seferlik, rastgele bir adresten bir kez alır. Kaydedilen karede bulunan herkesin yüzü pikselleştirilir; kimse bulunamazsa bütün kare bulanıklaştırılır. Studio çalışmazsa kare kaydedilmez.
- **Kamera şifresi kaydedilmez.** Bağlanırken şifre kutusuna yazılır, yalnızca o oturumda bellekte tutulur. Canlı kayıtta akış adresi yalnızca Studio sürecinin ortam değişkenine verilir; komut satırına ve dosyaya yazılmaz. Studio ya da FFmpeg çıktısında adres, kullanıcı adı ya da şifre geçerse Kafe Kamera onu günlüğe ve hata iletisine yazmadan önce `****` ile gizler. (Studio'nun kendi şifreli günlüğünün içeriği denetlenemez.)
- AugeLab lisans kodu saklanmaz; yalnızca Studio'nun kendi komutuna verilir.
- **Canlı izlemede (IP kamera, HTTP akışı) ham görüntü diske yazılmaz:** Studio yalnızca algılamaları (kutu ve iskelet noktaları) ve saniyede bir, yüzleri gizlenmiş küçük bir önizleme yazar; canlı izleme durunca bunlar da silinir. **USB kamerada** görüntü hâlâ parça parça kaydedilir: parça analiz edilene kadar yüzleri açık haliyle `gecici\kayit\` altında durur; analizden sonra, durdurunca ve Kapat'ta silinir (kapanışta süren iş en çok 20 saniye beklenir; dosya kullanımdaysa bu yazılır ve dosya açılışta silinir). Program çökerse ya da konsol penceresi kapatılırsa parça, bir sonraki iş başlarken ya da program yeniden açılırken silinir.

## Sınırlar

- AugeLab Studio gerekir (Windows 10/11, 64 bit). Studio yoksa ya da lisansı etkin değilse yeni videolar analiz edilmez; program nedenini iş kaydında ve sihirbazda Türkçe yazar. Önceden algılanmış videolar yine raporlanır.
- Henüz denenmedi: AugeLab Studio önceden kuruluyken kurulum, programı kaldırma, eski bir sürümün (0.1.0) üstüne kurma, kurulumda reddedilen lisans kodu, Studio'yu kurulum dosyası yerine programdaki sihirbazla kurma.
- Her iş Studio'yu yeniden başlatır; bu yüzden bağlantı denemesindeki tek kare bile en az Studio'nun açılışı ve modelin yüklenmesi kadar sürer.
- Örnek videolar yapay zekâ ile üretildi (15–30 sn); gerçek kişi yoktur. Bu yüzden panelde süreler saniye olarak görünür; gerçek kamerada aynı ölçümler dakika ve saat olarak birikir.
- Studio'daki canlı kayıt yalnızca bu bilgisayarda çalışan, şifreli bir deneme HTTP (MJPEG) akışıyla denendi; gerçek bir IP kamerayla ve RTSP ile denenmedi.
- Canlı ölçümler, içinde bulunulan 15 dakikalık parçanın algılamaları üzerinde birkaç saniyede bir yeniden hesaplanır; parça bitince sonucu güne eklenir. Parça sınırında süren bir oturum iki oturum olarak sayılabilir (0.2.0'daki parça parça izlemeyle aynı). Canlı kameralarda işaretli video üretilmez (pano önizlemesi var). Analiz işlemcide (CPU) yapılır: bu bilgisayarda bir kamera 3 fps'de Studio'nun yaklaşık 1,1 GB belleğini ve işlemcinin büyük kısmını kullandı; birkaç kamera aynı anda izlenecekse analiz hızını düşürün ve kameraların alt akışını kullanın.
- Turuncu dışındaki hazır renkler, o rengi giyen çalışanların olduğu bir videoda denenmedi.
- Kişi takibi kopabildiği için "izlenen müşteri" sayısı gerçek kişi sayısından fazla çıkabilir.
- Kıyafet rengi seçilmeyen ya da renksiz giyinen çalışan müşteri sayılır. Kimlik tanıma olmadığı için çalışan sayısı "aynı anda görünen en çok kişi" olarak hesaplanır; kişiler birbirinden ayrılamazsa çalışan süresi tek "tüm çalışanlar" satırı olarak verilir.
- Tezgâh arkasında durmak "tezgâh" sayıldığı için oradaki "aktif %" boşta bekleyeni ayırt etmez.
- Masadaki kişi sayısı, kişi kapandığında ya da algılanmadığında eksik çıkabilir.
- Algılanmayan bir kişinin yüzü gizlenmez; algılama oranı kamera açısına bağlıdır.
- Adisyon/ciro eşleştirmesi ve saatlik personel planı yok.

## Kaynak koddan çalıştırma ve derleme

Python 3.12 ve kurulu AugeLab Studio ile:

    py -3.12 -m venv .venv
    .venv\Scripts\python -m pip install -r requirements-gelistirme.txt
    .venv\Scripts\python kurulum\motor_deps.py
    .venv\Scripts\python uygulama.py

`kurulum\motor_deps.py`, motorun Studio'da bulamadığı paketleri (`motor\deps.txt`: ultralytics, lap) geliştirme ortamından `motor\deps\` klasörüne kopyalar. Kaynak koddan çalışırken veriler proje içindeki `veri/` klasörüne yazılır (`KAFE_KAMERA_VERI` ortam değişkeniyle değiştirilebilir).

Hazır sahne (`kurulum\sahne\kafe-kamera.pmod`) depoda yoktur; Studio sahneleri şifreli kaydedildiği için bir kez üretilir:

1. AugeLab Studio'yu açın (MCP sunucusu `127.0.0.1:8765`).
2. `.venv\Scripts\python kurulum\sablon.py`: Kafe bloklarını Studio'ya kaydeder ve sahneyi yeni bir sekmede kurar.
3. Studio'da o sekmeyi **Dosya → Farklı Kaydet** ile `kurulum\sahne\kafe-kamera.pmod` olarak kaydedin.

Sonra `kurulum\derle.cmd`: sınamaları çalıştırır, `dist\arayuzsuz\KafeKamera.exe`'yi ve Inno Setup 6 kuruluysa `dist\kurulum\KafeKamera-Kurulum-0.2.0.exe`'yi üretir. Sahne dosyası yoksa derleme açık bir iletiyle durur.

Sınamalar: `egitim\dene_arayuzsuz.py` (sahte Studio ile arayüzsüz koşu), `egitim\dene_kurulum.py` (Studio kurulumu ve kurulum dosyası), `egitim\dene_motor.py` (motoru Studio'nun Python'unda çalıştırıp 0.1.0 algılamasıyla karşılaştırır).

## Lisans

[GNU AGPL-3.0](LICENSE). Kişi ve duruş algılama Ultralytics YOLO11 (`yolo11s-pose.pt`) ile, kişi takibi Ultralytics içindeki ByteTrack ile yapılır; Ultralytics ve model ağırlıkları AGPL-3.0 lisanslı olduğu için bu proje de AGPL-3.0'dır. Motor Studio'ya Ultralytics (AGPL-3.0) ve lap (BSD-2-Clause) kopyalarıyla birlikte yerleşir; PyTorch, torchvision, NumPy ve OpenCV motorla gelmez, AugeLab Studio'nun kendi Python ortamından kullanılır.
Exe ayrıca OpenCV (Apache-2.0), NumPy (BSD), openpyxl (MIT), Pillow, certifi (MPL-2.0), ffmpeg (imageio-ffmpeg derlemesi, GPL; kaynak kodu ffmpeg.org) ve hazır AugeLab Studio sahnesini (`kafe-kamera.pmod`, Studio'nun şifreli sahne biçimi) içerir. `mcp` paketi yalnızca geliştirme aracı `kurulum/sablon.py` içindir; programa girmez. AugeLab Studio ayrı bir üründür ve kendi lisans koşullarıyla kurulur.
