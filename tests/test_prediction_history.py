from datetime import datetime, timezone
from betmodel.dashboard import Dashboard, utc_window
from betmodel.performance import saved_combinations, performance_summary

def test_history_filters_creation_day_and_excludes_pending_from_win_rate(tmp_path):
    from betmodel.performance import prediction_history
    app=Dashboard(tmp_path)
    performance_summary(app.engine)
    with app.engine.begin() as c:
        for i,(hour,outcome) in enumerate([(13,'won'),(14,'won'),(15,'lost'),(16,None)]):
            c.execute(saved_combinations.insert().values(identity=str(i),mode='model',target='2',
                created_at=datetime(2026,9,17,hour),legs=[],outcome=outcome,payout=2 if outcome=='won' else 0))
    window=utc_window('2026-09-18',-600,-600)
    result=prediction_history(app.engine,window,'model',1,2)
    assert result['total']==3 and len(result['items'])==2
    assert result['summary']['2']['win_rate']==.5
    assert result['summary']['2']['pending']==1
    assert performance_summary(app.engine)['model']['2']['win_rate']==2/3
    assert prediction_history(app.engine,window,'odds-only')['total']==0
