"""
SAS-to-Python translation for the web app.

Reuses the pipeline's translator helpers (model, file ordering, response
clean-up and per-call timing and token tracking) with a general-purpose prompt,
so it works for any SAS program, not just the CMS star rating pipeline.
The generated Python is only syntax-checked. It is never executed.
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

from reporting.token_usage import TokenUsageTracker  # noqa: E402
from translation.translation import MODEL, _send, remove_markdown_fence, sas_file_sort_key  # noqa: E402

SYSTEM_INSTRUCTION = """
You are an expert SAS programmer and Python data engineer. Translate SAS
programs into clean, idiomatic, runnable Python 3 using pandas and numpy.

Rules:
- Preserve the SAS logic exactly: data steps, merges, BY-group processing,
  missing-value semantics, macro logic, sorting and output datasets.
- Translate SAS macros into Python functions that RETURN their results; never
  write results with globals().
- Name each output DataFrame after its SAS dataset (without the library prefix).
- Import everything you use. Keep paths and inputs as clearly named variables
  instead of inventing file locations.
- When several files are translated in one session, later files may use names
  defined by earlier ones; keep names consistent across files.
- Where SAS behaviour cannot be reproduced exactly (e.g. PROC FASTCLUS
  convergence, formats, ODS output), add a short comment saying so.
- Return only the Python code, with no explanation outside code comments.
"""


@dataclass
class Translation:
    sas_name: str
    python_name: str
    sas_source: str
    python_code: str
    tokens: int | None
    seconds: float | None
    syntax_ok: bool
    syntax_error: str | None


def order_files(files: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Macros first, then numbered programs in order, then the rest (same rule as the pipeline)."""
    return sorted(files, key=lambda f: sas_file_sort_key(Path(f[0])))


def check_syntax(code: str) -> str | None:
    try:
        ast.parse(code)
        return None
    except SyntaxError as exc:
        return f"line {exc.lineno}: {exc.msg}"


def translate_files(
    files: list[tuple[str, str]],
    *,
    api_key: str | None = None,
    client=None,
    usage: TokenUsageTracker | None = None,
    model: str = MODEL,
    on_progress=None,
) -> list[Translation]:
    """
    Translate (filename, sas_source) pairs in dependency order, in one chat so
    later files can reuse earlier names. Pass `client` to inject a fake in tests.
    """
    usage = usage if usage is not None else TokenUsageTracker(model=model)
    client = client or genai.Client(api_key=api_key)
    chat = client.chats.create(
        model=model,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, temperature=0.2),
    )
    ordered = order_files(files)
    results = []
    for index, (name, source) in enumerate(ordered, start=1):
        if on_progress:
            on_progress(index, len(ordered), name)
        python_name = f"{Path(name).stem}.py"
        message = (f"Translate SAS file {index} of {len(ordered)}: {name}\n"
                   f"Output file: {python_name}\n\n```sas\n{source}\n```\n\n"
                   "Return only the Python code for this file.")
        response = _send(chat, message, usage, f"translate {name}")
        if not response.text or not response.text.strip():
            raise RuntimeError(f"The model returned no translation for {name}")
        code = remove_markdown_fence(response.text)
        call = usage.calls[-1]
        error = check_syntax(code)
        results.append(Translation(
            sas_name=name, python_name=python_name, sas_source=source, python_code=code,
            tokens=call.total if call.reported else None, seconds=call.seconds,
            syntax_ok=error is None, syntax_error=error,
        ))
    return results
