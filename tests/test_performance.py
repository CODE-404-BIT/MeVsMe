from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from betmodel.db import init_db
from betmodel.models import Fixture, TeamMatchStat, ProviderMapping
from betmodel.performance import record_combinations, settle_saved, performance_summary, pending_fixture_ids

NOW = datetime(2026, 9, 18, 10)


@pytest.fixture
def engine():
    engine = create_engine('sqlite://')
    init_db(engine)
    with Session(engine) as s:
        for i in range(1, 4):
            s.add(Fixture(id=i, source='test', provider_id=str(i), competition='test', season='2026',
                          kickoff=NOW + timedelta(hours=i), home_team=f'H{i}', away_team=f'A{i}', status='SCHEDULED'))
        s.commit()
    return engine


def combo(key='MATCH_HOME', line=None, odds=2., fid=1, probability=.6):
    return {'legs': [{'fixture_id': fid, 'market_key': key, 'selection': key, 'line': line,
                      'odds': odds, 'bookmaker': 'Test'}], 'joint_probability': probability, 'model_version': 'v1'}


def finish(engine, fid=1, home=2, away=0, status='FINISHED'):
    with Session(engine) as s:
        s.get(Fixture, fid).status = status
        for is_home, goals in [(1, home), (0, away)]:
            s.add(TeamMatchStat(fixture_id=fid, team_name=f'H{fid}' if is_home else f'A{fid}', is_home=is_home, goals=goals))
        s.commit()


def stats(engine):
    return performance_summary(engine)['model']['2']


@pytest.mark.parametrize('family,attribute',[('CORNERS','corners'),('CARDS','cards'),('SHOTS','shots'),('SOT','shots_on_target'),('GOALS','goals')])
def test_team_market_settles_own_team_not_combined_total(engine,family,attribute):
    item=combo()
    item['legs'][0].update(market_key='TEAM_'+family+'_OVER',selection='H1 Over 2.5',line=2.5)
    assert record_combinations(engine,'2','historical',[item],NOW)==1
    with Session(engine) as s:
        s.get(Fixture,1).status='FINISHED'
        s.add(TeamMatchStat(fixture_id=1,team_name='H1',is_home=1,**{attribute:2}))
        s.add(TeamMatchStat(fixture_id=1,team_name='A1',is_home=0,**{attribute:10}))
        s.commit()
    assert settle_saved(engine)==1
    assert performance_summary(engine)['historical']['2']['lost']==1


def test_dedup_frozen_prices_and_separate_cohorts(engine):
    assert record_combinations(engine, 2, 'model', [combo()], NOW) == 1
    assert record_combinations(engine, 2, 'model', [combo(odds=4., probability=.9)], NOW) == 0
    assert record_combinations(engine, 3, 'model', [combo()], NOW) == 1
    assert record_combinations(engine, 2, 'odds-only', [combo(probability=None)], NOW) == 1
    assert pending_fixture_ids(engine) == [1]
    finish(engine)
    assert settle_saved(engine) == 3
    assert settle_saved(engine) == 0
    assert stats(engine)['roi'] == 1.
    assert stats(engine)['brier'] == pytest.approx(.16)
    assert performance_summary(engine)['odds-only']['2']['brier'] is None


@pytest.mark.parametrize('mutation', ['late', 'missing', 'duplicate', 'invalid_odds', 'postponed'])
def test_rejects_invalid_or_nonprospective_records(engine, mutation):
    item = combo()
    now = NOW
    if mutation == 'late': now = NOW + timedelta(hours=1)
    if mutation == 'missing': item['legs'][0]['fixture_id'] = 99
    if mutation == 'duplicate': item['legs'] *= 2
    if mutation == 'invalid_odds': item['legs'][0]['odds'] = float('nan')
    if mutation == 'postponed':
        with Session(engine) as s:
            s.get(Fixture, 1).status = 'POSTPONED'
            s.commit()
    assert record_combinations(engine, 2, 'model', [item], now) == 0
    assert stats(engine)['generated'] == 0
    assert stats(engine)['win_rate'] is None


@pytest.mark.parametrize('key,line,home,away,outcome,payout', [
    ('MATCH_HOME', None, 2, 0, 'won', 2.), ('MATCH_DRAW', None, 2, 0, 'lost', 0.),
    ('BTTS_YES', None, 2, 1, 'won', 2.), ('BTTS_NO', None, 2, 1, 'lost', 0.),
    ('TOTAL_GOALS_OVER', 2.0, 2, 0, 'void', 1.),
    ('TOTAL_GOALS_OVER', 2.25, 2, 0, 'partial', .5),
    ('TOTAL_GOALS_OVER', 1.75, 2, 0, 'partial', 1.5),
    ('TOTAL_GOALS_UNDER', 2.25, 2, 0, 'partial', 1.5),
    ('TOTAL_GOALS_UNDER', 1.75, 2, 0, 'partial', .5),
])
def test_settlement(engine, key, line, home, away, outcome, payout):
    record_combinations(engine, 2, 'model', [combo(key, line)], NOW)
    finish(engine, home=home, away=away)
    assert settle_saved(engine) == 1
    result = stats(engine)
    assert result[outcome] == 1
    assert result['roi'] == payout - 1
    assert result['brier_sample_size'] == int(outcome in {'won', 'lost'})


@pytest.mark.parametrize('status,key,expected', [('POSTPONED', 'MATCH_HOME', 0), ('FINISHED', 'TEAM_SHOTS_OVER', 0), ('CANCELLED', 'MATCH_HOME', 1)])
def test_unavailable_stays_pending_and_explicit_cancellation_refunds(engine, status, key, expected):
    record_combinations(engine, 2, 'model', [combo(key, 2.5)], NOW)
    finish(engine, status=status)
    assert settle_saved(engine) == expected
    assert stats(engine)['pending'] == 1 - expected


def test_partial_accumulator_multiplies_returns_excludes_binary_score(engine):
    item = combo('TOTAL_GOALS_OVER', 1.75)
    item['legs'] += combo(fid=2)['legs']
    record_combinations(engine, 2, 'model', [item], NOW)
    finish(engine)
    assert settle_saved(engine) == 0
    finish(engine, fid=2)
    settle_saved(engine)
    assert stats(engine)['partial'] == 1
    assert stats(engine)['roi'] == 2.
    assert stats(engine)['win_rate'] is None
    assert stats(engine)['brier'] is None


def test_reordered_legs_dedup_but_bookmaker_is_distinct(engine):
    item = combo()
    item['legs'] += combo(fid=2)['legs']
    assert record_combinations(engine, 2, 'model', [item], NOW) == 1
    item['legs'].reverse()
    assert record_combinations(engine, 2, 'model', [item], NOW) == 0
    item['legs'][0]['bookmaker'] = 'Other'
    assert record_combinations(engine, 2, 'model', [item], NOW) == 1


def test_explicit_available_corner_totals_can_settle(engine):
    record_combinations(engine, 2, 'model', [combo('TOTAL_CORNERS_OVER', 8.5)], NOW)
    finish(engine)
    assert settle_saved(engine) == 0
    with Session(engine) as s:
        for row in s.query(TeamMatchStat).all():
            row.corners = 5
        s.commit()
    assert settle_saved(engine) == 1
    assert stats(engine)['won'] == 1


def test_missing_final_goals_and_invalid_probability_are_not_fabricated(engine):
    record_combinations(engine, 2, 'model', [combo(probability=float('nan'))], NOW)
    finish(engine, home=None)
    assert settle_saved(engine) == 0
    with Session(engine) as s:
        s.query(TeamMatchStat).filter_by(is_home=1).one().goals = 2
        s.commit()
    settle_saved(engine)
    assert stats(engine)['brier'] is None
    assert stats(engine)['brier_sample_size'] == 0


def test_api_cancellation_requires_verified_provider_marker(engine):
    record_combinations(engine, 2, 'model', [combo()], NOW)
    with Session(engine) as s:
        fixture = s.get(Fixture, 1)
        fixture.source = 'api-football'
        fixture.status = 'CANCELLED'
        s.commit()
    assert settle_saved(engine) == 0
    with Session(engine) as s:
        s.add(ProviderMapping(source='api-football', entity_type='fixture_final_status', provider_key='1', canonical_key='CANC'))
        s.commit()
    assert settle_saved(engine) == 1
    assert stats(engine)['void'] == 1


def test_leg_probability_and_version_are_frozen_without_affecting_identity(engine):
    from betmodel.performance import saved_combinations
    from sqlalchemy import select
    item = combo()
    item['legs'][0].update(probability=.6, model_version='leg-v1')
    assert record_combinations(engine, 2, 'model', [item], NOW) == 1
    item['legs'][0].update(probability=.8, model_version='leg-v2')
    assert record_combinations(engine, 2, 'model', [item], NOW) == 0
    with engine.connect() as conn:
        snapshot = conn.execute(select(saved_combinations.c.legs)).scalar_one()[0]
    assert snapshot['probability'] == .6
    assert snapshot['model_version'] == 'leg-v1'
