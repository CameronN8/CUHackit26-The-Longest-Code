"""Compatibility wrapper for moved calibration tool."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "tools" / "calibrate_pixels.py"
    runpy.run_path(str(target), run_name="__main__")
