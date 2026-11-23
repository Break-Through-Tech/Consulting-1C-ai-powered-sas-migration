import csv
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from src.reporting.cost_savings import estimate_savings, load_assumptions
from src.reporting.run_summary import build_run_summary, write_run_summary
from src.reporting.runtime import sas_runtime_by_program, time_python_stages
from src.reporting.token_usage import TokenUsageTracker

SAS_LOG = """NOTE: SAS initialization used:
      real time           1.66 seconds
1    *Note: it takes less than 5 minutes to run this program;
NOTE: DATA statement used (Total process time):
      real time           0.50 seconds
      cpu time            0.10 seconds
      real time           1:02.25
40   *Note: it takes less than 5 minutes to run this program;
      real time           0.25 seconds
"""
SAS_FILES = ["0 - Standardize.sas", "1 - Stage one.sas", "Star_Macros.sas"]

ASSUMPTIONS = {
    "currency": "USD", "sas_annual_license_cost": 1000, "license_allocation": "equal",
    "runs_per_year": 10, "server_cost_per_hour": 36,
    "sas_maintenance_hours_per_script": 2, "python_maintenance_hours_per_script": 1,
    "sas_developer_hourly_rate": 50, "python_developer_hourly_rate": 50,
    "llm_cost_per_script": None,
}


def write_driver(directory, files):
    (directory / "translated_pipeline.py").write_text(f"_stage_files = {files!r}\n")


class SasRuntimeTests(unittest.TestCase):
    def test_sums_real_time_per_program_and_skips_initialisation(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "SAS_Log.log"
            log.write_text(SAS_LOG)
            result = sas_runtime_by_program(log, SAS_FILES)
        self.assertAlmostEqual(result["0 - Standardize.sas"], 0.50 + 62.25)
        self.assertAlmostEqual(result["1 - Stage one.sas"], 0.25)
        self.assertIsNone(result["Star_Macros.sas"])  # runs inside the other programs


class PythonStageTimingTests(unittest.TestCase):
    def test_times_each_stage_and_stops_after_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "a.py").write_text("import time\ntime.sleep(0.05)\n")
            (d / "b.py").write_text("raise RuntimeError('boom')\n")
            (d / "c.py").write_text("x = 1\n")
            write_driver(d, ["a.py", "b.py", "c.py"])
            result = time_python_stages(d)
        self.assertGreaterEqual(result["a.py"]["seconds"], 0.05)
        self.assertIn("boom", result["b.py"]["error"])
        self.assertIsNone(result["c.py"]["seconds"])
        self.assertIn("not timed", result["c.py"]["error"])


class CostSavingsTests(unittest.TestCase):
    def test_per_script_savings_math(self):
        scripts = [
            {"script": "a", "sas_file": "a.sas", "lines": 30, "sas_runtime_seconds": 3600,
             "python_runtime_seconds": 1800, "tokens_used": 12000},
            {"script": "b", "sas_file": "b.sas", "lines": 10, "sas_runtime_seconds": None,
             "python_runtime_seconds": None, "tokens_used": None},
        ]
        s = estimate_savings(scripts, ASSUMPTIONS, {"a.sas": 0.5})
        a, b = s["scripts"]
        # licence 500 + compute (10 runs x 0.5 h saved x 36) 180 + maintenance (2-1) x 50 = 50
        self.assertAlmostEqual(a["annual_savings"], 500 + 180 + 50)
        # conversion cost is the AI tokens only: no review labor
        self.assertAlmostEqual(a["ai_conversion_cost"], 0.5)
        self.assertEqual(a["tokens_used"], 12000)
        self.assertNotIn("one_time_conversion_cost", a)
        self.assertAlmostEqual(a["payback_months"], round(0.5 / (730 / 12), 2))
        self.assertEqual((b["ai_conversion_cost"], b["payback_months"]), (0, 0))
        self.assertAlmostEqual(s["totals"]["annual_savings"], 730 + 550)
        self.assertEqual(s["totals"]["tokens_used"], 12000)

    def test_lines_of_code_allocation_and_no_savings_payback(self):
        scripts = [{"script": n, "sas_file": n, "lines": l, "sas_runtime_seconds": 0, "python_runtime_seconds": 0}
                   for n, l in (("a", 30), ("b", 10))]
        loc = estimate_savings(scripts, {**ASSUMPTIONS, "license_allocation": "lines_of_code"})
        self.assertEqual([r["license_savings"] for r in loc["scripts"]], [750, 250])
        none = estimate_savings(scripts, {**ASSUMPTIONS, "sas_annual_license_cost": 0,
                                          "sas_maintenance_hours_per_script": 1})
        self.assertIsNone(none["scripts"][0]["payback_months"])

    def test_rejects_missing_assumptions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.json"
            path.write_text(json.dumps({"currency": "USD"}))
            with self.assertRaises(ValueError):
                load_assumptions(path)

    def test_repo_assumptions_file_is_valid(self):
        load_assumptions(Path(__file__).resolve().parents[1] / "config" / "cost_assumptions.json")


class RunSummaryTests(unittest.TestCase):
    def test_builds_and_writes_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sas_dir, py_dir, latest = root / "sas", root / "py", root / "out" / "latest"
            sas_dir.mkdir(); py_dir.mkdir(); latest.mkdir(parents=True)
            for name in SAS_FILES:
                (sas_dir / name).write_text("data a;\nset b;\nrun;\n")
                (py_dir / name.replace(".sas", ".py")).write_text("x = 1\n")
            write_driver(py_dir, [n.replace(".sas", ".py") for n in SAS_FILES])
            (root / "SAS_Log.log").write_text(SAS_LOG)
            (root / "a.json").write_text(json.dumps(ASSUMPTIONS))
            (latest / "verification_report.md").write_text("# Report\n")

            meta = SimpleNamespace(prompt_token_count=900, candidates_token_count=100, thoughts_token_count=0,
                                   cached_content_token_count=0, total_token_count=1000)
            usage = TokenUsageTracker()
            usage.record("translate 0 - Standardize.sas", SimpleNamespace(usage_metadata=meta), seconds=4.2)
            usage.record("generate README.md", SimpleNamespace(usage_metadata=meta), seconds=1.0)
            last = root / "out" / "last_translation_tokens.json"
            summary = build_run_summary(
                sas_files_dir=sas_dir, sas_log=root / "SAS_Log.log", translated_dir=py_dir,
                assumptions_path=root / "a.json", usage=usage, last_translation_path=last,
                phase_seconds={"translation_seconds": 5.0, "validation_seconds": 2.0, "attempt_seconds": 7.0},
            )
            write_run_summary(summary, latest, root / "out" / "runtime_history.csv",
                              run="r", attempt=1, translation="fresh", last_translation_path=last)

            rows = {r["script"]: r for r in summary["runtime"]}
            self.assertEqual(rows["0 - Standardize"]["translation_seconds"], 4.2)
            self.assertIsNotNone(rows["1 - Stage one"]["python_runtime_seconds"])
            report = (latest / "verification_report.md").read_text()
            self.assertIn("## Run time", report)
            self.assertIn("## Estimated cost savings", report)
            self.assertIn("| Tokens used | AI conversion cost |", report)
            self.assertIn("no review labor", report)
            savings_rows = {r["script"]: r for r in summary["savings"]["scripts"]}
            self.assertEqual(savings_rows["0 - Standardize"]["tokens_used"], 1000)
            self.assertEqual(summary["tokens"]["other_tokens"], 1000)  # README call isn't a script

            # a later run that skips translation reuses the saved per-script tokens
            skipped = build_run_summary(
                sas_files_dir=sas_dir, sas_log=root / "SAS_Log.log", translated_dir=py_dir,
                assumptions_path=root / "a.json", usage=TokenUsageTracker(), last_translation_path=last,
                phase_seconds={},
            )
            self.assertIn("last translation run (r,", skipped["tokens"]["source"])
            self.assertEqual({r["script"]: r["tokens_used"] for r in skipped["savings"]["scripts"]}["0 - Standardize"], 1000)

            # with nothing saved, tokens are reported as not measured
            fresh = build_run_summary(
                sas_files_dir=sas_dir, sas_log=root / "SAS_Log.log", translated_dir=py_dir,
                assumptions_path=root / "a.json", usage=TokenUsageTracker(),
                last_translation_path=root / "missing.json", phase_seconds={},
            )
            self.assertIn("not measured", fresh["tokens"]["note"])
            self.assertIsNone(fresh["savings"]["totals"]["tokens_used"])
            for name in ("runtime.csv", "runtime.json", "cost_savings.csv", "cost_savings.json"):
                self.assertTrue((latest / name).exists(), name)
            with (root / "out" / "runtime_history.csv").open() as f:
                history = list(csv.DictReader(f))
            self.assertEqual(history[0]["annual_savings"], str(summary["savings"]["totals"]["annual_savings"]))


if __name__ == "__main__":
    unittest.main()
