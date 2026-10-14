# CMS Hospital Star Rating Pipeline - Python Translation Documentation

This document explains the Python port of the SAS-based CMS Hospital Star Rating calculation programs for the July 2025 release.

## Overview of Python Modules

The pipeline is split into five sequentially executed Python modules:

1. **`Star_Macros.py`**: Translates all core reusable SAS macros (`keep_hos`, `grp_score`, `report`, `kmeans`, `nation_avg0`, `nation_avg_peer`, and `nation_avg`) into Python functions.
2. **`0 - Data and Measure Standardization_2025Jul.py`**: Performs volume-based exclusions ($\le 100$ hospitals), filters and categorizes measures into domains, applies hospital inclusion checks, and standardizes and direction-flips measure scores.
3. **`1 - First stage_Simple Average of Measure Scores_2025Jul.py`**: Invokes domain score calculations via `grp_score` for all five quality groups: Mortality, Safety, Readmission, Patient Experience, and Timely/Effective Care.
4. **`2 - Second Stage_Weighted Average and Categorize Star_2025Jul.py`**: Merges group scores, computes weighted summary scores with weight redistribution for missing groups, applies reporting criteria, runs peer-grouped K-means clustering to assign Star ratings, and aggregates national averages.
5. **`translated_pipeline.py`**: An orchestration module that imports and executes all prior modules in sequence to produce the complete analysis datasets in Python.

---

## Execution Dependency and Workflow

The modules build upon each other in a strictly ordered pipeline:

- `Star_Macros.py` must be loaded first to provide all macro functions.
- `0 - Data and Measure Standardization_2025Jul.py` loads `Star_Macros.py` and creates standardized base files (`Std_data_2025Jul_analysis`).
- `1 - First stage_Simple Average of Measure Scores_2025Jul.py` runs after standardization and depends on domain definitions.
- `2 - Second Stage_Weighted Average and Categorize Star_2025Jul.py` depends on both standardization and domain scores, generating the final hospital-level star rating table and national average summaries.
- `translated_pipeline.py` ties everything together into a unified execution flow.

---

## Required Dependencies and External Data Files

### Python Packages
- `pandas`
- `numpy`
- `scikit-learn` (`KMeans`)

### External Data Files
The scripts expect a directory structure matching the SAS setup (`translation/sas_files/`), specifically:
- `Alldata_2025Jul.csv` (representing raw Hospital Compare data files).

---

## Discrepancies and Unresolved Behaviors

1. **SAS Dataset Storage vs. Python Globals**: SAS macro variables and permanent datasets (`LIBNAME R`) are simulated in Python by storing data frames in module-level global variables or returning them explicitly from functions.
2. **FASTCLUS and PROC UNIVARIATE**: SAS's `FASTCLUS` procedure with specific convergence and seed options is translated using `sklearn.cluster.KMeans` initialized with quintile medians as seeds. Minor differences in clustering iterations or convergence tolerances between SAS and scikit-learn may yield slight variations in boundary cases.
3. **Paths**: Path macros (`PATH1`, `PATH2`, `PATH3`) default to `translation/sas_files`. Users must ensure input CSV files exist at these locations.

---

## How to Run the Pipeline

To execute the entire end-to-end translation pipeline and reproduce the star ratings and summary statistics, run the orchestrator script:

```bash
python translated_pipeline.py
```
