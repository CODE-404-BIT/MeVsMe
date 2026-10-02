from pathlib import Path
from betmodel.dashboard import Dashboard
from test_dashboard import seed_database

def test_history_cards_do_not_invent_probability_for_small_samples(tmp_path):
    app=Dashboard(tmp_path);seed_database(app.engine)
    cards=app.matches('2026-09-17',0,0)['matches']
    assert cards
    assert all('confidence' in c and c['confidence'] is None for c in cards)
    assert all(c['confidence_reason'] for c in cards)
