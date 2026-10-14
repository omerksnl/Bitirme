# Kanal D haber etiketleme

Başlatmak için proje klasöründe:

```powershell
python scriptler/news_labeler.py
```

Tarayıcı: http://127.0.0.1:8765

30/31 Ocak ve 3/4/5 Şubat 2025 tarihli beş TAM Kanal D bülteni hazırlandı. Kaynak VTT/SRT korunur; tekrarları temizlenen metin ve zaman konumları ayrı kaydedilir. Eski model önerileri aktarılmadı, etiketler kullanıcı tarafından oluşturulur.

1. Soldan bülteni seç.
2. Yeni haberin İLK kelimesine tıkla. Aynı kelimeye tekrar tıklamak işareti kaldırır.
3. Sağdan türü seç: Haber, Diğer (açılış/reklam/kapanış) veya Belirsiz. İsteğe bağlı kısa olay adı gir.
4. Kaydet. Sayfa kapanınca kayıtlı işaretler kalır. Kaydedilmemiş değişiklikte ayrılma uyarısı vardır.
5. Bültenin tamamını okuduktan ve belirsiz yerleri çözdükten sonra “Bültenin tamamını inceledim” kutusunu işaretle ve tekrar kaydet.

Aynı olayın anonsu, muhabir paketi, röportajları ve yorumu bir arada kalmalı. Yeni bağımsız olay yeni haber. Siyasi açıklama ayrı haber olarak sunuluyorsa ayır; aynı olaya verilen tepkileri sırf kişi değiştiği için bölme. Tartışmalı ayrımı Belirsiz bırakıp birlikte inceleyebiliriz.

İlk bölüm bültenin başlangıcını korur ve silinemez. Selamlama ile ilk haber aynı bölümde kalmasın; ilk haberin başlangıcını ayrıca işaretle. Metindeki her kelime başlangıcı kullanılabilir; kelime ortası veya sırasız/tekrarlı sınır kaydedilemez. Belirsiz bölüm içeren bülten tamamlandı olarak onaylanamaz. Başka sekmedeki eski sürümün yeni kaydı ezmesi engellenir.

Veri: `data/etiketleme/KanalD/documents/<id>/labels.json`. Her kayıtta `exports/revision_XXXX/` altında bölünmüş TXT'ler ve sections.json oluşur; önceki kayıt sürümleri korunur. Bu yeni etiketleme alanı temizliğe dahil edilmedi. Etiketlenmiş bölümler birleştirildiğinde kaynak temiz TXT birebir korunur. Başlıklar metni değiştirmez.

HTTP yalnız 127.0.0.1'e bağlıdır. API anahtarı gerekmez, ücretli çağrı ve dış yayın yoktur. Terminal kapatılırsa sunucu durur; yeniden başlatınca kayıtlar geri gelir.

Temizlik geçmişi ve araştırma kanıtları yerel `data/denemeler/akademik_arsiv/` altında korunur. Ham ekonomi dataset'i ve kişisel etiketleme dosyaları temizliğe dahil edilmedi. Temizlenen yöntemler arşivden geri çıkarılabilir; eski pilot komutları çıkarılmamış deney klasörlerini varsayılan olarak kullanmamalı. `data/etiketleme/` ve `data/incelemeler/` kişisel çalışma verileri Git dışında tutulur.
