from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import Settings


class Base(DeclarativeBase):
    pass


def create_engine_for(settings: Settings) -> Engine:
    settings.ensure_directories()
    url=settings.database_url or f"sqlite:///{settings.database_path}"
    options={'pool_pre_ping':True,'pool_size':2,'max_overflow':1,'pool_timeout':15} if url.startswith('postgresql') else {}
    return create_engine(url, future=True,**options)


def conflict_insert(table,engine):
    if engine.dialect.name=='postgresql':
        from sqlalchemy.dialects.postgresql import insert
    elif engine.dialect.name=='sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:raise ValueError('Unsupported database backend')
    return insert(table)


def application_tables():
    from . import models
    from .performance import saved_combinations
    from .learning import attempts
    from .state_store import state
    return list(Base.metadata.sorted_tables)+[saved_combinations,attempts,state]


def init_db(engine: Engine) -> None:
    from . import models  # noqa: F401
    Base.metadata.create_all(engine)
    for table in application_tables():table.create(engine,checkfirst=True)


def session_factory(engine: Engine):
    return sessionmaker(bind=engine, expire_on_commit=False)
