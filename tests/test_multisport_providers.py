from datetime import datetime,timezone
import httpx
import pytest
from betmodel.config import Settings
from betmodel.db import create_engine_for,init_db


def test_api_sports_preserves_hockey_overtime_scope():
    from betmodel.providers.api_sports import parse_games
    raw={'id':1,'date':'2026-10-01T18:00:00Z','status':{'short':'AOT'},
         'league':{'id':57,'name':'NHL','season':2026},
         'teams':{'home':{'id':1,'name':'A'},'away':{'id':2,'name':'B'}},
         'scores':{'home':3,'away':2}}
    rows=parse_games('icehockey',[raw])
    assert rows[0]['scope']=='including_overtime'
    assert rows[0]['home_score']==3 and rows[0]['status']=='FINISHED'
    raw['status']['short']='UNKNOWN'
    assert parse_games('icehockey',[raw])==[]


def test_basketball_missing_final_score_is_not_fabricated():
    from betmodel.providers.api_sports import parse_games
    raw={'id':1,'date':'2026-10-01T18:00:00Z','status':{'short':'FT'},
         'league':{'id':12,'name':'League'},
         'teams':{'home':{'id':1,'name':'A'},'away':{'id':2,'name':'B'}},
         'scores':{'home':{'total':None},'away':{'total':99}}}
    assert parse_games('basketball',[raw])==[]


def test_odds_parser_only_uses_complete_two_way_winner_market():
    from betmodel.providers.odds_api import parse_odds
    raw={'id':'a','sport_key':'basketball_nba','commence_time':'2026-10-02T20:00:00Z',
         'home_team':'A','away_team':'B','bookmakers':[{'key':'book','markets':[
          {'key':'h2h','last_update':'2026-10-02T10:00:00Z','outcomes':[{'name':'A','price':1.5},{'name':'B','price':2.8}]}]}]}
    events,quotes=parse_odds([raw],'basketball')
    assert len(events)==1 and len(quotes)==2
    assert quotes[0]['scope']=='including_overtime'
    raw['bookmakers'][0]['markets'][0]['outcomes'].pop()
    assert parse_odds([raw],'basketball')[1]==[]


def test_missing_key_never_calls_provider_or_leaks_secret(tmp_path):
    from betmodel.providers.sport_http import SportHTTP
    engine=create_engine_for(Settings(tmp_path));init_db(engine)
    calls=[]
    with httpx.Client(transport=httpx.MockTransport(lambda req:calls.append(req))) as http:
        client=SportHTTP(engine,http,'basketball','',datetime(2026,10,2,tzinfo=timezone.utc))
        with pytest.raises(ValueError,match='not configured'):client.get('/games',{'date':'2026-10-02'})
    assert calls==[]


def test_budget_cache_survives_new_client_and_redacts_provider_errors(tmp_path):
    from betmodel.providers.sport_http import SportHTTP
    engine=create_engine_for(Settings(tmp_path));init_db(engine);calls=[]
    def respond(req):
        calls.append(req)
        return httpx.Response(200,json={'response':[]},headers={'x-ratelimit-requests-remaining':'79'})
    now=datetime(2026,10,2,tzinfo=timezone.utc)
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        for _ in range(2):SportHTTP(engine,http,'basketball','private-key',now).get('/games',{'date':'2026-10-02'})
    assert len(calls)==1
