from argparse import Namespace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from news_batch_windows import assemble, collect_results, prepare, slices, validate_payload, window_text, windows, word_spans
from openai_news_batch import load_json
import openai_news_batch as cli


def boundary(local, **extra):
    return {"start_token": local, "title": "Haber", "topic": "Konu", "kind": "news", "confidence": 1.0, "reason": "Yeni olay", **extra}


def api_result(identifier, payload):
    return {"custom_id": identifier, "response": {"status_code": 200, "body": {"status": "completed", "output": [
        {"type": "message", "content": [{"type": "output_text", "text": json.dumps(payload)}]}
    ]}}}


def write_results(path, records):
    path.write_text("\n".join(json.dumps(record) for record in reversed(records)) + "\n", encoding="utf-8")


def test_window(count, core, context, index=0):
    return {**windows(count, core, context)[index], "custom_id": "test-window"}


class WindowTests(unittest.TestCase):
    def test_cli_review_stage_routes_to_separate_job_and_output(self):
        with patch("sys.argv", ["openai_news_batch.py", "collect", "--job", "data/jobs/demo", "--stage", "review"]), patch.object(cli, "collect", return_value=0) as action:
            self.assertEqual(cli.main(), 0)
            args = action.call_args.args[0]
            self.assertEqual(args.job, Path("data/jobs/demo/review"))
            self.assertEqual(args.output.name, "demo")

    def test_owned_regions_cover_every_word_once_and_context_overlaps(self):
        ranges = windows(23, 8, 3)
        self.assertEqual([i for w in ranges for i in range(w["core_start"], w["core_end"])], list(range(23)))
        self.assertLess(ranges[1]["view_start"], ranges[0]["view_end"])
        self.assertEqual(ranges[-1]["core_end"], 23)

    def test_each_word_has_its_own_explicit_id_and_source_is_not_rewritten(self):
        text = "İlk  enflayon.\nİkinci haber."
        self.assertEqual(window_text(text, windows(4, 4, 1)[0]), "[0001] İlk\n[0002] enflayon.\n[0003] İkinci\n[0004] haber.")

    def test_continuing_story_does_not_force_boundary_at_window_start(self):
        window = test_window(20, 8, 2, 1)
        self.assertEqual(validate_payload({"boundaries": []}, window, "detect"), ([], []))

    def test_context_observation_is_valid_and_can_be_reassigned(self):
        window = test_window(20, 8, 2, 1)
        context, _ = validate_payload({"boundaries": [boundary(2)]}, window, "detect")
        self.assertEqual(context[0]["global_word"], 7)
        valid, _ = validate_payload({"boundaries": [boundary(3)]}, window, "detect")
        self.assertEqual(valid[0]["global_word"], 8)

    def test_review_must_account_for_every_candidate(self):
        window = test_window(12, 8, 2)
        candidates = [{"candidate_id": "c0001", "global_word": 0}, {"candidate_id": "c0002", "global_word": 4}]
        with self.assertRaises(ValueError):
            validate_payload({"boundaries": [boundary(1, review_of="c0001", verdict="supported")], "discarded": []}, window, "review", candidates)

    def test_review_can_move_add_and_discard_with_trace(self):
        window = test_window(12, 8, 2)
        candidates = [{"candidate_id": "c0001", "global_word": 1}, {"candidate_id": "c0002", "global_word": 4}]
        payload = {"boundaries": [boundary(1, review_of="c0001", verdict="supported"), boundary(6, review_of="", verdict="uncertain")],
                   "discarded": [{"candidate_id": "c0002", "reason": "Aynı haberin devamı"}]}
        result, discarded = validate_payload(payload, window, "review", candidates)
        self.assertEqual([item["review_action"] for item in result], ["moved", "added"])
        self.assertEqual(discarded[0]["candidate_id"], "c0002")

    def test_candidate_cannot_be_both_kept_and_discarded(self):
        window = test_window(8, 8, 2)
        payload = {"boundaries": [boundary(1, review_of="c0001", verdict="supported")], "discarded": [{"candidate_id": "c0001", "reason": "duplicate"}]}
        with self.assertRaises(ValueError):
            validate_payload(payload, window, "review", [{"candidate_id": "c0001", "global_word": 0}])

    def test_duplicate_and_out_of_order_boundaries_are_rejected(self):
        window = test_window(8, 8, 2)
        for ids in [[1, 1], [3, 2], [True], [0], [9]]:
            with self.assertRaises(ValueError):
                validate_payload({"boundaries": [boundary(i) for i in ids]}, window, "detect")

    def test_full_source_is_preserved_and_even_confident_results_need_review(self):
        text = "  İlk haber.\r\n\r\nYeni haber.\n"
        result = slices(text, [{**boundary(1), "global_word": 0}, {**boundary(1), "global_word": 2}])
        self.assertEqual("".join(item["text"] for item in result), text)
        self.assertTrue(all(item["needs_review"] and not item["human_approved"] for item in result))

    def fixture(self, root):
        source = root / "input/Show"
        source.mkdir(parents=True)
        text = "  Merhaba  izleyenler.\r\nİlk haber başladı. İlk haber sürüyor.\nYeni haber başladı.\n"
        (source / "20250101.txt").write_bytes(text.encode("utf-8"))
        job = root / "job"
        args = Namespace(input=source.parent, job=job, per_channel=1, model="test", review_model=None, window_words=4, context_words=1, max_chars=10000)
        prepare(args)
        manifest = load_json(job / "manifest.json")
        records = []
        for window in manifest["requests"]:
            starts = [0, 3] if window["core_start"] == 0 else [9] if window["core_start"] == 8 else []
            items = [boundary(index - window["view_start"] + 1) for index in starts]
            if window["core_start"] == 0:
                items[0]["kind"] = "opening"
            records.append(api_result(window["custom_id"], {"boundaries": items}))
        results = root / "detect.jsonl"
        write_results(results, records)
        return job, results, records, text

    def test_missing_or_failed_window_blocks_whole_bulletin(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job, results, records, _ = self.fixture(root)
            write_results(results, records[:1] + records[2:])
            report = assemble(job, results)
            self.assertEqual(report["successful_documents"], 0)
            self.assertIn("sonuç eksik", " ".join(report["documents"][0]["errors"]))
            records[1] = {"custom_id": records[1]["custom_id"], "error": {"code": "batch_expired"}}
            write_results(results, records)
            self.assertEqual(assemble(job, results)["successful_documents"], 0)

    def test_duplicate_or_unknown_api_result_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job, results, records, _ = self.fixture(root)
            write_results(results, records + records[:1])
            with self.assertRaises(ValueError):
                assemble(job, results)
            records[0]["custom_id"] = "unexpected"
            write_results(results, records)
            with self.assertRaises(ValueError):
                assemble(job, results)

    def test_context_duplicates_missing_intro_and_bad_id_are_recoverable_for_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job, results, records, _ = self.fixture(root)
            manifest = load_json(job / "manifest.json")
            # Actual failure pattern: intro starts at ID 2, a context boundary
            # repeats an owned proposal, and one ID is outside the view.
            first = manifest["requests"][0]
            records[0] = api_result(first["custom_id"], {"boundaries": [boundary(2, kind="opening"), boundary(4)]})
            middle = manifest["requests"][1]
            records[1] = api_result(middle["custom_id"], {"boundaries": [boundary(1, title="Context hypothesis")]})
            last = manifest["requests"][2]
            records[2] = api_result(last["custom_id"], {"boundaries": [boundary(3), boundary(999)]})
            write_results(results, records)
            report = assemble(job, results)
            self.assertEqual(report["successful_documents"], 1)
            document = report["documents"][0]
            self.assertEqual(document["boundaries"][0]["global_word"], 0)
            self.assertTrue(document["boundaries"][0]["synthetic_source_start"])
            duplicates = [item for item in document["boundaries"] if item["global_word"] == 3]
            self.assertEqual(len(duplicates), 1)
            self.assertEqual(len(duplicates[0]["observations"]), 2)
            self.assertEqual(duplicates[0]["owner_window_id"], first["custom_id"])
            self.assertEqual(duplicates[0]["title"], "Haber")
            self.assertEqual({item["code"] for item in document["warnings"]}, {"synthetic_source_start", "out_of_view_token"})

    def test_review_ignores_context_candidate_owned_by_another_window(self):
        window = test_window(20, 8, 2, 1)
        window["visible_candidates"] = [{"candidate_id": "context", "global_word": 7}]
        diagnostics = []
        result, _ = validate_payload({"boundaries": [boundary(2, review_of="context", verdict="supported")], "discarded": []}, window, "review", [], diagnostics)
        self.assertEqual(result, [])
        self.assertEqual(diagnostics[0]["code"], "context_review_owned_elsewhere")

    def test_unordered_detection_proposals_are_reported_instead_of_losing_window(self):
        window = test_window(8, 8, 2)
        diagnostics = []
        proposals, _ = validate_payload({"boundaries": [boundary(4), boundary(1)]}, window, "detect", diagnostics=diagnostics)
        self.assertEqual(len(proposals), 2)
        self.assertEqual(diagnostics[0]["code"], "proposal_order_normalized")

    def test_two_stage_pipeline_moves_boundaries_preserves_bytes_and_never_submits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job, results, _, text = self.fixture(root)
            output = root / "out"
            self.assertEqual(collect_results(job, results, output), 0)
            self.assertFalse(output.exists())
            review_job = job / "review"
            manifest = load_json(review_job / "manifest.json")
            self.assertEqual(manifest["stage"], "review")
            self.assertFalse((review_job / "batch_state.json").exists())
            records = []
            for window in manifest["requests"]:
                items = []
                for candidate in window["owned_candidates"]:
                    index = candidate["global_word"]
                    corrected = 2 if index == 3 else 8 if index == 9 else index
                    items.append(boundary(corrected-window["view_start"]+1, review_of=candidate["candidate_id"], verdict="supported"))
                    items[-1]["kind"] = candidate["kind"]
                records.append(api_result(window["custom_id"], {"boundaries": items, "discarded": []}))
            reviewed_results = root / "review.jsonl"
            write_results(reviewed_results, records)
            self.assertEqual(collect_results(review_job, reviewed_results, output), 0)
            folder = output / "Show/20250101"
            metadata = load_json(folder / "haberler.json")
            self.assertEqual(b"".join((folder / item["file"]).read_bytes() for item in metadata["segments"]), text.encode("utf-8"))
            self.assertEqual((folder / "haber_001.txt").read_bytes(), "İlk haber başladı. İlk haber sürüyor.\n".encode("utf-8"))
            self.assertTrue(metadata["needs_review"])
            self.assertFalse(metadata["semantic_review_completed"])
            self.assertEqual(load_json(output / "ayirma_raporu.json")["files"][0]["moved_boundaries"], 2)

    def test_collect_downloads_and_prepares_review_without_paid_submission(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job, results, _, _ = self.fixture(root)
            (job / "batch_state.json").write_text(json.dumps({"batch_id": "test-batch", "status": "validating"}), encoding="utf-8")
            client = MagicMock()
            client.batches.retrieve.return_value = Namespace(status="completed", output_file_id="test-output", error_file_id=None)
            client.files.content.return_value = Namespace(content=results.read_bytes())
            with patch.object(cli, "api_client", return_value=client):
                self.assertEqual(cli.collect(Namespace(job=job, output=root / "out")), 0)
            client.batches.create.assert_not_called()
            client.files.create.assert_not_called()
            self.assertEqual(load_json(job / "batch_state.json")["status"], "completed")
            self.assertFalse((job / "review/batch_state.json").exists())

    def test_submitting_existing_job_cannot_charge_again(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job, _, _, _ = self.fixture(root)
            (job / "batch_state.json").write_text(json.dumps({"batch_id": "existing"}), encoding="utf-8")
            with patch.object(cli, "api_client") as client:
                with self.assertRaises(ValueError):
                    cli.submit(Namespace(job=job))
                client.assert_not_called()

    def test_review_submit_before_collect_has_clear_error_and_no_api_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(cli, "api_client") as client:
                with self.assertRaisesRegex(ValueError, "Önce collect"):
                    cli.submit(Namespace(job=Path(temporary) / "review"))
                client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
