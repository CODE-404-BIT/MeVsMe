# Free cloud deployment: Render + Neon

## Approved intent

Move the existing personal football dashboard and its saved records to the cloud for $0 within the providers' free allowances. Use Render Free for the Python web application and Neon Free for persistent PostgreSQL storage. Preserve fixtures, statistics, prices, historical suggestion snapshots and measured results. Keep the Windows/local SQLite workflow working.

This document specifies the implementation required by that choice. No cloud resources have been created and no data has been uploaded.

## Deployment shape

One Render Python web service, explicitly `plan: free`, serves the existing static dashboard and authenticated API. A production WSGI server runs one application process with a small thread pool. This preserves the dashboard's current single-job lock. Bind to Render's provided PORT on 0.0.0.0; the local launcher continues binding only to loopback.

One Neon Free project holds all durable records. Do not provision Render Postgres: its free database expires after 30 days. No paid workers, cron services, persistent disks, custom domains or automatic upgrades are included. Use the provided HTTPS onrender.com address.

Render sleeps while idle. Fetching fixtures, research and analysis remain user-triggered; uninterrupted background operation is not promised. Interrupted jobs report interruption after restart and can be retried. Already committed data remains intact.

## Cloud access and secrets

The public service is private to its owner through an authenticated login. Store the owner's password hash and session-signing secret as Render secrets; use Secure, HttpOnly, SameSite cookies. All application APIs require authentication, except a minimal health endpoint. Protect state-changing requests with CSRF tokens and exact allowed-origin checks. Bound request bodies and login attempts. Do not expose database URLs, provider keys, raw exception traces or local files.

Cloud startup fails closed if DATABASE_URL, authentication configuration or the expected public hostname is absent. It must never silently fall back to temporary SQLite storage on Render. Local mode keeps its existing loopback restrictions.

The football API key is a Render secret, not bundled in source or migrated into a public repository. Browser key changes remain session-only. Do not ask the owner to paste secret values into chat.

## PostgreSQL compatibility and migration

Add an optional PostgreSQL driver and DATABASE_URL configuration. Use a small connection pool with connection health checks and TLS for Neon. Leave Settings(root) using SQLite by default for local commands and existing tests.

Replace the SQLite-specific insert in performance.py with dialect-aware conflict handling. Initialize the ORM tables plus the separately declared saved_combinations and learning_attempts tables. Audit dates, JSON values, null handling, grouping and transaction behavior under actual PostgreSQL.

Take a consistent SQLite backup using the SQLite backup API before migration. The migration reads that backup and inserts into an empty Neon destination inside a transaction, preserving IDs and foreign-key relationships. Copy every application table, including prediction snapshots and learning attempts. Reset PostgreSQL ID sequences after copying. Refuse a nonempty destination instead of overwriting it.

Verify table counts, sample fixture/stat relationships, prediction JSON and settled-outcome counts. Failure rolls back the import. Keep the local database and backup unchanged; switching back to the local launcher is the rollback path. Local/cloud copies do not automatically synchronise.

## Durable state beyond the database

Render's filesystem is temporary. Persist the research-source report, relevant refresh timestamps/quota checkpoints and cache metadata needed to avoid repeat API requests in PostgreSQL. Downloaded CSV/HTML files may remain disposable caches because the imported records and source provenance are durable. Rebuilding caches must not erase existing history or reset provider limits.

Generated analysis can be recalculated after restart; frozen priced predictions and their outcomes must survive. Unpriced draft slips remain drafts and must not be recorded as priced bets during deployment or migration. No uploaded SQLite file, raw data directory or credential file may be included in the source repository.

## Resource limits

Render Free currently provides 512 MB RAM and limited CPU. Profile importing the migrated history, loading the largest saved day and generating slips before publication. Limit concurrent analytical work and numerical-library threads. Bound candidate enumeration and avoid retaining duplicate full datasets. If the realistic workload cannot fit the free instance, report the failed fit rather than choosing a paid plan.

## Delivery artifacts

- PostgreSQL-compatible configuration and database writes, preserving local SQLite.
- Authenticated cloud entry point and production start command.
- render.yaml pinned to the free service plan, health check and secret placeholders.
- Safe SQLite-to-PostgreSQL migration command with dry-run/count verification.
- Deployment instructions for a private source repository, Neon Free and Render Free.
- Documented local backup and restore procedure; credentials excluded from artifacts.

## Verification and acceptance

Run the existing suite, cloud authentication/CSRF/host tests, PostgreSQL integration tests and a migration rehearsal against a disposable database. Check that unauthed visitors cannot read matches, obtain tokens or trigger jobs. Verify saved data survives application restarts. Exercise actual two-/three-selection views on desktop and mobile, inspect memory usage, and verify secrets are absent from responses and build artifacts.

Publication is complete only when the authenticated HTTPS URL works and the migrated database counts match. Local preparation is not evidence of a live deployment.

## Access currently missing

No callable Render/Neon connector or configured Render, Neon or GitHub token was found. The project is not currently a Git repository. The owner must provide an authenticated account connection or perform the account dashboard steps. No paid service is authorized.

## Official references checked

- https://render.com/docs/free
- https://render.com/docs/blueprint-spec
- https://render.com/docs/web-services
- https://neon.com/blog/how-to-make-the-most-of-neons-free-plan

## Review status

Owner approved this design on 2026-09-19. Implementation planning is authorized; cloud account access remains unconnected.
