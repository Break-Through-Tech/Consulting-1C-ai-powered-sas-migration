"""Finance summary for translated scripts, using the pipeline's cost model."""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from reporting.cost_savings import estimate_savings, load_assumptions  # noqa: E402

ASSUMPTIONS_FILE = REPO_ROOT / "config" / "cost_assumptions.json"


def default_assumptions() -> dict[str, Any]:
    return load_assumptions(ASSUMPTIONS_FILE)


def code_lines(source: str) -> int:
    return sum(1 for line in source.splitlines() if line.strip())


def ai_cost(call, input_price: float, output_price: float) -> float:
    """USD for one call at the given prices per 1M tokens (0 for free tier)."""
    return (call.prompt * input_price + (call.output + call.thinking) * output_price) / 1_000_000


def finance_summary(translations, usage, assumptions: dict[str, Any],
                    input_price: float = 0.0, output_price: float = 0.0) -> dict[str, Any]:
    """
    Annual savings per translated script. Scripts are not executed, so compute
    (run time) savings are not included; the AI conversion cost is the priced
    tokens of each script's translation call.
    """
    calls = {c.label[len("translate "):]: c for c in usage.calls if c.label.startswith("translate ")}
    scripts = [{
        "script": Path(t.sas_name).stem, "sas_file": t.sas_name, "lines": code_lines(t.sas_source),
        "sas_runtime_seconds": None, "python_runtime_seconds": None, "tokens_used": t.tokens,
    } for t in translations]
    costs = {name: ai_cost(c, input_price, output_price) for name, c in calls.items()}
    summary = estimate_savings(scripts, {**assumptions, "llm_cost_per_script": None}, costs)
    summary["prices_per_million"] = {"input": input_price, "output": output_price}
    return summary


COLUMNS = [("script", "Script"), ("sas_lines", "SAS lines"), ("license_share_pct", "Licence share %"),
           ("sas_annual_cost", "SAS cost/yr"), ("python_annual_cost", "Python cost/yr"),
           ("annual_savings", "Savings/yr"), ("tokens_used", "Tokens used"),
           ("ai_conversion_cost", "AI conversion cost"), ("first_year_net_savings", "Year-1 net"),
           ("payback_months", "Payback (months)")]


def summary_csv(summary: dict[str, Any]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([label for _, label in COLUMNS])
    for row in summary["scripts"]:
        writer.writerow([row.get(key) for key, _ in COLUMNS])
    t = summary["totals"]
    writer.writerow(["TOTAL", "", "", t["sas_annual_cost"], t["python_annual_cost"], t["annual_savings"],
                     t["tokens_used"], t["ai_conversion_cost"], t["first_year_net_savings"], t["payback_months"]])
    return out.getvalue()


def summary_markdown(summary: dict[str, Any], translations) -> str:
    c, t, a = summary["currency"], summary["totals"], summary["assumptions"]
    lines = [
        "# SAS to Python conversion summary", "",
        f"- Scripts converted: {len(translations)}",
        f"- Tokens used: {t['tokens_used'] if t['tokens_used'] is not None else 'n/a'}",
        f"- AI conversion cost (tokens only, no review labor): {c} {t['ai_conversion_cost']:,.4f}",
        f"- Estimated annual savings: **{c} {t['annual_savings']:,.2f}**",
        f"- First-year net savings: **{c} {t['first_year_net_savings']:,.2f}**", "",
        "Estimates use the assumptions below. Licence savings only happen if the SAS licence is "
        "reduced or retired. Scripts were not executed, so compute savings are not included. "
        "The Python code is AI-generated and has not been validated against SAS output.", "",
        "## Assumptions", "", "```json", json.dumps(a, indent=2), "```", "",
        "## Per script", "", "| " + " | ".join(label for _, label in COLUMNS) + " |",
        "|" + "---|" * len(COLUMNS),
    ]
    for row in summary["scripts"]:
        lines.append("| " + " | ".join("" if row.get(k) is None else str(row.get(k)) for k, _ in COLUMNS) + " |")
    return "\n".join(lines) + "\n"
