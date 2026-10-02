import re
import pytest
from werkzeug.security import generate_password_hash
from betmodel.cloud import create_app
from betmodel.cloud_config import CloudSettings
from betmodel.dashboard import Dashboard

ORIGIN = 'https://dashboard.example'

@pytest.fixture
def client(tmp_path):
    config = CloudSettings('unused', ORIGIN, generate_password_hash('test-password'), 's'*48)
    app = create_app(tmp_path, config, dashboard=Dashboard(tmp_path))
    app.config['TESTING'] = True
    return app.test_client()

def login(client, password='test-password'):
    page = client.get('/login', base_url=ORIGIN)
    token = re.search(r'name="csrf" value="([^"]+)"', page.text)[1]
    return client.post('/login', base_url=ORIGIN, data={'csrf':token,'password':password}, headers={'Origin':ORIGIN})

def test_private_api_requires_session(client):
    for path in ['/api/status','/api/matches?date=2026-09-19','/api/performance','/api/recommendations?date=2026-10-02']:
        assert client.get(path, base_url=ORIGIN).status_code == 401
    assert client.post('/api/jobs', base_url=ORIGIN, json={}).status_code == 401
    assert client.get('/healthz', base_url=ORIGIN).status_code == 200
    assert client.get('/', base_url=ORIGIN).status_code == 302

def test_login_csrf_host_origin_logout(client):
    assert client.get('/login', base_url='https://evil.example').status_code == 403
    assert client.post('/login',base_url=ORIGIN,data={'password':'test-password'},headers={'Origin':ORIGIN}).status_code==403
    assert login(client,'wrong').status_code == 401
    response = login(client)
    assert response.status_code == 302
    cookie = response.headers['Set-Cookie']
    assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=Lax' in cookie
    status = client.get('/api/status', base_url=ORIGIN).json
    token = status['token']
    headers = {'Origin':ORIGIN,'X-Dashboard-Token':token}
    assert client.post('/api/settings',base_url=ORIGIN,json={'key':'test-key'},headers=headers).status_code==200
    assert client.post('/api/settings',base_url=ORIGIN,json={'key':'x'},headers={'X-Dashboard-Token':token,'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/settings',base_url=ORIGIN,json={'key':'x'}).status_code==403
    assert client.get('/../data/app.db',base_url=ORIGIN).status_code==404
    assert client.post('/api/settings',base_url=ORIGIN,data='x'*5000,headers=headers).status_code==413
    assert client.post('/logout',base_url=ORIGIN,headers=headers).status_code==200
    assert client.get('/api/status',base_url=ORIGIN).status_code==401

def test_login_limit_cannot_be_bypassed_with_forwarded_address(client):
    for _ in range(10):
        assert login(client,'wrong').status_code == 401
    assert client.get('/login',base_url=ORIGIN).status_code == 200
    with client.session_transaction(base_url=ORIGIN) as session: token=session['csrf']
    assert client.post('/login',base_url=ORIGIN,data={'csrf':token,'password':'test-password'},
        headers={'Origin':ORIGIN,'X-Forwarded-For':'1.2.3.4'}).status_code==429


def test_revoked_cookie_cannot_be_replayed_and_token_alone_fails(client):
    login(client)
    cookie=client.get_cookie('session',domain='dashboard.example').value
    token=client.get('/api/status',base_url=ORIGIN).json['token']
    stranger=client.application.test_client()
    assert stranger.post('/api/jobs',base_url=ORIGIN,json={},headers={'Origin':ORIGIN,'X-Dashboard-Token':token}).status_code==401
    client.post('/logout',base_url=ORIGIN,headers={'Origin':ORIGIN,'X-Dashboard-Token':token})
    stranger.set_cookie('session',cookie,domain='dashboard.example')
    assert stranger.get('/api/status',base_url=ORIGIN).status_code==401


def test_expired_session_is_rejected(client):
    from datetime import datetime,timedelta,timezone
    from betmodel.state_store import save_state
    login(client)
    with client.session_transaction(base_url=ORIGIN) as session:sid=session['sid']
    save_state(client.application.extensions['dashboard'].engine,'session:'+sid,{'owner':True},
        datetime.now(timezone.utc)-timedelta(seconds=1))
    assert client.get('/api/status',base_url=ORIGIN).status_code==401
