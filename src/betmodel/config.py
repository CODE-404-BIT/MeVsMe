from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    database_url: str | None = None

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
