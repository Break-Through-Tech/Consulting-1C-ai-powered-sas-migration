"""
Accuracy report: one place that answers "how close is the Python output to SAS?"

Fills three gaps in the per-table PASS/FAIL validation:
  * coverage  - every SAS reference CSV must have been compared; a reference
                with no matching Python output is reported (and should fail
                the run) instead of being silently skipped
  * accuracy  - the share of compared values that match, per table and overall
  * stars     - agreement on the final star rating, with a SAS-vs-Python
                confusion table

It reads the ValidationResult objects the pipeline already produces, plus the
saved STAR output, so it never re-runs or re-implements the comparison.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

STAR_FILE = "STAR_2025JUL.csv"
KEY = "provider_id"


def latest_results_by_reference(all_results: dict[str, dict]) -> dict[str, Any]:
    """
    Map each reference CSV name to its ValidationResult. A table carried
    forward through later stages is validated more than once; the last
    (most downstream) comparison wins.
    """
    latest = {}
    for stage_result in all_results.values():
        for result in stage_result.values():
            if result.reference_path is not None:
                latest[Path(result.reference_path).name] = result
    return latest


def unvalidated_references(all_results: dict[str, dict], reference_dir: Path) -> list[str]:
    """Reference CSVs that no stage produced a matching output for."""
    validated = {name.lower() for name in latest_results_by_reference(all_results)}
    return sorted(p.name for p in Path(reference_dir).glob("*.csv") if p.name.lower() not in validated)


def table_accuracy(result) -> dict[str, Any]:
    """Share of compared cells that match within the validator's tolerances."""
    compared = sum(c["compared_count"] for c in result.column_comparisons.values())
    mismatched = sum(c["mismatch_count"] for c in result.column_comparisons.values())
    worst = sorted(
        ((name, c) for name, c in result.column_comparisons.items() if c["mismatch_count"]),
        key=lambda item: item[1]["mismatch_count"], reverse=True,
    )
    return {
        "passed": bool(result.passed),
        "rows_expected": result.row_count_expected,
        "rows_compared": result.compared_row_count,
        "values_compared": compared,
        "values_mismatched": mismatched,
        "accuracy": (compared - mismatched) / compared if compared else None,
        "missing_columns": list(result.missing_columns),
        "worst_columns": {name: c["mismatch_count"] for name, c in worst[:5]},
    }


def _read_keyed(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    df[KEY] = df[KEY].str.strip().str.zfill(6)
    return df


def star_agreement(actual_dir: Path, reference_dir: Path) -> dict[str, Any] | None:
    """Compare final star ratings hospital by hospital; None if either file is missing."""
    actual_path, reference_path = Path(actual_dir) / STAR_FILE, Path(reference_dir) / STAR_FILE
    if not actual_path.exists() or not reference_path.exists():
        return None
    actual, expected = _read_keyed(actual_path), _read_keyed(reference_path)
    if "star" not in actual or "star" not in expected:
        return None

    def as_label(series: pd.Series) -> pd.Series:
        stars = pd.to_numeric(series, errors="coerce")
        return stars.map(lambda s: "none" if pd.isna(s) else str(int(s)))

    merged = expected[[KEY, "star"]].merge(actual[[KEY, "star"]], on=KEY, how="outer",
                                           suffixes=("_sas", "_python"), indicator=True)
    sas, py = as_label(merged["star_sas"]), as_label(merged["star_python"])
    both = merged["_merge"] == "both"
    rated = both & (sas != "none")
    labels = ["1", "2", "3", "4", "5", "none"]
    confusion = pd.crosstab(sas[both], py[both]).reindex(index=labels, columns=labels, fill_value=0)
    differ = both & (sas != py)
    return {
        "hospitals_compared": int(both.sum()),
        "hospitals_missing_from_python": int((merged["_merge"] == "left_only").sum()),
        "hospitals_extra_in_python": int((merged["_merge"] == "right_only").sum()),
        "sas_rated": int(rated.sum()),
        "rated_matching": int((rated & (sas == py)).sum()),
        "agreement_rated": float((rated & (sas == py)).sum() / rated.sum()) if rated.sum() else None,
        "agreement_all": float((both & (sas == py)).sum() / both.sum()) if both.sum() else None,
        "off_by_one": int((differ & (sas != "none") & (py != "none")
                           & ((pd.to_numeric(sas, errors="coerce") - pd.to_numeric(py, errors="coerce")).abs() == 1)).sum()),
        "confusion": {row: {col: int(confusion.loc[row, col]) for col in labels} for row in labels},
        "sample_mismatches": merged.loc[differ, [KEY, "star_sas", "star_python"]].head(10)
                                   .fillna("none").to_dict("records"),
    }


def build_accuracy_report(all_results: dict[str, dict], reference_dir: Path, actual_dir: Path) -> dict[str, Any]:
    latest = latest_results_by_reference(all_results)
    tables = {name: table_accuracy(result) for name, result in sorted(latest.items())}
    compared = sum(t["values_compared"] for t in tables.values())
    mismatched = sum(t["values_mismatched"] for t in tables.values())
    unvalidated = unvalidated_references(all_results, reference_dir)
    total_refs = len(list(Path(reference_dir).glob("*.csv")))
    crashed = sorted(stage for stage, res in all_results.items() if "__execution__" in res)
    return {
        "coverage": {
            "references": total_refs,
            "validated": total_refs - len(unvalidated),
            "unvalidated": unvalidated,
        },
        "crashed_stages": crashed,
        "overall_value_accuracy": (compared - mismatched) / compared if compared else None,
        "values_compared": compared,
        "values_mismatched": mismatched,
        "tables": tables,
        # only trust the saved STAR file if it was produced (and validated) in this run
        "stars": star_agreement(actual_dir, reference_dir)
                 if STAR_FILE.lower() in {n.lower() for n in latest} else None,
        "complete": not unvalidated and not crashed,
    }


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4%}" if 0.9999 < value < 1 else f"{value:.2%}"


def format_accuracy_report(report: dict[str, Any]) -> str:
    cov = report["coverage"]
    lines = ["", "=" * 64, "ACCURACY REPORT: Python vs SAS", "=" * 64]
    status = "COMPLETE" if report["complete"] else "INCOMPLETE"
    lines.append(f"Coverage: {cov['validated']}/{cov['references']} SAS reference files compared  [{status}]")
    for name in cov["unvalidated"]:
        lines.append(f"  NOT VALIDATED: {name} (no Python output with a matching name)")
    for stage in report["crashed_stages"]:
        lines.append(f"  CRASHED: {stage}")
    lines.append(f"Overall value accuracy: {_pct(report['overall_value_accuracy'])} "
                 f"({report['values_compared'] - report['values_mismatched']:,}/{report['values_compared']:,} values)")
    lines.append("")
    lines.append(f"  {'table':<36}{'accuracy':>10}{'mismatched':>12}  status")
    for name, t in report["tables"].items():
        lines.append(f"  {name:<36}{_pct(t['accuracy']):>10}{t['values_mismatched']:>12,}  "
                     f"{'PASS' if t['passed'] else 'FAIL'}")
        if t["missing_columns"]:
            lines.append(f"      missing columns: {t['missing_columns']}")
        if t["worst_columns"]:
            lines.append(f"      most mismatches: {t['worst_columns']}")

    stars = report["stars"]
    lines.append("")
    if stars is None:
        lines.append("Star ratings: not compared (STAR output missing)")
    else:
        lines.append(f"Star ratings: {stars['rated_matching']:,}/{stars['sas_rated']:,} SAS-rated hospitals match "
                     f"({_pct(stars['agreement_rated'])}); all hospitals incl. unrated: {_pct(stars['agreement_all'])}")
        if stars["hospitals_missing_from_python"] or stars["hospitals_extra_in_python"]:
            lines.append(f"  hospitals missing from Python: {stars['hospitals_missing_from_python']}, "
                         f"extra in Python: {stars['hospitals_extra_in_python']}")
        if stars["agreement_all"] != 1.0:
            lines.append(f"  off by exactly one star: {stars['off_by_one']}")
            labels = list(stars["confusion"])
            lines.append("  SAS (rows) vs Python (columns):")
            lines.append("  " + " " * 6 + "".join(f"{c:>7}" for c in labels))
            for row in labels:
                lines.append("  " + f"{row:>6}" + "".join(f"{stars['confusion'][row][c]:>7}" for c in labels))
    lines.append("=" * 64)
    return "\n".join(lines)


def save_accuracy_report(report: dict[str, Any], out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "accuracy_report.json").write_text(json.dumps(report, indent=2))
    (out_dir / "accuracy_report.txt").write_text(format_accuracy_report(report) + "\n")
