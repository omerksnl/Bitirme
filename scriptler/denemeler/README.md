# Önceki denemeler ve araştırma araçları

Bu klasördeki yöntemler günlük üretim için seçilen ana Sol modülü değildir. Kodları önceki sonuçları incelemek ve araştırmayı yeniden üretmek için korunur. Çalıştırma komutlarında proje kökünden `python -m` kullanılır; bağımlılıklar ve özel deney verileri ayrıca gerekebilir. Hazırlık/inceleme ücretsizdir; API araçlarının submit işlemi ücretlidir.

| Klasör | İçerik |
|---|---|
| `api/` | İlk bütün bülten/kelime ofseti Batch, iki aşamalı pencere kontrolü ve eski günlük kuyruk |
| `yerel/` | Öğrenilmiş kanal bias'ı, anlamsal birleştirme, süre öncüllü bütün bülten modeli |
| `degerlendirme/` | Eski deney maliyet/biçim incelemesi, sınır karşılaştırması ve inceleme TXT dışa aktarımı |
| `etiketleme/` | Yerel web tabanlı sınır işaretleme aracı; kullanıcı kayıtları yerelde kalır |
| `siniflandirma/` | Enflasyon penceresi hazırlama, QLoRA notebookları ve dataset yardımcı araçları |
| `docs/` | Önceki araştırmanın yöntem belgeleri ve literatür incelemesi |

## Yerel yöntemler

```powershell
python -m scriptler.denemeler.yerel.channel_news_bias --help
python -m scriptler.denemeler.yerel.global_news_time_trial --help
python -m scriptler.denemeler.yerel.same_event_merge --help
```

Yerel model araçları için `scriptler/requirements/local.txt`, anlamsal/E5 yöntemleri için `scriptler/requirements/local_semantic.txt` kullanılır. E5 model ağırlıkları `work/models/` altında yereldir. Profiller ve ayrıntılı deney verileri `data/denemeler/` altında ya da akademik ZIP arşivindedir. Komutların varlığı otomatik doğru haber üretimi anlamına gelmez.

## Eski API ve inceleme araçları

```powershell
python -m scriptler.denemeler.api.openai_news_batch --help
python -m scriptler.denemeler.api.daily_news_pipeline --help
python -m scriptler.denemeler.degerlendirme.audit_news_cost_results --help
python -m scriptler.denemeler.degerlendirme.evaluate_news_boundaries --help
python -m scriptler.denemeler.degerlendirme.export_news_review --help
python -m scriptler.denemeler.etiketleme.news_labeler --help
```

Eski API akışlarının veri hazırlıkları artık aktif çalışma klasöründe bulunmayabilir. Yeniden üretim için yerel akademik arşivdeki uygun verileri açmak gerekir. Eski günlük kuyruk ayırıcısı başarılı olmadığı için seçilen Sol günlük sistemi olarak kullanılmaz.

## Sınıflandırma çalışması

`siniflandirma/prepare_inflation_data.py`, `siniflandirma/notebooks/` ve `siniflandirma/tools/` önceki ekonomi sınıflandırma çalışmasını birlikte tutar. Notebook veri hazırlama yolları bu düzene güncellendi. Bunlar ana haber bölümleme modülünden bağımsızdır; pandas/scikit-learn veya Colab notebooklarında belirtilen ek bağımlılıkları gerektirebilir.

Ana modül: [Sol kullanım belgesi](../docs/GPT_NEWS_REVIEW_BATCH.md). Ortak dosya yazma, Batch gönderme, zaman çizgisi ve ölçüm işlevleri deney kodlarından çıkarılarak `scriptler/lib/` altında tek kopya tutulur.
