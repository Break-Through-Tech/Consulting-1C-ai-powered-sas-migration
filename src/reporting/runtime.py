"""
Run time measurement: how long SAS took vs. how long the Python translation takes.

* SAS run time per program is read from the SAS log ("real time" of every step).
* Python run time per translated script is measured by loading the stages in
  the order translated_pipeline.py lists them, under the same module names the
  stages use to find each other, so each stage is timed on its own (earlier
  stages are already loaded and are not re-run).
* Translation time per script (the Gemini call) is recorded by the token
  tracker, alongside that call's tokens.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import sys
import time
from pathlib import Path

_PROGRAM_START = re.compile(r"^\s*\d+\s+\*Note: it takes less than", re.I)
_REAL_TIME = re.compile(r"^\s*real time\s+([\d:.]+)\s*(seconds)?", re.I)
STAGE_MODULE_PREFIX = "_translated_sas_stage_"


def _seconds(text: str) -> float:
    """SAS writes 0.29, 1:02.33 (m:ss) or 1:02:03.00 (h:mm:ss)."""
    total = 0.0
    for part in text.split(":"):
        total = total * 60 + float(part)
    return total


def is_macro_file(name: str) -> bool:
    return "macro" in name.lower()


def sas_runtime_by_program(log_path: Path, sas_files: list[str]) -> dict[str, float | None]:
    """
    Sum the SAS "real time" of every step, per program.

    The log holds the programs in run order; each starts with the
    "*Note: it takes less than ..." header. They are matched in order to the
    non-macro SAS files (sorted by their leading stage number). The macro file
    is %INCLUDEd and runs inside the programs, so it gets None.
    """
    lines = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()
    sections: list[float] = []
    for line in lines:
        if _PROGRAM_START.match(line):
            sections.append(0.0)
        elif sections:
            match = _REAL_TIME.match(line)
            if match:
                sections[-1] += _seconds(match.group(1))

    programs = sorted((f for f in sas_files if not is_macro_file(f)), key=_stage_number)
    result: dict[str, float | None] = {f: None for f in sas_files}
    for name, seconds in zip(programs, sections):
        result[name] = round(seconds, 4)
    return result


def _stage_number(name: str) -> tuple[int, str]:
    match = re.match(r"^(\d+)", name)
    return (int(match.group(1)) if match else 10**6, name)


def stage_order(translated_dir: Path) -> list[str]:
    """The stage files in load order, as listed in translated_pipeline.py."""
    driver = Path(translated_dir) / "translated_pipeline.py"
    for node in ast.walk(ast.parse(driver.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_stage_files" for t in node.targets
        ):
            return list(ast.literal_eval(node.value))
    raise ValueError(f"No _stage_files list found in {driver}")


def time_python_stages(translated_dir: Path) -> dict[str, dict]:
    """
    Load each translated stage once, in order, and time it on its own.
    Returns {filename: {"seconds": float | None, "error": str | None}}.
    Stages after one that fails are not timed.
    """
    translated_dir = Path(translated_dir)
    import numpy, pandas  # noqa: F401  load libraries first so their import time isn't charged to stage 1
    _forget_stage_modules()
    results: dict[str, dict] = {}
    failed = None
    try:
        for index, filename in enumerate(stage_order(translated_dir)):
            if failed:
                results[filename] = {"seconds": None, "error": f"not timed: {failed} failed"}
                continue
            name = f"{STAGE_MODULE_PREFIX}{index:02d}"
            spec = importlib.util.spec_from_file_location(name, translated_dir / filename)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            start = time.perf_counter()
            try:
                spec.loader.exec_module(module)
            except Exception as exc:  # timing must never stop the pipeline
                failed = filename
                results[filename] = {"seconds": None, "error": f"{type(exc).__name__}: {exc}"}
                continue
            results[filename] = {"seconds": round(time.perf_counter() - start, 4), "error": None}
    finally:
        _forget_stage_modules()
    return results


def _forget_stage_modules() -> None:
    for name in [n for n in sys.modules if n.startswith(STAGE_MODULE_PREFIX)]:
        del sys.modules[name]


def runtime_table(sas_seconds: dict[str, float | None], python_timings: dict[str, dict],
                  translation_seconds: dict[str, float]) -> list[dict]:
    """One row per script, matching SAS and Python files by name stem."""
    rows = []
    for sas_name, sas_time in sas_seconds.items():
        stem = Path(sas_name).stem
        py_name = f"{stem}.py"
        timing = python_timings.get(py_name, {})
        py_time = timing.get("seconds")
        rows.append({
            "script": stem,
            "sas_file": sas_name,
            "python_file": py_name,
            "translation_seconds": translation_seconds.get(sas_name),
            "sas_runtime_seconds": sas_time,
            "python_runtime_seconds": py_time,
            "speedup": round(sas_time / py_time, 2) if sas_time and py_time else None,
            "note": ("macros run inside the other programs in SAS" if sas_time is None and is_macro_file(sas_name)
                     else timing.get("error") or ""),
        })
    return rows
