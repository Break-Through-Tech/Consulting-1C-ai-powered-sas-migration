"""
Estimated cost savings of converting each SAS script to Python, over one year.

For each script:
    SAS cost per year     = licence share + compute + maintenance
    Python cost per year  = compute + maintenance          (no licence)
    annual savings        = SAS cost per year - Python cost per year
    one-time cost         = review hours x Python rate + AI translation cost
    first-year net        = annual savings - one-time cost
    payback               = one-time cost / monthly savings

Assumptions come from config/cost_assumptions.json (placeholders until your
team fills them in). Run times are the measured SAS (from the log) and Python
times per run. The licence share is only a real saving if the SAS licence is
actually reduced or retired once the scripts are converted.
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
    "conversion_review_hours_per_script",
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
    llm_cost_by_script: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    scripts: [{"script", "sas_file", "lines", "sas_runtime_seconds", "python_runtime_seconds"}]
    llm_cost_by_script: measured AI translation cost per SAS file, if known.
    """
    a = assumptions
    total_lines = sum(s["lines"] for s in scripts) or 1
    equal = a.get("license_allocation") == "equal"
    rows = []
    raw = []  # unrounded per-script values, so totals aren't off by rounding
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
            llm = float(a["llm_cost_per_script"])
        else:
            llm = (llm_cost_by_script or {}).get(s["sas_file"], 0.0)
        one_time = a["conversion_review_hours_per_script"] * a["python_developer_hourly_rate"] + llm

        raw.append({"sas_annual_cost": sas_cost, "python_annual_cost": py_cost, "annual_savings": annual,
                    "license_savings": license_share, "compute_savings": sas_compute - py_compute,
                    "maintenance_savings": sas_maint - py_maint, "one_time_conversion_cost": one_time,
                    "first_year_net_savings": annual - one_time})
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
            "one_time_conversion_cost": round(one_time, 2),
            "ai_translation_cost": round(llm, 4),
            "first_year_net_savings": round(annual - one_time, 2),
            "payback_months": round(one_time / (annual / 12), 1) if annual > 0 else None,
        })

    def total(key):
        return round(sum(r[key] for r in raw), 4 if key == "compute_savings" else 2)

    totals = {k: total(k) for k in ("sas_annual_cost", "python_annual_cost", "annual_savings",
                                   "license_savings", "compute_savings", "maintenance_savings",
                                   "one_time_conversion_cost", "first_year_net_savings")}
    totals["payback_months"] = (round(totals["one_time_conversion_cost"] / (totals["annual_savings"] / 12), 1)
                                if totals["annual_savings"] > 0 else None)
    return {"currency": a.get("currency", "USD"), "assumptions": a, "scripts": rows, "totals": totals}


SAVINGS_FIELDS = ["script", "sas_lines", "license_share_pct", "sas_annual_cost", "python_annual_cost",
                  "annual_savings", "license_savings", "compute_savings", "maintenance_savings",
                  "one_time_conversion_cost", "ai_translation_cost", "first_year_net_savings",
                  "payback_months"]


def save_savings(savings: dict[str, Any], out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cost_savings.json").write_text(json.dumps(savings, indent=2))
    with (out_dir / "cost_savings.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SAVINGS_FIELDS)
        writer.writeheader()
        writer.writerows(savings["scripts"])
        writer.writerow({"script": "TOTAL", **{k: v for k, v in savings["totals"].items() if k in SAVINGS_FIELDS}})


def format_savings(savings: dict[str, Any]) -> str:
    c = savings["currency"]
    lines = ["", "=" * 64, f"ESTIMATED ANNUAL COST SAVINGS ({c}, placeholder assumptions)", "=" * 64,
             f"  {'script':<40}{'per year':>11}{'one-time':>10}{'year-1 net':>11}"]
    for r in savings["scripts"]:
        name = r["script"] if len(r["script"]) <= 39 else r["script"][:36] + "..."
        lines.append(f"  {name:<40}{r['annual_savings']:>11,.2f}{r['one_time_conversion_cost']:>10,.2f}"
                     f"{r['first_year_net_savings']:>11,.2f}")
    t = savings["totals"]
    lines.append(f"  {'TOTAL':<40}{t['annual_savings']:>11,.2f}{t['one_time_conversion_cost']:>10,.2f}"
                 f"{t['first_year_net_savings']:>11,.2f}")
    if t["payback_months"] is not None:
        lines.append(f"Payback: {t['payback_months']} months. Edit config/cost_assumptions.json with real figures.")
    lines.append("=" * 64)
    return "\n".join(lines)
