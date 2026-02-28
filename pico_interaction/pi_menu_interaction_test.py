"""Pi-side manual test for rotary menu interaction on player display Pico.

What this does:
1) Sends mock player snapshot data so menu has dev/resources context.
2) Activates one player's menu (default player 1 / index 0) and resets to root.
3) Continuously reads menu events from Pico and prints them.

Use this while physically rotating/pressing the encoder on the active player.
"""

import time

from pi_uart_state_sender import (
    read_menu_events,
    send_players_to_pico,
    send_turn_start_menu,
)


ACTIVE_PLAYER_IDX = 0  # 0-based: 0->P1, 1->P2, 2->P3
POLL_INTERVAL_S = 0.05


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
    print("Sending mock player snapshot...")
    packet = send_players_to_pico(build_mock_players())
    print("snapshot bytes:", len(packet))

    print(f"Activating player menu: P{ACTIVE_PLAYER_IDX + 1}")
    ctrl = send_turn_start_menu(ACTIVE_PLAYER_IDX)
    print("menu-control bytes:", len(ctrl))

    print("Now rotate/press encoder. Waiting for menu events (Ctrl+C to stop).")
    try:
        while True:
            events = read_menu_events(timeout_s=POLL_INTERVAL_S, max_events=20)
            for event in events:
                print("MENU EVENT:", event)
            time.sleep(POLL_INTERVAL_S)
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
