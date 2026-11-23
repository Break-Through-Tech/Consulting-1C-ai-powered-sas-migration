# SAS to Python Verification Report

**Verdict: PASS**

- Run: `run_20261123_041432` (attempt 1), 2026-11-23T04:15:18
- Translation: skipped (existing translated files)
- Validation checks: 21 passed, 0 failed
- Coverage: 10/10 SAS output files compared
- Overall value accuracy: **100.0000%** (1,100,660 of 1,100,660 values)
- Star rating agreement: **100.0000%** (2,891 of 2,891 SAS-rated hospitals)
- Token usage: 0 (translation skipped, no API calls)

## Accuracy by table

| SAS output | Accuracy | Values compared | Mismatched | Status |
|---|---:|---:|---:|---|
| LESS100_MEASURE.csv | n/a (empty) | 0 | 0 | PASS |
| MEASURE_AVERAGE_STDDEV_2025JUL.csv | 100.0000% | 245 | 0 | PASS |
| NATIONAL_AVERAGE_2025JUL.csv | 100.0000% | 9 | 0 | PASS |
| OUTCOME_MORTALITY.csv | 100.0000% | 91,320 | 0 | PASS |
| OUTCOME_READMISSION.csv | 100.0000% | 127,848 | 0 | PASS |
| OUTCOME_SAFETY.csv | 100.0000% | 100,452 | 0 | PASS |
| PROCESS.csv | 100.0000% | 136,980 | 0 | PASS |
| PTEXP.csv | 100.0000% | 100,452 | 0 | PASS |
| STAR_2025JUL.csv | 100.0000% | 118,716 | 0 | PASS |
| STD_DATA_2025JUL_ANALYSIS.csv | 100.0000% | 424,638 | 0 | PASS |

## Console summary

```
ACCURACY REPORT: Python vs SAS
================================================================
Coverage: 10/10 SAS reference files compared  [COMPLETE]
Overall value accuracy: 100.00% (1,100,660/1,100,660 values)

  table                                 accuracy  mismatched  status
  LESS100_MEASURE.csv                        n/a           0  PASS
  MEASURE_AVERAGE_STDDEV_2025JUL.csv     100.00%           0  PASS
  NATIONAL_AVERAGE_2025JUL.csv           100.00%           0  PASS
  OUTCOME_MORTALITY.csv                  100.00%           0  PASS
  OUTCOME_READMISSION.csv                100.00%           0  PASS
  OUTCOME_SAFETY.csv                     100.00%           0  PASS
  PROCESS.csv                            100.00%           0  PASS
  PTEXP.csv                              100.00%           0  PASS
  STAR_2025JUL.csv                       100.00%           0  PASS
  STD_DATA_2025JUL_ANALYSIS.csv          100.00%           0  PASS

Star ratings: 2,891/2,891 SAS-rated hospitals match (100.00%); all hospitals incl. unrated: 100.00%
```

## Run time

- Conversion (AI translation) time: n/a (translation skipped this run)
- This attempt: translation n/a, validation 46.0s, total 46.0s
- One run of all scripts: SAS 2.86s (from the SAS log), Python 1.38s

| Script | Conversion time | SAS run time | Python run time | Note |
|---|---:|---:|---:|---|
| 0 - Data and Measure Standardization_2025Jul | n/a | 1.61s | 0.23s |  |
| 1 - First stage_Simple Average of Measure Scores_2025Jul | n/a | 0.27s | 0.87s |  |
| 2 - Second Stage_Weighted Average and Categorize Star_2025Jul | n/a | 0.98s | 0.27s |  |
| Star_Macros | n/a | n/a | 0.00s | macros run inside the other programs in SAS |

## Estimated cost savings (per year)

> Estimates use the **placeholder assumptions** in `config/cost_assumptions.json`. Replace them with real figures before sharing. Licence savings only happen if the SAS licence is reduced or retired.

- Annual savings, all scripts: **USD 8,000.00** (licence 8,000.00, maintenance 0.00, compute 0.0033)
- AI conversion cost (translation tokens only, no review labor): not measured yet; first-year net: **USD 8,000.00**; payback immediate (no upfront cost)
- Tokens: not measured yet (run once with SKIP_TRANSLATION_FOR_TESTING = False).

| Script | SAS cost/yr | Python cost/yr | Savings/yr | Tokens used | AI conversion cost | Year-1 net | Payback (months) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 - Data and Measure Standardization_2025Jul | 3,357.11 | 480.00 | 2,877.11 | n/a | 0.0000 | 2,877.11 | 0.0 |
| 1 - First stage_Simple Average of Measure Scores_2025Jul | 1,473.53 | 480.00 | 993.53 | n/a | 0.0000 | 993.53 | 0.0 |
| 2 - Second Stage_Weighted Average and Categorize Star_2025Jul | 2,322.18 | 480.00 | 1,842.17 | n/a | 0.0000 | 1,842.17 | 0.0 |
| Star_Macros | 2,767.19 | 480.00 | 2,287.19 | n/a | 0.0000 | 2,287.19 | 0.0 |
