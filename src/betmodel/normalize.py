from __future__ import annotations

import re
import unicodedata


_MARKET_ALIASES = {
    "over 2 5 goals": "TOTAL_GOALS_OVER",
    "under 2 5 goals": "TOTAL_GOALS_UNDER",
    "1x2 home": "MATCH_HOME",
    "1x2 draw": "MATCH_DRAW",
    "1x2 away": "MATCH_AWAY",
    "btts yes": "BTTS_YES",
    "btts no": "BTTS_NO",
}


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("-", " ")
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def canonical_market_key(raw_name: str) -> str:
    normalized = normalize_name(raw_name)
    return _MARKET_ALIASES.get(normalized, f"UNKNOWN:{normalized}")



def _selection_side_and_line(selection: str) -> tuple[str, float] | None:
    match = re.fullmatch(
        r"\s*(over|under)\s+([0-9]+(?:[.,][0-9]+)?)\s*",
        selection,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(1).upper(), float(match.group(2).replace(",", "."))


def canonical_live_market(
    market_name: str,
    selection: str,
    home_team: str,
    away_team: str,
) -> tuple[str, str, float | None] | None:
    """Map a small, explicit set of live-provider market names to canonical keys.

    The mapping intentionally fails closed. New provider wording must be added with a
    test before it can enter the recommendation engine.
    """
    market = normalize_name(market_name)
    value = normalize_name(selection)

    if market == "match winner":
        if value == "home":
            return "MATCH_HOME", home_team, None
        if value == "draw":
            return "MATCH_DRAW", "Draw", None
        if value == "away":
            return "MATCH_AWAY", away_team, None
        return None

    if market in {"both teams score", "both teams to score"}:
        if value == "yes":
            return "BTTS_YES", "Yes", None
        if value == "no":
            return "BTTS_NO", "No", None
        return None

    total_markets = {
        "goals over under": "TOTAL_GOALS",
        "total goals over under": "TOTAL_GOALS",
        "corners over under": "TOTAL_CORNERS",
        "total corners": "TOTAL_CORNERS",
        "total corners over under": "TOTAL_CORNERS",
        "cards over under": "TOTAL_CARDS",
        "total cards": "TOTAL_CARDS",
        "total cards over under": "TOTAL_CARDS",
    }
    family = total_markets.get(market)
    side_line = _selection_side_and_line(selection)
    if family and side_line:
        side, line = side_line
        return f"{family}_{side}", f"{side.title()} {line:g}", line

    team_markets = {
        "home team total goals": ("TEAM_GOALS", home_team),
        "away team total goals": ("TEAM_GOALS", away_team),
        "home team total corners": ("TEAM_CORNERS", home_team),
        "away team total corners": ("TEAM_CORNERS", away_team),
        "home team total cards": ("TEAM_CARDS", home_team),
        "away team total cards": ("TEAM_CARDS", away_team),
        "home team total shots": ("TEAM_SHOTS", home_team),
        "away team total shots": ("TEAM_SHOTS", away_team),
        "home team shots on target": ("TEAM_SOT", home_team),
        "away team shots on target": ("TEAM_SOT", away_team),
        "home team total shots on target": ("TEAM_SOT", home_team),
        "away team total shots on target": ("TEAM_SOT", away_team),
    }
    team_family = team_markets.get(market)
    if team_family and side_line:
        family, team = team_family
        side, line = side_line
        return f"{family}_{side}", f"{team} {side.title()} {line:g}", line

    return None
