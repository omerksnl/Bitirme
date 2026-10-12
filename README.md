# Ulusal Ana Haber Arşivleyicisi

Bu araç 1 Ekim 2026'dan başlayarak Show, ATV, NOW, Sözcü TV ve Halk TV'nin
YouTube üzerindeki ana haber bültenleri için aday bulur. Her adayı kullanıcıya
gösterir; kabul edilen videonun metadata dosyasını ve varsa Türkçe altyazısını
arşivler.

## Kurulum

```powershell
python -m pip install -r requirements.txt
```

## Çalıştırma

```powershell
python news_archiver.py
```

Program iki tarih seçeneği sunar:

1. 1 Ekim 2026'dan itibaren tamamlanmamış sıradaki gün.
2. Kullanıcının `gün-ay-yıl` biçiminde gireceği tarih.

1 Ekim sınırı yalnızca otomatik sıradaki gün hesabı içindir. Manuel tarih
seçeneğinde daha eski veya daha yeni herhangi bir geçerli tarih girilebilir.

Belirli bir tarihi doğrudan açmak için:

```powershell
python news_archiver.py --date 02-10-2026
```

## İnceleme tuşları

- `Y`: Adayı kabul et ve metadata/altyazıyı arşivle.
- `N`: Sonraki adayı göster.
- `M`: YouTube linkini elle gir.
- `S`: O kanal ve tarihi atla.
- `Q`: Programı kapat. Önceki kararlar korunur.

Kararlar `data/decisions.csv` dosyasında, kabul edilen içerikler ise
`data/archive/<kanal>/<tarih>/` altında tutulur.

Kabul edilen videoda Türkçe YouTube altyazısı yoksa kayıt
`data/transcription_queue.csv` dosyasına eklenir. Altyazı varsa araç otomatik
olarak `raw_transcript.txt`, `timed_transcript.txt`, `stories.txt` ve
`stories.json` üretir.

Kanal D ve Star kendi video oynatıcılarını kullandığı için bu ilk ortak YouTube
aracına dahil değildir; onlar için ayrı kaynak adaptörleri eklenecektir.

## Transkripti haber paragraflarına ayırma

Ham VTT her zaman korunur. Kanal bazlı geçiş ifadeleri `config.json` içindeki
`story_splitter.transition_patterns` listesine düzenli ifade olarak eklenir.
Ardından türetilmiş TXT ve zaman damgalı JSON yeniden üretilebilir:

```powershell
python transcript_processor.py --channel show --date 2026-10-01
```

Her haber `stories.txt` içinde ayrı paragraftır. Kurallar tanımlı değilse araç
yanlış sınır tahmini yapmaz ve transkripti tek paragraf bırakır. Ayrıntılı kayıt,
sınır nedeni ve zaman aralığı `stories.json` içinde tutulur.
