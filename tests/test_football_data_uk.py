from pathlib import Path
from betmodel.providers.football_data_uk import parse_match_csv, parse_odds_csv

FIXTURE = Path(__file__).parent / "fixtures" / "football_data_uk_sample.csv"


def test_parse_team_match_statistics():
    rows = parse_match_csv(FIXTURE, competition="E0", season="2026-27")
    assert len(rows) == 2
    first = rows[0]
    assert first.home_team == "Arsenal"
    assert first.home_goals == 2
    assert first.home_shots == 17
    assert first.home_sot == 6
    assert first.home_corners == 8
    assert first.away_cards == 3


def test_parse_match_and_total_goal_odds():
    odds = parse_odds_csv(FIXTURE, competition="E0", season="2026-27")
    arsenal = [o for o in odds if o.home_team == "Arsenal"]
    keys = {(o.market_key, o.selection, o.decimal_odds) for o in arsenal}
    assert ("MATCH_HOME", "Arsenal", 1.45) in keys
    assert ("MATCH_DRAW", "Draw", 4.60) in keys
    assert ("MATCH_AWAY", "Everton", 7.50) in keys
    assert ("TOTAL_GOALS_OVER", "Over 2.5", 1.80) in keys
    assert ("TOTAL_GOALS_UNDER", "Under 2.5", 2.00) in keys


def test_auto_competition_uses_div_column():
    rows = parse_match_csv(FIXTURE, competition="AUTO", season="2026-27")
    assert [row.competition for row in rows] == ["E0", "E1"]
    odds = parse_odds_csv(FIXTURE, competition="AUTO", season="2026-27")
    liverpool = [o for o in odds if o.home_team == "Liverpool"]
    assert liverpool and all(o.competition == "E1" for o in liverpool)
