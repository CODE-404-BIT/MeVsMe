from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass(frozen=True)
class FixtureRecord:
    source: str
    provider_id: str
    competition: str
    season: str
    kickoff: datetime
    home_team: str
    away_team: str
    status: str = "SCHEDULED"
    league_id: str | None = None
    country: str | None = None


@dataclass(frozen=True)
class TeamMatchRecord:
    source: str
    competition: str
    season: str
    match_date: date
    home_team: str
    away_team: str
    home_goals: Optional[float] = None
    away_goals: Optional[float] = None
    home_shots: Optional[float] = None
    away_shots: Optional[float] = None
    home_sot: Optional[float] = None
    away_sot: Optional[float] = None
    home_corners: Optional[float] = None
    away_corners: Optional[float] = None
    home_cards: Optional[float] = None
    away_cards: Optional[float] = None


@dataclass(frozen=True)
class OddsRecord:
    source: str
    competition: str
    season: str
    match_date: date
    home_team: str
    away_team: str
    market_key: str
    selection: str
    decimal_odds: float
    line: Optional[float] = None
    bookmaker: Optional[str] = None
    source_timestamp: Optional[datetime] = None
