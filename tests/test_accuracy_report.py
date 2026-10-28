from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.reporting.accuracy_report import (
    STAR_FILE, build_accuracy_report, format_accuracy_report, unvalidated_references,
)
from src.validation.validation import compare_dataframe


class AccuracyReportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.reference_dir, self.actual_dir = root / "reference", root / "actual"
        self.reference_dir.mkdir()
        self.actual_dir.mkdir()

    def write_pair(self, name, expected, actual):
        expected.to_csv(self.reference_dir / name, index=False)
        actual.to_csv(self.actual_dir / name, index=False)
        return compare_dataframe(actual, self.reference_dir / name, "stage", Path(name).stem)

    def stars(self, sas, python):
        ids = [f"{i:06d}" for i in range(1, len(sas) + 1)]
        return self.write_pair(
            STAR_FILE,
            pd.DataFrame({"PROVIDER_ID": ids, "star": sas}),
            pd.DataFrame({"provider_id": ids, "star": python}),
        )

    def test_reference_without_python_output_is_reported(self):
        result = self.stars([1, 2], [1, 2])
        pd.DataFrame({"x": [1]}).to_csv(self.reference_dir / "PTEXP.csv", index=False)
        all_results = {"stage": {"star": result}}

        self.assertEqual(unvalidated_references(all_results, self.reference_dir), ["PTEXP.csv"])
        report = build_accuracy_report(all_results, self.reference_dir, self.actual_dir)
        self.assertFalse(report["complete"])
        self.assertIn("NOT VALIDATED: PTEXP.csv", format_accuracy_report(report))

    def test_value_accuracy_and_star_agreement(self):
        # 4 hospitals: one off by one star, one SAS-unrated that Python rates
        result = self.stars([3, 4, 5, None], [3, 3, 5, 2])
        report = build_accuracy_report({"stage": {"star": result}}, self.reference_dir, self.actual_dir)

        star_table = report["tables"][STAR_FILE]
        self.assertEqual(star_table["values_compared"], 4)
        self.assertEqual(star_table["values_mismatched"], 2)
        self.assertAlmostEqual(report["overall_value_accuracy"], 0.5)

        stars = report["stars"]
        self.assertEqual((stars["rated_matching"], stars["sas_rated"]), (2, 3))
        self.assertEqual(stars["off_by_one"], 1)
        self.assertEqual(stars["confusion"]["4"]["3"], 1)
        self.assertEqual(stars["confusion"]["none"]["2"], 1)

    def test_stale_star_file_is_ignored_when_star_was_not_validated(self):
        self.stars([1, 2], [5, 5])  # files on disk, but not part of this run's results
        report = build_accuracy_report({}, self.reference_dir, self.actual_dir)
        self.assertIsNone(report["stars"])
        self.assertEqual(report["coverage"]["unvalidated"], [STAR_FILE])


if __name__ == "__main__":
    unittest.main()
