# Repository Layout

This project keeps runtime gameplay code at the repository root and groups one-off tools/tests into dedicated folders.

## Main Runtime

- `main.py`: primary game loop entry point.
- `turn_logic.py`, `setup_phase.py`, `vp_scoring.py`: gameplay phases and scoring.
- `hardware_control.py`: hardware abstraction layer.
- `main_display/`: HDMI GUI controller and assets.
- `pico_interaction/`: Pi/Pico communication and OLED/menu modules.

## Utility Scripts

- `tools/calibrate_pixels.py`: camera coordinate calibration utility.
- `tools/visualize_board.py`: board state visualization utility.
- `tools/lights_clock_smoke.py`: simple lights clock smoke script.

## Pi Interaction Tests

- `pico_interaction/tests/`: Pi-side hardware/protocol test scripts.

Compatibility wrappers remain at previous script paths (for example `calibratePixels.py` and `pico_interaction/pi_oled_direct_test.py`) so older commands keep working.
