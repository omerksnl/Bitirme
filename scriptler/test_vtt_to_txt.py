import unittest
from vtt_to_txt import convert, correct_words


def sample(*cues):
    return "WEBVTT\n\n" + "\n\n".join(f"{start} --> {end}\n{text}" for start, end, text in cues)


class VttTests(unittest.TestCase):
    def test_rolling_partial_and_full_repetition(self):
        text, _ = convert(sample(
            ("00:00:00.000", "00:00:02.000", "Bugün enflasyon yükseldi"),
            ("00:00:01.900", "00:00:03.000", "enflasyon yükseldi ve fiyatlar arttı"),
            ("00:00:02.900", "00:00:04.000", "ve fiyatlar arttı")), {})
        self.assertEqual(text, "Bugün enflasyon yükseldi ve fiyatlar arttı\n")

    def test_inline_tags_and_both_lines_preserved(self):
        text, _ = convert(sample(
            ("00:00:00.000", "00:00:02.000", "İlk<00:00:00.100><c> satır</c>\nİkinci satır &amp; bilgi")), {})
        self.assertEqual(text, "İlk satır İkinci satır & bilgi\n")

    def test_deliberate_repetition_after_pause_and_speaker(self):
        text, _ = convert(sample(
            ("00:00:00.000", "00:00:02.000", "Fiyatlar arttı."),
            ("00:00:08.000", "00:00:10.000", "Fiyatlar arttı."),
            ("00:00:09.900", "00:00:12.000", ">> Fiyatlar arttı.")), {})
        self.assertEqual(text.count("Fiyatlar arttı."), 3)

    def test_single_word_emphasis_preserved(self):
        text, _ = convert(sample(
            ("00:00.000", "00:01.000", "Çok"),
            ("00:01.000", "00:02.000", "çok önemli")), {})
        self.assertEqual(text, "Çok çok önemli\n")

    def test_explicit_corrections_preserve_names_and_numbers(self):
        text, changes = correct_words("Enflayon %42,5. ENFLAYON. Ömer ekonmi.", {"enflayon": "enflasyon", "ekonmi": "ekonomi"})
        self.assertEqual(text, "Enflasyon %42,5. ENFLASYON. Ömer ekonomi.")
        self.assertEqual(sum(changes.values()), 3)

    def test_invalid_vtt_is_reported(self):
        with self.assertRaises(ValueError):
            convert("WEBVTT\n", {})


if __name__ == "__main__":
    unittest.main()
