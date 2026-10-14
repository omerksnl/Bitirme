"""Türkçe haber transkriptlerinden QLoRA sınıflandırma verisi hazırlar.

1. Her "enflasyon..." ifadesinin çevresinden kelime penceresi çıkarır.
2. Yinelenen pencereleri temizler ve pencereler.csv üretir.
3. Dengeli bir etiketleme şablonu üretir.
4. Etiketli şablon verildiğinde dosya bazlı train/val/test bölmesi yapar.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit


TARGET_RE = re.compile(r"^enflasyon[\wçğıöşüÇĞİÖŞÜ]*$", re.IGNORECASE)
TOKEN_RE = re.compile(r"\S+", re.UNICODE)
DATE_RE = re.compile(r"^(20\d{2})(\d{2})(\d{2})")
VALID_LABELS = {"iyimser", "kotumser", "notr"}


def normalize_label(value: object) -> str:
    text = str(value).strip().casefold()
    translations = {
        "iyimser": "iyimser",
        "pozitif": "iyimser",
        "olumlu": "iyimser",
        "kötümser": "kotumser",
        "kotumser": "kotumser",
        "negatif": "kotumser",
        "olumsuz": "kotumser",
        "nötr": "notr",
        "notr": "notr",
        "neutral": "notr",
    }
    return translations.get(text, text)


def extract_date(filename: str) -> tuple[str | None, str | None]:
    match = DATE_RE.match(filename)
    if not match:
        return None, None
    year, month, day = match.groups()
    return f"{year}-{month}-{day}", f"{year}-{month}"


def extract_windows(text: str, radius: int) -> list[tuple[int, str]]:
    tokens = TOKEN_RE.findall(re.sub(r"\s+", " ", text).strip())
    output: list[tuple[int, str]] = []
    for index, token in enumerate(tokens):
        cleaned = token.strip(".,;:!?()[]{}\"'“”‘’…-–—/")
        if TARGET_RE.match(cleaned):
            start = max(0, index - radius)
            end = min(len(tokens), index + radius + 1)
            output.append((index, " ".join(tokens[start:end])))
    return output


def build_windows(input_dir: Path, radius: int) -> pd.DataFrame:
    rows: list[dict] = []
    for path in sorted(input_dir.rglob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        channel = path.parent.name
        date, month = extract_date(path.name)
        source_id = f"{channel}/{path.name}"
        for mention_index, window in extract_windows(text, radius):
            normalized = re.sub(r"\s+", " ", window).strip().casefold()
            rows.append(
                {
                    "ornek_id": hashlib.sha1(
                        f"{source_id}|{mention_index}|{normalized}".encode("utf-8")
                    ).hexdigest()[:16],
                    "pencere": window,
                    "kanal": channel,
                    "grup": "belirsiz",
                    "tarih": date,
                    "ay": month,
                    "dosya": path.name,
                    "kaynak_id": source_id,
                    "ifade_sirasi": mention_index,
                    "pencere_hash": hashlib.sha1(normalized.encode("utf-8")).hexdigest(),
                }
            )

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError(f"'{input_dir}' altında enflasyon ifadesi bulunamadı.")

    # Aynı metin penceresi farklı yerlerde tekrar ediyorsa tek örnek tutulur.
    frame = frame.drop_duplicates(subset=["pencere_hash"], keep="first").reset_index(drop=True)
    return frame


def annotation_sample(frame: pd.DataFrame, size: int, seed: int) -> pd.DataFrame:
    """Kanal dağılımını koruyarak etiketlenecek örnek seçer."""
    size = min(size, len(frame))
    parts = []
    for _, group in frame.groupby("kanal", sort=True):
        count = min(len(group), max(1, round(size * len(group) / len(frame))))
        parts.append(group.sample(n=count, random_state=seed))
    sampled = pd.concat(parts, ignore_index=True)
    if len(sampled) > size:
        sampled = sampled.sample(size, random_state=seed)
    elif len(sampled) < size:
        remaining = frame.loc[~frame["ornek_id"].isin(sampled["ornek_id"])]
        sampled = pd.concat(
            [sampled, remaining.sample(size - len(sampled), random_state=seed)],
            ignore_index=True,
        )
    sampled = sampled.sample(frac=1, random_state=seed).reset_index(drop=True)
    sampled.insert(2, "etiket", "")
    sampled.insert(3, "etiketleyen", "")
    sampled.insert(4, "not", "")
    return sampled


def grouped_split(
    labeled: pd.DataFrame, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Aynı bültene ait örnekleri tek split içinde tutar: %70/%10/%20."""
    first = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=seed)
    train_val_idx, test_idx = next(
        first.split(labeled, groups=labeled["kaynak_id"])
    )
    train_val = labeled.iloc[train_val_idx].reset_index(drop=True)
    test = labeled.iloc[test_idx].reset_index(drop=True)

    second = GroupShuffleSplit(n_splits=1, test_size=0.125, random_state=seed)
    train_idx, val_idx = next(
        second.split(train_val, groups=train_val["kaynak_id"])
    )
    train = train_val.iloc[train_idx].reset_index(drop=True)
    val = train_val.iloc[val_idx].reset_index(drop=True)
    return train, val, test


def validate_and_split(label_file: Path, output_dir: Path, seed: int) -> None:
    labeled = pd.read_csv(label_file, encoding="utf-8-sig")
    required = {"pencere", "etiket", "kanal", "dosya", "kaynak_id"}
    missing = required - set(labeled.columns)
    if missing:
        raise ValueError(f"Etiket dosyasında eksik sütunlar: {sorted(missing)}")

    labeled["etiket"] = labeled["etiket"].map(normalize_label)
    labeled = labeled[labeled["etiket"].isin(VALID_LABELS)].copy()
    if labeled.empty:
        raise ValueError("Geçerli etiketli örnek bulunamadı.")
    if labeled["etiket"].nunique() < 3:
        raise ValueError("Train/val/test üretmek için üç etiket de bulunmalı.")

    train, val, test = grouped_split(labeled, seed)
    for name, frame in (("train", train), ("val", val), ("test", test)):
        frame.to_csv(output_dir / f"{name}.csv", index=False, encoding="utf-8-sig")
        print(name, len(frame), frame["etiket"].value_counts().to_dict())

    split_sources = {
        "train": set(train["kaynak_id"]),
        "val": set(val["kaynak_id"]),
        "test": set(test["kaynak_id"]),
    }
    assert split_sources["train"].isdisjoint(split_sources["val"])
    assert split_sources["train"].isdisjoint(split_sources["test"])
    assert split_sources["val"].isdisjoint(split_sources["test"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--radius", type=int, default=15)
    parser.add_argument("--annotation-size", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--labels", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    windows = build_windows(args.input, args.radius)
    windows.to_csv(args.output / "pencereler.csv", index=False, encoding="utf-8-sig")
    print(f"pencereler.csv: {len(windows)} benzersiz pencere")

    template = annotation_sample(windows, args.annotation_size, args.seed)
    template.to_csv(
        args.output / "etiketleme_sablonu.csv", index=False, encoding="utf-8-sig"
    )
    print(f"etiketleme_sablonu.csv: {len(template)} örnek")

    if args.labels:
        validate_and_split(args.labels, args.output, args.seed)


if __name__ == "__main__":
    main()
