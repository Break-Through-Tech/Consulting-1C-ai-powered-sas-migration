"""
Estimated cost savings of converting each SAS script to Python, over one year.

For each script:
    SAS cost per year     = licence share + compute + maintenance
    Python cost per year  = compute + maintenance          (no licence)
    annual savings        = SAS cost per year - Python cost per year
    AI conversion cost    = cost of the tokens used to translate the script
                            (one-time; $0 when no token prices are set)
    first-year net        = annual savings - AI conversion cost
    payback               = AI conversion cost / monthly savings

The conversion cost is the AI translation only. It does not include anyone's
time reviewing the converted code. Tokens used per script come from the
translation run; the cost uses GEMINI_INPUT_PRICE_PER_M and
GEMINI_OUTPUT_PRICE_PER_M from .env, so free-tier usage counts as $0.

Assumptions come from config/cost_assumptions.json (placeholders until your
team fills them in). The licence share is only a real saving if the SAS
licence is actually reduced or retired once the scripts are converted.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

REQUIRED = [
    "sas_annual_license_cost", "runs_per_year", "server_cost_per_hour",
    "sas_maintenance_hours_per_script", "python_maintenance_hours_per_script",
    "sas_developer_hourly_rate", "python_developer_hourly_rate",
]


def load_assumptions(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if not isinstance(data.get(k), (int, float))]
    if missing:
        raise ValueError(f"{path}: missing or non-numeric assumptions: {missing}")
    if data.get("license_allocation", "lines_of_code") not in ("lines_of_code", "equal"):
        raise ValueError(f"{path}: license_allocation must be 'lines_of_code' or 'equal'")
    return {k: v for k, v in data.items() if not k.startswith("_")}


def count_code_lines(path: Path) -> int:
    """Non-blank lines in a SAS file."""
    return sum(1 for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
               if line.strip())


def estimate_savings(
    scripts: list[dict[str, Any]],
    assumptions: dict[str, Any],
    ai_cost_by_script: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    scripts: [{"script", "sas_file", "lines", "sas_runtime_seconds",
               "python_runtime_seconds", "tokens_used"}]
    ai_cost_by_script: priced AI translation cost per SAS file, if token prices are set.
    """
    a = assumptions
    total_lines = sum(s["lines"] for s in scripts) or 1
    equal = a.get("license_allocation") == "equal"
    rows, raw = [], []  # raw keeps unrounded values so totals aren't off by rounding
    for s in scripts:
        share = (1 / len(scripts)) if equal else s["lines"] / total_lines
        license_share = a["sas_annual_license_cost"] * share

        def compute(seconds):
            return (seconds or 0) / 3600 * a["runs_per_year"] * a["server_cost_per_hour"]

        sas_compute = compute(s.get("sas_runtime_seconds"))
        py_compute = compute(s.get("python_runtime_seconds"))
        sas_maint = a["sas_maintenance_hours_per_script"] * a["sas_developer_hourly_rate"]
        py_maint = a["python_maintenance_hours_per_script"] * a["python_developer_hourly_rate"]

        sas_cost = license_share + sas_compute + sas_maint
        py_cost = py_compute + py_maint
        annual = sas_cost - py_cost

        if a.get("llm_cost_per_script") is not None:
            ai_cost = float(a["llm_cost_per_script"])
        else:
            ai_cost = (ai_cost_by_script or {}).get(s["sas_file"], 0.0)

        raw.append({"sas_annual_cost": sas_cost, "python_annual_cost": py_cost, "annual_savings": annual,
                    "license_savings": license_share, "compute_savings": sas_compute - py_compute,
                    "maintenance_savings": sas_maint - py_maint, "ai_conversion_cost": ai_cost,
                    "first_year_net_savings": annual - ai_cost})
        rows.append({
            "script": s["script"],
            "sas_lines": s["lines"],
            "license_share_pct": round(share * 100, 2),
            "sas_annual_cost": round(sas_cost, 2),
            "python_annual_cost": round(py_cost, 2),
            "annual_savings": round(annual, 2),
            "license_savings": round(license_share, 2),
            "compute_savings": round(sas_compute - py_compute, 4),
            "maintenance_savings": round(sas_maint - py_maint, 2),
            "tokens_used": s.get("tokens_used"),
            "ai_conversion_cost": round(ai_cost, 4),
            "first_year_net_savings": round(annual - ai_cost, 2),
            "payback_months": _payback(ai_cost, annual),
        })

    def total(key):
        return round(sum(r[key] for r in raw), 4 if key in ("compute_savings", "ai_conversion_cost") else 2)

    totals = {k: total(k) for k in ("sas_annual_cost", "python_annual_cost", "annual_savings",
                                   "license_savings", "compute_savings", "maintenance_savings",
                                   "ai_conversion_cost", "first_year_net_savings")}
    known = [s.get("tokens_used") for s in scripts if s.get("tokens_used") is not None]
    totals["tokens_used"] = sum(known) if known else None
    totals["payback_months"] = _payback(totals["ai_conversion_cost"], totals["annual_savings"])
    return {"currency": a.get("currency", "USD"), "assumptions": a, "scripts": rows, "totals": totals}


def _payback(one_time: float, annual: float) -> float | None:
    if annual <= 0:
        return None
    return round(one_time / (annual / 12), 2)


SAVINGS_FIELDS = ["script", "sas_lines", "license_share_pct", "sas_annual_cost", "python_annual_cost",
                  "annual_savings", "license_savings", "compute_savings", "maintenance_savings",
                  "tokens_used", "ai_conversion_cost", "first_year_net_savings", "payback_months"]


def save_savings(savings: dict[str, Any], out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cost_savings.json").write_text(json.dumps(savings, indent=2))
    with (out_dir / "cost_savings.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SAVINGS_FIELDS)
        writer.writeheader()
        writer.writerows(savings["scripts"])
        writer.writerow({"script": "TOTAL", **{k: v for k, v in savings["totals"].items() if k in SAVINGS_FIELDS}})


def _tokens(value) -> str:
    return "n/a" if value is None else f"{value:,}"


def format_savings(savings: dict[str, Any], token_note: str = "") -> str:
    c = savings["currency"]
    lines = ["", "=" * 72, f"ESTIMATED ANNUAL COST SAVINGS ({c}, placeholder assumptions)", "=" * 72,
             f"  {'script':<36}{'per year':>10}{'tokens':>10}{'AI cost':>9}{'year-1 net':>11}"]
    for r in savings["scripts"]:
        name = r["script"] if len(r["script"]) <= 35 else r["script"][:32] + "..."
        lines.append(f"  {name:<36}{r['annual_savings']:>10,.2f}{_tokens(r['tokens_used']):>10}"
                     f"{r['ai_conversion_cost']:>9,.2f}{r['first_year_net_savings']:>11,.2f}")
    t = savings["totals"]
    lines.append(f"  {'TOTAL':<36}{t['annual_savings']:>10,.2f}{_tokens(t['tokens_used']):>10}"
                 f"{t['ai_conversion_cost']:>9,.2f}{t['first_year_net_savings']:>11,.2f}")
    lines.append("AI cost = translation tokens only (no review labor).")
    if token_note:
        lines.append(token_note)
    lines.append("Edit config/cost_assumptions.json with real figures.")
    lines.append("=" * 72)
    return "\n".join(lines)
