"""
Run time and cost savings summary for one pipeline attempt.

Combines the measured run times (SAS log vs. Python stages, plus how long
each script took to translate) with the cost assumptions to estimate the
annual savings of each converted script, then writes:

    verification_output/latest/runtime.csv / runtime.json
    verification_output/latest/cost_savings.csv / cost_savings.json
    verification_output/runtime_history.csv     one row per attempt
    + "Run time" and "Estimated cost savings" sections in verification_report.md
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .cost_savings import count_code_lines, estimate_savings, format_savings, load_assumptions, save_savings
from .runtime import runtime_table, sas_runtime_by_program, time_python_stages
from .token_usage import TokenCall, TokenUsageTracker

RUNTIME_FIELDS = ["script", "sas_file", "python_file", "translation_seconds",
                  "sas_runtime_seconds", "python_runtime_seconds", "speedup", "note"]
HISTORY_FIELDS = ["timestamp", "run", "attempt", "translation", "translation_seconds",
                  "validation_seconds", "attempt_seconds", "sas_runtime_seconds",
                  "python_runtime_seconds", "annual_savings", "first_year_net_savings",
                  "payback_months", "currency"]


def _fmt(seconds: float | None, digits: int = 2) -> str:
    return "n/a" if seconds is None else f"{seconds:.{digits}f}s"


def _sum(values) -> float | None:
    values = [v for v in values if v is not None]
    return round(sum(values), 4) if values else None


def build_run_summary(
    *,
    sas_files_dir: Path,
    sas_log: Path,
    translated_dir: Path,
    assumptions_path: Path,
    usage: Any,
    phase_seconds: dict[str, float | None],
    last_translation_path: Path | None = None,
) -> dict[str, Any]:
    sas_files = sorted(p.name for p in Path(sas_files_dir).glob("*.sas"))
    sas_seconds = (sas_runtime_by_program(sas_log, sas_files) if Path(sas_log).exists()
                   else {f: None for f in sas_files})
    python_timings = time_python_stages(translated_dir)

    translation_seconds = {
        c.label[len("translate "):]: c.seconds
        for c in getattr(usage, "calls", []) if c.label.startswith("translate ")
    }
    tokens = token_source(usage, last_translation_path)

    rows = runtime_table(sas_seconds, python_timings, translation_seconds)
    totals = {
        "translation_seconds": _sum(r["translation_seconds"] for r in rows),
        "sas_runtime_seconds": _sum(r["sas_runtime_seconds"] for r in rows),
        "python_runtime_seconds": _sum(r["python_runtime_seconds"] for r in rows),
    }

    savings = None
    savings_error = None
    try:
        scripts = [{**r, "lines": count_code_lines(Path(sas_files_dir) / r["sas_file"]),
                    "tokens_used": tokens["by_script"].get(r["sas_file"])} for r in rows]
        savings = estimate_savings(scripts, load_assumptions(assumptions_path), tokens["cost_by_script"])
    except (OSError, ValueError) as exc:
        savings_error = str(exc)

    return {"runtime": rows, "runtime_totals": totals, "phases": phase_seconds,
            "savings": savings, "savings_error": savings_error, "tokens": tokens}


def token_source(usage: Any, last_translation_path: Path | None) -> dict[str, Any]:
    """
    Tokens used per SAS script, from this run's translation if there was one,
    otherwise from the last saved translation run. Costs are priced with the
    current GEMINI_*_PRICE_PER_M values; with no prices set they count as $0.
    """
    calls, source, model = list(getattr(usage, "calls", [])), "this run", getattr(usage, "model", "")
    if not any(c.label.startswith("translate ") for c in calls):
        calls = []
        if last_translation_path is not None and Path(last_translation_path).exists():
            saved = json.loads(Path(last_translation_path).read_text(encoding="utf-8"))
            calls = [TokenCall(**c) for c in saved.get("calls", [])]
            model = saved.get("model", "")
            source = f"last translation run ({saved.get('run', '?')}, {saved.get('timestamp', '?')})"
        else:
            source = "not measured: no translation run yet"

    priced = TokenUsageTracker(model=model, calls=calls)
    priced_ok = priced.estimated_cost() is not None
    by_script, cost_by_script, other = {}, {}, 0
    for c in calls:
        if c.label.startswith("translate "):
            name = c.label[len("translate "):]
            by_script[name] = c.total
            if priced_ok:
                cost_by_script[name] = priced.call_cost(c)
        else:
            other += c.total

    if not calls:
        note = "Tokens: not measured yet (run once with SKIP_TRANSLATION_FOR_TESTING = False)."
    else:
        note = f"Tokens from {source}."
        if other:
            note += f" Another {other:,} tokens went to generating the README (not in any script)."
        if not priced_ok:
            note += " No token prices set in .env, so AI cost counts as $0 (e.g. free tier)."
    return {"source": source, "model": model, "calls": calls, "by_script": by_script,
            "cost_by_script": cost_by_script, "other_tokens": other, "priced": priced_ok, "note": note}


def format_runtime(summary: dict[str, Any]) -> str:
    lines = ["", "=" * 64, "RUN TIME: SAS vs Python (one run of each script)", "=" * 64,
             f"  {'script':<40}{'convert':>9}{'SAS':>8}{'Python':>9}"]
    for r in summary["runtime"]:
        name = r["script"] if len(r["script"]) <= 39 else r["script"][:36] + "..."
        lines.append(f"  {name:<40}{_fmt(r['translation_seconds'], 1):>9}"
                     f"{_fmt(r['sas_runtime_seconds']):>8}{_fmt(r['python_runtime_seconds']):>9}")
    t = summary["runtime_totals"]
    lines.append(f"  {'TOTAL':<40}{_fmt(t['translation_seconds'], 1):>9}"
                 f"{_fmt(t['sas_runtime_seconds']):>8}{_fmt(t['python_runtime_seconds']):>9}")
    p = summary["phases"]
    lines.append(f"Attempt phases: translation {_fmt(p.get('translation_seconds'), 1)}, "
                 f"validation {_fmt(p.get('validation_seconds'), 1)}, total {_fmt(p.get('attempt_seconds'), 1)}")
    lines.append("=" * 64)
    return "\n".join(lines)


def _markdown(summary: dict[str, Any]) -> str:
    p, t = summary["phases"], summary["runtime_totals"]
    lines = ["", "## Run time", "",
             f"- Conversion (AI translation) time: {_fmt(t['translation_seconds'], 1)}"
             + ("" if t["translation_seconds"] is not None else " (translation skipped this run)"),
             f"- This attempt: translation {_fmt(p.get('translation_seconds'), 1)}, "
             f"validation {_fmt(p.get('validation_seconds'), 1)}, total {_fmt(p.get('attempt_seconds'), 1)}",
             f"- One run of all scripts: SAS {_fmt(t['sas_runtime_seconds'])} (from the SAS log), "
             f"Python {_fmt(t['python_runtime_seconds'])}",
             "", "| Script | Conversion time | SAS run time | Python run time | Note |",
             "|---|---:|---:|---:|---|"]
    for r in summary["runtime"]:
        lines.append(f"| {r['script']} | {_fmt(r['translation_seconds'], 1)} | "
                     f"{_fmt(r['sas_runtime_seconds'])} | {_fmt(r['python_runtime_seconds'])} | {r['note']} |")

    lines += ["", "## Estimated cost savings (per year)", ""]
    s = summary["savings"]
    tokens = summary.get("tokens") or {}
    if s is None:
        lines.append(f"Not calculated: {summary['savings_error']}")
        return "\n".join(lines) + "\n"
    c, tot = s["currency"], s["totals"]
    lines += [
        "> Estimates use the **placeholder assumptions** in `config/cost_assumptions.json`. "
        "Replace them with real figures before sharing. Licence savings only happen if the "
        "SAS licence is reduced or retired.",
        "",
        f"- Annual savings, all scripts: **{c} {tot['annual_savings']:,.2f}** "
        f"(licence {tot['license_savings']:,.2f}, maintenance {tot['maintenance_savings']:,.2f}, "
        f"compute {tot['compute_savings']:,.4f})",
        "- AI conversion cost (translation tokens only, no review labor): "
        + (f"{c} {tot['ai_conversion_cost']:,.4f} for {_tok(tot['tokens_used'])} tokens"
           if tot["tokens_used"] is not None else "not measured yet")
        + f"; first-year net: **{c} {tot['first_year_net_savings']:,.2f}**"
        + _payback_text(tot["payback_months"]),
        f"- {tokens.get('note', '')}",
        "", "| Script | SAS cost/yr | Python cost/yr | Savings/yr | Tokens used | AI conversion cost | Year-1 net | Payback (months) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in s["scripts"]:
        payback = "n/a" if r["payback_months"] is None else r["payback_months"]
        lines.append(f"| {r['script']} | {r['sas_annual_cost']:,.2f} | {r['python_annual_cost']:,.2f} | "
                     f"{r['annual_savings']:,.2f} | {_tok(r['tokens_used'])} | {r['ai_conversion_cost']:,.4f} | "
                     f"{r['first_year_net_savings']:,.2f} | {payback} |")
    return "\n".join(lines) + "\n"


def _payback_text(months) -> str:
    if months is None:
        return ""
    return "; payback immediate (no upfront cost)" if months == 0 else f"; payback {months} months"


def _tok(value) -> str:
    return "n/a" if value is None else f"{value:,}"


def write_run_summary(summary: dict[str, Any], latest_dir: Path, history_path: Path, *,
                      run: str, attempt: int, translation: str,
                      last_translation_path: Path | None = None) -> None:
    latest_dir = Path(latest_dir)
    latest_dir.mkdir(parents=True, exist_ok=True)

    # remember this run's per-script tokens so runs that skip translation can still report them
    tokens = summary.get("tokens") or {}
    if last_translation_path is not None and tokens.get("source") == "this run":
        Path(last_translation_path).write_text(json.dumps({
            "timestamp": datetime.now().isoformat(timespec="seconds"), "run": run, "attempt": attempt,
            "model": tokens.get("model", ""),
            "calls": [{k: getattr(c, k) for k in ("label", "prompt", "output", "thinking", "cached",
                                                   "total", "reported", "seconds")} for c in tokens["calls"]],
        }, indent=2))
    (latest_dir / "runtime.json").write_text(json.dumps(
        {k: summary[k] for k in ("runtime", "runtime_totals", "phases")}, indent=2))
    with (latest_dir / "runtime.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RUNTIME_FIELDS)
        writer.writeheader()
        writer.writerows(summary["runtime"])
    if summary["savings"] is not None:
        save_savings(summary["savings"], latest_dir)

    report = latest_dir / "verification_report.md"
    if report.exists():
        with report.open("a", encoding="utf-8") as f:
            f.write(_markdown(summary))

    history_path = Path(history_path)
    new_file = not history_path.exists()
    s = summary["savings"]
    with history_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "run": run, "attempt": attempt, "translation": translation,
            **{k: summary["phases"].get(k) for k in ("translation_seconds", "validation_seconds", "attempt_seconds")},
            "sas_runtime_seconds": summary["runtime_totals"]["sas_runtime_seconds"],
            "python_runtime_seconds": summary["runtime_totals"]["python_runtime_seconds"],
            "annual_savings": s["totals"]["annual_savings"] if s else "",
            "first_year_net_savings": s["totals"]["first_year_net_savings"] if s else "",
            "payback_months": s["totals"]["payback_months"] if s else "",
            "currency": s["currency"] if s else "",
        })


def print_run_summary(summary: dict[str, Any]) -> None:
    print(format_runtime(summary))
    if summary["savings"] is not None:
        print(format_savings(summary["savings"], (summary.get("tokens") or {}).get("note", "")))
    else:
        print(f"Cost savings not calculated: {summary['savings_error']}")
