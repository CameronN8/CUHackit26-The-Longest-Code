import argparse
import json
import random
from pathlib import Path
from typing import Any

from board_utils import DEV_CARD_COUNTS, build_empty_dev_cards, build_empty_resources, build_resource_bank

RESOURCE_POOL = (
    ["wood"] * 4
    + ["brick"] * 3
    + ["sheep"] * 4
    + ["wheat"] * 4
    + ["ore"] * 3
    + ["desert"]
)
ROLL_NUMBER_POOL = [2, 3, 3, 4, 4, 5, 5, 6, 6, 8, 8, 9, 9, 10, 10, 11, 11, 12]
SCRIPT_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize randomized Catan gameplay data into gameState.json"
    )
    parser.add_argument(
        "--input",
        default="startingBoard.json",
        help="Input board JSON path (default: startingBoard.json).",
    )
    parser.add_argument(
        "--output",
        default="gameState.json",
        help="Output game JSON path (default: gameState.json).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed for reproducible game initialization.",
    )
    return parser.parse_args()


def resolve_path(path_text: str) -> Path:
    raw = Path(path_text)
    return raw if raw.is_absolute() else (SCRIPT_DIR / raw)


def load_board(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        board = json.load(f)

    if not isinstance(board, dict):
        raise ValueError("Input JSON must be an object.")

    for key in ("settlements", "roads", "tiles", "players"):
        if key not in board:
            raise ValueError(f"Input JSON missing key: {key}")

    if not isinstance(board["tiles"], list) or len(board["tiles"]) != 19:
        raise ValueError("Input board must contain exactly 19 tiles.")

    return board


def build_development_deck(rng: random.Random) -> list[str]:
    deck: list[str] = []
    for card, count in DEV_CARD_COUNTS.items():
        deck.extend([card] * count)
    rng.shuffle(deck)
    return deck


def normalize_players(board: dict[str, Any]) -> None:
    for player in board["players"]:
        color = player.get("color")
        player.clear()
        player["color"] = color
        player["resources"] = build_empty_resources()
        player["development_cards"] = build_empty_dev_cards()
        player["played_knights"] = 0
        player["has_longest_road"] = False
        player["has_largest_army"] = False
        player["longest_road_length"] = 0
        player["pending_actions"] = []
        player["victory_points"] = 0


def reset_board_ownership(board: dict[str, Any]) -> None:
    for settlement in board["settlements"]:
        settlement["type"] = None
        settlement["color"] = None

    for road in board["roads"]:
        road["color"] = None


def randomize_tiles(board: dict[str, Any], rng: random.Random) -> None:
    resources = RESOURCE_POOL.copy()
    rolls = ROLL_NUMBER_POOL.copy()
    rng.shuffle(resources)
    rng.shuffle(rolls)

    roll_index = 0
    robber_index = None

    for idx, (tile, resource) in enumerate(zip(board["tiles"], resources)):
        tile["resource_type"] = resource
        if resource == "desert":
            tile["roll_number"] = None
            tile["robber"] = True
            robber_index = idx
        else:
            tile["roll_number"] = rolls[roll_index]
            tile["robber"] = False
            roll_index += 1

    board["robber_tile_index"] = robber_index


def initialize_meta(board: dict[str, Any]) -> None:
    board["bank"] = {
        "resources": build_resource_bank(),
        "development_deck": board.get("development_deck", []),
        "discarded_development_cards": [],
    }
    board["game"] = {
        "phase": "setup",
        "current_player_index": 0,
        "turn_number": 1,
        "winner": None,
        "last_roll": None,
    }
    board["setup_state"] = {
        "placements_required_per_player": 1,
        "order": list(range(len(board["players"]))),
        "placements_done": {p["color"]: 0 for p in board["players"]},
        "completed": False,
    }


def main() -> None:
    args = parse_args()
    input_path = resolve_path(args.input)
    output_path = resolve_path(args.output)

    board = load_board(input_path)
    rng = random.Random(args.seed)

    normalize_players(board)
    reset_board_ownership(board)
    randomize_tiles(board, rng)
    board["development_deck"] = build_development_deck(rng)
    initialize_meta(board)

    output_path.write_text(json.dumps(board, indent=2), encoding="utf-8")

    seed_text = f" seed={args.seed}" if args.seed is not None else ""
    print(f"Wrote {output_path} from {input_path}.{seed_text}")


if __name__ == "__main__":
    main()
