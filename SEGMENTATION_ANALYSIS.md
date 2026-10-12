# Haber Paragrafı Ayırma Analizi

İncelenen örnekler: Show, ATV, NOW, Halk TV ve Sözcü TV'nin 1 Ekim 2026
bültenlerinin zaman damgalı YouTube altyazıları.

## Ortak karar

Tek başına `şimdi`, `sırada`, `bakalım` veya YouTube'un `>>` konuşmacı
işareti haber sınırı değildir. Bu kelimeler röportaj ve yorum içinde de çok
sık geçmektedir. Nihai sınır için birden fazla sinyal birlikte aranmalıdır:

1. Kanal özelinde güçlü sunucu geçiş ifadesi.
2. Önceki sınırdan beri geçen asgari süre.
3. Konuşmacı değişimi.
4. Altyazı zamanlarında sessizlik veya jenerik/müzik işareti.
5. Komşu metin pencereleri arasında belirgin konu değişimi.

Ham VTT değişmeden tutulur. Taslak sınırlar ayrı JSON/TXT çıktısına yazılır ve
elle doğrulanır.

## Show Ana Haber

- Yaklaşık 36 dakikada çok sayıda kısa, kurgu haber paketi vardır.
- Sunucu her haberde sabit bir geçiş cümlesi kullanmamaktadır.
- `>>` işareti haber sınırlarında sık görülse de röportajlarda da görülür.
- Sessizlik tek başına güvenilir değildir; paket içindeki görüntü geçişlerinde
  de sessizlik oluşur.

Yöntem: 70 saniyelik asgari haber süresinden sonra konuşmacı değişimi, konu
yeniliği ve kısa sessizliğin birlikte puanlanması. Açıklamadaki bölüm zamanları
yalnızca değerlendirme için kullanılabilir; ana ayırıcı olmamalıdır.

## ATV Ana Haber

- Haber özetleri video açıklamasında bulunmaktadır fakat zaman damgası yoktur.
- Uzun siyasi paketler ve kısa haber turu aynı bültendedir.
- Açık geçiş örneği: `Sırada görüntüleriyle öne çıkan yurttan haber turu var.`

Yöntem: Açıklamadaki özetlerin ilk ayırt edici sözcüklerini transkriptte bulan
zayıf eşleştirme, güçlü sunucu geçişleri ve en az 60 saniyelik süre eşiği.
Eşleşmeyen kısımlarda konu değişimi aday sınır üretir.

## NOW Ana Haber

- Sunucu yorumları nedeniyle `şimdi` çok sık geçmektedir.
- Daha güçlü ifadeler vardır: `Şimdi o habere gidelim`, `Hız kesmeden devam
  ediyoruz`, `Şimdi sıradaki haber`, `Haberler bitmedi ama bir reklam arası`.
- Reklam öncesi ve sonrası ayrıca blok sınırıdır.

Yöntem: Yalnızca güçlü tam ifadeler, minimum 60 saniye ve reklam blokları.
Tek başına `şimdi` kesinlikle kullanılmamalıdır.

## Halk TV Ana Haber

- Yaklaşık iki saatlik, yorum ve konuk konuşması ağırlıklı bir yapı vardır.
- `Şimdi gelelim ...` konu değişiminde kullanılmaktadır fakat yorum içinde de
  benzer söyleyişler vardır.
- Uzun röportajlarda yüzlerce konuşmacı değişimi oluşmaktadır.

Yöntem: `Şimdi gelelim <konu>`, program içi reklam dönüşleri ve en az 90
saniyelik blok süresi. Konuk değişimi tek başına haber sınırı sayılmaz.

## Sözcü TV Ana Haber

- Yaklaşık iki saatlik sunucu yorumu, saha paketi ve reklam karışımıdır.
- Güçlü geçiş örnekleri: `Madem ... bakalım`, `dönelim`, `<dosyada> sıra`,
  `özel haberini getireceğim şimdi ekranlara`.
- Transkriptte reklam metinleri de bulunmaktadır (`Ne var sırada? DenizBank`).

Yöntem: Önce reklam bloklarını ayırmak, ardından güçlü sunucu ifadelerini en az
90 saniyelik süre eşiğiyle kullanmak. `Bir başka` ve `şimdi` tek başına sınır
sayılmamalıdır.

## Doğrulama biçimi

Her taslak paragraf için başlangıç zamanı, ilk cümle ve sınır nedeni yazılır.
İnceleyen kişi sınırı `doğru`, `sil` veya `buraya taşı` olarak işaretler. Bu
düzeltmeler kanalın sonraki günlerde kullanılacak kurallarına dönüştürülür.
