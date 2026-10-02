from datetime import datetime, timezone
import pytest
from betmodel.config import Settings
from betmodel.db import create_engine_for, init_db

NOW=datetime(2026,10,2,10,tzinfo=timezone.utc)


def event(sport='basketball',**changes):
    return dict(dict(sport=sport,provider='test',provider_id='1',competition='League',
        home='A',away='B',home_id='a',away_id='b',start='2026-10-02T20:00:00Z',
        status='SCHEDULED',scope='including_overtime',source='https://example.com'),**changes)


def test_sport_storage_is_idempotent_and_does_not_collide(tmp_path):
    from betmodel.multisport_store import upsert_events, load_events
    engine=create_engine_for(Settings(tmp_path));init_db(engine)
    upsert_events(engine,[event(),event('icehockey')])
    upsert_events(engine,[event()])
    assert len(load_events(engine))==2
    assert {r['sport'] for r in load_events(engine)}=={'basketball','icehockey'}


def test_incomplete_or_unknown_result_cannot_be_settled(tmp_path):
    from betmodel.multisport_store import upsert_events
    engine=create_engine_for(Settings(tmp_path));init_db(engine)
    with pytest.raises(ValueError):upsert_events(engine,[event(status='FINISHED')])
    with pytest.raises(ValueError):upsert_events(engine,[event(sport='made-up')])
    with pytest.raises(ValueError):upsert_events(engine,[event(provider_id=None)])
    with pytest.raises(ValueError):upsert_events(engine,[event(home_id=None)])


def test_ranking_requires_validated_probability_and_unique_future_events():
    from betmodel.multisport_recommendations import rank_picks
    rows=[dict(event(),event_key=str(i),probability=.7+i/1000,validated=True,
               sample_home=20,sample_away=20,latest_home='2026-10-01',latest_away='2026-10-01') for i in range(12)]
    rows += [dict(rows[-1]),dict(rows[0],event_key='bad',probability=1),
             dict(rows[0],event_key='unvalidated',validated=False)]
    result=rank_picks(rows,NOW)
    assert len(result)==10
    assert len({r['event_key'] for r in result})==10
    assert result[0]['event_key']=='11'
    assert all(0<r['probability']<1 for r in result)
    assert not rank_picks([dict(rows[0],start=NOW.isoformat())],NOW)
    assert not rank_picks([dict(rows[0],latest_home='2025-01-01')],NOW)


def test_history_rate_is_not_a_future_probability():
    from betmodel.multisport_recommendations import winner_evidence
    records=[dict(event(status='FINISHED',provider_id=str(i),start=f'2026-09-{i+1:02}T12:00:00Z'),
                  home_score=3,away_score=1) for i in range(10)]
    evidence=winner_evidence(event(),records,NOW)
    assert any(r['hits']==10 and r['trials']==10 for r in evidence)
    assert all('probability' not in r for r in evidence)
    assert not winner_evidence(event(scope='regulation'),records,NOW)


def test_model_does_not_promote_without_chronological_evidence():
    from betmodel.multisport_models import evaluate_winner_model
    result=evaluate_winner_model([], 'basketball', NOW)
    assert result['validated'] is False
    assert result['matches']==0


def test_future_result_cannot_change_model_and_scope_mixing_is_rejected():
    from betmodel.multisport_models import evaluate_winner_model
    rows=[event(status='FINISHED',home_score=100,away_score=90,start='2099-01-01T12:00:00Z')]
    assert evaluate_winner_model(rows,'basketball',NOW)==evaluate_winner_model([],'basketball',NOW)
    rows=[event(status='FINISHED',home_score=100,away_score=90,start='2026-09-01T12:00:00Z'),
          event(status='FINISHED',home_score=100,away_score=90,start='2026-09-02T12:00:00Z',scope='regulation')]
    with pytest.raises(ValueError,match='single competition'):evaluate_winner_model(rows,'basketball',NOW)


def test_forecast_attaches_only_current_exact_quote(tmp_path):
    from betmodel.multisport_store import upsert_quotes,event_key
    from betmodel.multisport_recommendations import attach_prices
    engine=create_engine_for(Settings(tmp_path));init_db(engine)
    row=dict(event(),event_key=event_key(event()),market='winner',selection='A')
    quote=dict(event_key=row['event_key'],bookmaker='Book',market='winner',selection='A',
        line=None,scope='including_overtime',odds=1.6,updated=NOW.isoformat())
    upsert_quotes(engine,[quote])
    assert attach_prices(engine,[row],NOW)[0]['odds']==1.6
    from datetime import timedelta
    assert 'odds' not in attach_prices(engine,[dict(row,odds=1.6)],NOW+timedelta(days=2))[0]
