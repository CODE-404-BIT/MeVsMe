from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine

from .db import session_factory
from .models import Fixture, OddsSnapshot, TeamMatchStat, ProviderMapping
from .domain import FixtureRecord
from .normalize import canonical_live_market
from .providers.api_football import ApiFootballOdds
from .providers.football_data_uk import parse_match_csv, parse_odds_csv


@dataclass(frozen=True)
class IngestSummary:
    fixtures: int
    team_stat_rows: int
    odds_rows: int


def _provider_fixture_id(match_date, home: str, away: str) -> str:
    return f"{match_date.isoformat()}::{home}::{away}"


def ingest_football_data_uk(
    engine: Engine,
    path: Path,
    competition: str,
    season: str,
) -> IngestSummary:
    matches = parse_match_csv(path, competition=competition, season=season)
    odds = parse_odds_csv(path, competition=competition, season=season)
    odds_by_key: dict[str, list] = {}
    for row in odds:
        key = _provider_fixture_id(row.match_date, row.home_team, row.away_team)
        odds_by_key.setdefault(key, []).append(row)

    Session = session_factory(engine)
    fixture_count = 0
    stat_count = 0
    odds_count = 0

    with Session.begin() as session:
        for row in matches:
            provider_id = _provider_fixture_id(row.match_date, row.home_team, row.away_team)
            fixture = session.scalar(
                select(Fixture).where(
                    Fixture.source == row.source,
                    Fixture.provider_id == provider_id,
                )
            )
            if fixture is None:
                fixture = Fixture(
                    source=row.source,
                    provider_id=provider_id,
                    competition=row.competition,
                    season=row.season,
                    match_date=row.match_date,
                    home_team=row.home_team,
                    away_team=row.away_team,
                    status="FINISHED" if row.home_goals is not None and row.away_goals is not None else "SCHEDULED",
                )
                session.add(fixture)
                session.flush()
            else:
                fixture.competition = row.competition
                fixture.season = row.season
                fixture.match_date = row.match_date
                fixture.home_team = row.home_team
                fixture.away_team = row.away_team
                fixture.status = "FINISHED" if row.home_goals is not None and row.away_goals is not None else "SCHEDULED"

            session.execute(delete(TeamMatchStat).where(TeamMatchStat.fixture_id == fixture.id))
            session.execute(delete(OddsSnapshot).where(OddsSnapshot.fixture_id == fixture.id, OddsSnapshot.source == row.source))

            session.add_all([
                TeamMatchStat(
                    fixture_id=fixture.id,
                    team_name=row.home_team,
                    is_home=1,
                    goals=row.home_goals,
                    shots=row.home_shots,
                    shots_on_target=row.home_sot,
                    corners=row.home_corners,
                    cards=row.home_cards,
                ),
                TeamMatchStat(
                    fixture_id=fixture.id,
                    team_name=row.away_team,
                    is_home=0,
                    goals=row.away_goals,
                    shots=row.away_shots,
                    shots_on_target=row.away_sot,
                    corners=row.away_corners,
                    cards=row.away_cards,
                ),
            ])
            stat_count += 2

            for odd in odds_by_key.get(provider_id, []):
                session.add(
                    OddsSnapshot(
                        fixture_id=fixture.id,
                        source=odd.source,
                        bookmaker=odd.bookmaker,
                        market_key=odd.market_key,
                        selection=odd.selection,
                        line=odd.line,
                        decimal_odds=odd.decimal_odds,
                        source_timestamp=odd.source_timestamp,
                        received_timestamp=datetime.utcnow(),
                    )
                )
                odds_count += 1
            fixture_count += 1

    return IngestSummary(fixture_count, stat_count, odds_count)



def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def ingest_api_football(
    engine: Engine,
    fixtures: list[FixtureRecord],
    odds_by_fixture: dict[str, list[ApiFootballOdds]],
) -> IngestSummary:
    """Upsert API-FOOTBALL fixtures and supported pre-match odds.

    This ingest path never creates match statistics: those require a separately
    verified statistics response. Unsupported market names are skipped.
    """
    Session = session_factory(engine)
    fixture_count = 0
    odds_count = 0
    received_at = datetime.now(timezone.utc).replace(tzinfo=None)

    with Session.begin() as session:
        for row in fixtures:
            fixture = session.scalar(
                select(Fixture).where(
                    Fixture.source == row.source,
                    Fixture.provider_id == row.provider_id,
                )
            )
            if fixture is None:
                fixture = Fixture(
                    source=row.source,
                    provider_id=row.provider_id,
                    competition=row.competition,
                    season=row.season,
                    kickoff=_naive_utc(row.kickoff),
                    match_date=row.kickoff.date(),
                    home_team=row.home_team,
                    away_team=row.away_team,
                    status=row.status,
                )
                session.add(fixture)
                session.flush()
            else:
                fixture.competition = row.competition
                fixture.season = row.season
                fixture.kickoff = _naive_utc(row.kickoff)
                fixture.match_date = row.kickoff.date()
                fixture.home_team = row.home_team
                fixture.away_team = row.away_team
                fixture.status = row.status

            import json
            for kind,value in [('fixture_league',row.league_id),('fixture_competition',
                    json.dumps({'country':row.country,'league_id':row.league_id}) if row.country else None)]:
                if not value:continue
                mapping=session.scalar(select(ProviderMapping).where(ProviderMapping.source==row.source,
                    ProviderMapping.entity_type==kind,ProviderMapping.provider_key==row.provider_id))
                if mapping is None:
                    session.add(ProviderMapping(source=row.source,entity_type=kind,provider_key=row.provider_id,canonical_key=value))
                else:mapping.canonical_key=value

            if row.provider_id in odds_by_fixture:
                session.execute(
                    delete(OddsSnapshot).where(
                        OddsSnapshot.fixture_id == fixture.id,
                        OddsSnapshot.source == row.source,
                    )
                )

            for odd in odds_by_fixture.get(row.provider_id, []):
                mapped = canonical_live_market(
                    odd.market_name,
                    odd.selection,
                    row.home_team,
                    row.away_team,
                )
                if mapped is None:
                    continue
                market_key, selection, line = mapped
                session.add(
                    OddsSnapshot(
                        fixture_id=fixture.id,
                        source=row.source,
                        bookmaker=odd.bookmaker,
                        market_key=market_key,
                        selection=selection,
                        line=line,
                        decimal_odds=odd.decimal_odds,
                        source_timestamp=_naive_utc(odd.source_timestamp),
                        received_timestamp=received_at,
                    )
                )
                odds_count += 1
            fixture_count += 1

    return IngestSummary(fixture_count, 0, odds_count)
