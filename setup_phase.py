from __future__ import annotations

from typing import Any, Callable

import vp_scoring

DetectBoardCallback = Callable[[dict[str, Any], str, str | None], None]


def _get_setup_order(game_state: dict[str, Any]) -> list[int]:
    setup = game_state.setdefault("setup_state", {})
    if "order" in setup and isinstance(setup["order"], list):
        return [int(v) for v in setup["order"]]

    order = list(range(len(game_state.get("players", []))))
    setup["order"] = order
    return order


def run_setup_phase(
    game_state: dict[str, Any],
    hardware,
    detect_board_callback: DetectBoardCallback,
) -> None:
    players = game_state.get("players", [])
    if not players:
        raise ValueError("No players in game state.")

    setup = game_state.setdefault("setup_state", {})
    required = int(setup.get("placements_required_per_player", 1))
    setup["placements_required_per_player"] = required
    setup.setdefault("placements_done", {p["color"]: 0 for p in players})

    order = _get_setup_order(game_state)

    hardware.display_lcd_message("Setup phase: place free settlement + road")

    for round_idx in range(required):
        for player_idx in order:
            player = players[player_idx]
            color = player["color"]
            hardware.clear_all_player_lights()
            hardware.set_player_light(color, True)
            hardware.display_lcd_message(
                f"{color}: place settlement+road (setup {round_idx + 1}/{required})"
            )

            hardware.wait_for_player_confirm(color)
            detect_board_callback(game_state, context="setup_placement", player_color=color)

            setup["placements_done"][color] = setup["placements_done"].get(color, 0) + 1

    hardware.clear_all_player_lights()
    hardware.display_lcd_message("Setup complete. Detecting board...")

    detect_board_callback(game_state, context="post_setup_finalize", player_color=None)

    vp_scoring.recompute_all_victory_points(game_state)

    game = game_state.setdefault("game", {})
    game["phase"] = "main"
    game["current_player_index"] = 0
    game["turn_number"] = 1
    setup["completed"] = True
