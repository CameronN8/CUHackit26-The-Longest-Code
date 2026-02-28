"""Compatibility wrapper for moved light-clock smoke test."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "tools" / "lights_clock_smoke.py"
    runpy.run_path(str(target), run_name="__main__")
