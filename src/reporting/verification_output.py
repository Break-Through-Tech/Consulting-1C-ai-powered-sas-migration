"""
Verification output: a fixed, easy-to-find folder with the result of the
latest SAS-vs-Python verification, plus a running history of every run.

    verification_output/
        accuracy_history.csv          one row per pipeline attempt, newest last
        latest/
            verification_report.md    readable summary with a PASS/FAIL verdict
            table_accuracy.csv        % of values matching, per SAS output table
            column_accuracy.csv       mismatch count and rate, per column
            star_confusion.csv        SAS star (rows) vs Python star (columns)
            accuracy_report.json      the full machine-readable report

Built from the accuracy report and ValidationResults the pipeline already has,
so it adds no comparison logic of its own.
"""
from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .accuracy_report import format_accuracy_report, latest_results_by_reference

HISTORY_FIELDS = [
    "timestamp", "run", "attempt", "translation", "verdict", "coverage",
    "overall_value_accuracy", "values_compared", "values_mismatched",
    "star_agreement_rated", "stars_matching", "stars_rated",
    "checks_passed", "checks_failed", "failing_tables",
]


def _pct(value: float | None) -> str:
    return "" if value is None else f"{value * 100:.4f}"


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _verdict(report: dict, checks_failed: int) -> str:
    return "PASS" if report["complete"] and checks_failed == 0 else "FAIL"


def _markdown(report: dict, info: dict) -> str:
    cov, stars = report["coverage"], report["stars"]
    lines = [
        "# SAS to Python Verification Report",
        "",
        f"**Verdict: {info['verdict']}**",
        "",
        f"- Run: `{info['run']}` (attempt {info['attempt']}), {info['timestamp']}",
        f"- Translation: {info['translation']}",
        f"- Validation checks: {info['checks_passed']} passed, {info['checks_failed']} failed",
        f"- Coverage: {cov['validated']}/{cov['references']} SAS output files compared",
        f"- Overall value accuracy: **{_pct(report['overall_value_accuracy']) or 'n/a'}%** "
        f"({report['values_compared'] - report['values_mismatched']:,} of {report['values_compared']:,} values)",
    ]
    if stars:
        lines.append(f"- Star rating agreement: **{_pct(stars['agreement_rated'])}%** "
                     f"({stars['rated_matching']:,} of {stars['sas_rated']:,} SAS-rated hospitals)")
    else:
        lines.append("- Star rating agreement: not compared (no star output from this run)")
    for name in cov["unvalidated"]:
        lines.append(f"- NOT VALIDATED: `{name}` had no matching Python output")
    for stage in report["crashed_stages"]:
        lines.append(f"- CRASHED: `{stage}`")

    tokens = info.get("token_usage")
    if tokens is not None:
        if tokens["api_calls"]:
            t = tokens["totals"]
            line = (f"- Token usage: **{t['total']:,} tokens** over {tokens['api_calls']} API calls "
                    f"({t['prompt']:,} prompt, {t['output']:,} output, {t['thinking']:,} thinking)")
            if tokens.get("estimated_cost_usd") is not None:
                line += f", est. ${tokens['estimated_cost_usd']:.4f}"
            lines.append(line)
        else:
            lines.append("- Token usage: 0 (translation skipped, no API calls)")

    lines += ["", "## Accuracy by table", "",
              "| SAS output | Accuracy | Values compared | Mismatched | Status |",
              "|---|---:|---:|---:|---|"]
    for name, t in report["tables"].items():
        acc = f"{_pct(t['accuracy'])}%" if t["accuracy"] is not None else "n/a (empty)"
        lines.append(f"| {name} | {acc} | {t['values_compared']:,} | {t['values_mismatched']:,} | "
                     f"{'PASS' if t['passed'] else 'FAIL'} |")
        if t["missing_columns"]:
            lines.append(f"| ↳ missing columns: {', '.join(t['missing_columns'])} | | | | |")

    if stars and stars["agreement_all"] != 1.0:
        labels = list(stars["confusion"])
        lines += ["", "## Star ratings: SAS (rows) vs Python (columns)", "",
                  "| SAS \\ Python | " + " | ".join(labels) + " |",
                  "|---|" + "---:|" * len(labels)]
        for row in labels:
            lines.append(f"| {row} | " + " | ".join(str(stars["confusion"][row][c]) for c in labels) + " |")
        lines.append(f"\nOff by exactly one star: {stars['off_by_one']}")

    lines += ["", "## Console summary", "", "```", format_accuracy_report(report).strip("\n="), "```", ""]
    return "\n".join(lines)


def write_verification_output(
    report: dict[str, Any],
    all_results: dict[str, dict],
    out_dir: Path,
    *,
    run: str,
    attempt: int,
    translation: str,
    checks_passed: int,
    checks_failed: int,
    token_usage: dict[str, Any] | None = None,
) -> Path:
    """Write latest/ and append to accuracy_history.csv. Returns the report path."""
    out_dir = Path(out_dir)
    latest = out_dir / "latest"
    if latest.exists():
        shutil.rmtree(latest)  # never leave files from an older run mixed in
    latest.mkdir(parents=True)

    stars = report["stars"]
    failing = [name for name, t in report["tables"].items() if not t["passed"]]
    info = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "run": run,
        "attempt": attempt,
        "translation": translation,
        "verdict": _verdict(report, checks_failed),
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
        "token_usage": token_usage,
    }

    _write_csv(latest / "table_accuracy.csv",
               ["table", "status", "accuracy_pct", "values_compared", "values_mismatched",
                "rows_expected", "rows_compared", "missing_columns"],
               [{"table": name, "status": "PASS" if t["passed"] else "FAIL",
                 "accuracy_pct": _pct(t["accuracy"]), "values_compared": t["values_compared"],
                 "values_mismatched": t["values_mismatched"], "rows_expected": t["rows_expected"],
                 "rows_compared": t["rows_compared"], "missing_columns": ";".join(t["missing_columns"])}
                for name, t in report["tables"].items()])

    column_rows = []
    for name, result in sorted(latest_results_by_reference(all_results).items()):
        for column, c in result.column_comparisons.items():
            column_rows.append({
                "table": name, "column": column, "kind": c["kind"],
                "compared": c["compared_count"], "mismatched": c["mismatch_count"],
                "accuracy_pct": _pct(1 - c["mismatch_rate"]) if c["compared_count"] else "",
                "max_abs_difference": "" if c["max_absolute_difference"] is None else c["max_absolute_difference"],
            })
    _write_csv(latest / "column_accuracy.csv",
               ["table", "column", "kind", "compared", "mismatched", "accuracy_pct", "max_abs_difference"],
               column_rows)

    if stars:
        labels = list(stars["confusion"])
        _write_csv(latest / "star_confusion.csv", ["sas_star"] + [f"python_{c}" for c in labels],
                   [{"sas_star": r, **{f"python_{c}": stars["confusion"][r][c] for c in labels}}
                    for r in labels])

    (latest / "accuracy_report.json").write_text(json.dumps({**info, **report}, indent=2))
    report_path = latest / "verification_report.md"
    report_path.write_text(_markdown(report, info), encoding="utf-8")

    history = out_dir / "accuracy_history.csv"
    new_file = not history.exists()
    with history.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow({
            **{k: info[k] for k in ("timestamp", "run", "attempt", "translation", "verdict",
                                    "checks_passed", "checks_failed")},
            "coverage": f"{report['coverage']['validated']}/{report['coverage']['references']}",
            "overall_value_accuracy": _pct(report["overall_value_accuracy"]),
            "values_compared": report["values_compared"],
            "values_mismatched": report["values_mismatched"],
            "star_agreement_rated": _pct(stars["agreement_rated"]) if stars else "",
            "stars_matching": stars["rated_matching"] if stars else "",
            "stars_rated": stars["sas_rated"] if stars else "",
            "failing_tables": ";".join(failing),
        })
    return report_path
