from datetime import datetime, timedelta, timezone

import pytest

from betmodel.dashboard import Dashboard
from betmodel.db import session_factory
from betmodel.models import Fixture, OddsSnapshot
from betmodel.historical_suggestions import suggestions, priced_patterns, build_combinations

NOW = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)


def record(**changes):
    return dict(dict(label='Over 0.5 goals', group='Combined unique matches',
                     hits=5, trials=5, window=5, **{'from':'2026-09-01','to':'2026-10-01'}), **changes)


def match(fid=1, **changes):
    return dict(dict(fixture_id=fid, home='A', away='B', competition='E0',
                     status='SCHEDULED', kickoff='2026-10-02T20:00:00Z', patterns=[record()]), **changes)


@pytest.mark.parametrize('p', [record(hits=4), record(hits=4,trials=4),
    record(**{'to':'2026-10-03'}), record(hits=6,trials=6,window=6),
    record(label='A: 1+ goals (away)', group='A')])
def test_nonqualifying_records_do_not_become_suggestions(p):
    assert suggestions({'matches':[match(patterns=[p])]}, NOW) == []


def seeded(tmp_path):
    app = Dashboard(tmp_path)
    evidence = {'matches':[]}
    with session_factory(app.engine).begin() as session:
        for i in range(2):
            fixture = Fixture(source='test', provider_id=str(i), competition='E0', season='2026',
                home_team='A', away_team='B', status='SCHEDULED',
                kickoff=datetime(2026,10,2,20))
            session.add(fixture)
            session.flush()
            evidence['matches'].append(match(fixture.id))
            session.add(OddsSnapshot(fixture_id=fixture.id,source='test',bookmaker='Book',
                market_key='TOTAL_GOALS_OVER',selection='Over 0.5',line=.5,decimal_odds=1.45,
                source_timestamp=NOW.replace(tzinfo=None),received_timestamp=NOW.replace(tzinfo=None)))
    app.results = build_combinations(priced_patterns(app.engine,evidence,NOW))
    assert len(app.results['2']) == 1
    return app, evidence


def test_perfect_record_does_not_require_model_or_odds():
    assert len(suggestions({'matches':[match(forecast={'available':False})]},NOW)) == 1


def test_latest_invalid_quote_does_not_revive_old_quote(tmp_path):
    app,evidence=seeded(tmp_path)
    with session_factory(app.engine).begin() as session:
        session.add(OddsSnapshot(fixture_id=evidence['matches'][0]['fixture_id'],source='test',
            bookmaker='Book',market_key='TOTAL_GOALS_OVER',selection='Over 0.5',line=.5,
            decimal_odds=1,source_timestamp=NOW.replace(tzinfo=None),
            received_timestamp=(NOW+timedelta(seconds=1)).replace(tzinfo=None)))
    assert not build_combinations(priced_patterns(app.engine,evidence,NOW))['2']


def test_response_revalidates_kickoff_and_cancellation(tmp_path):
    from betmodel.historical_suggestions import current_combinations
    app,evidence=seeded(tmp_path)
    items=app.results['2']
    assert current_combinations(app.engine,items,NOW) == items
    assert current_combinations(app.engine,items,NOW+timedelta(hours=10)) == []
    with session_factory(app.engine).begin() as session:
        session.get(Fixture,evidence['matches'][0]['fixture_id']).status='CANCELLED'
    assert current_combinations(app.engine,items,NOW) == []
    assert app.results['2'] == items  # Frozen original is not rewritten.


def test_changed_or_expired_quote_invalidates_cached_card(tmp_path):
    from betmodel.historical_suggestions import current_combinations
    app,evidence=seeded(tmp_path)
    assert current_combinations(app.engine,app.results['2'],NOW+timedelta(days=2)) == []
    with session_factory(app.engine).begin() as session:
        session.add(OddsSnapshot(fixture_id=evidence['matches'][0]['fixture_id'],source='test',
            bookmaker='Book',market_key='TOTAL_GOALS_OVER',selection='Over 0.5',line=.5,
            decimal_odds=1.6,source_timestamp=NOW.replace(tzinfo=None),
            received_timestamp=(NOW+timedelta(seconds=1)).replace(tzinfo=None)))
    assert current_combinations(app.engine,app.results['2'],NOW) == []


def test_analyze_has_no_unpriced_fallback(tmp_path,monkeypatch):
    from betmodel.accuracy_policy import analyze_evidence
    app,evidence=seeded(tmp_path)
    monkeypatch.setattr('betmodel.team_insights.evidence_for',lambda *a,**kw:evidence)
    with session_factory(app.engine).begin() as session:
        session.query(OddsSnapshot).delete()
    items,report=analyze_evidence(app.engine,(NOW,NOW+timedelta(days=1)),NOW)
    assert items == {'2':[],'3':[]}
    assert 'historical_slips' not in report
