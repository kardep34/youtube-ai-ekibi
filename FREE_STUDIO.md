# VORTEX 360 — yalnızca ücretsiz üretim

Bu sürüm konu veya video uzunluğunu bir örneğe sabitlemez. Dikey, yatay ve kare
formatları destekler. Hiçbir ödeme, abonelik, kredi veya ücretli API yedeği eklenmez.

## İncelemede bulunan eksikler

- Beş rol aynı konuyla ayrı ayrı çağrılıyor; önceki rolün çıktısı sonrakine aktarılmıyor.
- Sabit uzunluk isteyen senaryo talimatları var. Yeni stüdyonun sahne planında süre
  her projeye ve gerçek anlatım kaydına göre belirlenir.
- Gemini API anahtarının olması ücretsiz faturalandırma durumunu kanıtlamıyor.
  Yeni onarım, ayrıca verilen salt okunur Google izniyle anahtarın gerçek
  projesini ve Cloud Billing durumunu her üretim öncesinde doğrular.
- Ücretli olabilecek model yedekleri ve tekrar denemeleri vardı.
- Oturum kuyruğu kalıcı arşiv değil; oturum kapanınca çıktılar kaybolabilir.
- Mevcut sürümde kurgu, zamanlı altyazı ve MP4 render aşaması yoktu.
- Önceki testler gerçek ses erişimini, ücretsiz kotayı veya ses kalitesini doğrulamıyordu.

## Bu değişiklik

- Gemini metin ve ses üretimi, salt okunur proje doğrulaması olmadan durur.
  Anahtarın projesinde bağlı faturalandırma hesabı olmadığı doğrulandığında açılır.
  Bu kontrol model erişimi, bölgesel uygunluk veya ücretsiz kota garantisi vermez.
  Ödeme hesabı bağlıysa (pasif olsa bile), yetki eksikse veya Google yanıtı
  belirsizse üretim kapalı kalır. Ayrıntılar: REPAIR.md.
- NASA Image and Video Library ve Wikimedia Commons için anahtarsız, salt-okunur
  katalog araması eklenir. Eser adı, üretici, kaynak ve lisans bilgileri kaydedilir.
  Sonuç seçimi bir hak temizleme işlemi değildir; dosya sayfası incelenmelidir.
- Pexels ve YouTube Ses Kitaplığı **elle seçim bağlantılarıdır**. Pexels resmî API
  sayfasında 24 Kasım 2026 kontrolünde yeni anahtar verilmesinin durduğu yazıyordu.
  Bu yüzden çalışan otomatik API entegrasyonu olarak gösterilmez.
- Shotcut ve Audacity **indirme bağlantılarıdır**; ChatGPT eklentisi değillerdir.
- Panelde üretilen son Algenib veya diğer ses, yeniden yüklemeden kurguya aktarılır.
- Her projede farklı ses kaydı yüklenebilir; dinleme ve onay alanı eklenir.
  Mekanik yerel ses üretimi kalite tercihi nedeniyle bu sürüme dahil edilmez.
- Kullanıcı metni/senaryoyu yapıştırır; görsel ve klipleri dosya olarak yükler.
  FFmpeg sahneleri sırayla işler, isteğe bağlı altyazı, anlatım ve müziği birleştirir.
- JSON proje, SRT altyazı, atıf metni, teknik ölçüm raporu, MP4 ve ZIP indirilebilir.
  JSON medya içermez; projeyi geri açınca dosyalar tekrar yüklenmelidir.
- Kayıtlı bir kaynak dosyasının atıf koşullarına uymak kullanıcı incelemesi gerektirir.
  Ücretsiz arama içeriğin koşulsuz veya her kullanım için uygun olduğu anlamına gelmez.

## Kurulum

Streamlit Community Cloud, `requirements.txt` ile Python paketlerini ve
`packages.txt` ile ffmpeg, fonts-dejavu-core paketlerini yükler.
Mevcut Gemini anahtarı ve Google OAuth istemcisi kullanılır. Üretim için ayrı
salt okunur Google izni gerekir; ödeme veya yeni ücretli hizmet gerekmez.
Var olan panel şifresi korunur.

Yerelde (Debian/Ubuntu):

```sh
sudo apt-get install ffmpeg fonts-dejavu-core
python -m pip install -r requirements.txt
streamlit run app.py
```

Paketler ücretsizdir; donanım, internet ve barındırma kaynakları ayrıca gerekir.
Ücretsiz bulutta sınırsız üretim veya ağır AI video oluşturma garantisi yoktur.
RAM ve işlem süresi yetmezse aynı uygulama mevcut bilgisayarda çalıştırılabilir.
Sunucudaki yüklemeler toplam 200 MB ile sınırlıdır; her sahne en çok bir saattir.
Bu işleme sınırları bir içerik süresi önerisi değildir.

## Kullanım

1. Konuyu, onaylanmış anlatımı ve görüntü formatını girin.
2. Anlatımı yükleyin Sesin ölçülen süresine göre sahne
   sürelerini ayarlayın. 0,75 saniyeden fazla farkta render durur; ses sessizce kesilmez.
3. Sahne tablosuna yüklenen dosya adı, süre ve kısa altyazı girin. Altyazı sahnenin
   tamamında görünür; otomatik konuşma tanıma veya kelime hizalama yoktur.
4. Kaynaklarda arayın, dosyayı kaynak sayfasından indirin ve medya alanına yükleyin.
   Atıf kaydını tamamlayın. Otomatik medya indirme eklenmemiştir.
5. Önizleme üretin; sonra önizleme seçimini kapatarak tam çözünürlükte çıktı alın.
6. Projeyi ve ZIP'i indirin. YouTube'a yükleme ayrıca mevcut onayla yapılır.

Fotoğraflar sabit kadrajla gösterilir. Yatay medya bozulmadan sığdırılır ve boşluklar
doldurulur. Kaynak klip sesi kapatılır; kısa klipler döngülenir. Anlatım varsa ses
seviyesi düzenlenir, müzik düşük seviyede karıştırılır. Otomatik sinematik kamera,
yüz koruma, gerçek doğrulama ve profesyonel miks garantisi verilmez.

## Kalite yaklaşımı

Ses kaydının dinleme onayı dosyanın özetiyle ilişkilendirilir; farklı kayıt seçildiğinde
yeniden onay gerekir. Ortak görev paketi kaynak editörü, görsel yönetmeni, ses
yönetmeni ve son editör görevlerini de içerir. Bu paket ChatGPT’de kullanılır;
yeni otonom ajan veya ücretsiz yerel dil modeli kurulmuş olduğu anlamına gelmez.
Çıktı inceleme videosu olarak sunulur. Teknik rapor profesyonel kalite sertifikası
değildir. Sırf ücretsiz olması düşük kaliteyi kabul etme nedeni değildir.

## Sonraki geliştirmeler

Ücretsiz yerel konuşma tanıma (donanıma bağlı), kelime hizalama, sahne düzenleyici,
kalıcı proje arşivi ve ayrıntılı çıktı kalite raporu ayrı çalışmalar
olarak kalır. Bu sürüm bu özellikleri tamamlanmış gibi göstermez.

## Resmî kaynaklar

- https://images.nasa.gov/docs/images.nasa.gov_api_docs.pdf
- https://www.nasa.gov/nasa-brand-center/images-and-media/
- https://www.mediawiki.org/wiki/API:Imageinfo
- https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia
- https://www.pexels.com/api/
- https://support.google.com/youtube/answer/3376882
- https://ai.google.dev/gemini-api/docs/pricing
- https://ffmpeg.org/legal.html
- https://shotcut.org/
- https://www.audacityteam.org/
