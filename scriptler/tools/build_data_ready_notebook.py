from __future__ import annotations

import json
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "QLoRA_Inflation_Classifier.ipynb"
TARGET = Path(__file__).resolve().parents[1] / "QLoRA_Inflation_Classifier_DATA_READY.ipynb"


def markdown(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(True)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(True),
    }


notebook = json.loads(SOURCE.read_text(encoding="utf-8"))
for cell in notebook["cells"]:
    if cell["cell_type"] == "code":
        cell["execution_count"] = None
        cell["outputs"] = []

data_cells = [
    markdown(
        """## 3. Veri hazırlama

Tam haber bültenleri doğrudan eğitim örneği değildir. Bu bölüm her `enflasyon...`
ifadesinin çevresinden ±15 kelimelik pencere çıkarır, aynı pencereleri temizler ve
etiketleme şablonu üretir.

Drive düzeni:

```text
Benim_Colab_Projem/
├── veri/Ekonomi/-Ekonomi_Temiz_Text/
├── scriptler/prepare_inflation_data.py
├── sonuclar/enflasyon_verisi/
└── modeller/
```
"""
    ),
    code(
        """from google.colab import drive
drive.mount('/content/drive')

from pathlib import Path
import subprocess

PROJE_DIZINI = Path('/content/drive/MyDrive/Benim_Colab_Projem')
HAM_VERI = PROJE_DIZINI / 'veri' / 'Ekonomi' / '-Ekonomi_Temiz_Text'
VERI_CIKTI = PROJE_DIZINI / 'sonuclar' / 'enflasyon_verisi'
HAZIRLAMA_KODU = PROJE_DIZINI / 'scriptler' / 'prepare_inflation_data.py'

assert HAM_VERI.exists(), f'Ham veri klasörü bulunamadı: {HAM_VERI}'
assert HAZIRLAMA_KODU.exists(), f'Hazırlama kodu bulunamadı: {HAZIRLAMA_KODU}'
VERI_CIKTI.mkdir(parents=True, exist_ok=True)

subprocess.run([
    'python', str(HAZIRLAMA_KODU),
    '--input', str(HAM_VERI),
    '--output', str(VERI_CIKTI),
    '--radius', '15',
    '--annotation-size', '1200',
    '--seed', '42',
], check=True)

print('Çıktılar:', sorted(p.name for p in VERI_CIKTI.iterdir()))
"""
    ),
    markdown(
        """### 3.1 Etiketleme

İlk çalıştırmada `etiketleme_sablonu.csv` oluşur. Bu dosyadaki `etiket` sütunu
`iyimser`, `kotumser` veya `notr` değerleriyle doldurulmalı ve aynı klasöre
`etiketli_pencereler.csv` adıyla kaydedilmelidir.

Model eğitimi için etiket gereklidir. Boş etiketlerle train/validation/test
dosyaları üretilemez.
"""
    ),
    code(
        """ETIKETLI_DOSYA = VERI_CIKTI / 'etiketli_pencereler.csv'

if not ETIKETLI_DOSYA.exists():
    raise FileNotFoundError(
        f'{ETIKETLI_DOSYA} bulunamadı. '
        'Önce etiketleme_sablonu.csv dosyasını doldurup '
        'etiketli_pencereler.csv adıyla kaydedin.'
    )

subprocess.run([
    'python', str(HAZIRLAMA_KODU),
    '--input', str(HAM_VERI),
    '--output', str(VERI_CIKTI),
    '--radius', '15',
    '--annotation-size', '1200',
    '--seed', '42',
    '--labels', str(ETIKETLI_DOSYA),
], check=True)
"""
    ),
    markdown("### 3.2 Eğitim dosyalarını yükleme\n"),
    code(
        """import pandas as pd
from datasets import Dataset

# Notebook'un devamındaki kodlar bu klasörden okuyacak.
KLASOR = str(VERI_CIKTI)
CIKTI = str(PROJE_DIZINI / 'modeller' / ('qwen_qlora_ikili' if IKILI else 'qwen_qlora_uclu'))

def yukle(ad):
    df = pd.read_csv(f'{KLASOR}/{ad}.csv', encoding='utf-8-sig')
    df['etiket'] = df['etiket'].astype(str).str.strip().str.casefold()
    if IKILI:
        df = df[df['etiket'].isin(['iyimser', 'kotumser'])].copy()
    df['label'] = df['etiket'].map(ETIKET2ID)
    if df['label'].isna().any():
        hatali = sorted(df.loc[df['label'].isna(), 'etiket'].unique())
        raise ValueError(f'Geçersiz etiketler: {hatali}')
    return df.reset_index(drop=True)

train_df, val_df, test_df = yukle('train'), yukle('val'), yukle('test')
for ad, df in [('train', train_df), ('val', val_df), ('test', test_df)]:
    print(ad, len(df), df['etiket'].value_counts().to_dict())

# Aynı bülten farklı bölümlere sızmış mı kontrol et.
for sol_ad, sol, sag_ad, sag in [
    ('train', train_df, 'val', val_df),
    ('train', train_df, 'test', test_df),
    ('val', val_df, 'test', test_df),
]:
    ortak = set(sol['kaynak_id']) & set(sag['kaynak_id'])
    assert not ortak, f'{sol_ad}/{sag_ad} arasında kaynak sızıntısı var: {len(ortak)}'
"""
    ),
]

# Eski "## 3. Veri" markdown ve onu izleyen yükleme hücresini değiştir.
notebook["cells"] = notebook["cells"][:5] + data_cells + notebook["cells"][7:]

TARGET.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(TARGET)
