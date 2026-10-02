"""Compatibility entry point for the strict payout and scorecard browser checks."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name("browser_strict_combinations.py")), run_name="__main__")
