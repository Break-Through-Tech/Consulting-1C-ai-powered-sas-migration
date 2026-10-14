# Hospital Star Rating Calculation Pipeline: SAS to Python Translation

This project is a modular Python port of a four-part SAS program pipeline designed to calculate CMS Hospital Star Ratings. The workflow standardizes measure data, computes group (domain) scores using unweighted averages, combines these group scores into an overall weighted summary score, applies reporting eligibility criteria, and assigns final star ratings using *k*-means clustering across peer groups.

---

## Architecture and Module Execution Order

The pipeline is organized into five independently runnable yet sequentially dependent Python scripts. Each script builds upon variables, macros, or dataset outputs established by previous modules.

```
Star_Macros.py
  └──> 0 - Data and Measure Standardization_2025Jul.py
         └──> 1 - First stage_Simple Average of Measure Scores_2025Jul.py
                └──> 2 - Second Stage_Weighted Average and Categorize Star_2025Jul.py
                       └──> translated_pipeline.py (Orchestrator)
```

### 1. `Star_Macros.py`
* **Purpose:** Serves as the macro library for the pipeline. It defines reusable core operations as Python functions equivalent to SAS macros.
* **Key Functions:**
  * `keep_hos`: Filters out hospitals that do not have at least one valid measure.
  * `grp_score`: Computes domain scores, counts valid measures per domain, calculates measure weights, standardizes scores to mean=0 and std=1, and merges back summary statistics.
  * `report`: Evaluates reporting eligibility criteria based on measure counts per domain (e.g., requiring at least 3 measures in at least 3 domains, including at least one mortality or safety domain).
  * `kmeans_clust`: Implements a two-pass *k*-means clustering routine (using `sklearn.cluster.KMeans`) seeded with quintile medians, refines cluster assignments, sorts clusters by mean summary score, and maps them to Star ratings (1 through 5).
  * `nation_avg0`, `nation_avg_peer`, `nation_avg`: Calculates national average summary scores overall, by peer group, and by individual domain groups for reporting and QA.

### 2. `0 - Data and Measure Standardization_2025Jul.py`
* **Purpose:** Ingests raw hospital measure data (`HC.Alldata_2025Jul`), applies volume-based exclusion criteria (dropping measures with $\le 100$ hospitals), categorizes measures into outcome and process domains, standardizes original measure values, and flips negative-direction measures so higher scores consistently represent better performance.
* **Outputs:** 
  * `initial_data_2025Jul` (filtered raw data)
  * `std_data_2025Jul_analysis` (fully standardized analysis-ready dataset)
  * Domain measure lists (`measure_OM`, `measure_OS`, `measure_OR`, `measure_PtExp`, `measure_Process`)

### 3. `1 - First stage_Simple Average of Measure Scores_2025Jul.py`
* **Purpose:** Computes the simple average group (domain) scores for each hospital across the five quality domains: Outcomes-Mortality, Outcomes-Safety, Outcomes-Readmission, Patient Experience, and Timely and Effective Care.
* **Outputs:** 
  * `Outcome_mortality`, `Outcome_safety`, `Outcome_readmission`, `PtExp`, `Process` (DataFrames containing standardized group scores per provider).

### 4. `2 - Second Stage_Weighted Average and Categorize Star_2025Jul.py`
* **Purpose:** Merges all domain scores into a single dataset, calculates an overall hospital summary score using CMS fixed standard weights (Patient Experience: 0.22, Readmission: 0.22, Mortality: 0.22, Safety: 0.22, Process: 0.12) with dynamic weight redistribution for missing domains, determines hospital reporting indicators, and applies *k*-means clustering grouped by the number of valid measurement domains to assign final 1–5 Star ratings.
* **Outputs:** 
  * `star_2025Jul` (final hospital-level star rating dataset)
  * `national_average_2025Jul` (national benchmark summary scores and peer group means)

### 5. `translated_pipeline.py`
* **Purpose:** Acts as the top-level orchestrator script. It provides the automated environment loader that sequences the execution of passes 1 through 4, ensuring all workspace variables are passed correctly between modules.

---

## Dependencies and Requirements

### Python Packages
* `pandas`: For tabular data manipulation, merging, aggregation, and pivoting.
* `numpy`: For numerical operations, array manipulations, and handling missing values (`np.nan`).
* `scikit-learn` (`sklearn.cluster.KMeans`): Used in place of SAS `PROC FASTCLUS` to execute *k*-means clustering with specified initial seeds and convergence parameters.

### Required Data Files
* The pipeline expects raw hospital data to be available in the workspace environment (or loaded via external connectors matching the SAS `HC.Alldata_2025Jul` library reference).
* Expected input columns include `provider_id` alongside all listed measure columns (e.g., `MORT_30_AMI`, `COMP_HIP_KNEE`, `H_COMP_1_STAR_RATING`, etc.).

---

## How to Run the Pipeline

1. Ensure all required Python packages (`pandas`, `numpy`, `scikit-learn`) are installed in your Python environment.
2. Place all generated modules (`Star_Macros.py`, `0 - Data and Measure Standardization_2025Jul.py`, `1 - First stage_Simple Average of Measure Scores_2025Jul.py`, `2 - Second Stage_Weighted Average and Categorize Star_2025Jul.py`, and `translated_pipeline.py`) in the same working directory.
3. Execute the orchestrator script:
   ```bash
   python translated_pipeline.py
   ```
4. Each script executes sequentially upon import/load, reproducing the data transformations, intermediate datasets, and final outputs defined in the original SAS programs.

---

## Discrepancies and Unresolved SAS Behavior

* **SAS Procedures vs. Python Libraries:** SAS-specific procedures such as `PROC FASTCLUS`, `PROC STANDARD`, `PROC TRANSPOSE`, and `PROC TABULATE` have been translated into equivalent pandas DataFrame methods, NumPy calculations, and `scikit-learn`'s `KMeans` estimator. While mathematical logic is preserved, minor floating-point discrepancies can occur due to differences between SAS's proprietary optimization routines and Python's underlying numerical engines.
* **Macro Variables and Paths:** Hardcoded SAS file paths (e.g., `\\...\Starrating`, `C:\Users\...`) and dynamic symbol table references (`%LET`, `SYMPUTX`) have been translated into standard Python string variables and function arguments.
* **Environment State:** The SAS implementation relies on persistent library storage (`LIBNAME R`). The Python translation replicates this by maintaining state within global dictionaries and pandas DataFrames shared across imported module namespaces.
