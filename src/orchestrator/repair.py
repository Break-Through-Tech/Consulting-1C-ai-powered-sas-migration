from dataclasses import dataclass


@dataclass
class RepairDecision:
    action: str  # "continue", "retry", or "halt"
    reason: str


def decide_next_action(result: dict, stage_name: str, attempt: int = 1, max_attempts: int = 2) -> RepairDecision:
    """
    TENTATIVE decision logic. Real retry logic (re-calling translation
    with specific failure feedback) doesn't exist yet -- that requires
    compare_dataframe to be a trustworthy, real comparison first (it's
    still a row-count/column-name placeholder), and requires
    translation.py to support re-translating a single stage.

    For now: classify the outcome and say what *should* happen, without
    actually performing a retry. The orchestrator can act on this
    decision once the real retry mechanism exists.
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

    if attempt < max_attempts:
        decision = RepairDecision(
            "retry",
            f"{stage_name}: {len(failed)} check(s) failed ({list(failed)}). "
            f"Would retry (attempt {attempt}/{max_attempts}) once retry logic exists.",
        )
    else:
        decision = RepairDecision(
            "halt",
            f"{stage_name}: {len(failed)} check(s) still failing after {attempt} attempt(s) "
            f"({list(failed)}). Stopping rather than retrying indefinitely.",
        )

    print(decision.reason)
    return decision