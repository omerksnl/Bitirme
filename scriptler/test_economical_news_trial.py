import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from argparse import Namespace

from economical_news_trial import apply_group, cue_positions, peak_indices, snippet, submit_budgeted, write_sections, export_decisions
from openai_news_batch import digest,save_json


class EconomicalTests(unittest.TestCase):
    def test_rolling_caption_new_line_is_a_boundary_option(self):
        text="Bülten başladı önceki konu bitti Cumhurbaşkanı yeni açıklama yaptı konu değişti"
        raw="WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nBülten başladı önceki konu bitti\nCumhurbaşkanı<00:00:00.100><c> yeni açıklama yaptı konu değişti</c>\n"
        self.assertIn(5,cue_positions(text,raw,{}))

    def test_unique_prefix_matching_does_not_guess_repeated_anchor(self):
        text="Bir iki üç dört beş altı Bir iki üç dört beş yedi"
        raw="WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nBir iki üç dört beş\n"
        self.assertEqual(cue_positions(text,raw,{}),[0])

    def test_peak_suppression_keeps_strongest_change(self):
        positions=[0,24,48,72,96,120,144]
        selected,_=peak_indices([0.1,0.2,0.1,0.9,0.1,0.3,0.1],positions)
        self.assertIn(3,selected)
        self.assertTrue(all(abs(positions[a]-positions[b])>=48 for a in selected for b in selected if a!=b))

    def test_decisions_cannot_select_nonexistent_position_or_skip_candidates(self):
        candidates=[{"candidate_id":"P1","choices":{"B1":10}}]
        for payload in [{"decisions":[]},{"decisions":[{"candidate_id":"P1","decision":"split","chosen_boundary":"B2"}]},{"decisions":[{"candidate_id":"P1","decision":"merge","chosen_boundary":"B1"}]}]:
            with self.assertRaises(ValueError):
                apply_group(payload,candidates)
        result=apply_group({"decisions":[{"candidate_id":"P1","decision":"split","chosen_boundary":"B1"}]},candidates)
        self.assertEqual(result["P1"]["decision"],"split")

    def test_original_whitespace_and_turkish_text_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            text="  İlk enflayon haberi.\r\nİkinci haber.\n"
            folder=Path(temp)/"sections"
            write_sections(folder,text,[text.index("İkinci")],{})
            meta=json.loads((folder/"bolumler.json").read_text(encoding="utf-8"))
            self.assertEqual(b"".join((folder/item["file"]).read_bytes() for item in meta["sections"]),text.encode())
            self.assertFalse(meta["human_approved"])

    def test_budget_stops_api_submission(self):
        with tempfile.TemporaryDirectory() as temp:
            job=Path(temp)
            save_json(job/"maliyet_raporu.json",{"estimated_input_cost_usd":0.1,"output_cost_cap_usd":0.1})
            with patch("economical_news_trial.submit") as api:
                with self.assertRaises(ValueError):
                    submit_budgeted(Namespace(job=job,budget_usd=0.15))
                api.assert_not_called()

    def test_missing_api_results_are_pending_not_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            job=Path(temp)
            text="İlk haber. İkinci haber."
            (job/"source.txt").write_bytes(text.encode())
            save_json(job/"manifest.json",{"documents":[{"doc_id":"d","source":"Show/test.txt","snapshot":"source.txt","sha256":digest(text.encode())}],
                "requests":[{"custom_id":"r","doc_id":"d","candidate_ids":["P1"]}],
                "candidates":[{"candidate_id":"P1","doc_id":"d","char_position":text.index("İkinci"),"choices":{"B1":text.index("İkinci")}}]})
            results=job/"results.jsonl"
            results.write_text("",encoding="utf-8")
            self.assertEqual(export_decisions(job,results),1)
            meta=json.loads((job/"api_taslaklar/Show/test/bolumler.json").read_text(encoding="utf-8"))
            self.assertFalse(meta["all_candidate_decisions_received"])
            self.assertEqual(meta["decisions"][0]["decision"],"pending")


if __name__=="__main__":
    unittest.main()
