"""Toplu VTT -> TXT: python scriptler/vtt_to_txt.py --help."""
from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
from pathlib import Path
import sys

TIME = r"(?:\d{2,}:)?\d{2}:\d{2}[.,]\d{3}"
TIMING = re.compile(rf"^({TIME})\s+-->\s+({TIME})(?:\s.*)?$")
WORDS = re.compile(r"\w+(?:['’]\w+)*|[^\w\s]", re.UNICODE)
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent


def seconds(value: str) -> float:
    result = 0.0
    for part in value.split(":"):
        result = result * 60 + float(part.replace(",", "."))
    return result


def key(value: str) -> str:
    return unicodedata.normalize("NFC", value).translate(str.maketrans("Iİ", "ıi")).lower()


def tokens(text: str) -> list[str]:
    # Preserve the original spelling and punctuation in the output.
    return [key(match.group()) for match in WORDS.finditer(text)]


def read_cues(source: str) -> list[tuple[float, float, str, bool]]:
    lines = source.lstrip("\ufeff").splitlines()
    cues = []
    index = 0
    while index < len(lines):
        match = TIMING.match(lines[index].strip())
        if not match:
            index += 1
            continue
        start, end = map(seconds, match.groups())
        index += 1
        payload = []
        # Some automatic captions have an empty line before the payload.
        while index < len(lines):
            line = lines[index].strip()
            if TIMING.match(line):
                break
            if not line and payload:
                index += 1
                break
            if line:
                payload.append(line)
            index += 1
        raw = " ".join(payload)
        speaker = "<v " in raw or ">>" in html.unescape(raw)
        text = html.unescape(re.sub(r"<[^>]*>", "", raw))
        text = re.sub(r"\s+", " ", text.replace(">>", " ")).strip()
        text = unicodedata.normalize("NFC", text)
        if text:
            cues.append((start, end, text, speaker))
    return cues


def deduplicate(cues: list[tuple[float, float, str, bool]]) -> tuple[str, int]:
    parts: list[str] = []
    recent: list[str] = []
    previous_end = -100.0
    removed = 0
    for start, end, text, speaker in cues:
        matches = list(WORDS.finditer(text))
        current = [key(match.group()) for match in matches]
        overlap = 0
        # Only compare neighboring captions. Repeated statements later in a
        # broadcast, after a pause, or at a speaker change remain intact.
        if start - previous_end <= 1.0 and not speaker:
            for size in range(min(len(recent), len(current)), 0, -1):
                if recent[-size:] == current[:size]:
                    lexical = sum(bool(re.search(r"\w", token)) for token in current[:size])
                    if lexical >= 2 or (size == len(current) and start < previous_end):
                        overlap = size
                        break
        if overlap:
            removed += overlap
            text = text[matches[overlap - 1].end():].lstrip()
        if text:
            parts.append(text)
        if speaker or start - previous_end > 1.0:
            recent = []
        recent = (recent + current[overlap:])[-200:]
        previous_end = max(previous_end, end)
    return " ".join(parts), removed


def correct_words(text: str, corrections: dict[str, str]) -> tuple[str, dict[str, int]]:
    changes: dict[str, int] = {}
    mapping = {key(wrong): right for wrong, right in corrections.items()}
    def replace(match: re.Match) -> str:
        original = match.group()
        replacement = mapping.get(key(original))
        if replacement is None:
            return original
        if original.isupper():
            replacement = replacement.translate(str.maketrans("iı", "İI")).upper()
        elif original[0].isupper():
            replacement = replacement[0].translate(str.maketrans("iı", "İI")).upper() + replacement[1:]
        if original != replacement:
            changes[original + " → " + replacement] = changes.get(original + " → " + replacement, 0) + 1
        return replacement
    return re.sub(r"\w+(?:['’]\w+)*", replace, text), changes


def convert(source: str, corrections: dict[str, str]) -> tuple[str, dict]:
    cues = read_cues(source)
    if not cues:
        raise ValueError("Dosyada metin içeren geçerli VTT altyazısı bulunamadı")
    text, removed = deduplicate(cues)
    text, changes = correct_words(text, corrections)
    return text + "\n", {"cue_count": len(cues), "removed_overlap_tokens": removed, "word_corrections": changes}


def main() -> int:
    parser = argparse.ArgumentParser(description="VTT dosyalarını tekrarları temizleyerek UTF-8 TXT'ye dönüştürür.")
    parser.add_argument("--input", type=Path, default=ROOT / "data/Ekonomi/-Ekonomi_Temiz")
    parser.add_argument("--output", type=Path, default=ROOT / "data/Ekonomi/-Ekonomi_Temiz_Text_v2")
    parser.add_argument("--corrections", type=Path, default=ROOT / "scriptler/config/vtt_word_corrections.json")
    parser.add_argument("--overwrite", action="store_true", help="Var olan TXT dosyalarının üzerine yaz")
    args = parser.parse_args()
    corrections = json.loads(args.corrections.read_text(encoding="utf-8-sig"))
    if not isinstance(corrections, dict) or not all(isinstance(k, str) and isinstance(v, str) and k and v for k, v in corrections.items()):
        parser.error("Düzeltme listesi yanlış kelime: doğru kelime biçiminde bir JSON nesnesi olmalı")
    source = args.input.resolve()
    output = args.output.resolve()
    if not source.exists():
        parser.error(f"Kaynak bulunamadı: {source}")
    files = [source] if source.is_file() and source.suffix.lower() == ".vtt" else sorted(source.rglob("*.[vV][tT][tT]")) if source.is_dir() else []
    if not files:
        parser.error("VTT dosyası bulunamadı")
    base = source.parent if source.is_file() else source
    if output == base or base in output.parents:
        parser.error("Çıktı klasörü kaynak klasörün dışında olmalı")
    report = {"input": str(source), "output": str(output), "converted": 0, "skipped": 0, "errors": 0, "files": []}
    for file in files:
        target = output / file.relative_to(base).with_suffix(".txt")
        item = {"source": str(file.relative_to(base)), "target": str(target)}
        try:
            if target.exists() and not args.overwrite:
                item["status"] = "skipped"
                report["skipped"] += 1
            else:
                # Strict decoding reports damaged files instead of silently
                # substituting characters and corrupting Turkish words.
                text, stats = convert(file.read_text(encoding="utf-8-sig"), corrections)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
                item.update(stats, status="converted")
                report["converted"] += 1
        except (OSError, UnicodeError, ValueError) as error:
            item.update(status="error", error=str(error))
            report["errors"] += 1
        report["files"].append(item)
    output.mkdir(parents=True, exist_ok=True)
    (output / "vtt_conversion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dönüştürülen: {report['converted']} | Atlanan: {report['skipped']} | Hata: {report['errors']}")
    print(f"Çıktı: {output}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
