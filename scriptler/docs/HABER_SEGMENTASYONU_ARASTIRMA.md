# Haber bülteni bölümleme araştırması — 14 Ekim 2026

## Sorun ve mevcut kanıt

Hedef genel konu değişimi değil, editoryal haber olayı sınırıdır. Sunucu anonsu, muhabir anlatımı, röportaj ve stüdyoya dönüş aynı habere ait olabilir. İki ayrı olay ise aynı ekonomi/politika sözcüklerini paylaşabilir. Bu nedenle yerel metin benzerliği tek başına yeterli değildir.

28 Ocak Kanal D denemesinde 83 tahmini sınırın 51'i yanlış, 13 gerçek sınır eksikti. Birleştirme denemesi 12 yanlış sınırı kaldırdı; 39 yanlış sınır kaldı. Toleranslı değerlendirmede iki yararlı yakın sınır da kayboldu. Referanslar Codex incelemesidir, bağımsız insan onaylı altın veri değildir. Bu tarih artık geliştirme için görülmüştür; sonraki başarı iddiası yeni tarihlerle ölçülmelidir.

## Doğrudan ilgili birincil kaynaklar

1. **SpeechTopSeg (ECAI 2024)**: çok dilli yayın konuşması bölümleme projesi. Metin bloklarının temsillerini komşu bağlam ve Transformer ile işler. Euronews videolarının bölüm zamanlarından eğitim etiketleri üretir. Türkçe test edilmiş değildir. [Makale](https://arxiv.org/html/2409.06222v1), [kod](https://github.com/sakshishukla1996/SpeechTopSeg).
2. **Def-DTS (ACL Findings 2025)**: önceki/sonraki bağlamla konuşma niyetini değerlendirerek konu geçişlerini belirler. Konuyu geliştirme ile yeni konu başlatma ayrımını kullanır. Haber bülteni rollerine uyarlama aşağıdaki önerimizdir; makalenin Türkçe haberlerde doğrulanmış sonucu değildir. [Makale](https://arxiv.org/html/2505.21033v1), [kod](https://github.com/ElPlaguister/Def-DTS).
3. **Broadcast News Story Segmentation Using Conditional Random Fields and Multimodal Features (2012)**: metin, ses ve görüntü ipuçlarını sıralı modelle birleştirir. Bağımsız sınır sınıflandırması yerine etiketler arası ilişkileri kullanır. [Yayıncı sayfası](https://www.jstage.jst.go.jp/article/transinf/E95.D/5/E95.D_5_1206/_article/-char/en).
4. **Utiyama–Isahara (2001)**: tüm metnin olasılığına göre en iyi bölümlemeyi seçen yaklaşım. Bizim süre öncülleri ve yayın rolleriyle genişletmemiz ayrı bir deney olacaktır. [Makale](https://aclanthology.org/P01-1064/).

## Önerilen yeni deney

1. VTT zamanlarını ve kaynak karakter konumlarını koru. Altyazı satırlarını otomatik olarak cümle kabul etme; anlamlı konuşma blokları oluştur. Yazım düzeltmesini kaynak sınırlarından ayrı tut.
2. Bloklar için yayın rolü ve olay devamlılığı özellikleri çıkar: anons, paket anlatımı, alıntı/röportaj, stüdyoya dönüş, kısa haber, açılış/kapanış. Bunları elle yazılmış kanal tetikleyicileriyle değil örneklerden öğren. Kanal bias'ını ortak modelin üzerine ekle.
3. Bütün bülten için tutarlı bölümlemeyi birlikte seç. Olay tutarlılığı, rol geçişi, zaman boşluğu ve öğrenilen süre dağılımı birlikte puanlansın. Bölüm sayısına ceza kullanılsın ama her güne sabit 35 haber dayatılmasın. Kısa haberleri korumak için tek bir asgari süre kuralı koyulmasın. Eski aday listesinin kaçırdığı sınırları da değerlendirebilsin.
4. Yerel sonuçta belirsiz kalan sınırlı bölgeler için API desteğini ayrıca dene. Tam bülteni tekrar tekrar göndermek yerine kaynak blok kimlikleriyle karar al; metni API'ye yeniden yazdırma. Bu yaklaşımın maliyet ve doğruluğu henüz ölçülmemiştir.

## Eğitim verisini daha az elle üretmek

[Kanal D özel klipler](https://www.kanald.com.tr/kanal-d-ana-haber/ozel-klipler) sayfasında ayrı haber klipleri ve süreleri doğrulandı. [28 Ocak 2025 bülten sayfası](https://www.kanald.com.tr/kanal-d-ana-haber/bolumler/kanal-d-ana-haber-28-01-2025) da mevcut. Ancak o günün klip kapsamı veya klip altyazılarına erişim henüz doğrulanmadı.

Öneri: aynı günün tekil haber kliplerinin erişilebilir transkriptlerini tam bülten VTT'sine eşleştir. Uzun ve özgün ifade eşleşmeleri, sıralama ve zamanla yüksek güvenli otomatik eğitim etiketleri üret. Başlık eşleşmesi tek başına sınır kanıtı sayılmasın. Klip sunucu anonsunu içermeyebilir, kısaltılmış olabilir veya başka yayından gelebilir; bu farklar saklansın. Eşleşmeyen haberler otomatik silinmesin. Önce tek günün kapsamını ölç, sonra genişlet.

## Deney ve günlük çalışma koşulları

- Önceki denemeleri ve mevcut kaynakları koru; yeni sonuçları ayrı klasöre yaz.
- Geliştirmede mevcut günleri kullan, karşılaştırmayı daha önce incelenmemiş tarihlerde yap. Aynı gündemli komşu günlerin veri sızıntısı ihtimalini hesaba kat.
- Yanlış bölme, kaçırılan haber, sınır sapması, bölüm saflığı/kapsaması, Pk/WindowDiff, bülten başına süre ve maliyeti raporla. Sadece çıkan haber sayısını değerlendirme.
- Kaynak metin çıktılardan eksiksiz yeniden kurulabilsin. Günlük kuyruk, dosya karması, yeniden çalıştırma güvenliği ve hata kayıtları mevcut pipeline üzerinden korunsun.
- Veri envanterinde şu an yerel ses/video yok. Ses tonu, konuşmacı ve ekran başlığı özellikleri ancak kaynak medya sağlanırsa ayrı aşamada denenebilir.

İlk tercih: metin ve zamanla bütün bülten bölümleme deneyi; paralel araştırma konusu olarak tekil kliplerden eğitim etiketi üretiminin tek gün üzerinde uygulanabilirliğini ölçmek. Hazır projelerin Türkçede yeterli olduğu veya önerilen sistemin sorunu çözdüğü henüz iddia edilemez.
