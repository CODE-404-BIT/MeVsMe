from __future__ import annotations

from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd

from betmodel.domain import OddsRecord, TeamMatchRecord

SOURCE = "football-data.co.uk"


def _num(row: pd.Series, key: str):
    if key not in row or pd.isna(row[key]):
        return None
    try:
        return float(row[key])
    except (TypeError, ValueError):
        return None


def _parse_date(value) -> datetime.date:
    parsed = pd.to_datetime(value, dayfirst=True, errors="raise")
    return parsed.date()


def parse_match_csv(path: Path, competition: str, season: str) -> list[TeamMatchRecord]:
    frame = pd.read_csv(path)
    records: list[TeamMatchRecord] = []
    for _, row in frame.iterrows():
        if pd.isna(row.get("HomeTeam")) or pd.isna(row.get("AwayTeam")):
            continue
        records.append(
            TeamMatchRecord(
                source=SOURCE,
                competition=(str(row.get("Div", competition)).strip() if competition == "AUTO" else competition),
                season=season,
                match_date=_parse_date(row["Date"]),
                home_team=str(row["HomeTeam"]).strip(),
                away_team=str(row["AwayTeam"]).strip(),
                home_goals=_num(row, "FTHG"),
                away_goals=_num(row, "FTAG"),
                home_shots=_num(row, "HS"),
                away_shots=_num(row, "AS"),
                home_sot=_num(row, "HST"),
                away_sot=_num(row, "AST"),
                home_corners=_num(row, "HC"),
                away_corners=_num(row, "AC"),
                home_cards=_num(row, "HY"),
                away_cards=_num(row, "AY"),
            )
        )
    return records


def _append_odds(records: list[OddsRecord], base: dict, row: pd.Series, column: str, market: str, selection: str, line=None):
    value = _num(row, column)
    if value is not None and value > 1.0:
        records.append(
            OddsRecord(
                **base,
                market_key=market,
                selection=selection,
                decimal_odds=value,
                line=line,
                bookmaker="Bet365",
            )
        )


def parse_odds_csv(path: Path, competition: str, season: str) -> list[OddsRecord]:
    frame = pd.read_csv(path)
    records: list[OddsRecord] = []
    for _, row in frame.iterrows():
        if pd.isna(row.get("HomeTeam")) or pd.isna(row.get("AwayTeam")):
            continue
        home = str(row["HomeTeam"]).strip()
        away = str(row["AwayTeam"]).strip()
        base = dict(
            source=SOURCE,
            competition=(str(row.get("Div", competition)).strip() if competition == "AUTO" else competition),
            season=season,
            match_date=_parse_date(row["Date"]),
            home_team=home,
            away_team=away,
        )
        _append_odds(records, base, row, "B365H", "MATCH_HOME", home)
        _append_odds(records, base, row, "B365D", "MATCH_DRAW", "Draw")
        _append_odds(records, base, row, "B365A", "MATCH_AWAY", away)
        _append_odds(records, base, row, "B365>2.5", "TOTAL_GOALS_OVER", "Over 2.5", 2.5)
        _append_odds(records, base, row, "B365<2.5", "TOTAL_GOALS_UNDER", "Under 2.5", 2.5)
    return records


def download(url: str, destination: Path, timeout: float = 30.0) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        destination.write_bytes(response.content)
    return destination


def latest_fixtures_url() -> str:
    return "https://www.football-data.co.uk/matches/resources/fixtures.csv"


def season_csv_url(season_code: str, league_code: str) -> str:
    clean_season = "".join(ch for ch in season_code if ch.isdigit())
    clean_league = "".join(ch for ch in league_code.upper() if ch.isalnum())
    if len(clean_season) != 4:
        raise ValueError("season_code must look like 2627")
    if not clean_league:
        raise ValueError("league_code is required")
    return f"https://www.football-data.co.uk/mmz4281/{clean_season}/{clean_league}.csv"
