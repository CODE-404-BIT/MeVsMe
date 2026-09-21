"""Consistent SQLite backups and all-or-nothing import into an empty database."""
from pathlib import Path
import argparse
import json
import os
import sqlite3
from sqlalchemy import create_engine,inspect,select,func,text
from .db import application_tables,init_db


def backup_sqlite(source: Path,destination: Path) -> Path:
    source=source.resolve();destination=destination.resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation prevents accidental replacement of a previous backup.
    with destination.open('xb'):pass
    try:
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src:
            with sqlite3.connect(destination) as dst:
                src.backup(dst)
                if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup integrity check failed')
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def table_counts(engine):
    with engine.connect() as connection:
        return {t.name:connection.scalar(select(func.count()).select_from(t)) for t in application_tables()}


def migrate_snapshot(source: Path,target_engine,*,dry_run=True,state_root=None):
    path=source.resolve()
    if not path.is_file():raise ValueError('Source backup does not exist')
    if target_engine is not None and target_engine.dialect.name=='sqlite' and target_engine.url.database:
        if Path(target_engine.url.database).resolve()==path:raise ValueError('Source and destination must differ')
    report=None
    if state_root:
        report_path=Path(state_root)/'data/raw/research/report.json'
        if report_path.exists():
            report=json.loads(report_path.read_text(encoding='utf-8'))
            if not isinstance(report,dict):raise ValueError('Invalid research report')
    source_engine=create_engine('sqlite://',creator=lambda:sqlite3.connect(path.as_uri()+'?mode=ro',uri=True))
    try:
        tables=application_tables();names=set(inspect(source_engine).get_table_names())
        unknown=names-{t.name for t in tables}-{'sqlite_sequence'}
        if unknown:raise ValueError('Unknown source tables: '+', '.join(sorted(unknown)))
        with source_engine.connect() as src:
            if src.exec_driver_sql('PRAGMA integrity_check').scalar()!='ok':raise ValueError('Source integrity check failed')
            counts={t.name:src.scalar(select(func.count()).select_from(t)) if t.name in names else 0 for t in tables}
            if dry_run:return {'dry_run':True,'counts':counts}
            init_db(target_engine)
            with target_engine.begin() as target:
                if target_engine.dialect.name=='postgresql':
                    target.execute(text('SELECT pg_advisory_xact_lock(78642101)'))
                    # Block application writes while checking and importing the destination.
                    quoted=', '.join(target_engine.dialect.identifier_preparer.quote(t.name) for t in tables)
                    target.execute(text('LOCK TABLE '+quoted+' IN ACCESS EXCLUSIVE MODE'))
                if any(target.scalar(select(func.count()).select_from(t)) for t in tables):
                    raise ValueError('Migration requires an empty destination')
                for table in tables:
                    if table.name not in names:continue
                    result=src.execute(select(table)).mappings()
                    for batch in result.partitions(500):target.execute(table.insert(),[dict(r) for r in batch])
                    if target.scalar(select(func.count()).select_from(table))!=counts[table.name]:
                        raise ValueError('Migration count mismatch: '+table.name)
                    if target_engine.dialect.name=='postgresql' and 'id' in table.c:
                        sequence=target.scalar(text('SELECT pg_get_serial_sequence(:table_name, :column_name)'),
                                               {'table_name':table.name,'column_name':'id'})
                        if sequence:
                            maximum=target.scalar(select(func.max(table.c.id)))
                            target.execute(text('SELECT setval(CAST(:sequence AS regclass), :value, :called)'),
                                           {'sequence':sequence,'value':maximum or 1,'called':maximum is not None})
                # Check the saved JSON, null probabilities and identities rather than counts alone.
                from .performance import saved_combinations
                if saved_combinations.name in names:
                    for batch in src.execute(select(saved_combinations)).mappings().partitions(500):
                        copied={row['id']:dict(row) for row in target.execute(select(saved_combinations).where(
                            saved_combinations.c.id.in_([row['id'] for row in batch]))).mappings()}
                        if any(dict(row)!=copied.get(row['id']) for row in batch):raise ValueError('Prediction snapshot verification failed')
                if report is not None:
                    from .state_store import state
                    from .db import conflict_insert
                    target.execute(conflict_insert(state,target_engine).values(key='research-report',payload=report)
                        .on_conflict_do_nothing(index_elements=['key']))
            return {'dry_run':False,'counts':counts}
    finally:source_engine.dispose()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--state-root',type=Path,help='Optional original project root for the saved research report')
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--apply',action='store_true');mode.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    try:
        engine=None
        if args.apply:
            from .cloud_config import CloudSettings
            from .config import Settings
            from .db import create_engine_for
            # Validate URL without requiring unrelated web login settings for a local migration.
            from sqlalchemy.engine import make_url
            url=make_url(os.environ.get('DATABASE_URL',''))
            if url.drivername not in {'postgres','postgresql','postgresql+psycopg'} or url.query.get('sslmode') not in {'require','verify-ca','verify-full'}:
                raise ValueError('DATABASE_URL requires PostgreSQL with TLS')
            engine=create_engine_for(Settings(Path('.'),url.set(drivername='postgresql+psycopg').render_as_string(hide_password=False)))
        print(json.dumps(migrate_snapshot(args.source,engine,dry_run=not args.apply,state_root=args.state_root),indent=2))
    except Exception:
        parser.exit(1,'Migration failed; check source, empty destination, TLS and connectivity. Credentials were not logged.\n')


if __name__=='__main__':main()
