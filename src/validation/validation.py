from dataclasses import dataclass, field
from pathlib import Path
import pandas as pd


@dataclass
class ValidationResult:
    stage_name: str
    variable_name: str
    reference_path: Path
    passed: bool
    row_count_actual: int
    row_count_expected: int
    missing_columns: list = field(default_factory=list)
    extra_columns: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [f"[{status}] {self.stage_name} :: {self.variable_name}"]
        lines.append(f"    rows: {self.row_count_actual} actual vs {self.row_count_expected} expected")
        if self.missing_columns:
            lines.append(f"    missing columns: {self.missing_columns}")
        if self.extra_columns:
            lines.append(f"    extra columns: {self.extra_columns}")
        for note in self.notes:
            lines.append(f"    note: {note}")
        return "\n".join(lines)


def compare_dataframe(actual_df, reference_csv_path, stage_name, variable_name, numeric_tolerance=1e-4):
    """
    PLACEHOLDER comparison: checks row count and column names match.
    TODO: replace with datacompy for real key-matched, tolerance-aware comparison.
    """
    notes = []

    if not reference_csv_path.exists():
        return ValidationResult(
            stage_name=stage_name, variable_name=variable_name,
            reference_path=reference_csv_path, passed=False,
            row_count_actual=len(actual_df), row_count_expected=-1,
            notes=[f"Reference file not found: {reference_csv_path}"],
        )

    expected_df = pd.read_csv(reference_csv_path)
    actual_cols = {c.strip().lower() for c in actual_df.columns}
    expected_cols = {c.strip().lower() for c in expected_df.columns}
    missing_columns = sorted(expected_cols - actual_cols)
    extra_columns = sorted(actual_cols - expected_cols)

    row_count_actual = len(actual_df)
    row_count_expected = len(expected_df)
    rows_match = row_count_actual == row_count_expected

    passed = rows_match and not missing_columns
    if not rows_match:
        notes.append("Row counts differ.")
    if missing_columns:
        notes.append(f"Missing columns: {missing_columns}")

    return ValidationResult(
        stage_name=stage_name, variable_name=variable_name,
        reference_path=reference_csv_path, passed=passed,
        row_count_actual=row_count_actual, row_count_expected=row_count_expected,
        missing_columns=missing_columns, extra_columns=extra_columns, notes=notes,
    )