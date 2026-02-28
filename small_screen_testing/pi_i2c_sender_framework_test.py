"""Pi-side test loop for the new snapshot sender backbone.

No command-line arguments.
Edit the hardcoded test values below, run this script, and it will continuously
send player snapshots to Pico.
"""

import time

from pi_i2c_channel_sender import send_players_to_pico


def build_mock_players(tick: int):
    players = [
        {
            "color": "orange",
            "resources": {
                "wood": (2 + tick) % 8,
                "brick": 1,
                "sheep": 3,
                "wheat": 0,
                "ore": 1,
            },
            "victory_points": 3 + (tick % 2),
            "development_cards": {
                "knight": 1,
                "victory_point": 0,
                "road_building": 0,
                "year_of_plenty": 0,
                "monopoly": 0,
            },
        },
        {
            "color": "blue",
            "resources": {
                "wood": 0,
                "brick": (4 + tick) % 8,
                "sheep": 1,
                "wheat": 2,
                "ore": 2,
            },
            "victory_points": 5,
            "development_cards": {
                "knight": 0,
                "victory_point": 1,
                "road_building": 1,
                "year_of_plenty": 0,
                "monopoly": 0,
            },
        },
        {
            "color": "red",
            "resources": {
                "wood": 1,
                "brick": 1,
                "sheep": 1,
                "wheat": 1,
                "ore": (1 + tick) % 8,
            },
            "victory_points": 2,
            "development_cards": {
                "knight": 2,
                "victory_point": 0,
                "road_building": 0,
                "year_of_plenty": tick % 2,
                "monopoly": 0,
            },
        },
    ]
    return players


def main():
    tick = 0
    print("sending mock players with send_players_to_pico(...) ... Ctrl+C to stop")
    try:
        while True:
            players = build_mock_players(tick)
            packet = send_players_to_pico(players)
            print(f"tick={tick} sent {len(packet)} bytes")
            tick += 1
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
