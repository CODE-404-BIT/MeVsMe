"""Research-gated price combinations for the 2x and 3x views."""
from datetime import datetime, timezone


def _research_combinations(engine, window, target, now):
    from .accuracy_policy import analyze_evidence

    combinations, report = analyze_evidence(engine, window, now=now)
    return combinations[target], report


def price_combinations(engine, window, target, now=None):
    if target not in {"2", "3"}:
        raise ValueError("invalid combination target")
    now = now or datetime.now(timezone.utc)
    results, report = _research_combinations(engine, window, target, now)
    return {"items":results, "limited":report["limited"], "mode":"odds-only",
            "researched":True, "research_policy":report.get("policy", "accuracy-v2"),
            "research_report":report["reason"], "research_evidence":report.get("evidence_combinations", {})}
