import csv
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.reporting.accuracy_report import STAR_FILE, build_accuracy_report
from src.reporting.verification_output import write_verification_output
from src.validation.validation import compare_dataframe


class VerificationOutputTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.ref, self.act, self.out = self.root / "ref", self.root / "act", self.root / "out"
        self.ref.mkdir()
        self.act.mkdir()

    def run_once(self, python_stars, extra_reference=False):
        ids = ["000001", "000002", "000003", "000004"]
        pd.DataFrame({"PROVIDER_ID": ids, "star": [1, 2, 3, 4]}).to_csv(self.ref / STAR_FILE, index=False)
        actual = pd.DataFrame({"provider_id": ids, "star": python_stars})
        actual.to_csv(self.act / STAR_FILE, index=False)
        if extra_reference:
            pd.DataFrame({"x": [1]}).to_csv(self.ref / "PTEXP.csv", index=False)
        result = compare_dataframe(actual, self.ref / STAR_FILE, "stage", "Star_2025jul")
        all_results = {"stage": {"Star_2025jul": result}}
        report = build_accuracy_report(all_results, self.ref, self.act)
        failed = int(not result.passed) + int(extra_reference)
        return write_verification_output(
            report, all_results, self.out, run="run_test", attempt=1,
            translation="fresh SAS-to-Python translation",
            checks_passed=1 - int(not result.passed), checks_failed=failed,
        )

    def history(self):
        with (self.out / "accuracy_history.csv").open() as f:
            return list(csv.DictReader(f))

    def test_passing_run_writes_all_outputs(self):
        report_path = self.run_once([1, 2, 3, 4])
        latest = self.out / "latest"
        for name in ("verification_report.md", "table_accuracy.csv", "column_accuracy.csv",
                     "star_confusion.csv", "accuracy_report.json"):
            self.assertTrue((latest / name).exists(), name)
        self.assertIn("**Verdict: PASS**", report_path.read_text(encoding="utf-8"))
        row = self.history()[0]
        self.assertEqual((row["verdict"], row["overall_value_accuracy"]), ("PASS", "100.0000"))

    def test_failing_run_reports_fail_and_accuracy(self):
        text = self.run_once([1, 2, 3, 3], extra_reference=True).read_text(encoding="utf-8")
        self.assertIn("**Verdict: FAIL**", text)
        self.assertIn("NOT VALIDATED: `PTEXP.csv`", text)
        self.assertIn("Off by exactly one star: 1", text)
        row = self.history()[0]
        self.assertEqual(row["verdict"], "FAIL")
        self.assertEqual(row["overall_value_accuracy"], "75.0000")
        self.assertEqual(row["coverage"], "1/2")

    def test_history_appends_and_latest_is_replaced(self):
        self.run_once([1, 2, 3, 3])
        (self.out / "latest" / "stale.txt").write_text("old")
        self.run_once([1, 2, 3, 4])
        self.assertEqual([r["verdict"] for r in self.history()], ["FAIL", "PASS"])
        self.assertFalse((self.out / "latest" / "stale.txt").exists())


if __name__ == "__main__":
    unittest.main()
