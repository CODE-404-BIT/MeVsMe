from datetime import datetime, timezone
from betmodel.dashboard import Dashboard


def test_public_parser_requires_completed_result_and_preserves_competition():
    from betmodel.public_history import parse_results
    html='''<a class="matches-list-match" href="/football/matches/match123_A-B-online">
    <time datetime="2026-09-13T00:00:00+10:00"></time><span class="match-result-status loser"></span>
    <span class="team team1"><span>A</span></span><span class="score has-score">0:2</span>
    <span class="team team2"><span>B</span></span><abbr title="Armenia / Premier League">Premier League</abbr></a>'''
    rows=parse_results(html,datetime(2026,9,18,tzinfo=timezone.utc))
    assert len(rows)==1
    assert rows[0]['home']=='A' and rows[0]['away']=='B'
    assert rows[0]['date']=='2026-09-12'
    assert rows[0]['competition']=='Armenia / Premier League'
    assert parse_results(html.replace('match-result-status loser','live'),datetime(2026,9,18,tzinfo=timezone.utc))==[]
    assert parse_results(html,datetime(2026,9,1,tzinfo=timezone.utc))==[]


def test_country_scope_never_maps_unknown_premier_league_to_england():
    import pandas as pd
    from betmodel.team_insights import competition_history
    frame=pd.DataFrame([{'competition':'E0','competition_name':'E0','home_team':'arsenal','away_team':'chelsea'},
        {'competition':'public:Armenia / Premier League','competition_name':'Premier League','home_team':'gandzasar','away_team':'fc urartu'}])
    scoped=competition_history(frame,'Premier League','Gandzasar','FC Urartu')
    assert set(scoped.competition)=={'public:Armenia / Premier League'}
    assert competition_history(frame,'Premier League','Unknown A','Unknown B').empty


def test_public_import_is_idempotent_and_sources_remain_auditable(tmp_path):
    from betmodel.public_history import import_public_results
    from betmodel.team_insights import load_history
    app=Dashboard(tmp_path)
    rows=[{'url':'https://www.live-result.com/football/matches/match123_A-B-online',
        'competition':'Armenia / Premier League','date':'2026-09-12','home':'Gandzasar','away':'Urartu',
        'home_goals':0,'away_goals':2}]
    import_public_results(app.engine,rows);import_public_results(app.engine,rows)
    history=load_history(app.engine,datetime(2026,9,18,tzinfo=timezone.utc))
    assert len(history)==1
    assert history.iloc[0].away_team=='fc urartu'
    assert history.iloc[0].source==rows[0]['url']
