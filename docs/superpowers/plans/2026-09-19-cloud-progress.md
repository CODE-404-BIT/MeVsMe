# Execution ledger — plan: 2026-09-19-free-cloud-deployment.md

Owner approved specification, plan and native execution. Publication is authorized on free services only.

Ruling: Work in the existing non-Git project — there is no branch/worktree to isolate; consistent data backup retained. Tests use separate directories and disposable PostgreSQL. Cost: source edits are in place, so preserve this changed-file record.

Pre-flight: explicit Settings database URL feeds Dashboard and migration; local Settings ignore cloud environment. Shared API dispatch must retain local host/token behavior. Durable state must be included in migration table order before cloud startup. Cloud startup must fail closed.

Task 1: complete. Explicit cloud PostgreSQL config/TLS and local SQLite isolation tested; invalid origin/pooler settings rejected. Dependencies installed.
Task 2: complete locally. Consistent backup, dry run, real PostgreSQL 16 import/count/JSON/null/sequence verification, populated destination refusal and injected rollback all passed. Original backup unchanged. Local report import supported.
Task 3: complete locally. Durable state, research reports, response/blocked caches, refresh checkpoints, key-hashed quotas, expired-state pruning and advisory job guard tested. Public result cache metadata survives temporary-file loss.
Task 4: complete. Shared API routes retain local host/token policy. Cloud login, secure cookie, CSRF, host/origin checks, expiry/revocation, body limits and no-session denial tested. Real HTTPS Chrome caught null Origin under no-referrer; same-origin policy fixed it without weakening origin checks.
Task 5: complete. Explicit Render Free configuration, Python 3.12, private setup/migration guide. Official Render schema validation passed. Linux package asset/leak audit passed. Local wheel attempt lacked setuptools; equivalent actual Linux package build and audit passed.
Task 6: complete for available local acceptance. Full suite with TEST_POSTGRES_URL: 181 passed, 61 existing datetime warnings. HTTPS desktop/mobile browser: passed, no JS errors. Linux 512 MiB profile: 201.9 MiB process RSS, 152.2 MiB cgroup peak, 65.2 seconds; busiest scheduled day and public research completed. Not a claim about actual Render networking or future unlimited data growth.
Task 7: blocked by missing authenticated Render/Neon access and private GitHub source repository. No cloud resources published; no paid resources created. Local preparation complete.

Ruling: Use direct PostgreSQL URLs and reject Neon transaction-pooler hosts — session advisory locks need a stable database session. Cost: up to three direct connections.
Ruling: Use a bounded global login throttle for the single owner — no documented proxy chain is trusted. Cost: ten failed attempts temporarily affect all devices.
Ruling: Migrate existing durable state and saved research report, not old in-memory checkpoints — those values were never persisted. Cost: an old running local server's in-memory quota state cannot be reconstructed; the first subsequent provider response restores authoritative quota.
Final review: independent cloud_review found two Important lifecycle issues, no critical auth/migration issue.
Final: fixed rolling restart stuck-busy state — test_rolling_restart_observes_completion_and_disappearance RED→GREEN.
Final: fixed pre-worker initialization lock leak — test_start_failure_releases_guard (quota/checkpoint/thread) RED→GREEN.
Final full suite after fixes: 181/181 passed. No deferred minor review findings.

Changed files so far: config.py, db.py, dashboard.py, performance.py, cloud_config.py, migrate_cloud.py, pyproject.toml, tests/test_cloud_database.py, tests/test_cloud_migration.py.

Additional changed/new files: state_store.py, cloud.py, cloud_wsgi.py, api_routes.py, web.py, history_research.py, public_history.py, providers/api_football.py, static/app.js, static/login.css, templates/login.html, render.yaml, .python-version, .gitignore, .dockerignore, Dockerfile.cloud-test, scripts/profile_cloud.py, tests/test_cloud_state.py, test_cloud_checkpoints.py, test_cloud_http.py, test_cloud_postgres.py, browser_cloud_check.py, docs/cloud-deployment.md, README.md.
