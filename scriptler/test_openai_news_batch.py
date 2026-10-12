import json
from pathlib import Path
import tempfile
import unittest

from openai_news_batch import digest, export_results, make_request, save_json, split_original


def segment(quote, kind="news", confidence=0.9):
    return {"start_quote": quote, "title": "Başlık", "topic": "Konu", "kind": kind, "confidence": confidence, "reason": "Konu değişimi"}


def response(identifier, payload):
    return {"custom_id": identifier, "response": {"status_code": 200, "body": {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(payload)}]}]}}}


class BatchTests(unittest.TestCase):
    def test_slices_preserve_all_original_whitespace_and_typos(self):
        text = "  İyi akşamlar.\n\nEnflayon arttı.  Yeni konu başladı.\n"
        parts = split_original(text, {"segments": [segment("İyi akşamlar.", "opening"), segment("Enflayon arttı."), segment("Yeni konu başladı.")]})
        self.assertEqual("".join(p["text"] for p in parts), text)
        self.assertIn("Enflayon", parts[1]["text"])

    def test_invented_corrected_or_ambiguous_quotes_are_rejected(self):
        for text, quote in [("Enflayon arttı.", "Enflasyon arttı."), ("Tekrar aynı. Tekrar aynı.", "Tekrar aynı.")]:
            with self.assertRaises(ValueError):
                split_original(text, {"segments": [segment(quote)]})

    def test_skipped_start_and_out_of_order_are_rejected(self):
        for parts in [[segment("İkinci haber.")], [segment("İlk haber."), segment("Üçüncü haber."), segment("İkinci haber.")]]:
            with self.assertRaises(ValueError):
                split_original("İlk haber. İkinci haber. Üçüncü haber.", {"segments": parts})

    def test_request_uses_responses_structured_outputs(self):
        request = make_request("test", "bülten", "Show", "my-model")
        self.assertEqual(request["url"], "/v1/responses")
        self.assertTrue(request["body"]["text"]["format"]["strict"])
        self.assertFalse(request["body"]["store"])

    def test_out_of_order_results_map_by_id_and_preserve_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job = root / "job"
            requests = []
            rows = []
            for identifier, text in [("a", "A haberi.\n"), ("b", "B haberi.\n")]:
                snapshot = job / f"{identifier}.txt"
                snapshot.parent.mkdir(exist_ok=True)
                raw = text.encode("utf-8")
                snapshot.write_bytes(raw)
                requests.append({"custom_id": identifier, "snapshot": snapshot.name, "source": f"Show/{identifier}.txt", "sha256": digest(raw)})
                rows.append(response(identifier, {"segments": [segment(text.strip())]}))
            save_json(job / "manifest.json", {"requests": requests, "model": "test"})
            results = root / "results.jsonl"
            results.write_text("\n".join(json.dumps(row) for row in reversed(rows)), encoding="utf-8")
            output = root / "out"
            self.assertEqual(export_results(job, results, output), 0)
            self.assertEqual((output / "Show/a/haber_001.txt").read_bytes(), "A haberi.\n".encode())
            self.assertEqual((output / "Show/b/haber_001.txt").read_bytes(), "B haberi.\n".encode())
            with self.assertRaises(ValueError):
                export_results(job, results, output)

    def test_missing_result_does_not_create_fabricated_news(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job = root / "job"
            save_json(job / "manifest.json", {"requests": [{"custom_id": "missing", "source": "Show/a.txt"}]})
            results = root / "results.jsonl"
            results.write_text("", encoding="utf-8")
            output = root / "out"
            self.assertEqual(export_results(job, results, output), 1)
            self.assertEqual(list(output.rglob("haber_*.txt")), [])


if __name__ == "__main__":
    unittest.main()
