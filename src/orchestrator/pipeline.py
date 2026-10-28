import sys
import json
import shutil
import inspect
import traceback
from datetime import datetime
from pathlib import Path
import importlib.util
import pandas as pd

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))
from translation.translation import translate_sas_files
from validation.validation import compare_dataframe, ValidationResult
from orchestrator.repair import decide_next_action
from reporting.logger import log_results

REPO_ROOT = Path(__file__).resolve().parents[2]
TRANSLATED_DIR = REPO_ROOT / "src" / "translation" / "translated_files"
ACTUAL_OUTPUT_DIR = REPO_ROOT / "src" / "orchestrator" / "actual_output"
REFERENCE_DIR = REPO_ROOT / "data" / "Project_1" / "SAS Output CSV"
LOG_DIR = REPO_ROOT / "logs"
# one folder per pipeline run, holding a snapshot of every attempt
RUN_DIR = LOG_DIR / f"run_{datetime.now():%Y%m%d_%H%M%S}"

MAX_ATTEMPTS = 2

# TEMPORARY: set to True to skip calling translate_sas_files() entirely and
# just test the orchestrator against whatever's already in translated_files/
# (e.g. the hand-fixed stage 0). Set back to False once translation.py's
# fixes land and you want to test real, fresh translation again.
SKIP_TRANSLATION_FOR_TESTING = True


def auto_match_stage_outputs(module: object) -> list[tuple[str, str]]:
    """
    Automatically find which of a stage's output variables correspond to
    which reference CSVs, by matching names case-insensitively.
    """
    matches = []
    module_vars = {
        name: value for name, value in vars(module).items()
        if not name.startswith("_") and isinstance(value, pd.DataFrame)
    }
    for reference_path in REFERENCE_DIR.glob("*.csv"):
        reference_stem = reference_path.stem.lower()
        for var_name, var_value in module_vars.items():
            if var_name.lower() == reference_stem:
                matches.append((var_name, reference_path.name))
                break
    return matches


def save_and_validate(actual_df, reference_filename, stage_name, variable_name):
    ACTUAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    actual_path = ACTUAL_OUTPUT_DIR / reference_filename
    actual_df.to_csv(actual_path, index=False)
    actual_df_from_csv = pd.read_csv(actual_path)
    reference_path = REFERENCE_DIR / reference_filename
    return actual_df_from_csv, reference_path


def run_stage(stage_path: Path) -> object:
    """Execute one translated stage file as a Python module and return it."""
    module_name = f"_pipeline_stage_{stage_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, stage_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load stage: {stage_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def clear_stage_modules() -> None:
    """
    Forget every stage module loaded by a previous attempt. Each translated
    file loads the stage before it through sys.modules, so without this a
    retry could silently reuse the previous attempt's version of a stage.
    """
    stale = [name for name in sys.modules
             if name.startswith(("_translated_sas_stage_", "_pipeline_stage_"))]
    for name in stale:
        del sys.modules[name]


# ALL AT ONCE: translate all 4 files together (needed so variables from
# stage 0 correctly feed into stage 1, stage 2, etc. via the shared chat
# session in translate_sas_files()). If anything fails validation, we
# retranslate everything and try again, up to MAX_ATTEMPTS, rather than
# retrying one stage at a time.

# build a readable, sectioned summary of every issue found
def build_issue_report(all_results: dict[str, dict]) -> dict[str, list[str]]:
    """
    Turn raw ValidationResults into a readable, per-stage list of issue
    descriptions, suitable for showing a person or passing back into a
    (future) feedback-aware translation call.
    """
    issues_by_stage = {}
    for stage_name, stage_result in all_results.items():
        stage_issues = []
        for variable_name, result in stage_result.items():
            # a blocked stage never ran, so there's nothing in it to fix; the
            # crash is already reported against the stage that caused it
            if result.passed or variable_name == "__blocked__":
                continue
            if variable_name == "__execution__":
                # row/column counts are meaningless for a stage that crashed; the error is what matters
                stage_issues.append("crashed while running: " + " | ".join(n.strip() for n in result.notes))
            else:
                stage_issues.extend(result.summary().splitlines())
        if stage_issues:
            issues_by_stage[stage_name] = stage_issues
    return issues_by_stage


def translator_accepts_feedback() -> bool:
    """True once translate_sas_files() has a `feedback` parameter (issue #32)."""
    return "feedback" in inspect.signature(translate_sas_files).parameters


def call_translator(issue_report: dict[str, list[str]]) -> None:
    """
    Translate all stages. The first attempt has no issue report; on a retry,
    pass the previous attempt's issues so the translator can make targeted
    fixes. Until #32 adds the `feedback` parameter, fall back to a blind retry.
    """
    if not issue_report:
        translate_sas_files()
    elif translator_accepts_feedback():
        print(f"Retranslating with feedback on {len(issue_report)} stage(s).")
        translate_sas_files(feedback=issue_report)
    else:
        print("translate_sas_files() doesn't accept feedback yet (#32), so this retry is blind.")
        translate_sas_files()


def find_failing_stage(exc: Exception, stage_path: Path) -> str:
    """
    Name the translated file whose top-level code was running when exc was
    raised. Each stage loads the stage before it first, so a crash in stage 0
    also shows up when running stages 1 and 2; this points the feedback at
    the stage that actually broke instead of every stage downstream of it.
    """
    failing_stage = stage_path.name
    for frame in traceback.extract_tb(exc.__traceback__):
        frame_path = Path(frame.filename)
        # "<module>" frames are a file's top-level code, as opposed to a function
        # it calls (e.g. a Star_Macros helper), which is the caller's problem
        if frame_path.parent == TRANSLATED_DIR and frame.name == "<module>":
            failing_stage = frame_path.name
    return failing_stage


def translated_code_frames(exc: Exception) -> list[str]:
    """
    The traceback lines that are inside translated files, innermost last, e.g.
    "at 0 - Data and Measure Standardization_2025Jul.py line 107: x = df.describe()".
    The preamble's loader lines are skipped since every stage has them.
    """
    lines = []
    for frame in traceback.extract_tb(exc.__traceback__):
        frame_path = Path(frame.filename)
        if frame_path.parent == TRANSLATED_DIR and "exec_module" not in (frame.line or ""):
            lines.append(f"at {frame_path.name} line {frame.lineno}: {frame.line}")
    return lines


def failed_result(stage_name: str, variable_name: str, notes: list[str]) -> ValidationResult:
    """A failed ValidationResult for a stage that never produced outputs to compare."""
    return ValidationResult(
        stage_name=stage_name,
        variable_name=variable_name,
        reference_path=None,
        passed=False,
        row_count_actual=0,
        row_count_expected=0,
        notes=notes,
    )


def save_attempt(attempt: int, issue_report: dict, failure_count: int, decision) -> Path:
    """
    Snapshot this attempt's translated files and results under RUN_DIR, since
    the next attempt's translation overwrites translated_files/.
    """
    attempt_dir = RUN_DIR / f"attempt_{attempt}"
    files_dir = attempt_dir / "translated_files"
    files_dir.mkdir(parents=True, exist_ok=True)
    for path in TRANSLATED_DIR.iterdir():
        if path.is_file():
            shutil.copy2(path, files_dir / path.name)

    summary = {
        "attempt": attempt,
        "failure_count": failure_count,
        "decision": decision.action,
        "reason": decision.reason,
        "issue_report": issue_report,
    }
    (attempt_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return attempt_dir


def restore_attempt(attempt_dir: Path) -> None:
    """Copy a saved attempt's translated files back into translated_files/."""
    for path in (attempt_dir / "translated_files").iterdir():
        shutil.copy2(path, TRANSLATED_DIR / path.name)


attempt = 1
issue_report = {}             # empty on the first attempt; filled from each attempt's failures
previous_failure_count = None  # failure count from the last attempt, to detect a retry that didn't help
best = None                    # (attempt, failure_count, saved attempt folder) with the fewest failures
while attempt <= MAX_ATTEMPTS:
    last_attempt = attempt
    print(f"\nTranslation + validation attempt {attempt}/{MAX_ATTEMPTS}")

    if SKIP_TRANSLATION_FOR_TESTING:
        print("SKIP_TRANSLATION_FOR_TESTING is on — using existing files in translated_files/, no API call made.")
    else:
        call_translator(issue_report)

    # start each attempt from a clean slate so the freshly translated files are the ones that run
    clear_stage_modules()

    translated_paths = sorted(TRANSLATED_DIR.glob("*.py"))
    stage_paths = [p for p in translated_paths if p.suffix == ".py" and p.name != "translated_pipeline.py"]
    stage_validations = {}
    all_results = {}

    for stage_path in stage_paths:
        try:
            module = run_stage(stage_path)
        except Exception as exc:
            print(f"ERROR running {stage_path.name}: {exc}")
            # point the feedback at the generated line that failed, not at library internals (e.g. pandas)
            crash_notes = [f"Stage crashed: {type(exc).__name__}: {exc}", *translated_code_frames(exc)]
            failing_stage = find_failing_stage(exc, stage_path)

            if failing_stage == stage_path.name:
                all_results[stage_path.name] = {
                    "__execution__": failed_result(stage_path.name, "__execution__", crash_notes)
                }
            else:
                # the crash happened while loading an earlier stage: report it once, against that stage
                print(f"    caused by {failing_stage}, which this stage loads first")
                all_results.setdefault(failing_stage, {})["__execution__"] = failed_result(
                    failing_stage, "__execution__", crash_notes
                )
                all_results[stage_path.name] = {
                    "__blocked__": failed_result(
                        stage_path.name, "__blocked__",
                        [f"Did not run: depends on {failing_stage}, which crashed."],
                    )
                }
            log_results(all_results[stage_path.name], stage_path.name, LOG_DIR)
            continue

        stage_validations[stage_path.name] = auto_match_stage_outputs(module)
        result = {}
        for variable_name, reference_filename in stage_validations.get(stage_path.name, []):
            actual_df = getattr(module, variable_name, None)
            if actual_df is None:
                print(f"MISSING: {stage_path.name} has no variable '{variable_name}'")
                continue
            actual_df, reference_path = save_and_validate(actual_df, reference_filename, stage_path.name, variable_name)
            result[variable_name] = compare_dataframe(actual_df, reference_path, stage_path.name, variable_name)
            print(result[variable_name].summary())

        log_results(result, stage_path.name, LOG_DIR)
        all_results[stage_path.name] = result

    # build the sectioned issue report ACROSS all stages
    issue_report = build_issue_report(all_results)

    # one decision for the whole run, based on everything found
    flat_results = {
        f"{stage}::{var}": r
        for stage, stage_result in all_results.items()
        for var, r in stage_result.items()
    }
    decision = decide_next_action(
        flat_results, "full pipeline", attempt, MAX_ATTEMPTS,
        translation_skipped=SKIP_TRANSLATION_FOR_TESTING,
        previous_failure_count=previous_failure_count,
    )

    failure_count = sum(not r.passed for r in flat_results.values())
    attempt_dir = save_attempt(attempt, issue_report, failure_count, decision)
    if best is None or failure_count < best[1]:
        best = (attempt, failure_count, attempt_dir)

    if decision.action != "retry":
        break

    print(f"Retrying with feedback on {len(issue_report)} stage(s): {list(issue_report)}")
    previous_failure_count = failure_count
    attempt += 1

best_attempt, best_failure_count, best_dir = best
print(f"\nBest attempt: {best_attempt} of {last_attempt}, with {best_failure_count} failed check(s). "
      f"Snapshots of every attempt are in {RUN_DIR.relative_to(REPO_ROOT)}")
# a later attempt can be worse than an earlier one; leave translated_files/ at the best
if best_attempt != last_attempt and not SKIP_TRANSLATION_FOR_TESTING:
    restore_attempt(best_dir)
    print(f"Restored attempt {best_attempt}'s translated files into {TRANSLATED_DIR.relative_to(REPO_ROOT)}")