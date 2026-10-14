# Bütün bülten bölümleme deneyi

`global_news_trial.py` kelime uzunluğu öncülüyle ilk denemedir. Bu eski giriş noktası ve ölçümleri, 15 Ekim temizliğinden sonra `data/denemeler/akademik_arsiv/yontemler_ve_olcumler.zip` içinde özgün proje yollarıyla korunur. Yeniden üretmek için ilgili kod/veri yollarını ZIP'ten proje köküne geri açmak gerekir.

`global_news_time_trial.py` aynı yaklaşımı zamanlı kaynak ve öğrenilen süre dağılımıyla dener. Deneme `data/denemeler/butun_bulten_zamanli_02` altındadır. Yerel multilingual-e5-small modeli gerekir; mevcut `work/models` kopyasını kullanır. İnternet bağlantısı, model indirme veya API çağrısı yapmaz.

Üç eğitim gününden kısa/uzun bölümlerin süre dağılımı öğrenilir. Yerel kanal başlangıç puanı, bölümün anlam bütünlüğü ve süre öncülü dinamik programlamayla birlikte değerlendirilir. Ayarlar yalnız 4 Şubat geliştirme gününde seçilmiştir. Altyazı içindeki kelime zamanları doğrusal tahmindir. Metin blokları hesaplama birimidir; gerçek cümle veya haber kabul edilmez.

Sınır adayları altyazı başlangıçları, cümle başlangıçları, büyük harfle başlayan kelimeler veya yüksek başlangıç puanı alan kelimelerdir. Referans konumları adaylara eklenmez. Bu kısıtın kapsamı raporda saklanmalıdır. Tam yayın rolü sınıflandırıcısı henüz eğitilmedi.

Tek bir yeni zamanlı VTT/SRT dosyası için:

```powershell
python -m scriptler.denemeler.yerel.global_news_time_trial apply --input "kaynak.vtt" --output "data/denemeler/butun_bulten_zamanli_02/yeni_taslaklar"
```

Aynı kaynak ve model yeniden çalıştırıldığında mevcut çıktı gösterilir. Değişen kaynak veya model yeni sürüm klasörü üretir. Her çıktı `transcript.txt`, `timeline.json`, `sections.json` ve kaynak metni eksiksiz koruyan taslak TXT dosyaları içerir. Bütün bölümler inceleme bekler. Aynı çıktıdaki yarım işlem otomatik olarak yeniden yazılmaz.

Tam denemeyi yeni klasöre kurmak için:

```powershell
python -m scriptler.denemeler.yerel.global_news_time_trial trial --job "data/denemeler/yeni_butun_bulten_deneyi"
```

Arşivdeki `align_editorial_evidence.py`, resmî klip sayfasından alınan kısa kanıt ifadelerini bir zamanlı kaynağa eşleştirir. Açıklama metninin haberin tamamını temsil ettiğini varsaymaz; otomatik başlangıç/bitiş etiketi üretmez. Tam klip transkriptiyle hizalama ve eğitim etiketi üretme aşaması tamamlanmadı; başarısız/eksik araştırma kanıtı olarak saklandı.

Bu yerel yöntem tek başına günlük sisteme üretim modeli olarak bağlanmadı. Devam edilen API yapılandırması `gpt_news_review_batch.py` içindeki kısa biçimli Sol low'dur. Eski günlük pencere yönteminin başlatıcısı arşive alındı. Performans raporu, kalan yanlış sınırlar nedeniyle otomatik yayımlama doğruluğunu kanıtlamaz.
