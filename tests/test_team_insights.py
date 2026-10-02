from datetime import date, datetime, timezone, timedelta
import pandas as pd
from betmodel.team_insights import historical_patterns, team_key, predict_match


def history():
    return pd.DataFrame([{'date':pd.Timestamp(2026,1,1)+pd.Timedelta(days=i),'home_team':'Arsenal','away_team':'Chelsea',
        'home_goals':2,'away_goals':1,'home_corners':None,'away_corners':None,'source':'test','competition':'E0'} for i in range(60)])


def test_perfect_records_are_not_guaranteed_forecasts_and_missing_stats_excluded():
    results=historical_patterns(history(),'Arsenal','Chelsea')
    perfect=[r for r in results if r['hits']==r['trials']]
    assert perfect
    assert all(r['posterior_mean']<1 for r in perfect)
    assert all(r['trials']>=5 for r in perfect)
    assert not any('corners' in r['label'].lower() for r in results)


def test_team_identity_preserves_womens_and_youth_squads():
    assert team_key('England U20 W') != team_key('England')
    assert team_key('England W') != team_key('England')
    assert team_key('Manchester United') == team_key('Man United')


def test_unknown_teams_have_no_prediction():
    result=predict_match(history(),'Unknown','Chelsea')
    assert result['available'] is False
    assert 'probabilities' not in result


def test_forecast_includes_ranked_correct_scores():
    result=predict_match(history(),'Arsenal','Chelsea')
    assert result['available'] is True
    assert result['correct_scores']
    assert len(result['correct_scores']) == 5
    assert result['correct_scores'][0]['probability'] >= result['correct_scores'][-1]['probability']


def test_model_cutoff_allows_current_updates_but_caps_historical_queries():
    from betmodel.team_insights import _forecast_model_cutoff
    now=datetime(2026,9,18,12,tzinfo=timezone.utc)
    start=now.replace(hour=0)
    assert _forecast_model_cutoff((start,start+timedelta(days=1)),now+timedelta(hours=3),now)==now
    past=start-timedelta(days=10)
    assert _forecast_model_cutoff((past,past+timedelta(days=1)),None,now)==past+timedelta(days=1)
    assert _forecast_model_cutoff((past,past+timedelta(days=1)),past.replace(tzinfo=None),now)==past
