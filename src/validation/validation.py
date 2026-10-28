import csv
from dataclasses import asdict, dataclass, field
import math
from pathlib import Path
from typing import Any

import pandas as pd


AGGREGATE_STATISTICS = ("count", "mean", "std", "min", "q25", "median", "q75", "max", "sum")
GROUP_COLUMNS = ("report_indicator", "star")
MAX_MISMATCH_SAMPLES = 10
MAX_KEY_SAMPLES = 20
MAX_GROUPS = 25


def _column_key(name: Any) -> str:
    return str(name).strip().lower()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or value is pd.NA:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _is_missing(value: Any) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _key_value(value: Any) -> str | None:
    if _is_missing(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _normalized_columns(columns: pd.Index) -> tuple[dict[str, Any], list[str]]:
    mapping: dict[str, Any] = {}
    duplicates = []
    for column in columns:
        key = _column_key(column)
        if key in mapping:
            duplicates.append(str(column))
        else:
            mapping[key] = column
    return mapping, duplicates


def _duplicate_column_keys(columns: pd.Index) -> set[str]:
    keys = [_column_key(column) for column in columns]
    return {key for key in keys if keys.count(key) > 1}


def _numeric_series(series: pd.Series) -> pd.Series | None:
    converted = pd.to_numeric(series, errors="coerce")
    non_missing = series.notna()
    if not non_missing.any() or converted[non_missing].notna().all():
        return converted.astype(float)
    return None


def _close(actual: float, expected: float, absolute_tolerance: float, relative_tolerance: float) -> bool:
    return math.isclose(
        actual,
        expected,
        abs_tol=absolute_tolerance,
        rel_tol=relative_tolerance,
    )


def _aggregate_statistics(series: pd.Series) -> dict[str, float | int | None]:
    numeric = _numeric_series(series)
    if numeric is None:
        return {}
    values = numeric.dropna()
    if values.empty:
        return {statistic: None for statistic in AGGREGATE_STATISTICS}
    return {
        "count": int(values.count()),
        "mean": float(values.mean()),
        "std": float(values.std(ddof=1)) if len(values) > 1 else None,
        "min": float(values.min()),
        "q25": float(values.quantile(0.25)),
        "median": float(values.median()),
        "q75": float(values.quantile(0.75)),
        "max": float(values.max()),
        "sum": float(values.sum()),
    }


def _stats_comparison(
    actual: pd.Series,
    expected: pd.Series,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> dict[str, dict[str, Any]]:
    actual_stats = _aggregate_statistics(actual)
    expected_stats = _aggregate_statistics(expected)
    comparisons = {}
    for statistic in AGGREGATE_STATISTICS:
        actual_value = actual_stats.get(statistic)
        expected_value = expected_stats.get(statistic)
        difference = (
            actual_value - expected_value
            if actual_value is not None and expected_value is not None
            else None
        )
        if statistic == "count":
            passed = actual_value == expected_value
        elif actual_value is None or expected_value is None:
            passed = actual_value is expected_value
        else:
            passed = _close(actual_value, expected_value, absolute_tolerance, relative_tolerance)
        comparisons[statistic] = {
            "actual": actual_value,
            "expected": expected_value,
            "difference": difference,
            "passed": passed,
        }
    return comparisons


def _duplicate_key_info(series: pd.Series) -> tuple[int, list[str], set[str]]:
    keys = series.map(_key_value)
    duplicated = keys.notna() & keys.duplicated(keep=False)
    duplicate_rows = int(duplicated.sum())
    samples = sorted(set(keys[duplicated].dropna().tolist()))[:MAX_KEY_SAMPLES]
    unique_keys = set(keys[~duplicated].dropna().tolist())
    return duplicate_rows, samples, unique_keys


@dataclass
class ValidationResult:
    stage_name: str
    variable_name: str
    reference_path: Path | None
    passed: bool
    row_count_actual: int
    row_count_expected: int
    missing_columns: list[str] = field(default_factory=list)
    extra_columns: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    duplicate_columns_actual: list[str] = field(default_factory=list)
    duplicate_columns_expected: list[str] = field(default_factory=list)
    key_column: str | None = None
    null_key_count_actual: int = 0
    null_key_count_expected: int = 0
    duplicate_key_rows_actual: int = 0
    duplicate_key_rows_expected: int = 0
    duplicate_key_samples_actual: list[str] = field(default_factory=list)
    duplicate_key_samples_expected: list[str] = field(default_factory=list)
    unmatched_key_count_actual: int = 0
    unmatched_key_count_expected: int = 0
    unmatched_key_samples_actual: list[str] = field(default_factory=list)
    unmatched_key_samples_expected: list[str] = field(default_factory=list)
    compared_row_count: int = 0
    column_comparisons: dict[str, dict[str, Any]] = field(default_factory=dict)
    aggregate_comparisons: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    grouped_aggregate_comparisons: dict[str, dict[str, Any]] = field(default_factory=dict)

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [f"[{status}] {self.stage_name} :: {self.variable_name}"]
        lines.append(
            f"    rows: {self.row_count_actual} actual vs "
            f"{self.row_count_expected} expected; {self.compared_row_count} rows compared"
        )
        if self.key_column:
            lines.append(
                f"    key {self.key_column}: unmatched {self.unmatched_key_count_actual} actual/"
                f"{self.unmatched_key_count_expected} expected; duplicate rows "
                f"{self.duplicate_key_rows_actual} actual/{self.duplicate_key_rows_expected} expected; "
                f"null keys {self.null_key_count_actual} actual/{self.null_key_count_expected} expected"
            )
        if self.missing_columns:
            lines.append(f"    missing columns: {self.missing_columns}")
        if self.extra_columns:
            lines.append(f"    extra columns (warning): {self.extra_columns}")
        if self.duplicate_columns_actual or self.duplicate_columns_expected:
            lines.append(
                "    duplicate columns: "
                f"{self.duplicate_columns_actual} actual / {self.duplicate_columns_expected} expected"
            )
        failing_columns = [
            (name, comparison)
            for name, comparison in self.column_comparisons.items()
            if not comparison["passed"]
        ]
        if failing_columns:
            lines.append(f"    columns with value differences: {len(failing_columns)}")
            for name, comparison in failing_columns[:5]:
                lines.append(
                    f"      {name}: {comparison['mismatch_count']} mismatches "
                    f"({comparison['mismatch_rate']:.2%}); "
                    f"max_abs_diff={comparison['max_absolute_difference']}"
                )
        for note in self.notes:
            lines.append(f"    note: {note}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return _json_safe(data)


def _read_reference(path: Path, key_column: str | None) -> tuple[pd.DataFrame, list[str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        header = next(csv.reader(file), [])
    expected_header_keys = [_column_key(column) for column in header]
    duplicate_columns = sorted({
        column for column, key in zip(header, expected_header_keys)
        if expected_header_keys.count(key) > 1
    })
    dtype = None
    if key_column:
        for column in header:
            if _column_key(column) == _column_key(key_column):
                dtype = {column: "string"}
                break
    return pd.read_csv(path, dtype=dtype), duplicate_columns


def compare_dataframe(
    actual_df: pd.DataFrame,
    reference_csv_path: Path,
    stage_name: str,
    variable_name: str,
    numeric_tolerance: float = 1e-4,
    *,
    relative_tolerance: float = 1e-6,
    key_column: str | None = None,
) -> ValidationResult:
    """Compare schema, row identity, values, and numeric aggregates against a SAS CSV."""
    if (
        not math.isfinite(numeric_tolerance)
        or not math.isfinite(relative_tolerance)
        or numeric_tolerance < 0
        or relative_tolerance < 0
    ):
        raise ValueError("Numeric tolerances must be finite, non-negative numbers.")
    reference_csv_path = Path(reference_csv_path)
    if not reference_csv_path.exists():
        return ValidationResult(
            stage_name=stage_name,
            variable_name=variable_name,
            reference_path=reference_csv_path,
            passed=False,
            row_count_actual=len(actual_df),
            row_count_expected=-1,
            notes=[f"Reference file not found: {reference_csv_path}"],
        )

    actual_columns, duplicate_columns_actual = _normalized_columns(actual_df.columns)
    selected_key = key_column
    if selected_key is None and "provider_id" in actual_columns:
        selected_key = "provider_id"
    expected_df, duplicate_columns_expected = _read_reference(reference_csv_path, selected_key)
    expected_columns, parsed_duplicate_columns = _normalized_columns(expected_df.columns)
    duplicate_columns_expected = sorted(set(duplicate_columns_expected + parsed_duplicate_columns))

    missing_columns = sorted(set(expected_columns) - set(actual_columns))
    extra_columns = sorted(set(actual_columns) - set(expected_columns))
    row_count_actual = len(actual_df)
    row_count_expected = len(expected_df)
    notes: list[str] = []
    if extra_columns:
        notes.append("Extra columns are reported as warnings and do not fail validation.")
    if duplicate_columns_actual or duplicate_columns_expected:
        notes.append("Duplicate normalized column names prevent unambiguous comparison of those columns.")

    ambiguous_actual = _duplicate_column_keys(actual_df.columns)
    ambiguous_expected = _duplicate_column_keys(expected_df.columns)
    ambiguous_expected.update(_column_key(name) for name in duplicate_columns_expected)
    if (
        selected_key
        and _column_key(selected_key) in actual_columns
        and _column_key(selected_key) in expected_columns
        and _column_key(selected_key) not in ambiguous_actual
        and _column_key(selected_key) not in ambiguous_expected
    ):
        key = _column_key(selected_key)
        actual_key_series = actual_df[actual_columns[key]]
        expected_key_series = expected_df[expected_columns[key]]
        actual_null_keys = int(actual_key_series.isna().sum())
        expected_null_keys = int(expected_key_series.isna().sum())
        duplicate_rows_actual, duplicate_samples_actual, actual_keys = _duplicate_key_info(actual_key_series)
        duplicate_rows_expected, duplicate_samples_expected, expected_keys = _duplicate_key_info(expected_key_series)
        unmatched_actual = sorted(actual_keys - expected_keys)
        unmatched_expected = sorted(expected_keys - actual_keys)
        common_keys = sorted(actual_keys & expected_keys)
        actual_key_values = actual_key_series.map(_key_value)
        expected_key_values = expected_key_series.map(_key_value)
        actual_duplicate_keys = set(actual_key_values[actual_key_values.duplicated(keep=False)].dropna())
        expected_duplicate_keys = set(expected_key_values[expected_key_values.duplicated(keep=False)].dropna())
        actual_index = {
            value: index for index, value in enumerate(actual_key_values.tolist())
            if value is not None and value not in actual_duplicate_keys
        }
        expected_index = {
            value: index for index, value in enumerate(expected_key_values.tolist())
            if value is not None and value not in expected_duplicate_keys
        }
        row_pairs = [(actual_index[value], expected_index[value], value) for value in common_keys]
        result_key = str(actual_columns[key])
    else:
        actual_null_keys = expected_null_keys = 0
        duplicate_rows_actual = duplicate_rows_expected = 0
        duplicate_samples_actual = duplicate_samples_expected = []
        unmatched_actual = unmatched_expected = []
        row_pairs = [
            (index, index, str(index))
            for index in range(min(row_count_actual, row_count_expected))
        ]
        result_key = None
        if selected_key and (
            _column_key(selected_key) in ambiguous_actual
            or _column_key(selected_key) in ambiguous_expected
        ):
            notes.append(f"Key column '{selected_key}' is duplicated; rows compared by position.")
        elif selected_key:
            notes.append(f"Requested key column '{selected_key}' is not present in both tables; rows compared by position.")
        else:
            notes.append("No shared provider_id key found; rows compared by position.")

    if len(row_pairs) < min(row_count_actual, row_count_expected):
        notes.append("Only uniquely keyed rows present on both sides are compared; null and duplicate-key rows are excluded.")

    column_comparisons: dict[str, dict[str, Any]] = {}
    numeric_columns: list[tuple[str, Any, Any]] = []
    for key in sorted(set(actual_columns) & set(expected_columns)):
        if key in ambiguous_actual or key in ambiguous_expected:
            continue
        if result_key and key == _column_key(result_key):
            continue
        actual_name = actual_columns[key]
        expected_name = expected_columns[key]
        actual_series = actual_df[actual_name]
        expected_series = expected_df[expected_name]
        actual_numeric = _numeric_series(actual_series)
        expected_numeric = _numeric_series(expected_series)
        if actual_numeric is not None and expected_numeric is not None:
            numeric_columns.append((key, actual_name, expected_name))

        mismatch_count = 0
        null_mismatch_count = 0
        maximum_difference = 0.0
        maximum_difference_key = None
        samples = []
        for actual_row, expected_row, matched_key in row_pairs:
            actual_value = actual_series.iloc[actual_row]
            expected_value = expected_series.iloc[expected_row]
            actual_missing = _is_missing(actual_value)
            expected_missing = _is_missing(expected_value)
            mismatch = False
            difference = None
            if actual_missing != expected_missing:
                mismatch = True
                null_mismatch_count += 1
            elif not actual_missing and actual_numeric is not None and expected_numeric is not None:
                actual_value = float(actual_numeric.iloc[actual_row])
                expected_value = float(expected_numeric.iloc[expected_row])
                difference = abs(actual_value - expected_value)
                if difference >= maximum_difference:
                    maximum_difference = difference
                    maximum_difference_key = matched_key
                mismatch = not _close(actual_value, expected_value, numeric_tolerance, relative_tolerance)
            elif not actual_missing:
                mismatch = str(actual_value).strip() != str(expected_value).strip()
            if mismatch:
                mismatch_count += 1
                if len(samples) < MAX_MISMATCH_SAMPLES:
                    samples.append({
                        "key": matched_key,
                        "actual": None if actual_missing else _json_safe(actual_value),
                        "expected": None if expected_missing else _json_safe(expected_value),
                        "absolute_difference": difference,
                    })

        compared_count = len(row_pairs)
        column_comparisons[str(actual_name)] = {
            "kind": "numeric" if actual_numeric is not None and expected_numeric is not None else "exact",
            "compared_count": compared_count,
            "mismatch_count": mismatch_count,
            "mismatch_rate": mismatch_count / compared_count if compared_count else 0.0,
            "null_mismatch_count": null_mismatch_count,
            "max_absolute_difference": maximum_difference if maximum_difference_key is not None else None,
            "max_difference_key": maximum_difference_key,
            "samples": samples,
            "passed": mismatch_count == 0,
        }

    aggregate_comparisons = {}
    for key, actual_name, expected_name in numeric_columns:
        aggregate_comparisons[str(actual_name)] = _stats_comparison(
            actual_df[actual_name], expected_df[expected_name], numeric_tolerance, relative_tolerance
        )

    grouped_aggregate_comparisons: dict[str, Any] = {}
    for group_key in GROUP_COLUMNS:
        if group_key not in actual_columns or group_key not in expected_columns:
            continue
        actual_group_name = actual_columns[group_key]
        expected_group_name = expected_columns[group_key]
        actual_groups = {
            _key_value(group_value): group
            for group_value, group in actual_df.groupby(actual_group_name, dropna=False, sort=True)
        }
        expected_groups = {
            _key_value(group_value): group
            for group_value, group in expected_df.groupby(expected_group_name, dropna=False, sort=True)
        }
        labels = sorted(set(actual_groups) | set(expected_groups), key=lambda value: (value is None, value or ""))
        truncated = len(labels) > MAX_GROUPS
        group_details = {}
        for label in labels[:MAX_GROUPS]:
            group_details[str(label)] = {
                "actual_rows": len(actual_groups[label]) if label in actual_groups else 0,
                "expected_rows": len(expected_groups[label]) if label in expected_groups else 0,
                "columns": {},
            }
            for key, actual_name, expected_name in numeric_columns:
                if label not in actual_groups or label not in expected_groups:
                    group_details[str(label)]["columns"][str(actual_name)] = {
                        "available_on_both_sides": False
                    }
                    continue
                group_details[str(label)]["columns"][str(actual_name)] = _stats_comparison(
                    actual_groups[label][actual_name],
                    expected_groups[label][expected_name],
                    numeric_tolerance,
                    relative_tolerance,
                )
        grouped_aggregate_comparisons[str(actual_group_name)] = {
            "groups": group_details,
            "truncated": truncated,
            "group_limit": MAX_GROUPS,
        }

    failed_columns = any(not comparison["passed"] for comparison in column_comparisons.values())
    passed = (
        row_count_actual == row_count_expected
        and not missing_columns
        and not duplicate_columns_actual
        and not duplicate_columns_expected
        and actual_null_keys == 0
        and expected_null_keys == 0
        and duplicate_rows_actual == 0
        and duplicate_rows_expected == 0
        and not unmatched_actual
        and not unmatched_expected
        and not failed_columns
    )
    if row_count_actual != row_count_expected:
        notes.append("Row counts differ.")
    if missing_columns:
        notes.append(f"Missing columns: {missing_columns}")
    if unmatched_actual or unmatched_expected:
        notes.append(
            f"Unmatched keys: {len(unmatched_actual)} actual-only, {len(unmatched_expected)} expected-only."
        )
    if duplicate_rows_actual or duplicate_rows_expected:
        notes.append(
            f"Duplicate key rows: {duplicate_rows_actual} actual, {duplicate_rows_expected} expected."
        )
    if actual_null_keys or expected_null_keys:
        notes.append(f"Null key rows: {actual_null_keys} actual, {expected_null_keys} expected.")
    if failed_columns:
        notes.append(f"{sum(not item['passed'] for item in column_comparisons.values())} columns differ beyond tolerance.")

    return ValidationResult(
        stage_name=stage_name,
        variable_name=variable_name,
        reference_path=reference_csv_path,
        passed=passed,
        row_count_actual=row_count_actual,
        row_count_expected=row_count_expected,
        missing_columns=[str(expected_columns[key]) for key in missing_columns],
        extra_columns=[str(actual_columns[key]) for key in extra_columns],
        notes=notes,
        duplicate_columns_actual=duplicate_columns_actual,
        duplicate_columns_expected=duplicate_columns_expected,
        key_column=result_key,
        null_key_count_actual=actual_null_keys,
        null_key_count_expected=expected_null_keys,
        duplicate_key_rows_actual=duplicate_rows_actual,
        duplicate_key_rows_expected=duplicate_rows_expected,
        duplicate_key_samples_actual=duplicate_samples_actual,
        duplicate_key_samples_expected=duplicate_samples_expected,
        unmatched_key_count_actual=len(unmatched_actual),
        unmatched_key_count_expected=len(unmatched_expected),
        unmatched_key_samples_actual=unmatched_actual[:MAX_KEY_SAMPLES],
        unmatched_key_samples_expected=unmatched_expected[:MAX_KEY_SAMPLES],
        compared_row_count=len(row_pairs),
        column_comparisons=column_comparisons,
        aggregate_comparisons=aggregate_comparisons,
        grouped_aggregate_comparisons=grouped_aggregate_comparisons,
    )
