# Scriptler

Seçilen haber bölümleme modülü **gpt_news_review_batch.py**: tam bülteni Sol low ile ayırır; kaynak metni yerelde, doğrulanan başlangıç konumlarından TXT dosyalarına keser. Bu sürüm üç kanallı pilotu içerir. Yeni günlerin sürekli otomatik işlenmesi sonraki aşamadır.

## Dosya düzeni

| Konum | İçerik |
|---|---|
| `gpt_news_review_batch.py` | Seçilen Sol pilotu, Batch ve kaynak doğrulama |
| `vtt_to_txt.py`, `vtt_word_corrections.json` | Yerel VTT dönüşümü ve küçük yazım düzeltme sözlüğü |
| `news_archiver.py`, `transcript_processor.py` | Kaynak toplama ve önceki transkript araçları |
| `channel_news_bias.py`, `global_news_time_trial.py`, `same_event_merge.py` | Yerel yöntemler ve ortak araştırma yardımcıları |
| `daily_news_pipeline.py`, `openai_news_batch.py`, `news_batch_windows.py` | Ortak zaman çizgisi/lock/kalıcılık ve eski kuyruk araçları; eski ayırıcı günlük üretim için seçilmedi |
| `audit_news_cost_results.py`, `evaluate_news_boundaries.py`, `export_news_review.py` | İnceleme, ölçüm ve kaynak koruma |
| `docs/` | Kullanım ve araştırma belgeleri |
| `tests/`, `run_tests.py` | Kaynak koruma, kalıcılık, bütçe ve bölümleme kontrolleri |
| `../data/haber_pipeline/` | Küçük, yeniden üretilebilir üç kanal pilot paketi |

QLoRA notebookları ve `prepare_inflation_data.py` ekonomi sınıflandırma çalışması için ayrıca korunur. Kullanıcı etiketleme aracı `news_labeler.py`, `web-prototype/public/etiketleme/` arayüzünü kullanır; kişisel kayıtları Git dışında tutar.

## Kurulum ve pilot

Proje kökünde Python 3.10+ ile:

```powershell
python -m pip install -r scriptler/requirements-news.txt
python scriptler/gpt_news_review_batch.py prepare --job data/denemeler/sol_yeni_01
```

prepare ücretli API çağrısı yapmaz. Git'teki pilot kaynakları ve dondurulmuş yerel önerilerden aynı üç isteği oluşturur. Tam gönderim/toplama akışı: [Sol kullanım belgesi](docs/GPT_NEWS_REVIEW_BATCH.md).

Tüm testleri çalıştırmak için kaynak toplama bağımlılığını da kur:

```powershell
python -m pip install -r scriptler/requirements.txt
python scriptler/run_tests.py
```

Testler ücretli API çağrısı yapmaz. Tokenizer önbelleği yoksa açık tokenizer verisi ilk kullanımda indirilebilir; geçici dosyalar Git dışında `work/` altında oluşur.

Yerel model ağırlıkları, Batch durumları, ham yanıtlar, araştırma arşivleri ve özel inceleme/etiketleme oturumları Git'e dahil edilmez. Genel sayısal pilot raporu veri paketinde bulunur; geçmiş ayrıntılı kanıtlar yerel akademik arşivde saklanır.
