from datetime import datetime,timezone,timedelta
import httpx
from betmodel.dashboard import Dashboard
from betmodel.api_routes import dispatch_api

NOW=datetime(2026,10,2,10,tzinfo=timezone.utc)


def test_missing_keys_produce_coverage_without_outbound_calls(tmp_path):
    from betmodel.multisport_refresh import refresh_sports
    app=Dashboard(tmp_path);calls=[]
    with httpx.Client(transport=httpx.MockTransport(lambda req:calls.append(req))) as http:
        report=refresh_sports(app.engine,(NOW,NOW+timedelta(days=1)),{},NOW,http=http)
    assert calls==[]
    assert set(report['sports'])=={'football','basketball','tennis','icehockey'}
    assert report['sports']['basketball']['status']=='missing_key'
    assert report['sports']['tennis']['history_status']=='unavailable'


def test_recommendation_endpoint_is_honestly_empty_without_data(tmp_path):
    app=Dashboard(tmp_path)
    status,payload=dispatch_api(app,'GET','/api/recommendations',{'date':'2026-10-02'})
    assert status==200
    assert payload['items']==[] and payload['stale'] is True
    assert set(payload['coverage'])=={'football','basketball','tennis','icehockey'}


def test_sport_combination_needs_exact_perfect_record_and_prices():
    from betmodel.multisport_recommendations import build_sport_combinations
    rows=[]
    for i in range(2):
        rows.append(dict(event_key=str(i),fixture='A v B',kickoff='2026-10-02T20:00:00Z',
            bookmaker='Book',selection='A',odds=1.45,updated=NOW.isoformat(),market='winner',scope='including_overtime',
            patterns=[{'hits':5,'trials':5,'from':'2026-09-01','to':'2026-10-01'}]))
    assert len(build_sport_combinations(rows,NOW)['2'])==1
    rows[0]['patterns'][0]['hits']=4
    assert build_sport_combinations(rows,NOW)=={'2':[],'3':[]}


def test_cancelled_event_disappears_from_cached_top_ten(tmp_path):
    from betmodel.multisport_store import upsert_events,event_key
    from betmodel.multisport_recommendations import recommendation_payload
    from betmodel.state_store import save_state
    app=Dashboard(tmp_path)
    row=dict(sport='basketball',provider='test',provider_id='1',competition='NBA',scope='including_overtime',
        home='A',away='B',home_id='a',away_id='b',start='2026-10-02T20:00:00Z',status='SCHEDULED')
    row['event_key']=event_key(row)
    upsert_events(app.engine,[row])
    saved=dict(row,validated=True,probability=.7,sample_home=20,sample_away=20,
               latest_home='2026-10-01',latest_away='2026-10-01')
    window=(NOW,NOW+timedelta(days=1))
    save_state(app.engine,'multisport-ranked:'+NOW.isoformat(),{'rows':[saved]})
    assert len(recommendation_payload(app.engine,window,NOW)['items'])==1
    upsert_events(app.engine,[dict(row,status='CANCELLED')])
    assert recommendation_payload(app.engine,window,NOW)['items']==[]


def test_repeated_refresh_uses_same_odds_cache_within_thirty_minutes(tmp_path):
    from betmodel.multisport_refresh import refresh_sports
    app=Dashboard(tmp_path);calls=[]
    def respond(request):
        calls.append(request.url.path)
        data=[{'key':'basketball_nba','active':True,'has_outrights':False}] if request.url.path.endswith('/sports') else []
        return httpx.Response(200,json=data)
    window=(NOW,NOW+timedelta(hours=14))
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        refresh_sports(app.engine,window,{'odds':'private-key'},NOW,http=http)
        refresh_sports(app.engine,window,{'odds':'private-key'},NOW+timedelta(minutes=1),http=http)
    assert calls.count('/v4/sports/basketball_nba/odds')==1


def test_season_cache_cannot_resurrect_cancelled_date_event(tmp_path):
    from betmodel.multisport_refresh import refresh_sports
    from betmodel.multisport_store import load_events
    app=Dashboard(tmp_path)
    def respond(request):
        return httpx.Response(200,json={'response':[{'id':1,'date':'2026-10-02T20:00:00Z',
            'league':{'id':1,'name':'League','season':2026},'scores':{},
            'status':{'short':'CANC' if 'date' in request.url.params else 'NS'},
            'teams':{'home':{'id':1,'name':'A'},'away':{'id':2,'name':'B'}}}]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        refresh_sports(app.engine,(NOW,NOW+timedelta(hours=14)),{'basketball':'private'},NOW,http=http)
    assert load_events(app.engine)[0]['status']=='CANCELLED'
