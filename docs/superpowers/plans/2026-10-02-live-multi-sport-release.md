# Live multi-sport release implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution, or superpowers:subagent-driven-development if the user selects delegation. Steps use checkbox syntax for tracking.

**Goal:** Publish and verify the approved changes in CODE-404-BIT/MeVsMe and the existing Render service, preserving Neon history.

**Architecture:** Reconcile the local changes with the authenticated remote source, rehearse additive migrations, deploy the tested revision and verify the private live app. No replacement service or fresh database.

**Tech Stack:** Git/GitHub, existing Render Blueprint, Neon PostgreSQL, Python 3.12 and browser checks.

**Spec:** `docs/superpowers/specs/2026-10-02-multi-sport-recommendations-design.md`

## Global constraints

- No paid upgrade, destructive re-import, credential in chat/source, or replacing existing saved records.
- Target repository CODE-404-BIT/MeVsMe; existing service srv-davjrrvavr4c73carfn0.
- An authenticated account connection is required for actual remote writes. Its absence does not prevent local implementation/testing.
- All four requested sports need verified actual source coverage. Missing-source screens alone do not satisfy completion.
- Live completion requires deployed revision, public HTTPS health, owner login, actual refresh, strict combination behavior and restart persistence.

## Review focus

- Local checkout may be older than GitHub: compare and reconcile, never upload the old archive over remote changes (task 1).
- New secrets are absent or a sport entitlement is unavailable: app stays operational and reports the specific sport failure (task 2).
- Migration leaves old history unreadable or changes IDs: count/JSON comparison must reject the release (task 2).
- Free-instance memory pressure or restart interrupts collection: bounded jobs/checkpoints and retry are verified (task 3).
- A successful build deploys the wrong branch/revision: inspect the deployed revision and live asset/API behavior (task 3).

## Task 1: obtain and reconcile the authoritative checkout

**Files:** repository metadata and a release record at `docs/multi-sport-release.md`; preserve all existing source files until compared.

- [ ] Confirm authenticated GitHub access and actual permissions. Inspect branch, latest commit and Render's connected branch. Do not infer installation/connection from a plugin suggestion.
- [ ] Create an isolated checkout using the worktree skill where applicable. Compare changed paths with this local workspace and resolve differences without dropping remote work.
- [ ] Record baseline commit, new commit IDs, exact changed files and observed public Render URL. Do not expose private source/credentials in public artifacts.
- [ ] Run affected tests in the reconciled checkout before publishing any changes.

## Task 2: deployment configuration and data rehearsal

**Files:** modify `render.yaml` and `docs/cloud-deployment.md`; extend `tests/test_cloud_postgres.py` and `tests/test_cloud_migration.py` as needed.

- [ ] Add optional secret references `API_BASKETBALL_KEY`, `API_HOCKEY_KEY`, `ODDS_API_KEY` with no values committed. Existing football settings remain valid. Any tennis credential is added only if required by the verified free source; no speculative secret or paid provider.
- [ ] Validate configuration against the current Render schema. Keep one worker/four threads, numerical thread caps, free plan, auth and the existing database connection. Missing new sport credentials must not crash the football dashboard.
- [ ] Back up production data through an authorized secure connection before applying additive schema changes. Rehearse against disposable PostgreSQL, compare existing table counts/IDs and saved-combination JSON, and verify both old/new snapshots survive restart.
- [ ] Run `.\.venv\Scripts\python.exe -m pytest -q` with PostgreSQL integration enabled according to existing test setup. Record actual pass/fail/skip counts, not prior results. Resolve failures before deployment.
- [ ] Document provider activation steps without secret values. An account entitlement failure remains an explicit release blocker for that sport.

## Task 3: deploy and verify the live product

**Files:** update `docs/multi-sport-release.md` and `docs/cloud-deployment.md` with verified facts.

- [ ] Profile representative four-sport refresh/ranking on Linux/Python 3.12 under the service's 512 MiB memory ceiling. Verify quota budgets and maximum concurrent jobs. Fix memory issues before release; no automatic paid resize.
- [ ] Publish the tested commit to the branch Render actually deploys using authenticated access. Existing user authorization covers this release; do not request deployment authorization again merely because the implementation is ready.
- [ ] Verify the Render deployment revision and startup logs, `/healthz`, unauthenticated redirect/rejection and owner login. Keep credentials in secure account/browser interfaces.
- [ ] Run one bounded authenticated live discovery job. Check four-sport coverage, automatic participant discovery, estimated probability provenance, scorecards, absence of unpriced fallback and exact perfect records on any returned combinations. An honestly empty qualifying result can pass behavior checks; unavailable/unverified sport data cannot pass sport integration checks.
- [ ] Verify phone-width layout, refresh/error states, UTC/local date boundary behavior, quotas and duplicate-tab refresh handling. Verify frozen records after a service restart without resetting imported history.
- [ ] Record deployed commit, public URL, verification evidence, model promotion status and remaining limits. If any requested sport is unavailable or deployment access is missing, report precisely what is incomplete; never mark local implementation as live completion.

## Rollback

- [ ] Keep the previous deployed revision and pre-migration backup reference. Prefer redeploying previous application code; additive tables can remain. Do not restore over new user data or delete tables without separately establishing that a restore is necessary and authorized.
