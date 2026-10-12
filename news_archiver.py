from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
DATA_DIR = ROOT / "data"
DECISIONS_PATH = DATA_DIR / "decisions.csv"
TRANSCRIPTION_QUEUE_PATH = DATA_DIR / "transcription_queue.csv"
BASE_DATE = date(2026, 10, 1)
MONTHS_TR = {
    1: "ocak", 2: "şubat", 3: "mart", 4: "nisan", 5: "mayıs", 6: "haziran",
    7: "temmuz", 8: "ağustos", 9: "eylül", 10: "ekim", 11: "kasım", 12: "aralık",
}
TERMINAL_DECISIONS = {"accepted", "skipped"}


@dataclass
class Candidate:
    url: str
    video_id: str
    title: str
    uploader: str
    upload_date: str
    duration: int
    score: int = 0


def normalize(value: str) -> str:
    value = value.casefold().replace("ı", "i")
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(ch)
    )


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config["base_date"] = date.fromisoformat(config.get("base_date", BASE_DATE.isoformat()))
    return config


def ensure_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not DECISIONS_PATH.exists():
        with DECISIONS_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=decision_fields())
            writer.writeheader()
    if not TRANSCRIPTION_QUEUE_PATH.exists():
        with TRANSCRIPTION_QUEUE_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["channel_id", "target_date", "video_id", "url", "reason", "queued_at"],
            )
            writer.writeheader()


def decision_fields() -> list[str]:
    return [
        "channel_id", "channel_name", "target_date", "decision", "video_id",
        "url", "title", "uploader", "duration_seconds", "score",
        "decision_source", "decided_at",
    ]


def read_decisions() -> list[dict[str, str]]:
    ensure_storage()
    with DECISIONS_PATH.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def latest_decision_map() -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for row in read_decisions():
        result[(row["channel_id"], row["target_date"])] = row["decision"]
    return result


def next_incomplete_date(base: date, channel_ids: list[str]) -> date:
    decisions = latest_decision_map()
    current = base
    while True:
        if not all(
            decisions.get((channel_id, current.isoformat())) in TERMINAL_DECISIONS
            for channel_id in channel_ids
        ):
            return current
        current += timedelta(days=1)


def parse_tr_date(raw: str) -> date:
    try:
        parsed = datetime.strptime(raw.strip(), "%d-%m-%Y").date()
    except ValueError as exc:
        raise ValueError("Tarih gün-ay-yıl biçiminde olmalı. Örnek: 02-10-2026") from exc
    return parsed


def date_terms(target: date) -> list[str]:
    month = MONTHS_TR[target.month]
    return [
        f"{target.day} {month} {target.year}",
        f"{target.day:02d} {month} {target.year}",
        target.strftime("%d.%m.%Y"),
        target.strftime("%d-%m-%Y"),
        target.strftime("%Y-%m-%d"),
    ]


def score_candidate(info: dict[str, Any], channel: dict[str, Any], target: date) -> int:
    title = normalize(info.get("title") or "")
    uploader = normalize(info.get("uploader") or info.get("channel") or "")
    duration = int(info.get("duration") or 0)
    score = 0

    if any(normalize(p) in uploader for p in channel["uploader_patterns"]):
        score += 40
    if any(normalize(p) in title for p in channel["title_patterns"]):
        score += 25
    if any(normalize(term) in title for term in date_terms(target)):
        score += 20
    upload_date = info.get("upload_date") or ""
    if upload_date == target.strftime("%Y%m%d"):
        score += 10
    if duration >= int(channel["minimum_duration_minutes"]) * 60:
        score += 15
    elif duration and duration < 10 * 60:
        score -= 40
    if any(normalize(p) in title for p in channel.get("exclude_patterns", [])):
        score -= 100
    return score


def import_ytdlp():
    try:
        import yt_dlp  # type: ignore
        return yt_dlp
    except ImportError:
        print("Eksik bağımlılık: yt-dlp")
        print("Kurulum: python -m pip install -r requirements.txt")
        raise SystemExit(2)


def discover_candidates(channel: dict[str, Any], target: date) -> list[Candidate]:
    yt_dlp = import_ytdlp()
    query_date = f"{target.day} {MONTHS_TR[target.month]} {target.year}"
    query = f"ytsearch12:{channel['name']} {query_date}"
    options = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(options) as ydl:
        result = ydl.extract_info(query, download=False)

    candidates: list[Candidate] = []
    for entry in (result or {}).get("entries") or []:
        if not entry:
            continue
        video_id = entry.get("id") or ""
        url = entry.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}"
        candidate = Candidate(
            url=url,
            video_id=video_id,
            title=entry.get("title") or "",
            uploader=entry.get("uploader") or entry.get("channel") or "",
            upload_date=entry.get("upload_date") or "",
            duration=int(entry.get("duration") or 0),
            score=score_candidate(entry, channel, target),
        )
        candidates.append(candidate)
    return sorted(candidates, key=lambda item: item.score, reverse=True)


def inspect_manual_url(url: str, channel: dict[str, Any], target: date) -> Candidate:
    yt_dlp = import_ytdlp()
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    return Candidate(
        url=info.get("webpage_url") or url,
        video_id=info.get("id") or "",
        title=info.get("title") or "",
        uploader=info.get("uploader") or info.get("channel") or "",
        upload_date=info.get("upload_date") or "",
        duration=int(info.get("duration") or 0),
        score=score_candidate(info, channel, target),
    )


def format_duration(seconds: int) -> str:
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


def show_candidate(channel: dict[str, Any], target: date, candidate: Candidate) -> None:
    print("\n" + "─" * 64)
    print(f"Kanal       : {channel['name']}")
    print(f"Hedef tarih : {target.strftime('%d-%m-%Y')}")
    print(f"Başlık      : {candidate.title}")
    print(f"Yükleyen    : {candidate.uploader}")
    print(f"Süre        : {format_duration(candidate.duration)}")
    print(f"Video       : {candidate.url}")
    print(f"Eşleşme     : {candidate.score}/110")
    print("─" * 64)


def save_decision(
    channel: dict[str, Any], target: date, decision: str,
    candidate: Candidate | None, source: str,
) -> None:
    ensure_storage()
    row = {
        "channel_id": channel["id"],
        "channel_name": channel["name"],
        "target_date": target.isoformat(),
        "decision": decision,
        "video_id": candidate.video_id if candidate else "",
        "url": candidate.url if candidate else "",
        "title": candidate.title if candidate else "",
        "uploader": candidate.uploader if candidate else "",
        "duration_seconds": candidate.duration if candidate else "",
        "score": candidate.score if candidate else "",
        "decision_source": source,
        "decided_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with DECISIONS_PATH.open("a", newline="", encoding="utf-8-sig") as handle:
        csv.DictWriter(handle, fieldnames=decision_fields()).writerow(row)


def queue_for_transcription(channel: dict[str, Any], target: date, candidate: Candidate, reason: str) -> None:
    ensure_storage()
    existing = TRANSCRIPTION_QUEUE_PATH.read_text(encoding="utf-8-sig")
    if candidate.video_id and candidate.video_id in existing:
        return
    with TRANSCRIPTION_QUEUE_PATH.open("a", newline="", encoding="utf-8-sig") as handle:
        csv.DictWriter(
            handle,
            fieldnames=["channel_id", "target_date", "video_id", "url", "reason", "queued_at"],
        ).writerow({
            "channel_id": channel["id"],
            "target_date": target.isoformat(),
            "video_id": candidate.video_id,
            "url": candidate.url,
            "reason": reason,
            "queued_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        })


def archive_subtitles(channel: dict[str, Any], target: date, candidate: Candidate) -> None:
    yt_dlp = import_ytdlp()
    folder = DATA_DIR / "archive" / channel["id"] / target.isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    options = {
        "quiet": False,
        "socket_timeout": 60,
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 5,
        "file_access_retries": 3,
        "continuedl": True,
        "skip_download": True,
        "writeinfojson": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["tr", "tr-orig"],
        "subtitlesformat": "vtt",
        "outtmpl": str(folder / "%(id)s.%(ext)s"),
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([candidate.url])

    vtt_files = sorted(folder.glob("*.vtt"))
    status = {
        "channel_id": channel["id"],
        "target_date": target.isoformat(),
        "video_id": candidate.video_id,
        "url": candidate.url,
        "subtitle_found": bool(vtt_files),
        "processed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    if vtt_files:
        from transcript_processor import write_outputs

        splitter = channel.get("story_splitter", {})
        patterns = splitter.get("transition_patterns", [])
        minimum = float(splitter.get("minimum_story_seconds", 20))
        raw_txt, timed_txt, stories_txt, stories_json = write_outputs(
            vtt_files[0], channel["id"], patterns, minimum
        )
        status.update({
            "subtitle_file": vtt_files[0].name,
            "raw_transcript_file": raw_txt.name,
            "timed_transcript_file": timed_txt.name,
            "stories_text_file": stories_txt.name,
            "stories_json_file": stories_json.name,
        })
        print(f"Ham transkript: {raw_txt}")
        print(f"Haber paragrafları: {stories_txt}")
    else:
        queue_for_transcription(channel, target, candidate, "youtube_subtitle_missing")
        status["transcription_queue"] = str(TRANSCRIPTION_QUEUE_PATH)
        print("Türkçe YouTube altyazısı bulunamadı; transkripsiyon kuyruğuna eklendi.")

    (folder / "archive_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def review_channel(channel: dict[str, Any], target: date) -> None:
    existing = latest_decision_map().get((channel["id"], target.isoformat()))
    if existing in TERMINAL_DECISIONS:
        print(f"{channel['name']}: bu tarih daha önce '{existing}' olarak işlendi.")
        return

    print(f"\n{channel['name']} için aday aranıyor...")
    candidates = discover_candidates(channel, target)
    index = 0
    while True:
        if index < len(candidates):
            candidate = candidates[index]
            show_candidate(channel, target, candidate)
        else:
            candidate = None
            print("\nBaşka otomatik aday bulunamadı.")

        choice = input("[Y] Kabul  [N] Sonraki  [M] Manuel link  [S] Atla  [Q] Çıkış: ").strip().lower()
        if choice == "y" and candidate:
            try:
                archive_subtitles(channel, target, candidate)
            except Exception as exc:
                save_decision(channel, target, "archive_failed", candidate, "download_error")
                print(f"Arşivleme başarısız oldu: {exc}")
                print("Bu kanal tamamlanmış sayılmadı; aynı tarih tekrar açıldığında yeniden denenecek.")
                return
            save_decision(channel, target, "accepted", candidate, "user")
            return
        if choice == "n" and candidate:
            index += 1
            continue
        if choice == "m":
            url = input("YouTube bağlantısı: ").strip()
            manual = inspect_manual_url(url, channel, target)
            show_candidate(channel, target, manual)
            confirm = input("Bu video kabul edilsin mi? [y/n]: ").strip().lower()
            if confirm == "y":
                try:
                    archive_subtitles(channel, target, manual)
                except Exception as exc:
                    save_decision(channel, target, "archive_failed", manual, "download_error")
                    print(f"Arşivleme başarısız oldu: {exc}")
                    print("Bu kanal tamamlanmış sayılmadı; aynı tarih tekrar açıldığında yeniden denenecek.")
                    return
                save_decision(channel, target, "accepted", manual, "manual_url")
                return
            continue
        if choice == "s":
            save_decision(channel, target, "skipped", None, "user")
            return
        if choice == "q":
            raise KeyboardInterrupt
        print("Geçersiz seçim.")


def choose_date(config: dict[str, Any]) -> date | None:
    channel_ids = [item["id"] for item in config["channels"]]
    next_date = next_incomplete_date(config["base_date"], channel_ids)
    while True:
        print("\nTarih seçimi")
        print(f"1) Sıradaki gün ({next_date.strftime('%d-%m-%Y')})")
        print("2) Tarihi kendim gireceğim")
        print("3) Çıkış")
        choice = input("Seçim: ").strip()
        if choice == "1":
            return next_date
        if choice == "2":
            try:
                return parse_tr_date(input("Tarih [gün-ay-yıl]: "))
            except ValueError as exc:
                print(exc)
        elif choice == "3":
            return None
        else:
            print("Geçersiz seçim.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ulusal ana haber YouTube arşivleyicisi")
    parser.add_argument("--date", help="Etkileşimsiz tarih seçimi: gün-ay-yıl")
    args = parser.parse_args()
    config = load_config()
    ensure_storage()
    target = parse_tr_date(args.date) if args.date else choose_date(config)
    if target is None:
        return 0

    try:
        for channel in config["channels"]:
            review_channel(channel, target)
    except KeyboardInterrupt:
        print("\nİşlem durduruldu. Kaydedilen kararlar korunuyor.")
        return 130

    print(f"\n{target.strftime('%d-%m-%Y')} için tüm YouTube kanalları gözden geçirildi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
