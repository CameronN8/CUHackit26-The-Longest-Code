import argparse
import json
import random
from pathlib import Path
from typing import Any, Callable

from board_detection import HSVBoardDetector, load_hsv_profile
from hardware_control import HardwareController
import setup_phase
import turn_logic
import vp_scoring

SCRIPT_DIR = Path(__file__).resolve().parent


DetectBoardCallback = Callable[[dict[str, Any], str, str | None], None]
StateSnapshotCallback = Callable[[dict[str, Any]], None]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run semi-digital Catan game loop")
    parser.add_argument(
        "--input",
        default="gameState.json",
        help="Input game state JSON path (default: gameState.json)",
    )
    parser.add_argument(
        "--output",
        default="runtimeState.json",
        help="Runtime output state JSON path (default: runtimeState.json)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed for deterministic turn flow.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=200,
        help="Safety cap for development runs.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Use console input prompts for hardware actions.",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=1,
        help="Webcam index for board detection (default: 1).",
    )
    parser.add_argument(
        "--detection-frames",
        type=int,
        default=5,
        help="Number of frames to read before each board detection sample.",
    )
    parser.add_argument(
        "--max-color-distance",
        type=float,
        default=120.0,
        help="Maximum HSV distance to accept a color match.",
    )
    parser.add_argument(
        "--hsv-profile",
        default=None,
        help="Optional JSON file mapping color names to HSV triplets.",
    )
    return parser.parse_args()


def resolve_path(path_text: str) -> Path:
    raw = Path(path_text)
    return raw if raw.is_absolute() else (SCRIPT_DIR / raw)


def load_state(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        state = json.load(f)
    if not isinstance(state, dict):
        raise ValueError("Game state file must be a JSON object")
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def initialize_runtime_defaults(game_state: dict[str, Any]) -> None:
    game = game_state.setdefault("game", {})
    game.setdefault("phase", "setup")
    game.setdefault("current_player_index", 0)
    game.setdefault("turn_number", 1)
    game.setdefault("winner", None)
    game.setdefault("last_roll", None)


def run_game_loop(
    game_state: dict[str, Any],
    hardware: HardwareController,
    rng: random.Random,
    max_turns: int,
    detect_board_callback: DetectBoardCallback,
    save_snapshot_callback: StateSnapshotCallback | None = None,
) -> None:
    initialize_runtime_defaults(game_state)

    if game_state["game"]["phase"] == "setup":
        setup_phase.run_setup_phase(game_state, hardware, detect_board_callback)
        if save_snapshot_callback:
            save_snapshot_callback(game_state)

    turns_executed = 0
    while game_state["game"]["phase"] == "main":
        vp_scoring.recompute_all_victory_points(game_state)
        winner = vp_scoring.get_winner(game_state)
        if winner is not None:
            game_state["game"]["winner"] = winner["color"]
            game_state["game"]["phase"] = "ended"
            if save_snapshot_callback:
                save_snapshot_callback(game_state)
            break

        if turns_executed >= max_turns:
            game_state["game"]["phase"] = "paused"
            print(f"Reached max turns ({max_turns}). Pausing game loop.")
            if save_snapshot_callback:
                save_snapshot_callback(game_state)
            break

        current_idx = int(game_state["game"].get("current_player_index", 0))
        player_count = len(game_state.get("players", []))
        if player_count == 0:
            raise ValueError("No players available in game state.")

        current_idx %= player_count
        game_state["game"]["current_player_index"] = current_idx

        turn_logic.run_player_turn(
            game_state,
            player_index=current_idx,
            hardware=hardware,
            detect_board_callback=detect_board_callback,
            rng=rng,
        )

        next_idx = (current_idx + 1) % player_count
        game_state["game"]["current_player_index"] = next_idx
        game_state["game"]["turn_number"] = int(game_state["game"].get("turn_number", 1)) + 1
        turns_executed += 1
        if save_snapshot_callback:
            save_snapshot_callback(game_state)

    if game_state["game"]["phase"] == "ended":
        winner_color = game_state["game"]["winner"]
        hardware.flash_winner(winner_color)
        hardware.display_lcd_message(f"Winner: {winner_color}")


def build_detect_callback(args: argparse.Namespace) -> DetectBoardCallback:
    hsv_profile_path = resolve_path(args.hsv_profile) if args.hsv_profile else None
    try:
        hsv_profile = load_hsv_profile(hsv_profile_path)
        detector = HSVBoardDetector(
            camera_index=args.camera_index,
            frames_to_average=args.detection_frames,
            max_color_distance=args.max_color_distance,
            hsv_profile=hsv_profile,
        )

        def detect_board_callback(state: dict[str, Any], context: str, player_color: str | None) -> None:
            try:
                detector.detect_and_apply(state, context=context, player_color=player_color)
            except Exception as exc:
                who = player_color if player_color else "system"
                print(f"[DETECT] context={context} trigger={who} failed: {exc}")

        return detect_board_callback

    except Exception as exc:
        print(f"[DETECT] Disabled due to setup error: {exc}")

        def fallback_callback(state: dict[str, Any], context: str, player_color: str | None) -> None:
            who = player_color if player_color else "system"
            print(f"[DETECT] context={context} trigger={who} (fallback no-op)")

        return fallback_callback


def main() -> None:
    args = parse_args()
    input_path = resolve_path(args.input)
    output_path = resolve_path(args.output)

    game_state = load_state(input_path)
    hardware = HardwareController(interactive=args.interactive)
    rng = random.Random(args.seed)
    detect_board_callback = build_detect_callback(args)

    run_game_loop(
        game_state=game_state,
        hardware=hardware,
        rng=rng,
        max_turns=args.max_turns,
        detect_board_callback=detect_board_callback,
        save_snapshot_callback=lambda state: save_state(output_path, state),
    )

    save_state(output_path, game_state)
    print(f"Saved runtime state to {output_path}")


if __name__ == "__main__":
    main()
