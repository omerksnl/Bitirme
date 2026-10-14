import tempfile
import unittest
from pathlib import Path

from transcript_processor import parse_vtt, split_stories


class TranscriptProcessorTests(unittest.TestCase):
    def test_youtube_rolling_captions_keep_only_new_line(self):
        sample = """WEBVTT

00:00:07.120 --> 00:00:08.910 align:start position:0%
Şov<00:00:07.359><c> Haber'den</c><00:00:08.080><c> akşamlar</c>

00:00:08.910 --> 00:00:08.920 align:start position:0%
Şov Haber'den akşamlar

00:00:08.920 --> 00:00:11.230 align:start position:0%
Şov Haber'den akşamlar
izleyenler.<00:00:09.559><c> Ben</c><00:00:09.840><c> Hande</c>

00:00:11.230 --> 00:00:13.000 align:start position:0%
izleyenler. Ben Hande
Günün başlıkları
"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "rolling.vtt"
            path.write_text(sample, encoding="utf-8")
            cues = parse_vtt(path)
        self.assertEqual(
            [cue.text for cue in cues],
            ["Şov Haber'den akşamlar", "izleyenler. Ben Hande", "Günün başlıkları"],
        )

    def test_transition_starts_new_paragraph(self):
        sample = """WEBVTT

00:00:00.000 --> 00:00:12.000
İlk haberin başlangıcı.

00:00:12.000 --> 00:00:25.000
İlk haber devam ediyor.

00:00:25.000 --> 00:00:35.000
Şimdi sıradaki haberimize geçiyoruz.
"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.vtt"
            path.write_text(sample, encoding="utf-8")
            cues = parse_vtt(path)
        stories = split_stories(cues, [r"şimdi sıradaki haberimize"], 20)
        self.assertEqual(len(stories), 2)
        self.assertTrue(stories[1].text.startswith("Şimdi sıradaki"))

    def test_no_rules_keeps_single_paragraph(self):
        sample = """WEBVTT

00:00:00.000 --> 00:00:10.000
Birinci metin.

00:00:10.000 --> 00:00:20.000
İkinci metin.
"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.vtt"
            path.write_text(sample, encoding="utf-8")
            stories = split_stories(parse_vtt(path), [], 20)
        self.assertEqual(len(stories), 1)


if __name__ == "__main__":
    unittest.main()
