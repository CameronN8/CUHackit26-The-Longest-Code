# The Longest Code

> A semi-autonomous, hardware-augmented Catan orchestration platform with real-time board-state intelligence, multi-display player UX, and event-driven turn control.

## What This Is

**The Longest Code** is a hybrid tabletop intelligence system that blends computer vision, embedded interaction, and game-state orchestration into one cohesive Catan runtime.

At a glance, the project delivers:

- Real-time game-state management for 3-player Catan
- Camera-assisted board detection and state reconciliation
- Hardware control for lights, LCD messaging, and dice output
- HDMI "command center" visual dashboard
- Rotary encoder-driven turn interface
- Direct Raspberry Pi OLED rendering pipeline for per-player screens

## Why It Is Cool

This isn’t just "a script that tracks points." It is a full-stack physical-digital game layer:

- **Vision layer** infers board context from camera frames
- **Rules layer** executes game logic and scoring
- **Interaction layer** accepts rotary/menu input from players
- **Display layer** broadcasts game context across HDMI + dedicated OLED panels
- **Control layer** drives physical feedback devices for gameplay flow

Think of it as a mini game operating system for a tabletop environment.

## Core Capabilities

- Turn lifecycle execution with automated dice roll handling
- Resource payout allocation (including bank constraints)
- Roll-of-7 discard handling
- Development card purchase flow
- Bank trade handling
- Victory point recomputation and winner detection
- Setup phase flow and transition to main phase
- Runtime snapshot persistence (`runtimeState.json`)

## Architecture

### Runtime Engine

- `main.py`: primary orchestrator and game loop
- `turn_logic.py`: per-turn rules and action handling
- `setup_phase.py`: initial placement/setup flow
- `vp_scoring.py`: VP recomputation and winner determination

### Hardware + Interaction

- `hardware_control.py`: hardware abstraction layer
- `pico_interaction/rotary_menu_controller.py`: rotary encoder + menu state machine
- `pico_interaction/pi_oled_direct.py`: direct Pi SSD1306 multi-screen renderer

### Visual Layers

- `main_display/gui_controller.py`: HDMI big-screen runtime display
- `pico_interaction/tests/pi_oled_direct_test.py`: direct OLED render smoke test

### Detection + Tools

- `board_detection.py`: HSV-based board detection pipeline
- `tools/calibrate_pixels.py`: interactive camera coordinate calibration
- `tools/visualize_board.py`: board rendering/inspection utility

## Project Layout

```text
.
|-- main.py
|-- turn_logic.py
|-- setup_phase.py
|-- vp_scoring.py
|-- hardware_control.py
|-- board_detection.py
|-- main_display/
|-- pico_interaction/
|   |-- pi_oled_direct.py
|   |-- rotary_menu_controller.py
|   `-- tests/
|-- tools/
|   |-- calibrate_pixels.py
|   |-- visualize_board.py
|   `-- lights_clock_smoke.py
|-- gameState.json
`-- runtimeState.json
```

## Quick Start

### 1) Create environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For Raspberry Pi OLED/rotary work:

```bash
pip install -r pico_interaction/requirements-pi.txt
```

### 2) Run the game loop

```bash
python3 main.py --input gameState.json --output runtimeState.json
```

### 3) Optional: launch with interactive prompts

```bash
python3 main.py --interactive
```

### 4) Test direct Pi OLED stack

```bash
python3 pico_interaction/pi_oled_direct_test.py
```

## Fancy Feature Spotlight: Direct OLED Turn UX

The project now supports direct Pi-driven SSD1306 rendering without a Pico bridge for player micro-displays:

- Screen 1: resource summary
- Screen 2: victory points
- Screen 3: action/menu interface

Combined with rotary encoder input, turn progression can be event-driven (e.g., immediate advance on `End Turn`) rather than fixed-delay polling.

## Command Examples

Run without big-screen viewer:

```bash
python3 main.py --no-big-screen
```

Tune board detection:

```bash
python3 main.py --camera-index 1 --detection-frames 5 --max-color-distance 120
```

Use custom HSV profile:

```bash
python3 main.py --hsv-profile hsv_profile.example.json
```

## Development Notes

- Utility scripts were grouped under `tools/`
- Pi hardware tests were grouped under `pico_interaction/tests/`
- Compatibility wrapper scripts remain in original locations to preserve legacy commands

## Vision

The long-term direction is a robust **tabletop automation platform** where computer vision, distributed displays, and physical interfaces fuse into a seamless gameplay experience.

In short: this project is what happens when game-night tooling meets systems engineering.

---

Built for CUHackit, engineered for dramatic board-game energy.
