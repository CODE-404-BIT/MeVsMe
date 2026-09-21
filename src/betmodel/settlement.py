from __future__ import annotations

from dataclasses import dataclass
from math import prod

from .optimizer import Combination


@dataclass(frozen=True)
class Settlement:
    status: str
    return_multiple: float
    profit: float


def settle_combination(combo: Combination, outcomes: dict[str, str]) -> Settlement:
    statuses: list[str] = []
    winning_odds: list[float] = []
    for leg in combo.legs:
        status = outcomes.get(leg.selection)
        if status not in {"win", "loss", "void"}:
            raise ValueError(f"missing/invalid settlement for {leg.selection}")
        statuses.append(status)
        if status == "win":
            winning_odds.append(leg.decimal_odds)

    if "loss" in statuses:
        return Settlement("loss", 0.0, -1.0)
    if all(status == "void" for status in statuses):
        return Settlement("void", 1.0, 0.0)

    return_multiple = prod(winning_odds) if winning_odds else 1.0
    return Settlement("win", return_multiple, return_multiple - 1.0)


def performance_summary(settlements: list[Settlement]) -> dict[str, float | int]:
    if not settlements:
        return {"bets": 0, "wins": 0, "losses": 0, "voids": 0, "hit_rate": 0.0, "roi": 0.0}
    decided = [s for s in settlements if s.status != "void"]
    wins = sum(s.status == "win" for s in settlements)
    losses = sum(s.status == "loss" for s in settlements)
    voids = sum(s.status == "void" for s in settlements)
    hit_rate = wins / len(decided) if decided else 0.0
    roi = sum(s.profit for s in settlements) / len(settlements)
    return {
        "bets": len(settlements),
        "wins": wins,
        "losses": losses,
        "voids": voids,
        "hit_rate": hit_rate,
        "roi": roi,
    }
