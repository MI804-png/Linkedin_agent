from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
os.environ["AUTOAPPLY_DISABLE_WEBAPP_SCHEDULER"] = "1"
sys.path.insert(0, str(ROOT / "webapp"))

import bot_runner  # type: ignore
import app as webapp_app  # type: ignore


class WatchRunOutcomeTests(unittest.TestCase):
    def test_nonzero_exit_marks_error(self) -> None:
        status, note = bot_runner._classify_watch_run_outcome(
            proc_returncode=1,
            stop_requested=False,
            run_history_entry=None,
            job_events=[],
        )
        self.assertEqual(status, "error")
        self.assertIn("code 1", note)

    def test_missing_history_and_events_marks_error(self) -> None:
        status, note = bot_runner._classify_watch_run_outcome(
            proc_returncode=0,
            stop_requested=False,
            run_history_entry=None,
            job_events=[],
        )
        self.assertEqual(status, "error")
        self.assertIn("without recording run history or job events", note)

    def test_recorded_history_marks_done(self) -> None:
        status, note = bot_runner._classify_watch_run_outcome(
            proc_returncode=0,
            stop_requested=False,
            run_history_entry={"stats": {"submitted": 2}},
            job_events=[],
        )
        self.assertEqual(status, "done")
        self.assertEqual(note, "")

    def test_history_stats_are_normalized(self) -> None:
        stats = bot_runner._extract_run_history_stats(
            {"stats": {"submitted": "2", "failures": 1, "manual_required": "3"}}
        )
        self.assertEqual(stats["submitted"], 2)
        self.assertEqual(stats["failures"], 1)
        self.assertEqual(stats["manual_required"], 3)


class RequirementsMetadataTests(unittest.TestCase):
    def test_requirements_metadata_reads_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            folder = Path(tmp_dir)
            sample = folder / "123_example_requirements.txt"
            sample.write_text(
                "Title: Backend Engineer\n"
                "Company: Example Corp\n"
                "URL: https://example.com/jobs/123\n\n"
                "Requirement body",
                encoding="utf-8",
            )

            original = webapp_app.STUDY_GUIDES_FOLDER
            webapp_app.STUDY_GUIDES_FOLDER = folder
            try:
                metadata = webapp_app._load_requirements_metadata("123")
            finally:
                webapp_app.STUDY_GUIDES_FOLDER = original

            self.assertEqual(
                metadata,
                {
                    "title": "Backend Engineer",
                    "company": "Example Corp",
                    "job_url": "https://example.com/jobs/123",
                },
            )


if __name__ == "__main__":
    unittest.main()