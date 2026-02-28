"""Compatibility wrapper for moved Pi menu interaction test."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "tests" / "pi_menu_interaction_test.py"
    runpy.run_path(str(target), run_name="__main__")
