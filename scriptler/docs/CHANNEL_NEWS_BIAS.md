# Kanal profiliyle haber ayırma

Bu belge ilk kısmi etiketli araştırma yöntemini anlatır. İlk `kanal_bias_01` denemesi ve sonuçları artık yerel `data/denemeler/akademik_arsiv/yontemler_ve_olcumler.zip` içinde. Sonraki tam bülten profili yerelde `data/denemeler/kanal_bias_tam_02` altında korunur. Aşağıdaki araştırma komutları uygun deney dosyaları geri açılmadan çalışmaz. Git'teki seçilen Sol pilotu [ayrı kullanım belgesindedir](GPT_NEWS_REVIEW_BATCH.md) ve bu özel deney klasörlerini gerektirmez.

Ortak motor, kanala özel öğrenilmiş profil. Kodda kanal adına göre ayrım veya geçiş sözcüğü listesi yok. İlk profil Kanal D için denendi; diğer kanalların profilleri henüz eğitilmedi.

Genel puan; altyazı başlangıcı, noktalama, duraklama, büyük harf ve komşu sözcük yeniliği gibi sayısal özelliklerden öğrenilir. Kanal modeli bunlara ek olarak girişteki 1–3 sözcüklük örüntüleri ve sağ/sol sözcük bağlamını örneklerden öğrenir. Son logit `genel + alpha * (kanal_modeli - genel)` olur. Alpha 0 ise kanal önceliği devre dışıdır. Hiçbir ifade tek başına zorunlu kesim değildir. Sigmoid çıktıları kalibre edilmiş güven olasılıkları değildir.

Her kelime başlangıcı adaydır; modelden kimlik veya kelime sayısı ürettirilmez. Kesimler doğrudan kodun kaynak konumlarına yapılır. Birbirine çok yakın adaylardan yüksek puanlı olan korunur. Bu yakınlık filtresi de kısa haberleri kaçırabilir. Olay semantiğini tam anlamayan bu küçük sınıflandırıcı, çok az etiketten öğrenir; üretim kalitesi iddiası yoktur.

## Pilot ayrımı

- Kanal D 29/30 Ocak 2025: eğitim, toplam 12 geçici sınır.
- 31 Ocak 2025: geliştirme, 6 geçici sınır; alpha/eşik yalnız burada seçildi.
- 3/4 Şubat 2025: profil dondurulduktan sonra test, 16 geçici sınır. Test sonucuna göre yeniden ayar yapılmadı.

Her tarihin ilk 9000 karakteri kesintisiz okunup etiketlendi. Tam bültenlerin tamamı etiketlenmedi. Eğitim ve test aynı sunucunun yakın tarihli yayınlarıdır; sunucu değişimine, diğer kanallara veya uzun dönem genellemeye kanıt sağlamaz. Etiketler Codex incelemesidir, kullanıcı onaylı bağımsız altın veri değildir. Bu küçük prototipin sonucu böyle yorumlanmalıdır.

## Kullanım

```powershell
python -m pip install -r scriptler/requirements-channel-bias.txt
python scriptler/channel_news_bias.py evaluate
python scriptler/channel_news_bias.py convert --input "data/Ekonomi/-Ekonomi_Temiz/KanalD" --output "data/denemeler/kanal_bias_01/yeni_taslaklar"
```

`--job` öğrenilmiş profilin ve etiketlerin dizinidir. Varsayılan `data/denemeler/kanal_bias_01`. `train` öğrenmeyi tekrar yapar; mevcut pilotta test sonucu görüldükten sonra train tekrar kullanılmamalı. Yeni yöntem veya etiketlerle yeni bir job ve yeni, görülmemiş test günleri gerekir.

VTT/SRT veya zamanlı TXT için mevcut tekrar temizleme kullanılır, zamanlar sidecar JSON'da korunur. Zaman bilgisi olmayan TXT de çalışır; kaynak metin korunur ve zaman uydurulmaz. Metin tabanlı özellikler yine kullanılabilir.

Çıktı kaynağın dışında olmalıdır. Dosya+profil+düzeltme listesi hashleri çıktı sürümünü belirler. Değişmeyen dosya tekrar çağrıldığında atlanır; değişen dosya/profil ayrı sürüme çıkar. Worker kilidi eşzamanlı yazımı engeller. `last_run.json` hata ve çıktı envanteri tutar; hatada komut hata kodu döndürür. Bozuk VTT düz metin sayılmaz. Giriş kanalı ile profil eşleşmesini çağıran iş akışı sağlamalıdır; bir Kanal D profili diğer kanallara otomatik uygulanmamalı.

API çağrısı yok; API anahtarı ve Torch/E5 gerekmiyor. Belirsiz yerlere API bağlamak için önce profilin farklı günlerde doğru/yanlış ve belirsiz kararları ölçülmeli. Kalibre edilmemiş puana göre otomatik API harcaması başlatılmadı. Günlük zamanlayıcı kurulmadı. Bütün haber bölümleri taslak ve inceleme bekliyor.
