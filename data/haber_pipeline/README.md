# Haber bölümleme pilot paketi

Bu paket, seçilen kısa biçimli Sol pilotunu yerel deneme klasörleri olmadan hazırlamak içindir. Ana kaynak dosyaları mevcut `data/Ekonomi/-Ekonomi_Temiz/` ağacından okunur.

- `pilot_sources.json`: KanalD, Show ve ATV için göreli kaynak yolları, ham/temiz metin SHA-256 değerleri ve dondurulmuş yerel model başlangıç önerileri. Bu öneriler referans etiket değildir; yeni günler için kesme kuralları olarak kullanılmaz.

Ham kaynak hash'i hesaplanırken Git'in Windows CRLF dönüşümünden etkilenmemek için satır sonları LF'ye normalize edilir; dosya içeriği yeniden yazılmaz. Temiz metin hash'i ayrıca doğrulanır.
- `references/`: Aynı üç kaynağın bölüm başlangıç konumları ve türleri. Metin ve haber başlıkları içermez. Codex incelemeleridir; bağımsız insan onaylı gold değildir. API isteklerine gönderilmez.
- `pilot_results.json`: Sol low, Luna low ve Luna medium için sayısal pilot ölçümleri ve cache yazımı dahil kullanım maliyeti. Reddedilen Luna yanıtlarının sınırları yalnız tanısal eşleştirme sonrasında değerlendirilmiştir; üretim kabulü değildir.

Ham API istek/yanıtları, anahtarlar, yerel Batch kimlikleri, kişisel etiketleme oturumları ve model ağırlıkları bu pakette yer almaz. Bunlar yerel çalışma alanında korunur. Bu üç kayıt önceden görülmüş tanı örnekleridir; tüm kanallarda başarı veya günlük otomasyonun tamamlandığı anlamına gelmez.

Çalıştırma: [Sol modülünün kullanım belgesi](../../scriptler/docs/GPT_NEWS_REVIEW_BATCH.md).
