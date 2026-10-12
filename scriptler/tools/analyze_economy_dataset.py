from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "data" / "Ekonomi" / "-Ekonomi_Temiz_Text"
DATE_RE = re.compile(r"^(20\d{6})")
WORDS_RE = re.compile(r"\b[\wÇĞİÖŞÜçğıöşü]+\b", re.UNICODE)
ECONOMY_TERMS = {
    "ekonomi", "enflasyon", "fiyat", "zam", "faiz", "dolar", "euro",
    "maaş", "asgari", "ücret", "kira", "market", "gıda", "enerji",
    "akaryakıt", "benzin", "motorin", "vergi", "bütçe", "işsizlik",
    "ihracat", "ithalat", "borsa", "altın", "emekli", "tcmb", "merkez bankası",
}
INFLATION_TERMS = {"enflasyon", "fiyat", "zam", "pahalılık", "hayat pahalılığı", "tüfe", "üfe"}


def pct(n: int, total: int) -> float:
    return round(n * 100 / total, 2) if total else 0.0


def percentile(values: list[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * q)
    return ordered[index]


records: list[dict] = []
errors: list[dict] = []
for path in sorted(ROOT.rglob("*.txt")):
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        errors.append({"path": str(path), "error": str(exc)})
        continue
    normalized = re.sub(r"\s+", " ", text).strip()
    lower = normalized.casefold()
    words = WORDS_RE.findall(normalized)
    match = DATE_RE.match(path.name)
    date = match.group(1) if match else None
    records.append(
        {
            "path": str(path),
            "channel": path.parent.name,
            "name": path.name,
            "date": date,
            "chars": len(normalized),
            "words": len(words),
            "empty": not normalized,
            "economy": any(term in lower for term in ECONOMY_TERMS),
            "inflation": any(term in lower for term in INFLATION_TERMS),
            "sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            "preview": normalized[:350],
        }
    )

by_channel: dict[str, list[dict]] = defaultdict(list)
by_hash: dict[str, list[dict]] = defaultdict(list)
for record in records:
    by_channel[record["channel"]].append(record)
    by_hash[record["sha256"]].append(record)

duplicates = [group for group in by_hash.values() if len(group) > 1 and group[0]["chars"] > 0]
word_counts = [r["words"] for r in records]
date_values = sorted(r["date"] for r in records if r["date"])

summary = {
    "root": str(ROOT),
    "files": len(records),
    "read_errors": len(errors),
    "empty": sum(r["empty"] for r in records),
    "short_under_50_words": sum(r["words"] < 50 for r in records),
    "economy_keyword_files": sum(r["economy"] for r in records),
    "inflation_keyword_files": sum(r["inflation"] for r in records),
    "date_min": date_values[0] if date_values else None,
    "date_max": date_values[-1] if date_values else None,
    "missing_date_in_filename": sum(r["date"] is None for r in records),
    "words": {
        "min": min(word_counts) if word_counts else 0,
        "median": int(statistics.median(word_counts)) if word_counts else 0,
        "p90": percentile(word_counts, 0.9),
        "p95": percentile(word_counts, 0.95),
        "max": max(word_counts) if word_counts else 0,
        "total": sum(word_counts),
    },
    "exact_duplicate_groups": len(duplicates),
    "files_in_exact_duplicate_groups": sum(len(g) for g in duplicates),
    "channels": {},
}

for channel, items in sorted(by_channel.items()):
    counts = [r["words"] for r in items]
    dates = sorted(r["date"] for r in items if r["date"])
    summary["channels"][channel] = {
        "files": len(items),
        "words_total": sum(counts),
        "words_median": int(statistics.median(counts)),
        "words_p95": percentile(counts, 0.95),
        "economy_keyword_files": sum(r["economy"] for r in items),
        "inflation_keyword_files": sum(r["inflation"] for r in items),
        "date_min": dates[0] if dates else None,
        "date_max": dates[-1] if dates else None,
    }

shortest = sorted(records, key=lambda r: r["words"])[:12]
longest = sorted(records, key=lambda r: r["words"], reverse=True)[:12]
no_economy = [r for r in records if not r["economy"]][:12]
duplicate_examples = [
    [{"path": r["path"], "words": r["words"]} for r in group[:5]]
    for group in sorted(duplicates, key=len, reverse=True)[:10]
]

output = {
    "summary": summary,
    "shortest_examples": shortest,
    "longest_examples": longest,
    "no_economy_keyword_examples": no_economy,
    "duplicate_examples": duplicate_examples,
    "read_errors": errors,
}

(Path(__file__).resolve().parents[2] / "dataset_analysis.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
