# Ana scriptler

Üst dizinde yalnız üç ana giriş noktası bulunur:

| Script | Görevi |
|---|---|
| `news_archiver.py` | Haber bülteni kaynaklarını toplar |
| `vtt_to_txt.py` | Altyazıları tekrarları temizleyerek TXT'ye dönüştürür |
| `gpt_news_review_batch.py` | Seçilen Sol low pilotunu hazırlar, gönderir, toplar ve doğrular |

## Klasörler

```text
scriptler/
├── news_archiver.py
├── vtt_to_txt.py
├── gpt_news_review_batch.py
├── requirements.txt
├── config/        # Kaynak ayarları ve yazım düzeltme sözlüğü
├── lib/           # Ortak Batch/JSON, zaman çizgisi, ölçüm ve transkript işlevleri
├── docs/          # Ana Sol modülünün kullanım belgesi
├── tests/         # Testler ve test çalıştırıcı
├── requirements/  # Ana ve araştırma araçlarının ayrı bağımlılık listeleri
└── denemeler/     # Önceki yöntemler, değerlendirme/etiketleme araçları ve QLoRA
```

Sol modülü ortak `lib/` işlevlerini kullanır; eski deney scriptlerini import etmez. Önceki araştırma araçlarının dizini ve komutları [denemeler/README.md](denemeler/README.md) içinde. Pilot kaynak seçimi, dondurulmuş yerel öneriler ve sayısal sonuçlar [data/haber_pipeline](../data/haber_pipeline/README.md) paketindedir.

## Kurulum ve pilot

Proje kökünde Python 3.10+ ile:

```powershell
python -m pip install -r scriptler/requirements.txt
python scriptler/gpt_news_review_batch.py prepare --job data/denemeler/sol_yeni_01
```

prepare ücretli API çağrısı yapmaz. Aynı üç pilot kaydı için başarılı Sol denemesiyle aynı istekleri oluşturur. Sürekli günlük veri seçimi ve işleyici bağlantısı sonraki aşamadır. Gönderim/toplama: [Sol kullanım belgesi](docs/GPT_NEWS_REVIEW_BATCH.md).

Testler:

```powershell
python scriptler/tests/run_tests.py
```

Testler ücretli API çağrısı yapmaz. Tokenizer önbelleği yoksa açık tokenizer verisi ilk kullanımda indirilebilir. Model ağırlıkları, çalışma durumları, ham API yanıtları, kişisel etiketler ve akademik arşivler Git dışında yerelde korunur.
