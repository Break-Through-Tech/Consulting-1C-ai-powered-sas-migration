"""
Token usage tracking for the Gemini translation calls.

Every Gemini response carries exact token counts in `response.usage_metadata`,
so this records those numbers per call instead of estimating them.

    usage = TokenUsageTracker(model="gemini-3.5-flash-lite")
    translate_sas_files(usage=usage)       # records each chat.send_message
    print(usage.format_summary())

Counts per call:
  prompt    - input tokens sent (grows each pass, since the chat resends history)
  output    - tokens in the visible response
  thinking  - the model's internal reasoning tokens (billed like output)
  cached    - prompt tokens served from cache (part of prompt)
  total     - total_token_count reported by the API

Optional cost estimate: set GEMINI_INPUT_PRICE_PER_M and GEMINI_OUTPUT_PRICE_PER_M
(USD per 1M tokens) in .env. Without them, no cost is shown.
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

COUNT_FIELDS = ("prompt", "output", "thinking", "cached", "total")


def _count(metadata: Any, name: str) -> int:
    value = getattr(metadata, name, None) if metadata is not None else None
    return int(value or 0)


@dataclass
class TokenCall:
    label: str
    prompt: int = 0
    output: int = 0
    thinking: int = 0
    cached: int = 0
    total: int = 0
    reported: bool = True  # False if the response had no usage_metadata


@dataclass
class TokenUsageTracker:
    model: str = ""
    calls: list[TokenCall] = field(default_factory=list)

    def record(self, label: str, response: Any) -> TokenCall:
        """Record the token counts from one Gemini response."""
        meta = getattr(response, "usage_metadata", None)
        call = TokenCall(
            label=label,
            prompt=_count(meta, "prompt_token_count"),
            output=_count(meta, "candidates_token_count"),
            thinking=_count(meta, "thoughts_token_count"),
            cached=_count(meta, "cached_content_token_count"),
            total=_count(meta, "total_token_count"),
            reported=meta is not None,
        )
        if call.reported and not call.total:
            call.total = call.prompt + call.output + call.thinking
        self.calls.append(call)
        return call

    def totals(self) -> dict[str, int]:
        return {name: sum(getattr(c, name) for c in self.calls) for name in COUNT_FIELDS}

    def estimated_cost(self) -> float | None:
        """USD estimate from GEMINI_INPUT_PRICE_PER_M / GEMINI_OUTPUT_PRICE_PER_M, if both are set."""
        try:
            input_price = float(os.environ["GEMINI_INPUT_PRICE_PER_M"])
            output_price = float(os.environ["GEMINI_OUTPUT_PRICE_PER_M"])
        except (KeyError, ValueError):
            return None
        t = self.totals()
        return (t["prompt"] * input_price + (t["output"] + t["thinking"]) * output_price) / 1_000_000

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "api_calls": len(self.calls),
            "calls_without_usage": sum(not c.reported for c in self.calls),
            "totals": self.totals(),
            "estimated_cost_usd": self.estimated_cost(),
            "calls": [asdict(c) for c in self.calls],
        }

    def format_summary(self, title: str = "TOKEN USAGE") -> str:
        lines = ["", "=" * 64, title, "=" * 64]
        if not self.calls:
            lines += ["No API calls made (translation skipped): 0 tokens used.", "=" * 64]
            return "\n".join(lines)
        lines.append(f"Model: {self.model or 'unknown'}    API calls: {len(self.calls)}")
        lines.append(f"  {'call':<44}{'prompt':>9}{'output':>9}{'thinking':>9}{'total':>10}")
        for c in self.calls:
            label = c.label if len(c.label) <= 43 else c.label[:40] + "..."
            note = "" if c.reported else "  (no usage reported)"
            lines.append(f"  {label:<44}{c.prompt:>9,}{c.output:>9,}{c.thinking:>9,}{c.total:>10,}{note}")
        t = self.totals()
        lines.append(f"  {'TOTAL':<44}{t['prompt']:>9,}{t['output']:>9,}{t['thinking']:>9,}{t['total']:>10,}")
        if t["cached"]:
            lines.append(f"  ({t['cached']:,} of the prompt tokens were served from cache)")
        cost = self.estimated_cost()
        if cost is not None:
            lines.append(f"Estimated cost: ${cost:.4f}")
        lines.append("=" * 64)
        return "\n".join(lines)


HISTORY_FIELDS = ["timestamp", "run", "attempt", "translation", "model", "api_calls",
                  "prompt_tokens", "output_tokens", "thinking_tokens", "cached_tokens",
                  "total_tokens", "estimated_cost_usd"]


def save_token_usage(usage: TokenUsageTracker, out_dir: Path) -> None:
    """Write token_usage.json and token_usage_calls.csv into out_dir."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "token_usage.json").write_text(json.dumps(usage.to_dict(), indent=2))
    with (out_dir / "token_usage_calls.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["label", *COUNT_FIELDS, "reported"])
        writer.writeheader()
        writer.writerows(asdict(c) for c in usage.calls)


def append_token_history(usage: TokenUsageTracker, history_path: Path, *, run: str,
                         attempt: int, translation: str) -> None:
    """Append one row per attempt to the token usage history CSV."""
    history_path = Path(history_path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not history_path.exists()
    t = usage.totals()
    cost = usage.estimated_cost()
    with history_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "run": run, "attempt": attempt, "translation": translation,
            "model": usage.model, "api_calls": len(usage.calls),
            "prompt_tokens": t["prompt"], "output_tokens": t["output"],
            "thinking_tokens": t["thinking"], "cached_tokens": t["cached"],
            "total_tokens": t["total"],
            "estimated_cost_usd": "" if cost is None else f"{cost:.6f}",
        })
