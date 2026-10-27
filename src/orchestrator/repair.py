from dataclasses import dataclass


@dataclass
class RepairDecision:
    action: str  # "continue", "retry", or "halt"
    reason: str


def decide_next_action(
    result: dict,
    stage_name: str,
    attempt: int = 1,
    max_attempts: int = 2,
    translation_skipped: bool = False,
    previous_failure_count: int | None = None,
) -> RepairDecision:
    """
    Decide whether to continue, retry, or halt after an attempt.

    Retry only when another translation could plausibly do better:
    - continue if every check passed
    - halt if translation was skipped, since a retry would rerun identical files
    - halt if this attempt failed as many checks as the last one (no improvement)
    - halt once max_attempts is reached
    - otherwise retry (the orchestrator passes the issue report as feedback)

    Crashed stages arrive here as failed "__execution__" results, so they
    count as failures like any other check.
    """
    if not result:
        decision = RepairDecision("halt", f"{stage_name}: no validations were run (no matched outputs).")
        print(decision.reason)
        return decision

    failed = {name: r for name, r in result.items() if not r.passed}

    if not failed:
        decision = RepairDecision("continue", f"{stage_name}: all {len(result)} check(s) passed.")
        print(decision.reason)
        return decision

    if translation_skipped:
        decision = RepairDecision(
            "halt",
            f"{stage_name}: {len(failed)} check(s) failed ({list(failed)}). "
            f"Not retrying: translation is skipped, so a retry would rerun the same files.",
        )
    elif previous_failure_count is not None and len(failed) >= previous_failure_count:
        decision = RepairDecision(
            "halt",
            f"{stage_name}: {len(failed)} check(s) failed, no better than the previous attempt's "
            f"{previous_failure_count} ({list(failed)}). Stopping since retranslating isn't helping.",
        )
    elif attempt < max_attempts:
        decision = RepairDecision(
            "retry",
            f"{stage_name}: {len(failed)} check(s) failed ({list(failed)}). "
            f"Retrying (attempt {attempt}/{max_attempts}).",
        )
    else:
        decision = RepairDecision(
            "halt",
            f"{stage_name}: {len(failed)} check(s) still failing after {attempt} attempt(s) "
            f"({list(failed)}). Stopping rather than retrying indefinitely.",
        )

    print(decision.reason)
    return decision