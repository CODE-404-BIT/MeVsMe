from datetime import datetime, timezone
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from betmodel import learning


def history(n=240):
    rng = np.random.default_rng(41)
    return pd.DataFrame({'date': pd.date_range('2025-01-01', periods=n),
        'home_team': ['a'+str(i%12) for i in range(n)],
        'away_team': ['a'+str((i*5+1)%12) for i in range(n)],
        'home_goals': rng.poisson(1.5,n), 'away_goals':rng.poisson(1.1,n),
        'competition':'E0'})


def test_cold_start_keeps_forecast_and_reports_samples(monkeypatch):
    engine=create_engine('sqlite://')
    monkeypatch.setattr(learning,'load_history',lambda *_:history(30))
    result=learning.update_models(engine)
    assert result['promoted']==0
    assert 'insufficient' in result['latest']['reason'].lower()
    forecast={'available':True,'probabilities':{'x':.4}}
    actual=learning.apply_learned_forecast(engine,history(30),'a0','a1',forecast,datetime.now(timezone.utc))
    assert actual['probabilities']==forecast['probabilities']
    assert actual['model_version']=='poisson-baseline-v1'


def test_chronological_evaluation_persists_and_does_not_repeat(monkeypatch,tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'learning.db'))
    monkeypatch.setattr(learning,'load_history',lambda *_:history())
    first=learning.update_models(engine)
    latest=first['latest']
    assert latest['development_end'] < latest['evaluation_start']
    assert latest['training_end'] < latest['development_start']
    assert latest['evaluation_matches']>=40
    assert latest['candidate']['brier'] is not None
    if latest['status']=='promoted':
        assert latest['candidate']['brier'] < latest['incumbent']['brier']
        assert latest['candidate']['log_loss'] < latest['baseline']['log_loss']
    second=learning.update_models(engine)
    assert second['attempts']==first['attempts']
    assert learning.learning_summary(create_engine('sqlite:///'+str(tmp_path/'learning.db')))['latest']==latest


def test_future_champion_cannot_change_past_forecasts(monkeypatch):
    engine=create_engine('sqlite://')
    pool=history()
    pool['home_goals']=np.random.default_rng(0).poisson(np.where(np.arange(240)%12<6,2.5,.7))
    monkeypatch.setattr(learning,'load_history',lambda *_:pool)
    assert learning.update_models(engine,datetime(2026,1,1))['promoted']==1
    original={'available':True,'probabilities':{'sentinel':.123}}
    result=learning.apply_learned_forecast(engine,history(),'a0','a1',original,datetime(2025,2,1,tzinfo=timezone.utc))
    assert result['probabilities']==original['probabilities']
    assert result['model_version']=='poisson-baseline-v1'
    future=learning.apply_learned_forecast(engine,pool,'a0','a1',original,datetime(2026,1,2,tzinfo=timezone.utc))
    assert future['model_version']!='poisson-baseline-v1'
    assert future['validation']['market']=='Over 2.5 goals'
    assert 0<future['probabilities']['TOTAL_GOALS_OVER:2.5']<1
    unknown=learning.apply_learned_forecast(engine,pool,'new team','a1',original,datetime(2026,1,2,tzinfo=timezone.utc))
    assert unknown['model_version']=='poisson-baseline-v1'
    assert unknown['probabilities']==original['probabilities']


def test_new_history_cannot_reuse_previous_holdout(monkeypatch):
    engine=create_engine('sqlite://')
    monkeypatch.setattr(learning,'load_history',lambda *_:history())
    learning.update_models(engine)
    monkeypatch.setattr(learning,'load_history',lambda *_:history(250))
    waiting=learning.update_models(engine)
    assert waiting['attempts']==1
    assert waiting['waiting'][0]['new_matches']==10
    assert '40' in waiting['waiting'][0]['reason']
    monkeypatch.setattr(learning,'load_history',lambda *_:history(280))
    latest=learning.update_models(engine)
    assert latest['attempts']==2
    assert latest['latest']['evaluation_start']>'2025-08-28'
