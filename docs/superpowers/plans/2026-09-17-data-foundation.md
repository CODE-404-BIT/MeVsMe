# Zero-Cost Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, provider-agnostic ingestion and normalization layer that downloads free football data, maps teams/markets to canonical forms, and stores reproducible records in SQLite.

**Architecture:** A CLI-first Python package keeps raw provider files, parses them into typed domain objects, normalizes identities/markets, and persists them via SQLAlchemy. Provider adapters are isolated so paid or optional sources never leak into the core.

**Tech Stack:** Python 3.12+, SQLAlchemy 2.x, pandas, httpx, pydantic, typer, pytest.

**Spec:** `docs/superpowers/specs/2026-09-17-zero-cost-data-foundation.md`

## Global Constraints
- No paid subscriptions, paid APIs, paid hosting requirements, or paid LLM APIs.
- Default database is SQLite at `data/app.db`.
- Raw downloaded files are cached under `data/raw/<provider>/`.
- The core must run without API keys.
- Ambiguous team mappings must fail closed rather than silently map.

---

## File Structure

- `pyproject.toml` — package metadata and free/open-source dependencies.
- `src/betmodel/config.py` — local paths and runtime settings.
- `src/betmodel/domain.py` — typed provider-agnostic records.
- `src/betmodel/db.py` — SQLAlchemy engine/session/base.
- `src/betmodel/models.py` — persistence tables.
- `src/betmodel/normalize.py` — identity and market normalization.
- `src/betmodel/providers/football_data_uk.py` — Football-Data.co.uk CSV ingestion.
- `src/betmodel/providers/openligadb.py` — OpenLigaDB ingestion.
- `src/betmodel/providers/football_data_org.py` — optional free-token adapter.
- `src/betmodel/ingest.py` — persistence orchestration.
- `src/betmodel/cli.py` — command-line entry points.
- `tests/` — focused unit/integration tests using fixtures, never network by default.

### Task 1: Project skeleton and configuration

**Files:**
- Create: `pyproject.toml`
- Create: `src/betmodel/__init__.py`
- Create: `src/betmodel/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings.from_env() -> Settings`
- Produces: `Settings.ensure_directories() -> None`

- [ ] **Step 1: Write the failing configuration test**

```python
from pathlib import Path
from betmodel.config import Settings


def test_settings_create_local_directories(tmp_path: Path):
    settings = Settings(root_dir=tmp_path)
    settings.ensure_directories()
    assert settings.data_dir.exists()
    assert settings.raw_dir.exists()
    assert settings.database_path.parent.exists()
```

- [ ] **Step 2: Run the test and verify failure**

Run: `pytest tests/test_config.py -v`
Expected: FAIL because `betmodel.config` does not exist.

- [ ] **Step 3: Implement settings and package metadata**

```python
from dataclasses import dataclass
from pathlib import Path
import os

@dataclass(frozen=True)
class Settings:
    root_dir: Path

    @property
    def data_dir(self) -> Path:
        return self.root_dir / "data"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "app.db"

    def ensure_directories(self) -> None:
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(Path(os.getenv("BETMODEL_ROOT", ".")).resolve())
```

`pyproject.toml` dependencies: SQLAlchemy, pandas, httpx, pydantic, typer, jinja2, numpy, scipy, scikit-learn, statsmodels, pytest.

- [ ] **Step 4: Run test and verify pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/betmodel tests/test_config.py
git commit -m "chore: scaffold zero-cost analytics package"
```

### Task 2: Domain records and normalization

**Files:**
- Create: `src/betmodel/domain.py`
- Create: `src/betmodel/normalize.py`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Produces: `normalize_name(value: str) -> str`
- Produces: `canonical_market_key(raw_name: str) -> str`
- Produces dataclasses: `FixtureRecord`, `TeamMatchRecord`, `OddsRecord`

- [ ] **Step 1: Write failing normalization tests**

```python
from betmodel.normalize import normalize_name, canonical_market_key


def test_normalize_name_removes_punctuation_and_case():
    assert normalize_name("Paris Saint-Germain FC") == "paris saint germain fc"


def test_market_aliases_are_canonical():
    assert canonical_market_key("Over 2.5 Goals") == "TOTAL_GOALS_OVER"
    assert canonical_market_key("1X2 Home") == "MATCH_HOME"
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/test_normalize.py -v`
Expected: FAIL because functions do not exist.

- [ ] **Step 3: Implement domain and normalization**

Use dataclasses with `date`, `datetime`, `Decimal | float` fields; define an explicit alias dictionary for supported V1 market names. Unknown markets return `UNKNOWN:<normalized>` rather than being guessed.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_normalize.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/betmodel/domain.py src/betmodel/normalize.py tests/test_normalize.py
git commit -m "feat: add canonical domain and market normalization"
```

### Task 3: SQLite persistence schema

**Files:**
- Create: `src/betmodel/db.py`
- Create: `src/betmodel/models.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `create_engine_for(settings: Settings) -> Engine`
- Produces: `init_db(engine: Engine) -> None`
- Tables: teams, fixtures, team_match_stats, odds_snapshots, provider_mappings, model_versions, predictions, recommendations.

- [ ] **Step 1: Write failing persistence test**

```python
from sqlalchemy import inspect
from betmodel.config import Settings
from betmodel.db import create_engine_for, init_db


def test_init_db_creates_core_tables(tmp_path):
    engine = create_engine_for(Settings(tmp_path))
    init_db(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"teams", "fixtures", "team_match_stats", "odds_snapshots"} <= tables
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/test_db.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement SQLAlchemy base/models and initialisation**

Use unique constraints on `(source, provider_id)` mappings and `(fixture_id, source, market_key, selection, line, source_timestamp)` odds snapshots.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_db.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/betmodel/db.py src/betmodel/models.py tests/test_db.py
git commit -m "feat: add sqlite persistence schema"
```

### Task 4: Football-Data.co.uk parser

**Files:**
- Create: `src/betmodel/providers/__init__.py`
- Create: `src/betmodel/providers/football_data_uk.py`
- Create: `tests/fixtures/football_data_uk_sample.csv`
- Test: `tests/test_football_data_uk.py`

**Interfaces:**
- Produces: `parse_match_csv(path: Path, competition: str, season: str) -> list[TeamMatchRecord]`
- Produces: `parse_odds_csv(path: Path, competition: str, season: str) -> list[OddsRecord]`
- Produces: `download(url: str, destination: Path) -> Path`

- [ ] **Step 1: Create a five-row fixture CSV and failing parser test**

Test that `FTHG`, `FTAG`, `HS`, `AS`, `HST`, `AST`, `HC`, `AC`, `HY`, `AY`, `B365H`, `B365D`, `B365A`, `B365>2.5`, `B365<2.5` map to canonical records when present, while missing optional columns do not crash parsing.

- [ ] **Step 2: Run test and verify failure**

Run: `pytest tests/test_football_data_uk.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement robust CSV parsing**

Use pandas, coerce numeric fields with `errors="coerce"`, parse dates with day-first support, and keep source=`football-data.co.uk` on every record.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_football_data_uk.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/betmodel/providers tests/fixtures tests/test_football_data_uk.py
git commit -m "feat: ingest free football-data.co.uk csv files"
```

### Task 5: Free fixture adapters

**Files:**
- Create: `src/betmodel/providers/openligadb.py`
- Create: `src/betmodel/providers/football_data_org.py`
- Test: `tests/test_free_fixture_providers.py`

**Interfaces:**
- Produces: `OpenLigaDBClient.fetch_matches(...) -> list[FixtureRecord]`
- Produces: `FootballDataOrgClient.fetch_matches(...) -> list[FixtureRecord]`
- `FootballDataOrgClient` raises a clear configuration error when token absent rather than becoming mandatory.

- [ ] **Step 1: Write tests using `httpx.MockTransport`**
- [ ] **Step 2: Verify tests fail**
- [ ] **Step 3: Implement both clients with strict timeouts and provenance timestamps**
- [ ] **Step 4: Run tests and verify pass**
- [ ] **Step 5: Commit**

### Task 6: Ingestion orchestration and CLI

**Files:**
- Create: `src/betmodel/ingest.py`
- Create: `src/betmodel/cli.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Produces: `ingest_football_data_uk(...) -> IngestSummary`
- CLI: `betmodel init-db`
- CLI: `betmodel ingest-football-data-uk PATH --competition CODE --season YYYY`

- [ ] **Step 1: Write failing end-to-end ingestion test against temporary SQLite**
- [ ] **Step 2: Run and verify failure**
- [ ] **Step 3: Implement idempotent upsert orchestration and Typer CLI**
- [ ] **Step 4: Run `pytest -q` and a CLI smoke test**
- [ ] **Step 5: Commit**
