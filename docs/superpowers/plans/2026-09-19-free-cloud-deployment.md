# Free Cloud Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the existing private dashboard on Render Free with its saved records migrated safely to Neon Free, preserving the local SQLite application.

**Architecture:** Add explicit PostgreSQL configuration and durable application state, then a Flask cloud adapter behind a single-process Gunicorn server. Reuse the existing dashboard service and share API dispatch with the loopback server. Import a consistent SQLite backup into an empty PostgreSQL database before accepting production traffic.

**Tech Stack:** Python 3.12+, SQLAlchemy 2, psycopg 3, PostgreSQL, Flask 3, Gunicorn, existing HTML/CSS/JavaScript, pytest and Playwright.

**Spec:** `docs/superpowers/specs/2026-09-19-free-cloud-deployment-design.md` (approved).

## Global Constraints

- "Keep the Windows/local SQLite workflow working."
- "One Render Python web service, explicitly `plan: free`, serves the existing static dashboard and authenticated API."
- "No paid workers, cron services, persistent disks, custom domains or automatic upgrades are included."
- "Cloud startup fails closed if DATABASE_URL, authentication configuration or the expected public hostname is absent."
- "Refuse a nonempty destination instead of overwriting it."
- "Do not ask the owner to paste secret values into chat."
- "Publication is complete only when the authenticated HTTPS URL works and the migrated database counts match."
- The checked backup is `data/backups/pre-cloud-20260919T103426077122Z.db`; SHA256 `d529435699a664f78fca8aec4452f7fcfb1b2ceaa9550163640507be1be2d6cf`. Take a newer backup immediately before the final import if local data has changed.
- No Git repository currently exists. Do not issue commits until an isolated checkout and private source repository exist. Keep a reviewed changed-file list meanwhile; never include `data/`, `.env*`, local credentials or the virtual environment.
- Run commands from the nested project directory. Windows test prefix is `.\.venv\Scripts\python.exe -m pytest`; Linux uses `python -m pytest`. Use a fresh workspace-local `--basetemp` for each full run.

## Review Focus

1. Missing/malformed cloud configuration must stop startup rather than silently creating a disposable SQLite database (Task 1).
2. An attacker with no session, a forged Host/Origin, or a stolen CSRF token alone must not read private data or launch work (Task 4).
3. A failed or repeated migration must not partially import or overwrite an existing destination (Task 2).
4. A restart or overlapping rollout must not lose committed predictions, reset API refresh checkpoints, or start duplicate analytical jobs (Task 3).
5. A long-running analysis under 512 MB must finish within the free instance's resource envelope or remain explicitly unapproved for deployment (Task 6).

## File responsibilities

- `config.py`, `db.py`: explicit database configuration and dialect-aware schema/writes.
- `cloud_config.py`: validated cloud-only settings; never logs secrets.
- `migrate_cloud.py`: local backup, dry run, transactional import and verification.
- `state_store.py`: persistent research reports, checkpoints, restart-safe job state and lock.
- `api_routes.py`: shared application API dispatch; no authentication policy.
- `cloud.py`: Flask authentication, security policy, static allowlist and lifecycle.
- `web.py`: retain local HTTP behavior while calling shared API dispatch.
- `templates/login.html`, `static/login.css`: owner login page with no external assets.
- `render.yaml`, `docs/cloud-deployment.md`: exact free deployment setup and recovery.
- `tests/test_cloud_*.py`, `tests/browser_cloud_check.py`: focused integration/security/migration/browser checks.
- `scripts/profile_cloud.py`: repeatable Linux resource measurement against a private database copy.

### Task 1: Explicit PostgreSQL support without changing local defaults

**Files:** Modify `src/betmodel/config.py`, `db.py`, `dashboard.py`, `performance.py`, `pyproject.toml`; create `cloud_config.py`, `tests/test_cloud_database.py`.

**Interfaces:** `Settings(root_dir: Path, database_url: str | None = None)`; `Dashboard(root: Path, *, database_url: str | None = None)`; `conflict_insert(table, engine)` returns the appropriate SQLAlchemy SQLite/PostgreSQL insert; `CloudSettings.from_env(env: Mapping[str,str])` returns database_url, public_origin, password_hash and secret_key.

- [ ] Write the local-default and missing-config tests first:
```python
def test_local_database_ignores_cloud_environment(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://wrong.invalid/db')
    engine = create_engine_for(Settings(tmp_path))
    assert engine.dialect.name == 'sqlite'

def test_cloud_config_requires_database():
    with pytest.raises(ValueError, match='DATABASE_URL'):
        CloudSettings.from_env({})
```
- [ ] Run `pytest tests/test_cloud_database.py -q` and verify the expected missing-interface failures.
- [ ] Add cloud dependencies under an optional `cloud` extra: Flask 3, Gunicorn, `psycopg[binary]>=3.2`. Keep local installs usable without these imports.
- [ ] Normalize `postgres://` / `postgresql://` to `postgresql+psycopg://` using SQLAlchemy URL parsing. Require `sslmode=require` or stronger in cloud configuration. Reject SQLite, credentials embedded in public origins, URL fragments, paths other than empty or `/` on the public origin, and public origins without HTTPS. Require a strong session secret and a Werkzeug password hash. Error messages name configuration fields, never their values.
- [ ] Keep `Settings(root)` local even if the shell has DATABASE_URL. Only the cloud entry point explicitly passes its validated URL. PostgreSQL engine parameters: `pool_pre_ping=True`, `pool_size=2`, `max_overflow=1`, `pool_timeout=15`.
- [ ] Implement dialect selection:
```python
def conflict_insert(table, engine):
    if engine.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    elif engine.dialect.name == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise ValueError('Unsupported database backend')
    return insert(table)
```
- [ ] Route immutable snapshot inserts through that helper; initialize ORM, saved-combination and learning metadata centrally. Run existing database/performance tests and the new configuration tests. Add tests for malformed URLs, insecure TLS options and error redaction.

### Task 2: Consistent backup and transactional migration

**Files:** Create `src/betmodel/migrate_cloud.py`, `tests/test_cloud_migration.py`; modify `db.py` to expose ordered application tables.

**Interfaces:** `backup_sqlite(source: Path, destination: Path) -> Path`; `table_counts(engine) -> dict[str,int]`; `migrate_snapshot(source: Path, target_engine, *, dry_run: bool = True) -> dict`. The module CLI reads `DATABASE_URL` from the environment and accepts `--source`, `--dry-run` or `--apply`; the default is dry-run.

- [ ] Add tests for unchanged source bytes and refusal of a populated target:
```python
def test_migration_refuses_nonempty_target(source_db, pg_engine):
    migrate_snapshot(source_db, pg_engine, dry_run=False)
    before = table_counts(pg_engine)
    with pytest.raises(ValueError, match='empty'):
        migrate_snapshot(source_db, pg_engine, dry_run=False)
    assert table_counts(pg_engine) == before
```
Define `source_db` as a SQLite test fixture with fixtures, team stats, a saved historical combination with JSON patterns, nullable probabilities and learning records. Define `pg_engine` against an explicitly named disposable database supplied through TEST_POSTGRES_URL, never DATABASE_URL; skip with a clear reason when absent.
- [ ] Run migration tests to observe missing implementation failures before writing the module.
- [ ] Open SQLite with `mode=ro`; create backups with `sqlite3.Connection.backup`. Check `PRAGMA integrity_check` equals `ok` before use. Refuse an existing backup destination.
- [ ] Create the target schema and inspect every known table before importing. Detect and reject unknown source application tables so data is not silently omitted. Read via SQLAlchemy typed columns so dates and JSON are decoded consistently.
- [ ] Import batches of at most 500 rows inside one target transaction, in foreign-key order. Include the Core `saved_combinations` and `learning_attempts` tables. Hold an advisory migration lock for PostgreSQL. Require zero target rows across all application tables before inserting.
- [ ] Reset each PostgreSQL integer primary-key sequence using `pg_get_serial_sequence` and `setval`, with the correct empty-table behavior. Never concatenate untrusted identifiers into SQL; use known schema table names or quoted identifiers.
- [ ] Compare row counts, sorted saved-combination identities, nullable probability values and selected stat relationships inside the transaction. Force a test failure midway and assert that no imported rows remain. Insert one new target fixture afterward to test sequences.
- [ ] Run `python -m betmodel.migrate_cloud --source data/backups/pre-cloud-20260919T103426077122Z.db --dry-run`; print counts and readiness only, never the connection URL. Apply only after the empty destination and accounts have been identified.

### Task 3: Persist research state and guard jobs across restarts

**Files:** Create `src/betmodel/state_store.py`, `tests/test_cloud_state.py`; modify `dashboard.py`, `history_research.py`, `public_history.py`, `db.py`, `migrate_cloud.py`.

**Interfaces:** `load_state(engine, key: str, now: datetime) -> dict | None`; `save_state(engine, key: str, payload: dict, expires_at: datetime | None = None) -> None`; `job_guard(engine)` is a context manager yielding whether the exclusive job lock was acquired. State uses a SQLAlchemy table with key primary key, JSON payload and nullable UTC expiry.

- [ ] Add and run restart/expiry tests before implementing state storage:
```python
def test_report_survives_new_engine(settings):
    first = create_engine_for(settings)
    save_state(first, 'research-report', {'sources': [], 'messages': ['saved']})
    first.dispose()
    second = create_engine_for(settings)
    assert load_state(second, 'research-report', datetime.now(timezone.utc))['messages'] == ['saved']
```
- [ ] Persist research reports, last-sync timestamps, per-fixture odds attempts, quota snapshots and blocked-season timestamps. Scope provider quotas by a hash of the API key, not the secret itself; store UTC observation time and reject expired daily/minute checkpoints. Never reuse yesterday's daily remaining count as today's authoritative quota.
- [ ] Check durable refresh markers before downloading disposable caches. A missing local file after Render restart must not force another metered provider call while a successful recent import is recorded. Imported database rows remain the source of truth.
- [ ] Use a PostgreSQL session advisory lock held on a dedicated connection throughout each background job, releasing in `finally`. Keep the local RLock behavior for SQLite. Test that a second process cannot start a job while the first holds the lock, and can proceed after release.
- [ ] Save job state and start time before work. If no live advisory lock remains but the saved job says running, expose an interrupted state and permit a retry. Do not mark another still-running instance's job interrupted during rolling deployment.
- [ ] Import existing local research report and usable checkpoints into the migration's state table. Test lost temporary directories, expired markers, restart interruption and absence of raw secrets in serialized state.

### Task 4: Private cloud HTTP application and unchanged local server

**Files:** Create `src/betmodel/api_routes.py`, `cloud.py`, `templates/login.html`, `static/login.css`, `tests/test_cloud_http.py`; modify `web.py` only to reuse dispatch and assets.

**Interfaces:** `dispatch_api(dashboard, method: str, path: str, args: dict, data: dict | None) -> tuple[int,dict]`; shared `ASSETS: dict[str,tuple[str,str]]`; `create_app(root: Path, config: CloudSettings, *, dashboard: Dashboard | None = None)` returns Flask. The injectable dashboard is for tests; the production factory supplies PostgreSQL configuration.

- [ ] Write and run unauthenticated access tests:
```python
def test_private_api_requires_session(cloud_client):
    assert cloud_client.get('/api/status').status_code == 401
    assert cloud_client.get('/api/matches?date=2026-09-19').status_code == 401
    assert cloud_client.post('/api/jobs', json={'kind': 'analyze'}).status_code == 401
    assert cloud_client.get('/healthz').status_code == 200
```
The `cloud_client` fixture constructs Flask with TESTING enabled, an injected temporary Dashboard, a test password hash and `https://dashboard.example` as public origin.
- [ ] Move existing API dispatch into the shared function, preserving status codes, input bounds and response bodies. Retain the existing static-file allowlist. Run `tests/test_dashboard_http.py` immediately to prevent regressions in the local server's Host and write-token protections.
- [ ] Implement GET/POST `/login`, POST `/logout` and session-gated application routes. Render login with a session CSRF token; validate passwords with Werkzeug. Rotate session and write token after successful login. Sessions expire after eight hours. Cookies are Secure, HttpOnly and SameSite=Lax.
- [ ] Limit login to ten failures per trusted client address per fifteen minutes, with bounded entries and expiring records. Do not trust arbitrary X-Forwarded-For. Use only the documented Render proxy boundary; include tests for spoofed forwarded headers. Reject unexpected Host and nonmatching Origin. Require exact HTTPS origin and per-session X-Dashboard-Token on authenticated writes.
- [ ] Limit request bodies to 4096 bytes. Return generic 401/403/429/500 responses and redact secrets from logs. Serve a minimal database health result without private metadata. Do not make login health dependent on revealing account configuration.
- [ ] Add tests for forged Host/Origin, token without session, logout invalidation, expired sessions, missing cloud configuration, static path traversal, raw secret redaction and request-size limits. Verify existing frontend status/token polling works after login.

### Task 5: Explicitly free deployment configuration and setup guide

**Files:** Create `render.yaml`, `src/betmodel/cloud_wsgi.py`, `.python-version`, `docs/cloud-deployment.md`; modify `README.md`, `.gitignore`, `pyproject.toml` package data for login assets.

**Interfaces:** `betmodel.cloud_wsgi:app` constructs exactly one application from CloudSettings and BETMODEL_ROOT. The deployment uses environment secrets DATABASE_URL, DASHBOARD_PASSWORD_HASH, DASHBOARD_SECRET_KEY and optional API_FOOTBALL_KEY. Public origin derives from the validated RENDER_EXTERNAL_HOSTNAME unless an explicit HTTPS PUBLIC_ORIGIN is provided.

- [ ] Write deployment configuration with the following fixed free-plan shape:
```yaml
services:
  - type: web
    name: daily-football-dashboard
    runtime: python
    plan: free
    buildCommand: pip install '.[cloud]'
    startCommand: gunicorn betmodel.cloud_wsgi:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120
    healthCheckPath: /healthz
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: DASHBOARD_PASSWORD_HASH
        sync: false
      - key: DASHBOARD_SECRET_KEY
        generateValue: true
      - key: API_FOOTBALL_KEY
        sync: false
      - key: OPENBLAS_NUM_THREADS
        value: '1'
      - key: OMP_NUM_THREADS
        value: '1'
```
- [ ] Pin the supported Python minor version to 3.12, verify current Render support before build, and use no paid database or disk declarations. Set Flask cloud root to an ephemeral working directory; persistent truth always remains in PostgreSQL.
- [ ] Document private Git source setup, selecting Neon Free, retrieving its TLS connection string directly into a local environment/Render secret, dry-run and apply migration, and deploying the Render free web service. Provide a `getpass`-based local password-hash command. Do not put plaintext credentials or database snapshots in Git.
- [ ] Describe free-tier sleep, source/API quotas, interruption behavior, 512 MB memory limit, database capacity checks and local rollback. Explicitly state that cloud/local data do not automatically synchronise.
- [ ] Validate the YAML against Render's official Blueprint schema and inspect the package file list for database/cache/secret leakage. Verify every asset served by the allowlist is packaged.

### Task 6: PostgreSQL rehearsal, memory profile and browser acceptance

**Files:** Create `scripts/profile_cloud.py`, `tests/browser_cloud_check.py`, `tests/test_cloud_postgres.py`; update existing tests only for documented interface changes.

**Interfaces:** `TEST_POSTGRES_URL` identifies a disposable PostgreSQL database. The profiling script accepts `--root` and `--date`, reads database configuration from the environment, and prints counts, duration and peak RSS only.

- [ ] Run the full suite, including actual PostgreSQL duplicate inserts, migration rollback, sequence correctness, job locking, JSON/date round-trips and restart persistence. An absent PostgreSQL URL is a disclosed incomplete verification, not a pass.
- [ ] Rehearse migration on a private copy of the real 18 MB backup. Assert source and destination table counts and historical outcome counts match. Never run destructive test teardown against the production Neon database.
- [ ] On Linux, profile imports, the largest stored match day and both combination tabs using `resource.getrusage(resource.RUSAGE_SELF).ru_maxrss`; measure whole-container memory as well if Docker is available. Exercise request concurrency and a background research job. Leave headroom below 512 MB; if the workload cannot fit, stop deployment and report it without upgrading.
- [ ] Browser-check login failure/success, matches, research, two-/three-selection slips, priced-history tracking and logout on desktop/mobile. Verify no JavaScript errors and no unauthenticated private API responses.
- [ ] Run one independent review focused on auth, PostgreSQL migrations and persistent state; resolve important findings and rerun affected checks. Retain evidence in `docs/cloud-deployment.md` without secrets.

### Task 7: Publish with connected accounts and verify the actual URL

**Files:** Update `docs/cloud-deployment.md` with deployment status and nonsecret URL.

**Interfaces:** Authenticated owner-controlled Render/Neon accounts and a private source repository; none are connected as of plan creation. Access must be supplied through tools, local secure configuration or owner dashboard actions, not chat credentials.

- [ ] Confirm the selected services are actually Free, that no trial-only or paid components are selected, and that the destination database is empty. If access is absent, finish Tasks 1–6 as far as local tools permit and report the exact remaining account steps.
- [ ] Take a fresh consistent local backup and rerun its integrity/count checks. Import into the verified empty Neon destination; keep local data untouched. Configure the secret fields in Render without exposing their values.
- [ ] Publish the private repository and create the free Render web service using the reviewed configuration. Do not enable paid scaling, workers, disks or upgrades. Verify database migration before making the owner dashboard usable.
- [ ] Open the actual HTTPS address, verify unauthenticated access is blocked, log in as owner, compare production counts, perform an on-demand analysis, restart the web service and confirm saved records survive.
- [ ] Deliver the working URL, short login/use instructions, free-tier limitations, backup location and measured verification results. If publication is blocked, state that the app is prepared but not deployed; never describe a local test server as a cloud deployment.

## Self-review and handoff

- Spec coverage: Tasks 1–2 cover PostgreSQL and migration; Task 3 covers durable research state and restarts; Task 4 covers public security; Task 5 covers free configuration; Task 6 covers resource/testing requirements; Task 7 covers actual deployment and rollback.
- All five review-focus conditions have explicit tests or measured acceptance steps.
- Proposed execution method: **Native**—implement in this session, then one independent review. Shared database and routing interfaces make sequential integration simpler and less expensive than fresh implementation agents for every task.
- Status: Owner approved native execution. Local implementation and acceptance completed; see 2026-09-19-cloud-progress.md. Publication awaits authenticated account access.
