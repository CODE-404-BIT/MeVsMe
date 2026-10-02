from datetime import datetime, timedelta, timezone
import httpx
from betmodel.dashboard import Dashboard
from betmodel.db import session_factory
from betmodel.models import Fixture, TeamMatchStat
from sqlalchemy import select


def test_refresh_fetches_saved_fixture_id_and_preserves_fulltime_score(tmp_path):
    from betmodel.result_refresh import refresh_results
    from betmodel.providers.api_football import ApiFootballClient
    app = Dashboard(tmp_path)
    now = datetime(2026, 9, 18, tzinfo=timezone.utc)
    with session_factory(app.engine).begin() as s:
        f = Fixture(source='api-football', provider_id='100', competition='Cup', season='2026',
                    home_team='A', away_team='B', kickoff=(now-timedelta(days=2)).replace(tzinfo=None), status='SCHEDULED')
        s.add(f); s.flush(); fid = f.id
    def handle(request):
        assert request.url.params['id'] == '100'
        return httpx.Response(200, json={'response':[{'fixture':{'id':100,'date':'2026-09-16T00:00:00Z','status':{'short':'AET'}},
            'league':{'id':1,'name':'Cup','season':2026},'teams':{'home':{'name':'A'},'away':{'name':'B'}},
            'goals':{'home':4,'away':2},'score':{'fulltime':{'home':1,'away':1}}}]})
    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        report = refresh_results(app.engine, ApiFootballClient('test',http=http), [fid], now=now)
    assert report['updated'] == 1
    with session_factory(app.engine)() as s:
        assert [r.goals for r in s.scalars(select(TeamMatchStat).order_by(TeamMatchStat.is_home))] == [1,1]


def test_result_refresh_stops_at_daily_reserve(tmp_path):
    from betmodel.result_refresh import refresh_results
    app=Dashboard(tmp_path)
    class Client:
        def _get(self,*args):raise AssertionError('Quota reserve must prevent requests')
    report=refresh_results(app.engine,Client(),[1],known_quota={'remaining':20})
    assert report['requests']==0


def test_abandoned_is_not_automatically_voided(tmp_path):
    from betmodel.result_refresh import refresh_results
    from betmodel.providers.api_football import ApiFootballClient
    app=Dashboard(tmp_path)
    now=datetime.now(timezone.utc)
    with session_factory(app.engine).begin() as s:
        f=Fixture(source='api-football',provider_id='2',competition='C',season='2026',home_team='A',away_team='B',
                  kickoff=(now-timedelta(days=1)).replace(tzinfo=None),status='SCHEDULED')
        s.add(f);s.flush();fid=f.id
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'response':[
        {'fixture':{'id':2,'status':{'short':'ABD'}}}]}))) as http:
        refresh_results(app.engine,ApiFootballClient('test',http=http),[fid],now=now)
    with session_factory(app.engine)() as s:
        assert s.get(Fixture,fid).status=='ABANDONED'
