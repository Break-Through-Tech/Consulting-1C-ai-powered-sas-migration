from __future__ import annotations

import ast
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


TRANSLATION_DIR = Path(__file__).resolve().parent
SAS_FILES_DIR = TRANSLATION_DIR / "sas_files"
OUTPUT_DIR = TRANSLATION_DIR / "translated_files"
MODEL = "gemini-3.5-flash-lite"

STAGE0_SETUP = '''# Input setup supplied by the translation tool.
from pathlib import Path

path1 = Path(__file__).resolve().parent.parent / "sas_files"
path2 = path1
path3 = path1
year = 2025
quarter = "Jul"
input_file = path1 / f"alldata_{year}{quarter.lower()}.csv"
all_data = pd.read_csv(input_file, dtype={"PROVIDER_ID": "string"})
'''

SYSTEM_INSTRUCTION = """
You are an expert SAS programmer and Python data engineer translating a set of
related SAS programs into a sequence of independently runnable Python modules.
The conversation contains earlier SAS files and their translations; use that
conversation as persistent project context on every pass.

Keep a consistent mapping for SAS macro definitions, macro variables, libraries,
datasets, columns, and intermediate results across all files. Ensure that each
created script imports every standard-library and third-party package it uses
(such as pandas as pd and numpy as np). Preserve names and dependencies
established by prior passes. Translate only the current SAS file and reuse
definitions from the immediately previous generated module. The translator adds
the previous-file loader automatically; do not write a second import for it.
Keep SAS steps executable at module level when imported. Do not add a main guard,
an __all__ declaration, or a `from __future__` import. If an input path or SAS
behavior is unresolved in the source, represent it consistently and clearly
rather than inventing a path or result.

Project-specific input-loading requirements for Stage 0:
- The translator inserts the input setup automatically before your Stage 0 code.
  It provides path1, path2, path3, year, quarter, input_file, and all_data.
  Do not repeat or replace this setup. Do not load the input dataset yourself.
  Generated files live in translated_files next to sas_files; the supplied
  setup loads alldata_2025jul.csv and preserves PROVIDER_ID as a string.
- Keep the column name PROVIDER_ID consistent across all generated modules.
- Use all_data directly for subsequent input-data operations. Assign output
  DataFrames to explicit variables matching their SAS dataset names (without
  the library prefix), so the orchestrator can recognize them. Use those
  variables directly in later stages. Do not use globals()[...] for dataset
  reads or writes, or globals().get(...) to find datasets.
- Do not catch input-loading errors and substitute empty or invented data.
  Missing or unreadable input must raise an error and stop execution.

For each Python-file request, return only Python code, without Markdown fences
or explanatory prose. Each output module keeps the corresponding SAS filename
stem. For the final documentation request, return Markdown only.

In addition to the Python
files, create one Markdown file that explains what each Python file does and how
they work together to express the same functionality as the SAS programs. Note
any discrepancies between the SAS and Python functionality and explain how the 
Python file(s) should be run to produce the same results as the SAS program. Also
note any dependencies and data files the scripts need.
""".strip()


def sas_file_sort_key(path: Path) -> tuple[int, int, str]:
    """Place shared macros first, then numbered pipeline stages in order."""
    if path.name.casefold() == "star_macros.sas":
        return (0, 0, path.name.casefold())

    match = re.match(r"^(\d+)", path.name)
    if match:
        return (1, int(match.group(1)), path.name.casefold())
    return (2, 0, path.name.casefold())


def remove_markdown_fence(text: str) -> str:
    """Strip an accidental outer code fence from a model response."""
    result = text.strip()
    if not result.startswith("```"):
        return result

    lines = result.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def read_sas_source(path: Path) -> str:
    """Read UTF-8 SAS files, falling back to the common Windows encoding."""
    source = path.read_bytes()
    try:
        return source.decode("utf-8-sig")
    except UnicodeDecodeError:
        return source.decode("cp1252")


def validate_stage0_loading(python_code: str) -> None:
    """Check that the generated processing body uses the supplied input setup.

    This structural check does not establish successful execution or SAS
    equivalence. The generated program must still be run on the real input.
    """
    try:
        tree = ast.parse(python_code)
    except SyntaxError as exc:
        raise ValueError(f"Generated Stage 0 has invalid Python syntax: {exc}") from exc

    supplied_names = {"path1", "path2", "path3", "year", "quarter", "input_file", "all_data"}
    uses_input = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id == "all_data" and isinstance(node.ctx, ast.Load):
                uses_input = True
            if node.id in supplied_names and isinstance(node.ctx, (ast.Store, ast.Del)):
                raise ValueError(
                    f"Generated Stage 0 replaces supplied input variable {node.id!r}. "
                    "Use the supplied setup directly. Existing Stage 0 was not overwritten."
                )
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound_name = alias.asname or (
                    alias.name.split('.')[0] if isinstance(node, ast.Import) else alias.name
                )
                if bound_name in supplied_names:
                    raise ValueError(
                        f"Generated Stage 0 imports over supplied variable {bound_name!r}. "
                        "Existing Stage 0 was not overwritten."
                    )
        if isinstance(node, ast.Call) and (
            (isinstance(node.func, ast.Attribute) and node.func.attr in ("read_csv", "read_sas"))
            or (isinstance(node.func, ast.Name) and node.func.id in ("read_csv", "read_sas"))
        ):
            raise ValueError(
                "Generated Stage 0 reloads input data; use the supplied all_data "
                "DataFrame. Existing Stage 0 was not overwritten."
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "globals":
                raise ValueError(
                    "Generated Stage 0 uses globals(); use explicit dataset "
                    "variables. Existing Stage 0 was not overwritten."
                )
    if not uses_input:
        raise ValueError(
            "Generated Stage 0 does not reference the supplied all_data DataFrame. "
            "Existing Stage 0 was not overwritten."
        )


def previous_stage_loader(previous_filename: str, previous_index: int) -> str:
    """Load a previous translated file, including filenames that aren't importable."""
    module_key = f"_translated_sas_stage_{previous_index:02d}"
    return f'''# Load the preceding SAS stage and expose its public names here.
import importlib.util as _importlib_util
import sys as _sys
from pathlib import Path as _Path

_previous_name = {module_key!r}
_previous_path = _Path(__file__).with_name({previous_filename!r})
_previous_module = _sys.modules.get(_previous_name)
_previous_spec = None
if _previous_module is None:
    _previous_spec = _importlib_util.spec_from_file_location(_previous_name, _previous_path)
    if _previous_spec is None or _previous_spec.loader is None:
        raise ImportError(f"Could not load previous translation: {{_previous_path}}")
    _previous_module = _importlib_util.module_from_spec(_previous_spec)
    _sys.modules[_previous_name] = _previous_module
    try:
        _previous_spec.loader.exec_module(_previous_module)
    except Exception:
        del _sys.modules[_previous_name]
        raise
globals().update({{name: value for name, value in vars(_previous_module).items()
                  if not name.startswith("_")}})
del _importlib_util, _sys, _Path, _previous_name, _previous_path
del _previous_module, _previous_spec
'''


def pipeline_driver(filenames: list[str]) -> str:
    """Create a driver that runs generated modules in their dependency order."""
    file_list = "[\n" + "\n".join(f"    {name!r}," for name in filenames) + "\n]"
    return f'''"""Load all translated SAS stages in dependency order."""
import importlib.util as _importlib_util
import sys as _sys
from pathlib import Path as _Path

_stage_files = {file_list}
for _stage_index, _stage_filename in enumerate(_stage_files):
    _stage_name = f"_translated_sas_stage_{{_stage_index:02d}}"
    _stage_module = _sys.modules.get(_stage_name)
    if _stage_module is None:
        _stage_path = _Path(__file__).with_name(_stage_filename)
        _stage_spec = _importlib_util.spec_from_file_location(_stage_name, _stage_path)
        if _stage_spec is None or _stage_spec.loader is None:
            raise ImportError(f"Could not load translated stage: {{_stage_path}}")
        _stage_module = _importlib_util.module_from_spec(_stage_spec)
        _sys.modules[_stage_name] = _stage_module
        try:
            _stage_spec.loader.exec_module(_stage_module)
        except Exception:
            del _sys.modules[_stage_name]
            raise
    globals().update({{name: value for name, value in vars(_stage_module).items()
                      if not name.startswith("_")}})

del _importlib_util, _sys, _Path, _stage_files, _stage_index
del _stage_filename, _stage_name, _stage_module
'''


def translate_sas_files(
    sas_files_dir: Path = SAS_FILES_DIR,
    output_dir: Path = OUTPUT_DIR,
) -> list[Path]:
    """Translate every SAS file in dependency order using one persistent chat."""
    sas_files = sorted(sas_files_dir.glob("*.sas"), key=sas_file_sort_key)
    if not sas_files:
        raise FileNotFoundError(f"No .sas files found in {sas_files_dir}")

    load_dotenv(TRANSLATION_DIR.parents[1] / ".env")
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is missing; add it to the project .env file.")

    client = genai.Client()
    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.2,
        ),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    pipeline_output = output_dir / "translated_pipeline.py"
    output_paths: list[Path] = []
    output_filenames = [f"{sas_path.stem}.py" for sas_path in sas_files]

    for index, sas_path in enumerate(sas_files, start=1):
        print(f"Translating {index}/{len(sas_files)}: {sas_path.name}")
        sas_source = read_sas_source(sas_path)
        predecessor_note = (
            f"The generated preamble will load `{output_filenames[index - 2]}` "
            "and expose its public names in this module. Use those names as needed; "
            "do not write a separate import for the prior file."
            if index > 1
            else "This is the first stage and has no prior translated file."
        )
        stage0_note = ""
        if re.match(r"^0\s*[-_]", sas_path.stem):
            stage0_note = f'''
The translator will insert this setup before your Stage 0 processing code:

```python
{STAGE0_SETUP}
```

Do NOT return that setup or reassign its variables. Return only the translated
processing code, using all_data directly (make working copies under other names).
Do not call read_csv or read_sas. Do not substitute empty data or use globals()
for dataset lookups or assignments. Keep PROVIDER_ID and explicit output DataFrame
names corresponding to SAS datasets without their library prefix. Include any
other imports your processing code needs. Use the supplied year and quarter for
output names rather than redefining them.
'''
        message = f"""Translate this SAS file as pass {index} of {len(sas_files)}.

File: {sas_path.name}
Output file: {output_filenames[index - 1]}

{predecessor_note}
{stage0_note}

Include imports for all packages used by this file. Its code will execute when
the module is loaded; later stages will load this file and reuse its public names.

```sas
{sas_source}
```

Use the existing conversation history to preserve shared names, definitions,
and dependencies. Return only the Python code for this file."""

        response = chat.send_message(message)
        if not response.text or not response.text.strip():
            raise RuntimeError(f"The model returned no translation for {sas_path.name}")

        python_code = remove_markdown_fence(response.text)
        if re.match(r"^0\s*[-_]", sas_path.stem):
            validate_stage0_loading(python_code)
            python_code = f"{STAGE0_SETUP}\n{python_code.lstrip()}"
        required_imports = "import numpy as np\nimport pandas as pd"
        if required_imports not in python_code:
            python_code = f"{required_imports}\n\n{python_code}"
        if index > 1:
            loader = previous_stage_loader(output_filenames[index - 2], index - 2)
            python_code = f"{loader}\n{python_code.lstrip()}"

        translated_path = output_dir / output_filenames[index - 1]
        translated_path.write_text(python_code + "\n", encoding="utf-8")
        output_paths.append(translated_path)

    pipeline_output.write_text(pipeline_driver(output_filenames), encoding="utf-8")
    output_paths.append(pipeline_output)
    print(f"Saved pipeline driver to {pipeline_output}")

    readme_output = output_dir / "README.md"
    readme_prompt = f"""Create the Markdown README requested in the system instructions.

Use the SAS sources and Python translations from the full conversation history.
The generated Stage 0 also includes the input setup supplied in its request;
that setup was inserted by the translator before the model's processing code.
Document these generated files: {', '.join(output_filenames)}, and
translated_pipeline.py.

Explain what each Python file does, how the files depend on and run after one
another, which Python packages and data files are required, and how to run the
pipeline. Identify discrepancies or unresolved SAS behavior and paths. Base the
documentation on the actual source and translated code in this conversation;
don't claim equivalence or invent input files, dependencies, or results.

Write the contents of README.md only, in Markdown, with no outer code fence."""
    readme_response = chat.send_message(readme_prompt)
    if not readme_response.text or not readme_response.text.strip():
        raise RuntimeError("The model returned no README documentation")

    readme_output.write_text(
        remove_markdown_fence(readme_response.text) + "\n",
        encoding="utf-8",
    )
    output_paths.append(readme_output)
    print(f"Saved README to {readme_output}")
    return output_paths


if __name__ == "__main__":
    translate_sas_files()
