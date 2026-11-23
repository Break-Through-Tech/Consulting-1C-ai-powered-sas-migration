# Results snapshot: SAS vs Python verification

A fixed copy of the pipeline's outputs, so the results can be viewed on GitHub
without running anything. Running the pipeline doesn't update these files: it
writes its live outputs to `verification_output/`, which is gitignored.

| | |
|---|---|
| Pipeline run | `run_20261123_041432` (2026-11-23), commit `3499d48` on `main` |
| Mode | Mode A: validated the existing translated files (no fresh translation, no API calls) |
| Command | `python src/orchestrator/pipeline.py`, from the repo root |

## Summary

| Result | Value |
|---|---|
| **Verdict** | **PASS**: all 21 validation checks passed |
| Coverage | 10 of 10 SAS output tables compared |
| Value accuracy | **100%** (1,100,660 of 1,100,660 values within tolerance) |
| Largest difference from SAS | 0.0000005 (floating-point rounding; tolerance is abs 1e-4 / rel 1e-6) |
| Star ratings | **2,891 of 2,891** SAS-rated hospitals get the same star (1,675 unrated in both) |
| Run time, one run of all scripts | SAS 2.86 s (from the SAS log) vs Python 1.33 s ± 0.02 s (mean of 30 runs), **about 2.1× faster** |
| Estimated savings | $8,000 per year, $0 AI conversion cost, first-year net $8,000 (**placeholder assumptions**, see below) |

### Run time per script (30 timed runs)

| Script | Python mean ± SD | SAS | Python vs SAS |
|---|---:|---:|---:|
| 0 - Data and Measure Standardization | 0.219 ± 0.010 s | 1.61 s | 7.3× faster |
| 1 - First stage (Simple Average) | 0.848 ± 0.017 s | 0.27 s | 3.1× slower |
| 2 - Second Stage (Weighted Average / Star) | 0.256 ± 0.004 s | 0.98 s | 3.8× faster |
| Star_Macros | 0.009 ± 0.001 s | runs inside the other programs | n/a |

The SAS times come from a single run recorded in `SAS_Log.log`, so they have
no spread. Treat the comparison as approximate.

## About the cost figures

- Every cost input is a **placeholder** from `config/cost_assumptions.json`
  (SAS licence $8,000 per year, equal maintenance hours and hourly rates for
  SAS and Python). Replace them with real figures before quoting any numbers.
- All of the $8,000 is the SAS licence share. That saving only happens if the
  licence is reduced or retired after the conversion. Compute savings are
  under a cent a year, and maintenance savings are $0 under the equal
  assumptions.
- **AI conversion cost** is the cost of the translation tokens only, with no
  review labor. It's $0 here because no token prices are set, which is the
  right setting for free-tier usage. `tokens_used` is blank because this run
  skipped translation, so it made no API calls.

## Files

| File | What it shows |
|---|---|
| `verification_report.md` | **Start here.** The full readable report: verdict, accuracy by table, run time and cost savings |
| `table_accuracy.csv` | Match percentage for each of the 10 SAS output tables |
| `column_accuracy.csv` | Mismatches and largest difference for each column (301 columns) |
| `star_confusion.csv` | SAS star (rows) vs Python star (columns) |
| `runtime.csv` / `runtime.json` | SAS vs Python run time per script, from this run |
| `runtime_statistics.csv` | Python run time per script over 30 timed runs (mean, SD, 95% CI), compared with SAS |
| `cost_savings.csv` / `cost_savings.json` | Estimated annual savings, tokens used and AI conversion cost per script |
| `token_usage.json` / `token_usage_calls.csv` | Gemini token usage (empty: translation was skipped) |
| `accuracy_report.json` | The full machine-readable accuracy report |

`runtime_statistics.csv` came from a separate timing run of the same
translated files (30 repetitions per script). The pipeline doesn't produce
it. Every other file is a direct copy of `verification_output/latest/` from
the run above.
