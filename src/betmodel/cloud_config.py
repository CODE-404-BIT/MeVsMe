"""Explicit cloud-only settings; invalid configuration never falls back to SQLite."""
from dataclasses import dataclass,field
from urllib.parse import urlsplit
from sqlalchemy.engine import make_url


@dataclass(frozen=True)
class CloudSettings:
    database_url: str=field(repr=False)
    public_origin: str
    password_hash: str=field(repr=False)
    secret_key: str=field(repr=False)

    @classmethod
    def from_env(cls,env):
        raw=env.get('DATABASE_URL','')
        try:
            url=make_url(raw)
            if url.drivername not in {'postgres','postgresql','postgresql+psycopg'} or not url.host or not url.database:
                raise ValueError()
            if url.query.get('sslmode') not in {'require','verify-ca','verify-full'}:raise ValueError()
            if '-pooler.' in url.host:raise ValueError()
            url=url.set(drivername='postgresql+psycopg')
        except Exception:raise ValueError('DATABASE_URL must specify a direct PostgreSQL connection with TLS') from None
        origin=env.get('PUBLIC_ORIGIN') or ('https://'+env['RENDER_EXTERNAL_HOSTNAME'] if env.get('RENDER_EXTERNAL_HOSTNAME') else '')
        try:
            parts=urlsplit(origin)
            _=parts.port
            if (parts.scheme!='https' or not parts.hostname or parts.username or parts.password or
                    parts.path not in {'','/'} or parts.query or parts.fragment or any(c.isspace() for c in origin)):
                raise ValueError()
        except ValueError:raise ValueError('PUBLIC_ORIGIN must be an HTTPS origin') from None
        password_hash=env.get('DASHBOARD_PASSWORD_HASH','')
        if not password_hash.startswith(('scrypt:','pbkdf2:sha256:')) or password_hash.count('$')!=2:
            raise ValueError('DASHBOARD_PASSWORD_HASH must be a Werkzeug password hash')
        secret=env.get('DASHBOARD_SECRET_KEY','')
        if len(secret)<32:raise ValueError('DASHBOARD_SECRET_KEY must have at least 32 characters')
        return cls(url.render_as_string(hide_password=False),origin.rstrip('/'),password_hash,secret)
