"""Gunicorn entry point: one process, explicit PostgreSQL, required owner login."""
import os
from pathlib import Path
from .cloud_config import CloudSettings
from .cloud import create_app

app=create_app(Path(os.getenv('BETMODEL_ROOT','/tmp/betmodel')),CloudSettings.from_env(os.environ))
