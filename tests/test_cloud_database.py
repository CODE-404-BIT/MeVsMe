import pytest
from betmodel.config import Settings
from betmodel.db import create_engine_for


def test_local_default_ignores_database_environment(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_URL','postgresql://invalid/db')
    assert create_engine_for(Settings(tmp_path)).dialect.name=='sqlite'


def test_cloud_requires_configuration():
    from betmodel.cloud_config import CloudSettings
    with pytest.raises(ValueError,match='DATABASE_URL'):
        CloudSettings.from_env({})


def test_explicit_database_setting(tmp_path):
    assert create_engine_for(Settings(tmp_path,database_url='sqlite://')).dialect.name=='sqlite'
@pytest.mark.parametrize('override', [
    {'DATABASE_URL':'sqlite:///private.db'},
    {'DATABASE_URL':'postgresql://owner:secret@host/db'},
    {'DATABASE_URL':'postgresql://owner:secret@host-pooler.neon.tech/db?sslmode=require'},
    {'PUBLIC_ORIGIN':'https://user:password@example.com'},
    {'PUBLIC_ORIGIN':'http://example.com'},
    {'PUBLIC_ORIGIN':'https://example.com/path'},
    {'PUBLIC_ORIGIN':'https://example.com:bad'},
    {'DASHBOARD_SECRET_KEY':'short'},
])
def test_cloud_rejects_unsafe_configuration_without_exposing_values(override):
    from betmodel.cloud_config import CloudSettings
    from werkzeug.security import generate_password_hash
    env={'DATABASE_URL':'postgresql://owner:secret@host/db?sslmode=require',
         'PUBLIC_ORIGIN':'https://example.com','DASHBOARD_PASSWORD_HASH':generate_password_hash('test'),
         'DASHBOARD_SECRET_KEY':'x'*40}
    env.update(override)
    with pytest.raises(ValueError) as error:CloudSettings.from_env(env)
    assert 'owner:secret' not in str(error.value)
