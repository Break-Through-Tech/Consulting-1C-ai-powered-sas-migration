import sys
from pathlib import Path
import importlib.util
import pandas as pd

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))
from translation.translation import translate_sas_files
from validation.validation import compare_dataframe
from orchestrator.repair import decide_next_action
from reporting.logger import log_results

REPO_ROOT = Path(__file__).resolve().parents[2]
TRANSLATED_DIR = REPO_ROOT / "src" / "translation" / "translated_files"
ACTUAL_OUTPUT_DIR = REPO_ROOT / "src" / "orchestrator" / "actual_output"
REFERENCE_DIR = REPO_ROOT / "data" / "Project_1" / "SAS Output CSV"
LOG_DIR = REPO_ROOT / "logs"

MAX_ATTEMPTS = 2

# TEMPORARY: skip re-translation so we can test the orchestrator against
# the hand-fixed stage 0 file, without it getting overwritten by a fresh
# (and possibly still-buggy) translation. Revert this once the real fix
# lands in translation.py's system instruction.
translated_paths = sorted(TRANSLATED_DIR.glob("*.py"))
# translated_paths = translate_sas_files()

stage_paths = [p for p in translated_paths if p.suffix == ".py" and p.name != "translated_pipeline.py"]
stage_paths = stage_paths[:1]  # TEMPORARY: only run stage 0 while stages 1-2 are still being fixed
stage_validations = {}


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


for stage_path in stage_paths:
    
  attempt = 1
  while attempt <= MAX_ATTEMPTS:
    module = run_stage(stage_path)

    stage_validations[stage_path.name] = auto_match_stage_outputs(module)

    result = {}
    for variable_name, reference_filename in stage_validations.get(stage_path.name, []):
        actual_df = getattr(module, variable_name, None)
        if actual_df is None:
            print(f"MISSING: {stage_path.name} has no variable '{variable_name}'")
            continue
        actual_df, reference_path = save_and_validate(actual_df, reference_filename, stage_path.name, variable_name)
        result[variable_name] = compare_dataframe(actual_df, reference_path, stage_path.name, variable_name)

    log_results(result, stage_path.name, LOG_DIR)
    decision = decide_next_action(result, stage_path.name, attempt, MAX_ATTEMPTS)
    
    # either it passed or max attempts as been hit, either way we are moving on
    if decision != "retry":
        break
    
    #TODO: translation.py doesn't yet support re-translating a single stage with feedback
    # once it does, we should call it here
    # retranslate_stage(stage_path, failure_notes=[r.notes for r in result.values() if not r.passed])
