# Ücretsiz üretim bağlantısı onarımı

Eski kontrol hiçbir koşulda ses veya metin üretimine izin vermiyordu. Yeni kontrol
Google API Keys `lookupKey` ile mevcut GEMINI_API_KEY anahtarının gerçek proje
numarasını bulur ve aynı projenin Cloud Billing `getBillingInfo` yanıtını okur.
Başarılı ve kimliği doğrulanmış yanıtta `billingEnabled` false ve
`billingAccountName` boş olmalıdır. Bağlı ama kapalı hesap da reddedilir.
Proto JSON'ın atladığı varsayılan false/boş alanlar, ancak kimliği doğrulanmış
başarılı BillingInfo kaydında kabul edilir. Hatalar, yönlendirmeler ve yetki
eksikleri üretimi açmaz. Proje numarası elle girilmez; başka projenin ücretsiz
olduğu beyanıyla bu anahtar kullanılamaz.

Kontrol her üretim ve ses modeli yedeği öncesinde yenilenir; başarılı durum
önbelleğe alınmaz. Dışarıdan eşzamanlı yapılan faturalandırma değişikliklerine karşı
kontrol ile üretim atomik değildir. Bu panel ödeme açmaz, hesap bağlamaz, IAM
izni vermez. Projeye başka araçlarla faturalandırma bağlanmamalıdır.

## İlk bağlantı

1. Panelin üstündeki **Google ücretsiz kullanım kontrolünü bağla** düğmesine basın.
2. **Salt okunur Google izin ekranını aç** ile mevcut Gemini projesine erişimi olan
   Google hesabını seçin. Bu, YouTube kanal izninden ayrı bir okuma iznidir.
3. **Ücretsiz kullanım durumunu kontrol et** sonucunu inceleyin. Başarılıysa
   eski Algenib üretimi kullanılabilir. Ses üretimi modelin ücretsiz kotasına,
   kullanılabilirliğine ve sunucu bölgesine ayrıca bağlıdır.

OAuth istemcisi zaten kullanılan `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`,
`YOUTUBE_REDIRECT_URI` ayarlarını kullanır. Google Cloud projesinde API Keys API
ve Cloud Billing API erişimi ve OAuth izin ekranında şu kapsamlar gerekir:

- `https://www.googleapis.com/auth/cloud-platform.read-only`
- `https://www.googleapis.com/auth/cloud-billing.readonly`

Kullanıcı hesabının anahtarın projesinde `apikeys.keys.lookup` ve
`resourcemanager.projects.get` izinleri olmalıdır. Uygulama bunları vermez.
Google OAuth uygulaması test modundaysa giriş yapan hesap test kullanıcıları
arasında olmalıdır. Google izin ekranı engelliyorsa OAuth yapılandırması kontrol
edilmelidir; **kart eklemek veya ücretli katmana geçmek çözüm değildir**.

Oturum izinleri yalnızca Streamlit oturum belleğindedir. Çıkışta silinir; yeniden
başlatmada yeniden bağlantı gerekebilir. Anahtarlar, tokenlar ve Google hata
gövdeleri kullanıcıya veya test raporlarına yazılmaz. lookupKey sorgusu anahtarı
Google'a gönderir; HTTP hata URL'leri özellikle gösterilmez.

## Diğer düzeltmeler

- Panelde üretilen ses, **Panelde üretilen son ses kaydını kullan** seçimiyle MP4
  stüdyosuna aktarılır; telefona indirip yeniden yüklemek gerekmez.
- Ses için mevcut dinleme onayı korunur ve kaydın özetiyle ilişkilidir.
- Botlar toplu çalışırken önceki botların çıktılarını sonraki botlara aktarır.
- Kota hatası (429) artık ana botta tekrar tekrar denenmez.
- Ücretsiz kontrol hataları genel bağlantı hatasının arkasında gizlenmez.

## Doğrulama sınırları

Yerel testler sahte Google yanıtlarıyla ücretsiz/ücretli proje, eksik yetki,
yönlendirme, yanlış anahtar kimliği, bağlantı kesintisi, OAuth durum imzası,
ses yedeğine geçerken yetki kaybı ve panel içi ses aktarımını kapsar.
Gerçek Google okuma izni henüz verilmediyse canlı ücretsiz ses üretimi
**doğrulanmış değildir**. Bu onarım Tollund videosunu tamamlanmış saymaz.

Resmî API belgeleri:
- https://docs.cloud.google.com/api-keys/docs/reference/rest/v2/keys/lookupKey
- https://docs.cloud.google.com/billing/docs/reference/rest/v1/projects/getBillingInfo
- https://docs.cloud.google.com/billing/docs/reference/rest/v1/ProjectBillingInfo
