"""Pi-side test loop for the new snapshot sender backbone.

No command-line arguments.
Edit the hardcoded test values below, run this script, and it will continuously
send player snapshots to Pico.
"""

import time
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pico_interaction.pi_uart_state_sender import (
    send_players_to_pico,
    send_tile_resource_vector_from_game_state,
)


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


def build_mock_game_state_with_tiles(tick: int):
    # Rotate a deterministic tile pattern so each loop sends changing vector data.
    resource_cycle = [
        "wood",
        "brick",
        "sheep",
        "wheat",
        "ore",
        "desert",
        "wood",
        "sheep",
        "brick",
        "ore",
        "wheat",
        "wood",
        "sheep",
        "brick",
        "ore",
        "wheat",
        "wood",
        "sheep",
        "brick",
    ]
    shift = tick % len(resource_cycle)
    rotated = resource_cycle[shift:] + resource_cycle[:shift]
    tiles = [{"resource_type": rt} for rt in rotated[:19]]
    return {"tiles": tiles}


def main():
    tick = 0
    print("sending mock players + mock tile vector ... Ctrl+C to stop")
    try:
        while True:
            players = build_mock_players(tick)
            players_packet = send_players_to_pico(players)

            mock_game_state = build_mock_game_state_with_tiles(tick)
            tiles_packet = send_tile_resource_vector_from_game_state(
                mock_game_state, desert_value=0
            )

            print(
                f"tick={tick} sent players={len(players_packet)} bytes "
                f"tiles={len(tiles_packet)} bytes"
            )
            tick += 1
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
