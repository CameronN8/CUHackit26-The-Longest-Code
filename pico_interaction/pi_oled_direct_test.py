"""Hardware test for direct Pi OLED rendering (no Pico bridge).

Display mapping:
- OLED #1 (resources SDA pin): resource counts
- OLED #2 (vp SDA pin): victory points
- OLED #3 (menu SDA pin): interface menu

Run on Raspberry Pi:
  python3 pico_interaction/pi_oled_direct_test.py
"""

from __future__ import annotations

import time

from pi_oled_direct import OledDependencyError, build_default_player_display

LOOP_DELAY_S = 0.5
PLAYER_IDX = 0


MENU_STATES = [
    ["P1 Action", ">Development", " Trading", " End Turn"],
    ["P1 Action", " Development", ">Trading", " End Turn"],
    ["P1 Action", " Development", " Trading", ">End Turn"],
]


def build_demo_resources(tick: int) -> dict[str, int]:
    return {
        "wood": (tick % 6),
        "brick": ((tick + 1) % 6),
        "sheep": ((tick + 2) % 6),
        "wheat": ((tick + 3) % 6),
        "ore": ((tick + 4) % 6),
    }


def build_demo_vp(tick: int) -> int:
    return 2 + (tick % 8)


def main() -> None:
    try:
        displays = build_default_player_display()
    except OledDependencyError as exc:
        print(exc)
        return

    print("Pi direct OLED test running. Press Ctrl+C to stop.")

    tick = 0
    try:
        while True:
            resources = build_demo_resources(tick)
            vp = build_demo_vp(tick)
            menu_lines = MENU_STATES[tick % len(MENU_STATES)]

            displays.draw_resource_count(resources=resources, player_idx=PLAYER_IDX)
            displays.draw_victory_points(victory_points=vp, player_idx=PLAYER_IDX)
            displays.draw_interface_menu(menu_lines)

            tick += 1
            time.sleep(LOOP_DELAY_S)
    except KeyboardInterrupt:
        print("Stopped OLED test.")


if __name__ == "__main__":
    main()
