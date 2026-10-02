from sqlalchemy import inspect
from betmodel.config import Settings
from betmodel.db import create_engine_for, init_db


def test_init_db_creates_core_tables(tmp_path):
    engine = create_engine_for(Settings(tmp_path))
    init_db(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"teams", "fixtures", "team_match_stats", "odds_snapshots"} <= tables
