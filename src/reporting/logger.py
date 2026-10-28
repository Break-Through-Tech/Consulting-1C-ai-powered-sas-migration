import json
from datetime import datetime, timezone
from pathlib import Path


def log_results(results: dict, stage_name: str, log_dir: Path) -> None:
    """
    Append this stage's validation results to a dated log file, as JSON
    lines, so you have a durable, readable record beyond just stdout.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"validation_log_{datetime.now(timezone.utc):%Y%m%d}.jsonl"

    with log_path.open("a") as f:
        for variable_name, result in results.items():
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **result.to_dict(),
                "stage": stage_name,
                "variable": variable_name,
                "summary": result.summary(),
            }
            f.write(json.dumps(entry, allow_nan=False) + "\n")