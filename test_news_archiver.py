import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import news_archiver as app


class NewsArchiverTests(unittest.TestCase):
    def test_parse_tr_date(self):
        self.assertEqual(app.parse_tr_date("02-10-2026"), date(2026, 10, 2))

    def test_manual_date_can_be_before_automatic_archive_start(self):
        self.assertEqual(app.parse_tr_date("30-09-2026"), date(2026, 9, 30))

    def test_score_prefers_official_full_dated_bulletin(self):
        channel = {
            "uploader_patterns": ["atv Haber"],
            "title_patterns": ["atv Ana Haber"],
            "exclude_patterns": ["Kahvaltı Haberleri"],
            "minimum_duration_minutes": 25,
        }
        info = {
            "title": "atv Ana Haber | 1 Ekim 2026",
            "uploader": "atv Haber",
            "upload_date": "20261001",
            "duration": 3100,
        }
        self.assertEqual(app.score_candidate(info, channel, date(2026, 10, 1)), 110)

    def test_next_date_requires_all_channels_to_be_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            decisions = Path(temp) / "decisions.csv"
            rows = (
                "channel_id,channel_name,target_date,decision,video_id,url,title,uploader,"
                "duration_seconds,score,decision_source,decided_at\n"
                "show,Show,2026-10-01,accepted,,,,,,,,\n"
                "atv,ATV,2026-10-01,skipped,,,,,,,,\n"
            )
            decisions.write_text(rows, encoding="utf-8-sig")
            with patch.object(app, "DECISIONS_PATH", decisions):
                self.assertEqual(
                    app.next_incomplete_date(date(2026, 10, 1), ["show", "atv"]),
                    date(2026, 10, 2),
                )

    def test_archive_failure_is_not_a_terminal_decision(self):
        with tempfile.TemporaryDirectory() as temp:
            decisions = Path(temp) / "decisions.csv"
            rows = (
                "channel_id,channel_name,target_date,decision,video_id,url,title,uploader,"
                "duration_seconds,score,decision_source,decided_at\n"
                "show,Show,2026-10-01,accepted,,,,,,,,\n"
                "atv,ATV,2026-10-01,archive_failed,,,,,,,,\n"
            )
            decisions.write_text(rows, encoding="utf-8-sig")
            with patch.object(app, "DECISIONS_PATH", decisions):
                self.assertEqual(
                    app.next_incomplete_date(date(2026, 10, 1), ["show", "atv"]),
                    date(2026, 10, 1),
                )


if __name__ == "__main__":
    unittest.main()
