"""Compatibility wrapper for moved Pi rotary encoder test."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "tests" / "pi_rotary_encoder_test.py"
    runpy.run_path(str(target), run_name="__main__")
