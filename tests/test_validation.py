import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.reporting.logger import log_results
from src.validation.validation import compare_dataframe


class CompareDataframeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.reference_path = Path(self.temp_dir.name) / "reference.csv"

    def write_reference(self, frame):
        frame.to_csv(self.reference_path, index=False)
        return self.reference_path

    def test_matches_rows_by_provider_id_and_compares_aggregates(self):
        actual = pd.DataFrame({
            "provider_id": ["002", "001"],
            "score": [2.00005, 1.0],
            "report_indicator": [1, 0],
            "star": [4, 3],
        })
        expected = pd.DataFrame({
            "PROVIDER_ID": ["001", "002"],
            "SCORE": [1.0, 2.0],
            "REPORT_INDICATOR": [0, 1],
            "STAR": [3, 4],
        })
        result = compare_dataframe(actual, self.write_reference(expected), "stage", "output")

        self.assertTrue(result.passed, result.summary())
        self.assertEqual(result.compared_row_count, 2)
        self.assertEqual(result.column_comparisons["score"]["mismatch_count"], 0)
        self.assertAlmostEqual(result.column_comparisons["score"]["max_absolute_difference"], 0.00005)
        self.assertEqual(result.column_comparisons["score"]["max_difference_key"], "002")
        self.assertIn("mean", result.aggregate_comparisons["score"])
        self.assertIn("report_indicator", result.grouped_aggregate_comparisons)
        json.dumps(result.to_dict(), allow_nan=False)

    def test_matches_keys_with_non_default_dataframe_index(self):
        actual = pd.DataFrame(
            {"provider_id": ["002", "001"], "value": [2, 1]},
            index=[20, 10],
        )
        expected = pd.DataFrame({"provider_id": ["001", "002"], "value": [1, 2]})
        result = compare_dataframe(actual, self.write_reference(expected), "stage", "output")

        self.assertTrue(result.passed, result.summary())
        self.assertEqual(result.compared_row_count, 2)

    def test_reports_unmatched_keys_and_value_samples(self):
        actual = pd.DataFrame({"provider_id": ["001", "003"], "score": [1.5, 3.0]})
        expected = pd.DataFrame({"PROVIDER_ID": ["001", "002"], "SCORE": [1.0, 2.0]})
        result = compare_dataframe(actual, self.write_reference(expected), "stage", "output")

        self.assertFalse(result.passed)
        self.assertEqual(result.unmatched_key_samples_actual, ["003"])
        self.assertEqual(result.unmatched_key_samples_expected, ["002"])
        comparison = result.column_comparisons["score"]
        self.assertEqual(comparison["mismatch_count"], 1)
        self.assertEqual(comparison["samples"][0]["key"], "001")

    def test_schema_warnings_and_duplicate_or_null_keys_are_reported(self):
        actual = pd.DataFrame({
            "provider_id": ["001", "001", None],
            "value": [1, 2, 3],
            "extra": ["a", "b", "c"],
        })
        expected = pd.DataFrame({"PROVIDER_ID": ["001", "002", None], "VALUE": [1, 2, 3]})
        result = compare_dataframe(actual, self.write_reference(expected), "stage", "output")

        self.assertFalse(result.passed)
        self.assertEqual(result.extra_columns, ["extra"])
        self.assertEqual(result.duplicate_key_rows_actual, 2)
        self.assertEqual(result.null_key_count_actual, 1)
        self.assertTrue(any("warning" in note for note in result.notes))

    def test_duplicate_column_names_are_reported_without_crashing(self):
        actual = pd.DataFrame([[1, 2]], columns=["provider_id", "PROVIDER_ID"])
        expected = pd.DataFrame({"provider_id": [1], "value": [2]})
        result = compare_dataframe(actual, self.write_reference(expected), "stage", "output")

        self.assertFalse(result.passed)
        self.assertEqual(result.duplicate_columns_actual, ["PROVIDER_ID"])

    def test_logger_persists_full_json_safe_result(self):
        actual = pd.DataFrame({"provider_id": ["001"], "value": [1.0]})
        expected = pd.DataFrame({"provider_id": ["001"], "value": [1.0]})
        result = compare_dataframe(actual, self.write_reference(expected), "stage", "output")

        log_results({"output": result}, "stage", Path(self.temp_dir.name))
        log_path = next(Path(self.temp_dir.name).glob("validation_log_*.jsonl"))
        with log_path.open(encoding="utf-8") as file:
            entry = json.loads(file.readline())
        self.assertEqual(entry["compared_row_count"], 1)
        self.assertIn("aggregate_comparisons", entry)
        self.assertIn("summary", entry)

    def test_missing_reference_is_an_explicit_failure(self):
        result = compare_dataframe(
            pd.DataFrame({"provider_id": ["001"]}),
            Path(self.temp_dir.name) / "missing.csv",
            "stage",
            "output",
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.row_count_expected, -1)
        self.assertIn("Reference file not found", result.notes[0])


if __name__ == "__main__":
    unittest.main()
