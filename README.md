# AI-Powered SAS Migration

---

### 👥 **Team Members**

**Example:**

| Name              | GitHub Handle | Contribution                                                             |
|-------------------|---------------|--------------------------------------------------------------------------|
| Jake Cordon       | @taylornguyen | Data exploration, visualization, overall project coordination            |
| Asmita Dulla      | @asmitadulla  | Data exploration, visualization, overall project coordination            |
| Karina Gonzalez   | @jramirez     | Data collection, exploratory data analysis (EDA), dataset documentation  |
| Rona Liu-Zhong    | @aminahassan  | Data preprocessing, feature engineering, data validation                 |
| Donovon Mott      | @MochiMunching| Model selection, hyperparameter tuning, model training and optimization  |
| Erica Muragaki    | @emuragaki    | Model evaluation, performance analysis, results interpretation           |
| Kimberly Rodriguez| @chrispark    | Model evaluation, performance analysis, results interpretation           |
| Amanda Wachuku    | @amandawachuku| Model evaluation, performance analysis, results interpretation           |

---

## 🎯 **Project Highlights**

**Example:**

- Developed a machine learning model using `[model type/technique]` to address `[challenge project task]`.
- Achieved `[key metric or result]`, demonstrating `[value or impact]` for `[host company]`.
- Generated actionable insights to inform business decisions at `[host company or stakeholders]`.
- Implemented `[specific methodology]` to address industry constraints or expectations.

---

## 👩🏽‍💻 **Setup and Installation**

This section walks you through running the SAS-to-Python pipeline on your own
machine, from a fresh clone to a verification report. The pipeline:

1. **Translates** the SAS programs into Python with Google Gemini (optional;
   off by default).
2. **Runs** the translated Python stages on the CMS hospital star rating data.
3. **Validates** every Python output against the original SAS output.
4. **Reports** accuracy, run time, token usage and estimated cost savings.

You can do steps 2–4 **without an API key**, using the translated files
already in the repo. That's the default, and the quickest way to check that
everything works.

### Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.12 or 3.13** | Required. The pinned packages (e.g. `numpy==2.5.3`) don't install on Python 3.11 or older. Check your version with `python --version`. Download from [python.org](https://www.python.org/downloads/). |
| **Git** | Used to clone the repo. On Windows, [Git for Windows](https://git-scm.com/download/win) includes Git Bash. |
| **A Gemini API key** | Optional. Only needed to run a fresh translation (Mode B below). Get one from [Google AI Studio](https://aistudio.google.com/apikey). |
| **About 1 GB of disk space** | For the virtual environment and packages. |

### Step 1: Clone the repository

```bash
git clone https://github.com/Break-Through-Tech/Consulting-1C-ai-powered-sas-migration.git
cd Consulting-1C-ai-powered-sas-migration
```

> **Run every command in this guide from this repo root folder.** The
> translated stage 0 loads its input data with a relative path, so running the
> pipeline from any other folder makes it crash.

### Step 2: Create and activate a virtual environment

A virtual environment keeps this project's packages separate from the rest of
your machine. The `.venv` folder is already gitignored.

**Windows (PowerShell):**
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```
If PowerShell blocks the activate script, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.

**Windows (Git Bash):**
```bash
py -3.12 -m venv .venv
source .venv/Scripts/activate
```

**macOS / Linux:**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

When it's active, your prompt starts with `(.venv)`. Run
`python --version` and confirm it says 3.12 or 3.13. Activate the environment
again each time you open a new terminal.

### Step 3: Install the dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

This takes a few minutes the first time.

### Step 4: Add your API key (only for fresh translations)

Skip this step if you only want to validate the existing translations.

Create a file named `.env` in the repo root (it's gitignored, so your key
stays private) containing:

```
GEMINI_API_KEY=your-key-here

# Optional: turns on the token cost estimate (USD per 1M tokens)
# GEMINI_INPUT_PRICE_PER_M=0.10
# GEMINI_OUTPUT_PRICE_PER_M=0.40
```

The prices in the comments are examples only. Use the current rates for the
model in `MODEL` (see [Configuration](#configuration)).

### Step 5: Check that the data is in place

The data ships with the repo, so there's nothing to download. Check that
these files exist:

| Path | What it is |
|---|---|
| `src/translation/sas_files/*.sas` | The 4 SAS programs that get translated |
| `src/translation/sas_files/alldata_2025jul.csv` | Input data for the pipeline (4,566 hospitals) |
| `data/Project_1/SAS Output CSV/*.csv` | The 10 SAS output tables that Python is validated against |
| `data/Project_1/SAS Programs/SAS_Log.log` | The SAS log, used for SAS run times |

### Step 6: Run the tests

```bash
python -m unittest discover -s tests -t .
```

Expected result: `Ran 37 tests ... OK (skipped=3)`. The 3 skipped tests
cover the web app's page and run once Streamlit is installed
(`pip install -r app/requirements.txt`). The tests use fake data and a fake
Gemini client, so they make no API calls.

### Step 7: Run the pipeline

```bash
python src/orchestrator/pipeline.py
```

The pipeline runs in one of two modes, set by `SKIP_TRANSLATION_FOR_TESTING`
near the top of `src/orchestrator/pipeline.py`.

**Mode A: validate the existing translations (default, no API key needed).**
With `SKIP_TRANSLATION_FOR_TESTING = True`, it runs the Python files already in
`src/translation/translated_files/` and validates them. It takes about
30–45 seconds, mostly spent comparing values against SAS.

**Mode B: translate fresh from SAS, then validate.** Set
`SKIP_TRANSLATION_FOR_TESTING = False` and add your API key (Step 4). The
pipeline sends each SAS file to Gemini, writes new Python files, validates
them, and retries with feedback on what failed, up to `MAX_ATTEMPTS` times.

> ⚠️ **Mode B overwrites `src/translation/translated_files/`.** The files in
> the repo were hand-fixed and verified to match SAS exactly, and a fresh
> translation may not. To get the verified files back, run
> `git checkout -- src/translation/translated_files`.

To regenerate the translations without validating them, run
`python src/translation/translation.py`. It also overwrites the files.

### Step 8: Check the results

A successful run ends like this:

```
full pipeline: all 21 check(s) passed.
Coverage: 10/10 SAS reference files compared  [COMPLETE]
Overall value accuracy: 100.00% (1,100,660/1,100,660 values)
Star ratings: 2,891/2,891 SAS-rated hospitals match (100.00%); all hospitals incl. unrated: 100.00%
Verification output written to verification_output/latest/verification_report.md
Total pipeline run time: 45.4s
```

Then open **`verification_output/latest/verification_report.md`**. It has the
PASS/FAIL verdict, accuracy for each table, run time, token usage and the cost
savings estimate. For what every output file contains, see
[Understanding the outputs](#understanding-the-outputs).

If a check fails, the terminal prints `[FAIL]` lines naming the table and
columns that differ, and the report lists them as well.

### Web app: drag-and-drop converter

`app/streamlit_app.py` is a web app for converting SAS without the
command line. You drop in `.sas` files and get back:
* the Python translation of each file, shown next to the SAS source, with
  downloads
* a **finance summary** for each script: estimated savings per year, tokens
  used, AI conversion cost, first-year net savings and payback. Visitors can
  change the cost assumptions in the sidebar.
* a `.zip` with all of the Python files, `finance_summary.csv` and `summary.md`

It uses the same Gemini model, file ordering, token tracking and cost model as
the pipeline, with a general-purpose prompt so it works on any SAS program.
The generated Python is syntax-checked but **never executed or validated
against SAS**. Only the CMS star rating pipeline above is validated.

**How the shared API key is protected**
* The Gemini key lives only in the app's server-side **secrets**. The browser
  never receives it, and it isn't in the repo.
* Visitors must enter an **access code** before they can translate anything.
  After 5 wrong codes, that browser is locked out for 10 minutes.
* **Limits:** `.sas` files only, up to 10 files and 200 KB each per
  translation; 5 translations per browser session per hour; and a daily cap
  across all visitors (`DAILY_TRANSLATION_LIMIT`, default 50).
* The app warns visitors not to upload confidential code, because files are
  sent to Google's Gemini API.

**Run it locally**
```bash
python -m pip install -r app/requirements.txt
```
Then create `.streamlit/secrets.toml` (it's gitignored) containing:
```toml
GEMINI_API_KEY = "your-key"
ACCESS_CODE = "choose-a-code"
# optional
DAILY_TRANSLATION_LIMIT = 50
GEMINI_INPUT_PRICE_PER_M = 0.0    # USD per 1M tokens; leave 0 for the free tier
GEMINI_OUTPUT_PRICE_PER_M = 0.0
```
Then run:
```bash
streamlit run app/streamlit_app.py
```
It opens at http://localhost:8501. Run it from the repo root so the settings
in `.streamlit/config.toml` are used.

**Deploy it for free on Streamlit Community Cloud**
1. Push the code to a GitHub repo you control, such as your fork.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub
   and create a new app from that repo.
3. Set the branch (e.g. `main`) and the main file path to
   `app/streamlit_app.py`. Under advanced settings, choose **Python 3.12** and
   paste the secrets from above (`GEMINI_API_KEY`, `ACCESS_CODE`, plus any
   optional ones).
4. Deploy. You get a public `https://<name>.streamlit.app` link. Share it,
   along with the access code, only with people who should use the key.

Streamlit Cloud installs `app/requirements.txt` (only Streamlit,
`google-genai` and `python-dotenv`), not the full research environment in the
root `requirements.txt`. Pushing to the branch redeploys the app
automatically. Free apps go to sleep when nobody's using them and take about
30 seconds to wake up.

**If someone else provides the API key:** they should create a separate key
just for this app in [Google AI Studio](https://aistudio.google.com/apikey),
so it can be revoked without affecting their other work. They can then add it
to the app's secrets themselves, or send it to you privately; never put it in
the repo, an issue or a chat. To stop the app using it, delete the key in AI
Studio or remove it from the app's secrets.

### Configuration

| Setting | Where | Default | What it does |
|---|---|---|---|
| `SKIP_TRANSLATION_FOR_TESTING` | `src/orchestrator/pipeline.py` | `True` | `True` validates the existing translations; `False` translates fresh with Gemini first |
| `MAX_ATTEMPTS` | `src/orchestrator/pipeline.py` | `2` | How many translate-and-validate attempts to make before stopping (Mode B) |
| `MODEL` | `src/translation/translation.py` | `gemini-3.5-flash-lite` | The Gemini model used for translation |
| `GEMINI_API_KEY` | `.env` | none | Needed for Mode B |
| `GEMINI_INPUT_PRICE_PER_M`, `GEMINI_OUTPUT_PRICE_PER_M` | `.env` | none | Optional. Turns on the token cost estimate |
| Cost assumptions | `config/cost_assumptions.json` | placeholders | SAS licence cost, runs per year, hourly rates, etc. Replace with real figures |
| Numeric tolerance | `compare_dataframe()` in `src/validation/validation.py` | abs `1e-4`, rel `1e-6` | How close a Python value must be to its SAS value to count as a match |

### Project structure

```
├── app/                           # ▶ drag-and-drop web app (streamlit run app/streamlit_app.py)
│   ├── streamlit_app.py           # the page: access code, upload, results, downloads
│   ├── translator.py              # Gemini translation (reuses the pipeline's helpers)
│   ├── finance.py                 # finance summary (reuses the pipeline's cost model)
│   ├── guard.py                   # access code, upload limits, rate limits
│   └── requirements.txt           # the app's own small dependency list
├── .streamlit/config.toml         # app settings (upload limit)
├── config/
│   └── cost_assumptions.json      # inputs for the cost savings estimate (placeholders)
├── data/Project_1/
│   ├── SAS Output CSV/            # the SAS outputs Python is validated against
│   ├── SAS Output/                # the same outputs as SAS datasets (.sas7bdat)
│   ├── SAS Programs/              # original SAS programs and SAS_Log.log
│   ├── Starrating/                # original input data
│   └── StarRatings_SASPackDoc_Jul2025.pdf   # CMS documentation for the SAS package
├── src/
│   ├── orchestrator/
│   │   ├── pipeline.py            # ▶ entry point: translate → run → validate → report
│   │   └── repair.py              # decides whether to retry a failed attempt
│   ├── translation/
│   │   ├── translation.py         # sends the SAS files to Gemini, writes the Python files
│   │   ├── sas_files/             # SAS programs + input data used by the pipeline
│   │   └── translated_files/      # the translated Python stages (verified against SAS)
│   ├── validation/
│   │   └── validation.py          # compares each Python output with its SAS output
│   └── reporting/
│       ├── accuracy_report.py     # coverage, value accuracy, star agreement
│       ├── verification_output.py # writes verification_output/ and the report
│       ├── token_usage.py         # Gemini token tracking
│       ├── runtime.py             # SAS vs Python run times
│       ├── cost_savings.py        # annual cost savings model
│       ├── run_summary.py         # combines run time and savings into the report
│       └── logger.py              # JSONL validation log
├── tests/                         # unit tests (python -m unittest discover -s tests -t .)
└── requirements.txt               # pinned Python packages (Python 3.12+)

Created when you run the pipeline (gitignored):
├── verification_output/           # latest report + history across runs
├── logs/                          # per-run snapshots and validation_log_YYYYMMDD.jsonl
└── src/orchestrator/actual_output/  # the Python outputs saved as CSV
```

### Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'pandas'` (or `dotenv`, `google`) | The virtual environment isn't active, or Step 3 was skipped. Activate `.venv` (Step 2) and install the requirements (Step 3). |
| `No matching distribution found for numpy==2.5.3` (or `ipykernel==7.4.0`) | Your Python is too old. Install Python 3.12 or 3.13 and recreate `.venv`. |
| In Git Bash, `python` points to `C:/msys64/...` or the wrong version | Another Python comes first on your PATH. Use the venv's Python directly (`.venv/Scripts/python`), or use `py -3.12`. |
| Stage 0 fails with `No objects to concatenate` | You're not in the repo root. `cd` into the repo folder and run the pipeline again. |
| `GEMINI_API_KEY is missing` | You're in Mode B without a key. Add it to `.env` (Step 4), or set `SKIP_TRANSLATION_FOR_TESTING = True`. |
| Checks fail after a Mode B run | The fresh translation differs from SAS. Read the `[FAIL]` lines and `verification_report.md`. To go back to the verified files, run `git checkout -- src/translation/translated_files`. |
| `LF will be replaced by CRLF` warnings in Git | Harmless Windows line-ending notices. You can ignore them. |

### Understanding the outputs

#### Validation

Validation matches rows by `provider_id` when it's available (otherwise by row
position), compares numeric values with an absolute tolerance of `1e-4` and a
relative tolerance of `1e-6`, and reports schema, key, per-column and
aggregate differences. The terminal shows a short summary, and detailed JSONL
results are appended to `logs/validation_log_YYYYMMDD.jsonl`.

#### Accuracy report

After validation, the pipeline prints an **accuracy report**
(`src/reporting/accuracy_report.py`), also saved as `accuracy_report.txt` and
`accuracy_report.json` in each `logs/run_*/attempt_N/` folder. It shows:

* **Coverage:** how many SAS reference CSVs were compared. A reference with no
  matching Python output is listed as `NOT VALIDATED` and fails the run
  instead of being silently skipped.
* **Value accuracy:** the share of compared values within tolerance, per
  table and overall.
* **Star agreement:** how many SAS-rated hospitals get the same star in
  Python, and how many are off by one. If any differ, a SAS-vs-Python
  confusion table is shown.

#### Verification output

Every run also writes a **verification output** to `verification_output/`
(`src/reporting/verification_output.py`). It's the same whether the run used
the existing translated files or a fresh SAS-to-Python translation:

* `latest/verification_report.md`: a readable summary with a PASS/FAIL
  verdict, overall value accuracy, star agreement and accuracy by table
* `latest/table_accuracy.csv` and `latest/column_accuracy.csv`: the match
  percentage for each SAS output table and each column
* `latest/star_confusion.csv`: SAS stars (rows) vs Python stars (columns)
* `latest/accuracy_report.json`: the full machine-readable report
* `accuracy_history.csv`: one row per run (verdict, accuracy, star
  agreement), so you can track accuracy across translation attempts

`latest/` is replaced on every run. The folder is gitignored.

#### Token usage

When the pipeline translates (`SKIP_TRANSLATION_FOR_TESTING = False`), it
records the exact token counts Gemini reports for every API call
(`src/reporting/token_usage.py`):

* Each translation call prints its tokens as it runs, and each attempt ends
  with a table of prompt, output, thinking and total tokens per call. If a run
  has more than one attempt, a whole-run total is printed too.
* `verification_output/latest/token_usage.json` and `token_usage_calls.csv`
  hold the latest attempt's counts, and the verification report includes the
  total.
* `verification_output/token_usage_history.csv` gets one row per attempt.
  Runs that skip translation are logged with 0 tokens.
* Optional cost estimate: set `GEMINI_INPUT_PRICE_PER_M` and
  `GEMINI_OUTPUT_PRICE_PER_M` (USD per 1M tokens) in `.env`. Thinking tokens
  are priced as output.

#### Run time and estimated cost savings

After each attempt the pipeline also reports
(`src/reporting/runtime.py`, `cost_savings.py`, `run_summary.py`):

* **Run time:** for each script, how long the AI took to convert it, how long
  it ran in SAS (summed from the step timings in `SAS_Log.log`), and how long
  the Python translation takes. Each stage is timed on its own. It also shows
  how long the attempt's translation and validation phases took, plus the
  total pipeline run time.
* **Estimated annual cost savings per script:**
  * SAS cost per year (licence share, compute, maintenance) minus Python
    cost per year (compute, maintenance)
  * **tokens used** to convert each script, and the **AI conversion cost**
    of those tokens: AI translation only, with no review labor included
  * first-year net savings and payback period
* **Tokens on runs that skip translation:** each translation run saves its
  per-script token counts to `verification_output/last_translation_tokens.json`.
  Runs that skip translation reuse them and say which run they came from.
  Before the first translation run, tokens show as "not measured".
* **AI cost:** tokens are priced with `GEMINI_INPUT_PRICE_PER_M` and
  `GEMINI_OUTPUT_PRICE_PER_M` from `.env`. With no prices set, which is the
  right setting for free-tier usage, the AI cost is $0 and the report says so.
* **Outputs in `verification_output/`:**
  * `latest/runtime.csv` and `latest/cost_savings.csv`, plus JSON versions
  * new "Run time" and "Estimated cost savings" sections in
    `verification_report.md`
  * one row per attempt in `runtime_history.csv`

The savings estimate uses `config/cost_assumptions.json`, where every value
is a **placeholder** (SAS licence cost, runs per year, server cost,
maintenance hours, hourly rates). Replace them with your
organization's real figures before sharing the numbers. The licence share is
only a real saving if the SAS licence is reduced or retired after the
conversion.

---

## 🏗️ **Project Overview**

**Describe:**

- How this project is connected to the Break Through Tech AI Program
- Your AI Studio host company and the project objective and scope
- The real-world significance of the problem and the potential impact of your work

---

## 📊 **Data Exploration**

**You might consider describing the following (as applicable):**

* The dataset(s) used: origin, format, size, type of data
* Data exploration and preprocessing approaches
* Insights from your Exploratory Data Analysis (EDA)
* Challenges and assumptions when working with the dataset(s)

**Potential visualizations to include:**

* Plots, charts, heatmaps, feature visualizations, sample dataset images

---

## 🧠 **Model Development**

**You might consider describing the following (as applicable):**

* Model(s) used (e.g., CNN with transfer learning, regression models)
* Feature selection and Hyperparameter tuning strategies
* Training setup (e.g., % of data for training/validation, evaluation metric, baseline performance)


---

## 📈 **Results & Key Findings**

**You might consider describing the following (as applicable):**

* Performance metrics (e.g., Accuracy, F1 score, RMSE)
* How your model performed
* Insights from evaluating model fairness

**Potential visualizations to include:**

* Confusion matrix, precision-recall curve, feature importance plot, prediction distribution, outputs from fairness or explainability tools

---

## 🚀 **Next Steps**

**You might consider addressing the following (as applicable):**

* What are some of the limitations of your model?
* What would you do differently with more time/resources?
* What additional datasets or techniques would you explore?

---

## 📝 **License**

Specify how your project can be used by others. Choose an appropriate license and link it here (e.g., MIT, Apache 2.0). Make sure your Challenge Advisor approves of the selected license type. 

**Example:**
This project is licensed under the MIT License.

---

## 📄 **References** (Optional but encouraged)

Cite relevant papers, articles, or resources that supported your project.

---

## 🙏 **Acknowledgements** (Optional but encouraged)

Thank your Challenge Advisor, host company representatives, TA, and others who supported your project.
