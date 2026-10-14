from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from scriptler.news_archiver import CONFIG_PATH, DATA_DIR


TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Cue:
    start: float
    end: float
    text: str
    speaker_change: bool = False


@dataclass
class Story:
    story_number: int
    start: float
    end: float
    text: str
    boundary_reason: str


def timestamp_to_seconds(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def seconds_to_clock(value: float) -> str:
    total = int(value)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def clean_caption_text(lines: Iterable[str]) -> str:
    raw_lines = [line.strip() for line in lines if line.strip()]
    # YouTube automatic VTT captions use a rolling two-line window. The first
    # line repeats the preceding cue while the final line contains the new
    # spoken words. Inline timestamp/<c> tags identify this format.
    rolling = any("<c>" in line or re.search(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", line) for line in raw_lines)
    selected = raw_lines[-1:] if rolling and raw_lines else raw_lines
    text = " ".join(selected)
    text = TAG_RE.sub("", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_vtt(path: Path) -> list[Cue]:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    cues: list[Cue] = []
    index = 0
    while index < len(lines):
        match = TIMESTAMP_RE.search(lines[index])
        if not match:
            index += 1
            continue
        start = timestamp_to_seconds(match.group("start"))
        end = timestamp_to_seconds(match.group("end"))
        index += 1
        payload: list[str] = []
        while index < len(lines) and lines[index].strip():
            payload.append(lines[index])
            index += 1
        text = clean_caption_text(payload)
        speaker_change = ">>" in text
        text = re.sub(r"\s*>>\s*", " ", text).strip()
        if text and cues:
            previous = cues[-1].text
            if text.startswith(previous + " "):
                text = text[len(previous):].strip()
        if text:
            cues.append(Cue(start=start, end=end, text=text, speaker_change=speaker_change))
        index += 1
    return remove_caption_repetition(cues)


def remove_caption_repetition(cues: list[Cue]) -> list[Cue]:
    """Remove exact repeated rolling-caption cues without rewriting raw VTT."""
    cleaned: list[Cue] = []
    for cue in cues:
        if cleaned and cue.text == cleaned[-1].text:
            cleaned[-1].end = max(cleaned[-1].end, cue.end)
            cleaned[-1].speaker_change = cleaned[-1].speaker_change or cue.speaker_change
        else:
            cleaned.append(cue)
    return cleaned


def matches_transition(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return pattern
    return None


def split_stories(
    cues: list[Cue], transition_patterns: list[str], minimum_story_seconds: float = 20,
) -> list[Story]:
    if not cues:
        return []
    stories: list[Story] = []
    current: list[Cue] = []
    current_reason = "broadcast_start"

    def flush() -> None:
        nonlocal current, current_reason
        if not current:
            return
        stories.append(
            Story(
                story_number=len(stories) + 1,
                start=current[0].start,
                end=current[-1].end,
                text=" ".join(cue.text for cue in current),
                boundary_reason=current_reason,
            )
        )
        current = []

    for cue in cues:
        matched = matches_transition(cue.text, transition_patterns)
        elapsed = cue.start - current[0].start if current else 0
        if matched and current and elapsed >= minimum_story_seconds:
            flush()
            current_reason = f"transition_pattern:{matched}"
        current.append(cue)
    flush()
    return stories


def write_outputs(
    vtt_path: Path, channel_id: str, patterns: list[str], minimum: float,
) -> tuple[Path, Path, Path, Path]:
    cues = parse_vtt(vtt_path)
    stories = split_stories(cues, patterns, minimum)
    raw_txt_path = vtt_path.with_name("raw_transcript.txt")
    timed_txt_path = vtt_path.with_name("timed_transcript.txt")
    txt_path = vtt_path.with_name("stories.txt")
    json_path = vtt_path.with_name("stories.json")
    raw_txt_path.write_text(
        " ".join(cue.text for cue in cues) + ("\n" if cues else ""),
        encoding="utf-8",
    )
    timed_txt_path.write_text(
        "\n".join(f"[{seconds_to_clock(cue.start)}] {cue.text}" for cue in cues)
        + ("\n" if cues else ""),
        encoding="utf-8",
    )
    txt_path.write_text(
        "\n\n".join(story.text for story in stories) + ("\n" if stories else ""),
        encoding="utf-8",
    )
    payload = {
        "channel_id": channel_id,
        "source_vtt": vtt_path.name,
        "transition_patterns": patterns,
        "story_count": len(stories),
        "stories": [asdict(story) for story in stories],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return raw_txt_path, timed_txt_path, txt_path, json_path


def load_channel(channel_id: str) -> dict:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for channel in config["channels"]:
        if channel["id"] == channel_id:
            return channel
    raise ValueError(f"Bilinmeyen kanal: {channel_id}")


def find_vtt(channel_id: str, target_date: str) -> Path:
    folder = DATA_DIR / "archive" / channel_id / target_date
    files = sorted(folder.glob("*.vtt"))
    if not files:
        raise FileNotFoundError(f"VTT bulunamadı: {folder}")
    return files[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="VTT transkriptini haber paragraflarına ayırır")
    parser.add_argument("--channel", required=True, help="Kanal kimliği: show, atv, now, sozcu, halk")
    parser.add_argument("--date", required=True, help="ISO tarih: 2026-10-01")
    parser.add_argument("--vtt", type=Path, help="İsteğe bağlı doğrudan VTT dosyası")
    args = parser.parse_args()

    channel = load_channel(args.channel)
    splitter = channel.get("story_splitter", {})
    patterns = splitter.get("transition_patterns", [])
    minimum = float(splitter.get("minimum_story_seconds", 20))
    vtt_path = args.vtt or find_vtt(args.channel, args.date)
    raw_txt_path, timed_txt_path, txt_path, json_path = write_outputs(
        vtt_path, args.channel, patterns, minimum
    )
    print(f"HAM:  {raw_txt_path}")
    print(f"ZAMANLI: {timed_txt_path}")
    print(f"TXT:  {txt_path}")
    print(f"JSON: {json_path}")
    if not patterns:
        print("Uyarı: Geçiş kuralı tanımlanmadığı için transkript tek paragraf bırakıldı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
