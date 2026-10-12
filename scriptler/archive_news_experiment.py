"""Önceki API denemelerinin verilerini ve yöntemini değişmeden arşivler."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "data/denemeler/onceki_api_deneme_2026-10-12"


def main():
    if TARGET.exists():
        raise SystemExit(f"Arşiv zaten var; üzerine yazılmadı: {TARGET}")
    TARGET.mkdir(parents=True)
    files = []
    for folder in [ROOT / "data/_openai_batch_runs", ROOT / "data/Ekonomi/Bizim haberlerimiz"]:
        if folder.exists():
            files.extend(path for path in folder.rglob("*") if path.is_file())
    files.extend(ROOT / "scriptler" / name for name in ["openai_news_batch.py", "news_batch_windows.py", "vtt_to_txt.py", "vtt_word_corrections.json", "requirements-openai.txt"])
    inventory = []
    usage = []
    with zipfile.ZipFile(TARGET / "veriler_ve_scriptler.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            raw = path.read_bytes()
            relative = str(path.relative_to(ROOT)).replace("\\", "/")
            archive.writestr(relative, raw)
            inventory.append({"path": relative, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
            if path.name == "results.jsonl":
                incoming = outgoing = requests = 0
                for line in raw.decode("utf-8").splitlines():
                    body = (json.loads(line).get("response") or {}).get("body") or {}
                    counts = body.get("usage") or {}
                    incoming += counts.get("input_tokens", 0)
                    outgoing += counts.get("output_tokens", 0)
                    requests += 1
                usage.append({"file": relative, "requests": requests, "input_tokens": incoming, "output_tokens": outgoing})
    (TARGET / "dosya_envanteri.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    (TARGET / "token_kullanimi.json").write_text(json.dumps(usage, ensure_ascii=False, indent=2), encoding="utf-8")
    method = """# Önceki API haber ayırma denemesi

## Veri ve aşamalar
Her kanaldan bir kayıt seçildi: 13 ana haber bülteni, toplam 86.844 kelime.
Model: gpt-4.1-mini-2025-04-14. İstekler OpenAI Batch /v1/responses üzerinden
strict JSON Schema ile gönderildi. Anahtar yalnız ortam değişkeninden okundu.

1. pilot: Bütün bülten tek istekte gönderildi; model haber başlangıcından
   alıntı kopyaladı. Birebir alıntı uyuşmazlıkları nedeniyle 13 dışa aktarma başarısız oldu.
2. pilot-v2: 8 kelimelik satır numaraları ve start_word sınırları kullanıldı.
   Metin korundu ancak cümle ortası kesimler, yanlış başlıklar ve uzun kapanışlar görüldü.
3. pilot-v3: 800 kelimelik ana pencereler, iki tarafta 160 kelimelik bağlam ve
   her kelimeye ayrı yerel kimlik kullanıldı. 13 bülten için 114 öneri isteği gönderildi.
4. pilot-v3/review: Aynı 114 pencere, ilk önerilerle birlikte ikinci modele
   gösterildi. Koruma/taşıma/ekleme/silme kararları istendi.
5. Örtüşen bağlamdaki aynı kaynak konumları birleştirildi. Eksik öneri kararları
   doğrulanmamış ilk öneri olarak korundu; çelişkiler raporlandı. Sonuçlar
   pilot-v3-kurtarilan altında 386 haber TXT taslağına çıkarıldı.

## Sonuç ve sınırlamalar
13 kaynak metin, tüm parçalar sırayla birleştirildiğinde birebir korunuyor.
12 bültende ikinci model denetimi eksik veya çelişkili. Bu dosyalar insan
tarafından onaylanmış doğru etiketler değildir; yeni modelin eğitim/veri
doğruluğu referansı olarak otomatik kullanılmamalıdır.

Kullanıcı toplam API harcamasını yaklaşık 0,60 dolar olarak bildirdi.
Token kullanımı token_kullanimi.json içindedir. Ham yanıtlar, istekler,
kaynak kopyaları, batch durumları, yöntem scriptleri ve bütün önceki
haber çıktı klasörleri ZIP'te saklandı. Gönderilmemiş all istek hazırlığı
da arşivde bulunur; bu klasörün varlığı ücretli gönderim yapıldığı anlamına gelmez.

## Yeniden üretim
ZIP içindeki scriptler bu arşivleme anındaki sürümdür. requests.jsonl ve
manifest.json kullanılan metin/pencere/model ayarlarını taşır; results.jsonl
gerçek API yanıtlarını taşır. Veri doğruluğu SHA-256 envanterinden kontrol edilebilir.
Kaynak dosyalar taşınmadı veya silinmedi. Yeni ekonomik deneme ayrı klasöre yazılır.
"""
    (TARGET / "NASIL_YAPTIK.md").write_text(method, encoding="utf-8")
    print(f"Arşiv: {TARGET}\nDosya: {len(inventory)}")


if __name__ == "__main__":
    main()
