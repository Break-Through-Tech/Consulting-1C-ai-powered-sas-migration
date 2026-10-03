"""
Basic SAS-to-Python translation script (Milestone 1).

Reads a single SAS program, sends it to Gemini with a translation prompt,
and saves the generated Python code to disk.

No validation or debug-repair loop yet -- that's Milestone 2.
"""

import os
import argparse
from pathlib import Path

from dotenv import load_dotenv
from google import genai


TRANSLATION_PROMPT_TEMPLATE = """You are an expert at translating SAS code to Python.

Translate the following SAS program into equivalent Python code using pandas,
numpy, and scikit-learn where appropriate.

Requirements:
- Preserve the same logical steps and order of operations as the original SAS code.
- Use pandas DataFrames in place of SAS datasets.
- Add a short comment above each major block explaining what it does.
- If the SAS code references a macro, translate its expanded logic inline
  (do not attempt to replicate SAS macro syntax in Python).
- Output ONLY valid Python code. Do not include explanations, markdown
  formatting, or code fences before or after the code.

SAS code to translate:

{sas_code}
"""


def load_sas_file(sas_path: Path) -> str:
    """Read the raw text of a SAS program."""
    return sas_path.read_text(encoding="utf-8")


def build_prompt(sas_code: str) -> str:
    """Fill the translation prompt template with the SAS source code."""
    return TRANSLATION_PROMPT_TEMPLATE.format(sas_code=sas_code)


def translate_sas_to_python(client: genai.Client, sas_code: str, model: str) -> str:
    """Send the SAS code to Gemini and return the generated Python code."""
    prompt = build_prompt(sas_code)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    return response.text


def strip_code_fences(text: str) -> str:
    """
    Defensive cleanup: models sometimes wrap output in ```python fences
    even when told not to. Strip them if present so the saved file is
    directly runnable.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop the opening fence line (``` or ```python)
        lines = lines[1:]
        # drop the closing fence line if present
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text


def main():
    parser = argparse.ArgumentParser(description="Translate a SAS program to Python using Gemini.")
    parser.add_argument(
        "--sas-file",
        type=str,
        required=True,
        help="Path to the input .sas file to translate.",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        required=True,
        help="Path to write the translated Python code to.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-3.8-flash",
        help="Gemini model to use (default: gemini-3.8-flash).",
    )
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found. Make sure it's set in your .env file."
        )

    client = genai.Client(api_key=api_key)

    sas_path = Path(args.sas_file)
    if not sas_path.exists():
        raise FileNotFoundError(f"SAS file not found: {sas_path}")

    print(f"Reading SAS file: {sas_path}")
    sas_code = load_sas_file(sas_path)

    print(f"Sending to Gemini ({args.model}) for translation...")
    raw_output = translate_sas_to_python(client, sas_code, args.model)
    python_code = strip_code_fences(raw_output)

    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(python_code, encoding="utf-8")

    print(f"Translated Python code written to: {output_path}")
    print("Note: this is an unvalidated, best-effort translation (Milestone 1).")


if __name__ == "__main__":
    main()