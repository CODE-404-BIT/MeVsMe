import threading
import httpx
import pytest
from betmodel.web import make_server


@pytest.fixture
def server(tmp_path):
    server = make_server(tmp_path, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def test_http_requires_local_host_and_write_token(server):
    with httpx.Client(base_url=server, trust_env=False) as client:
        assert client.get("/api/status", headers={"Host": "evil.example"}).status_code == 403
        assert client.post("/api/settings", json={"key": "secret"}).status_code == 403
        token = client.get("/api/status").json()["token"]
        assert client.post("/api/settings", json={"key": "secret"}, headers={
            "X-Dashboard-Token": token, "Origin": "https://evil.example"}).status_code == 403
        assert client.post("/api/settings", json={"key": "secret"}, headers={
            "X-Dashboard-Token": token}).status_code == 200
        assert "secret" not in client.get("/api/status").text
        assert client.get("/api/matches?date=bad").status_code == 400
        assert client.get("/../pyproject.toml").status_code == 404
        assert client.get("/").status_code == 200
        assert client.get('/api/performance').json()['cohorts']['model']['2']['win_rate'] is None
        assert client.post('/api/price-combinations',json={'date':'2026-09-18'}).status_code==403
        prices=client.post('/api/price-combinations',json={'date':'2026-09-18','target':'2'},headers={'X-Dashboard-Token':token})
        assert prices.status_code==200
        assert prices.json()['total']==0
        assert client.get('/performance.js').status_code==200
