# Sol ile haber bölümleme — seçilen yapılandırma

15 Ekim 2026 temizliği sonrası devam edilen model **gpt-6.1-sol**, reasoning **low**, tam bülten başına bir Batch Responses isteği ve **kısa sayısal birim kimlikleri**dir. Çıkış sınırı düşünme dahil 4096 token. Yeni prepare işleri de başarılı kısa biçimi kullanır; metin ve koordinatlar korunur, kimlik listesi şemada tekrar edilmez.

Varsayılan mevcut iş: `data/denemeler/maliyet_optimizasyonu_01/compact_sol`. Bu üç kayıt daha önce gönderilmiş ve tamamlanmıştır; tekrar submit edilmez. Ham ve kontrol edilmiş çıktılar bu işin `haberler/` ve `kontrol_edilmis/` dizinlerinde kalır. İnceleme referansları bağımsız insan onaylı gold değildir.

Bu mevcut iş ve ham yanıtlar yereldir; Git'te bulunmaz. Git'teki `data/haber_pipeline/pilot_sources.json`, kaynak seçimlerini ve dondurulmuş yerel önerileri taşır. Ana kaynaklardan aynı üç istek yeniden hazırlanabilir; yerel deneme/model klasörleri gerekmez. Sayısal geçmiş sonuçlar `data/haber_pipeline/pilot_results.json` içindedir. Referansların yalnız konum/tür bilgisi paylaşılır, haber metni ve kişisel etiketleme oturumları paylaşılmaz.

## Mevcut sonuçlar

```powershell
python scriptler/gpt_news_review_batch.py evaluate
```

Önceden collect edilmiş yerel sonuçlar için internet/API erişimi gerektirmez. Temiz bir Git kopyasında önce hazırlık, gönderim ve toplama gerekir; evaluate API yanıtı üretmez. Üç kayıt: KanalD 2025-01-27, Show 2024-11-29 ve ATV 2025-01-27. Üçü de kaynak doğrulamasından geçti. Kaynak korunması, doğru haber sınırlarının garanti edildiği anlamına gelmez; manuel düzeltmeler ayrı kopyada saklanır.

## Yeni pilot hazırlığı

```powershell
python scriptler/gpt_news_review_batch.py prepare --job data/denemeler/sol_yeni_01
```

Bu komut yereldir ve yine tanımlı üç pilot kaydını hazırlar; yeni gün veya 14 kanal için otomatik bir veri seçim komutu değildir. Sürekli günlük işleyicinin bu seçilen Sol yapılandırmasıyla bağlanması ayrı aşamadır. Eski başarısız pencere işleyicisinin run_daily_news.ps1 başlatıcısı akademik arşive alındı.

API anahtarı kullanıcı PowerShell oturumunda tanımlandıktan sonra, bilinçli ücretli gönderim:

```powershell
if (-not $env:OPENAI_API_KEY) { $env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'OpenAI API key' -AsSecureString)).Password }
python scriptler/gpt_news_review_batch.py submit --job data/denemeler/sol_yeni_01
python scriptler/gpt_news_review_batch.py status --job data/denemeler/sol_yeni_01
```

Completed olduktan sonra:

```powershell
python scriptler/gpt_news_review_batch.py collect --job data/denemeler/sol_yeni_01
python scriptler/gpt_news_review_batch.py evaluate --job data/denemeler/sol_yeni_01
```

Aynı iş tekrar gönderilmez, eksik/şüpheli sonuçlar otomatik ücretli yeniden denemeye çıkarılmaz. Anahtar kaynak koda yazılmaz. Collector yalnız seçilen kaynak biriminde aynen ve tekil eşleşen alıntıları kabul eder; cümleleri düzeltmez veya yeniden üretmez. TXT'ler yerelde kaynak konumlarına göre kesilir.

## Maliyet ve arşiv

İndirilen üç kısa Sol yanıtında cache yazımı dahil hesaplanan toplam $0.05685275. Üç kayıt ortalamasını 14 bülten/gün ve 30 güne uzatmak yaklaşık $7.96/ay eder; farklı günlerde kullanım değişir. Bu faturanın kendisi değildir. Cache yazımı 1.25x giriş, Sol cache okuması 0.05x giriş, düşünme dahil çıkış ayrı hesaplanır. Fiyat kaynağı [OpenAI Docs](https://developers.openai.com/api/docs/models/gpt-6.1-sol), kontrol tarihi 15 Ekim 2026.

Yeni hazırlıkların tahmini üst maliyeti cache yazımını kapsar. Eski manifestlerin tarihsel tahminleri değiştirilmedi. Yerel $10 bütçe defteri temizlenmedi; geçmiş işleri unutturup yeniden harcama açmaması için korunur. Bu defter hesabın tamamını veya başka scriptleri kapsamaz.

Yerel model/profil dosyaları, ana veri ve etiketler korunmuştur. Sol-Luna low ve medium karşılaştırmaları açık araştırma kayıtları olarak durur. Önceki uzun Sol, pencere, E5 ve diğer yerel yöntemlerin bilimsel kanıtları `data/denemeler/akademik_arsiv/` altında, özgün yollar ve SHA-256 envanteriyle saklanır. Aynı kaynaktan yeniden çıkarılabilir taslak TXT'ler ve önbellekler kaldırılmıştır. Arşiv kökündeki `TEMIZLIK_RAPORU.md` saklama/silme politikasını açıklar.

Bu arşiv ve çalışma dizinleri Git dışındadır. Belgeler `scriptler/docs/`, testler `scriptler/tests/` altındadır. Çalıştırma: `python scriptler/run_tests.py`.
