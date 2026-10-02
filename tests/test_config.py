from pathlib import Path
from betmodel.config import Settings


def test_settings_create_local_directories(tmp_path: Path):
    settings = Settings(root_dir=tmp_path)
    settings.ensure_directories()
    assert settings.data_dir.exists()
    assert settings.raw_dir.exists()
    assert settings.database_path.parent.exists()
