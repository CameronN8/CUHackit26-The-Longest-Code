"""Pi-side interactive rotary menu smoke test.

Run this on the Raspberry Pi. It does all menu logic on Pi:
- reads rotary encoder pins
- computes menu state/actions
- sends render lines to player's 3rd OLED via UART packet
- prints returned actions for main game logic integration
"""

import time
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pico_interaction.pi_uart_state_sender import send_menu_render, send_players_to_pico
from pico_interaction.rotary_menu_controller import PiRotaryEncoder, PlayerTurnMenu


# ===== PI ROTARY WIRING (BCM GPIO) =====
ENC_CLK_PIN = 17
ENC_DT_PIN = 27
ENC_SW_PIN = 22
# =======================================

ACTIVE_PLAYER_IDX = 0
LOOP_DELAY_S = 0.03


def build_mock_players():
    return [
        {
            "color": "orange",
            "resources": {"wood": 3, "brick": 2, "sheep": 1, "wheat": 2, "ore": 1},
            "victory_points": 4,
            "development_cards": {
                "knight": 1,
                "victory_point": 0,
                "road_building": 1,
                "year_of_plenty": 0,
                "monopoly": 0,
            },
        },
        {
            "color": "blue",
            "resources": {"wood": 2, "brick": 1, "sheep": 2, "wheat": 1, "ore": 0},
            "victory_points": 3,
            "development_cards": {
                "knight": 0,
                "victory_point": 1,
                "road_building": 0,
                "year_of_plenty": 0,
                "monopoly": 1,
            },
        },
        {
            "color": "red",
            "resources": {"wood": 1, "brick": 3, "sheep": 0, "wheat": 2, "ore": 2},
            "victory_points": 5,
            "development_cards": {
                "knight": 2,
                "victory_point": 0,
                "road_building": 0,
                "year_of_plenty": 1,
                "monopoly": 0,
            },
        },
    ]


def main():
    players = build_mock_players()
    send_players_to_pico(players)

    menu = PlayerTurnMenu(active_player_idx=ACTIVE_PLAYER_IDX)
    menu.set_players(players)
    encoder = PiRotaryEncoder(ENC_CLK_PIN, ENC_DT_PIN, ENC_SW_PIN)

    lines = menu.get_render_lines()
    send_menu_render(ACTIVE_PLAYER_IDX, lines)
    print("Menu test running. Rotate/press encoder. Ctrl+C to stop.")

    try:
        while True:
            delta, pressed = encoder.read_input()
            if delta == 0 and not pressed:
                time.sleep(LOOP_DELAY_S)
                continue

            action = menu.update(delta, pressed)
            lines = menu.get_render_lines()
            send_menu_render(ACTIVE_PLAYER_IDX, lines)

            if action:
                print("ACTION:", action)

            time.sleep(LOOP_DELAY_S)
    except KeyboardInterrupt:
        pass
    finally:
        PiRotaryEncoder.cleanup()
        print("Stopped.")


if __name__ == "__main__":
    main()
