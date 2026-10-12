# Ekonomi Haber Verisi — İlk Analiz

## İncelenen veri

- Kaynak: `Ekonomi/-Ekonomi_Temiz_Text`
- Kanal sayısı: 13
- Metin dosyası: 3.204
- Tarih aralığı: 1 Aralık 2023 – 5 Şubat 2025
- Toplam kelime: 20.493.205
- Okuma/UTF-8 hatası: 0
- Boş dosya: 0
- Tam metin yinelenmesi: 2 grup, toplam 4 dosya

## Uzunluk

- En kısa dosya: 330 kelime
- Medyan: 5.259 kelime
- %90 yüzdelik: 11.460 kelime
- %95 yüzdelik: 12.420 kelime
- En uzun dosya: 34.969 kelime

Dosyaların çoğu tek bir haber değil, birden fazla haber içeren tam bülten transkriptidir. Metinlerin neredeyse tamamı tek satırdır; noktalama ve konuşmacı sınırları zayıftır.

## Enflasyon kapsamı

- `enflasyon...` biçimindeki toplam ifade sayısı: 14.114
- Enflasyon ifadesi geçen dosya: 1.886 / 3.204 (%58,9)
- Eşleşen dosyalarda medyan tekrar: 4
- Tek dosyadaki en yüksek tekrar: 132

Notebook'taki `pencereler.csv (~14 bin)` ifadesi bu sayı ile uyumludur: her enflasyon ifadesi için yaklaşık bir ±15 kelimelik pencere üretilmiş görünüyor.

## Kanal dağılımı

| Kanal | Dosya | Medyan kelime | Tarih aralığı |
|---|---:|---:|---|
| AHaber | 63 | 17.145 | 2024-11-18 – 2025-02-01 |
| ATV | 418 | 4.827 | 2023-12-01 – 2025-01-31 |
| Fox/NOW | 365 | 5.285 | 2023-12-01 – 2024-11-30 |
| HaberTürk | 353 | 9.795 | 2023-12-01 – 2024-12-01 |
| Halk | 63 | 12.117 | 2024-09-02 – 2024-11-29 |
| KRT | 226 | 11.161 | 2024-04-16 – 2024-12-01 |
| Kanal7 | 103 | 4.462 | 2024-05-17 – 2024-11-29 |
| KanalD | 159 | 5.214 | 2024-06-18 – 2025-02-05 |
| Show | 358 | 2.871 | 2023-12-01 – 2024-11-30 |
| SözcüTV | 361 | 7.184 | 2023-12-01 – 2024-11-30 |
| StarTV | 363 | 4.530 | 2023-12-01 – 2024-12-01 |
| TRT | 104 | 4.420 | 2023-12-01 – 2024-11-30 |
| TV100 | 268 | 9.470 | 2023-12-01 – 2024-11-30 |

Kanallar hem örnek sayısı hem transkript uzunluğu hem de tarih kapsamı bakımından dengesizdir. Rastgele satır bölmesi kanal ve tarih sızıntısına yol açabilir.

## QLoRA notebook'unun beklediği veri

Notebook doğrudan `.txt` dosyalarını okumuyor. Şunları bekliyor:

- `train.csv`, `val.csv`, `test.csv`: `pencere`, `etiket` sütunları
- `pencereler.csv`: en az `pencere`, `kanal`, `grup`, `ay`, `dosya` sütunları
- Etiketler: `iyimser`, `kotumser`, `notr`
- Girdi: `enflasyon` ifadesinin çevresindeki ±15 kelimelik kısa pencere

Notebook çıktısına göre mevcut etiketli örnekler:

- Train: 563
- Validation: 81
- Test: 160
- Toplam: 804

Bu dört CSV dosyası mevcut proje klasöründe bulunmuyor.

## Sonuç

Mevcut 3.204 `.txt` dosyası QLoRA'ya doğrudan verilemez. Bunlar kaynak külliyattır. Eğitimden önce:

1. Her `enflasyon` ifadesinin ±15 kelimelik penceresi çıkarılmalı.
2. Aynı/örtüşen pencereler temizlenmeli.
3. Her pencereye iyimser, kötümser veya nötr etiketi verilmeli.
4. Bölme satır bazında değil, dosya veya tarih bazında yapılmalı.
5. Aynı bültene ait pencereler yalnızca tek bir split'te bulunmalı.
6. Test seti insan tarafından ve mümkünse iki bağımsız etiketleyiciyle hazırlanmalı.

Bu veri, tam bülten üzerinde doğrudan sınıflandırma için uygun değildir; pencere tabanlı ton sınıflandırması için uygun bir ham kaynaktır.
