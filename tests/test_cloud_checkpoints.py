from datetime import datetime,timezone,timedelta
import pytest
from betmodel.dashboard import Dashboard
from betmodel.state_store import cached_provider_request,save_state,quota_key


def test_metered_response_survives_lost_files(tmp_path):
    app=Dashboard(tmp_path)
    calls=[]
    def fetch():calls.append(True);return [{'fixture':{'id':123}}]
    assert cached_provider_request(app.engine,'private-key','/fixtures',{'id':'123'},fetch)==fetch_result()
    app.engine.dispose()
    second=Dashboard(tmp_path)
    assert cached_provider_request(second.engine,'private-key','/fixtures',{'id':'123'},fetch)==fetch_result()
    assert len(calls)==1
    from sqlalchemy import select
    from betmodel.state_store import state
    with second.engine.connect() as c:assert 'private-key' not in str(c.execute(select(state)).all())

def fetch_result():return [{'fixture':{'id':123}}]

def test_expired_quota_not_reused(tmp_path,monkeypatch):
    monkeypatch.setenv('API_FOOTBALL_KEY','private-key')
    app=Dashboard(tmp_path)
    save_state(app.engine,quota_key(app.key),{'quota':{'remaining':0},'observed':datetime.now(timezone.utc).isoformat()},datetime.now(timezone.utc)-timedelta(seconds=1))
    assert Dashboard(tmp_path).quota is None


def test_provider_quota_saved_even_on_error(tmp_path):
    import httpx
    from betmodel.providers.api_football import ApiFootballClient
    from betmodel.state_store import load_state
    app=Dashboard(tmp_path)
    http=httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(429,
        headers={'x-ratelimit-requests-remaining':'0'},json={'errors':{'limit':'reached'}})))
    client=ApiFootballClient('private-key',http=http,checkpoint_engine=app.engine)
    with pytest.raises(httpx.HTTPStatusError):client._get('/fixtures',{'date':'2026-09-19'})
    assert load_state(app.engine,quota_key('private-key'))['quota']['remaining']==0
