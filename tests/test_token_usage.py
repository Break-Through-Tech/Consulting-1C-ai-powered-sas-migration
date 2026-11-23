import csv
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from src.reporting.token_usage import TokenUsageTracker, append_token_history, save_token_usage
from src.translation import translation


def fake_response(text="x = all_data.copy()", prompt=100, output=20, thinking=5, cached=0, total=None):
    meta = SimpleNamespace(
        prompt_token_count=prompt, candidates_token_count=output, thoughts_token_count=thinking,
        cached_content_token_count=cached,
        total_token_count=prompt + output + thinking if total is None else total,
    )
    return SimpleNamespace(text=text, usage_metadata=meta)


class TokenUsageTrackerTests(unittest.TestCase):
    def test_records_and_totals_calls(self):
        usage = TokenUsageTracker(model="m")
        usage.record("a", fake_response(prompt=100, output=20, thinking=5, cached=40))
        usage.record("b", fake_response(prompt=300, output=50, thinking=0))
        self.assertEqual(usage.totals(),
                         {"prompt": 400, "output": 70, "thinking": 5, "cached": 40, "total": 475})
        self.assertIn("TOTAL", usage.format_summary())

    def test_missing_usage_metadata_counts_zero_and_is_flagged(self):
        usage = TokenUsageTracker()
        call = usage.record("a", SimpleNamespace(text="x", usage_metadata=None))
        self.assertFalse(call.reported)
        self.assertEqual(usage.totals()["total"], 0)
        self.assertEqual(usage.to_dict()["calls_without_usage"], 1)
        self.assertIn("no usage reported", usage.format_summary())

    def test_no_calls_means_translation_skipped(self):
        self.assertIn("0 tokens used", TokenUsageTracker().format_summary())

    def test_cost_estimate_only_when_prices_set(self):
        usage = TokenUsageTracker()
        usage.record("a", fake_response(prompt=1_000_000, output=500_000, thinking=500_000))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(usage.estimated_cost())
        with mock.patch.dict(os.environ, {"GEMINI_INPUT_PRICE_PER_M": "0.10",
                                          "GEMINI_OUTPUT_PRICE_PER_M": "0.40"}):
            self.assertAlmostEqual(usage.estimated_cost(), 0.10 + 0.40)

    def test_saves_files_and_appends_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            usage = TokenUsageTracker(model="m")
            usage.record("a", fake_response())
            save_token_usage(usage, out / "latest")
            for attempt in (1, 2):
                append_token_history(usage, out / "history.csv", run="r", attempt=attempt, translation="fresh")
            self.assertEqual(json.loads((out / "latest" / "token_usage.json").read_text())["totals"]["total"], 125)
            self.assertTrue((out / "latest" / "token_usage_calls.csv").exists())
            with (out / "history.csv").open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual([r["attempt"] for r in rows], ["1", "2"])
            self.assertEqual(rows[0]["total_tokens"], "125")


class TranslatorRecordsTokensTests(unittest.TestCase):
    """Runs the real translate_sas_files with a fake Gemini client (no API call)."""

    def test_every_api_call_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            sas_dir, out_dir = Path(tmp) / "sas", Path(tmp) / "out"
            sas_dir.mkdir()
            (sas_dir / "0 - Standardize.sas").write_text("data a; set b; run;")
            (sas_dir / "1 - Stage one.sas").write_text("data c; set a; run;")

            responses = iter([fake_response(prompt=1000, output=200),
                              fake_response(prompt=2500, output=300),
                              fake_response(text="# README", prompt=4000, output=600)])
            chat = SimpleNamespace(send_message=lambda message: next(responses))
            client = SimpleNamespace(chats=SimpleNamespace(create=lambda **kwargs: chat))

            usage = TokenUsageTracker(model=translation.MODEL)
            with mock.patch.object(translation.genai, "Client", return_value=client), \
                 mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test"}):
                translation.translate_sas_files(sas_dir, out_dir, usage=usage)

            self.assertEqual([c.label for c in usage.calls],
                             ["translate 0 - Standardize.sas", "translate 1 - Stage one.sas",
                              "generate README.md"])
            self.assertEqual(usage.totals()["prompt"], 7500)
            self.assertEqual(usage.totals()["total"], 7500 + 1100 + 15)


if __name__ == "__main__":
    unittest.main()
