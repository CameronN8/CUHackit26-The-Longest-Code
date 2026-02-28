import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from board_detection import HSVBoardDetector, load_hsv_profile
from hardware_control import HardwareController
import setup_phase
import turn_logic
import vp_scoring

try:
    from pico_interaction.pi_oled_direct import build_default_player_display
    from pico_interaction.rotary_menu_controller import PiRotaryEncoder, PlayerTurnMenu
except Exception:
    build_default_player_display = None
    PiRotaryEncoder = None
    PlayerTurnMenu = None

SCRIPT_DIR = Path(__file__).resolve().parent

ENC_CLK_PIN = 17
ENC_DT_PIN = 27
ENC_SW_PIN = 22
MENU_POLL_DELAY_S = 0.03


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
    parser.add_argument(
        "--no-big-screen",
        action="store_true",
        help="Disable automatic launch of big screen HDMI viewer.",
    )
    parser.add_argument(
        "--big-screen-poll-ms",
        type=int,
        default=700,
        help="Refresh interval for big screen viewer in milliseconds.",
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


class DirectPiTurnInput:
    def __init__(self) -> None:
        if PiRotaryEncoder is None or PlayerTurnMenu is None:
            raise RuntimeError("rotary menu dependencies unavailable")

        self.encoder = PiRotaryEncoder(ENC_CLK_PIN, ENC_DT_PIN, ENC_SW_PIN)
        self.menu = PlayerTurnMenu(active_player_idx=0)
        self.displays = None
        self._active_player_idx = None

        if build_default_player_display is not None:
            try:
                self.displays = build_default_player_display()
            except Exception as exc:
                print(f"[PI-OLED] Disabled direct OLED output: {exc}")

    def _render(self, game_state: dict[str, Any], player_idx: int) -> None:
        if self.displays is None:
            return

        players = game_state.get("players", [])
        player = players[player_idx] if player_idx < len(players) else {}
        if isinstance(player, dict):
            self.displays.apply_snapshot(player, player_idx=player_idx)
        self.displays.draw_interface_menu(self.menu.get_render_lines())

    def _normalize_event(self, event: dict[str, Any]) -> dict[str, Any]:
        event_type = str(event.get("type", ""))
        if event_type == "end_turn":
            return {"type": "end_turn"}
        if event_type == "buy_dev_card":
            return {"type": "buy_development_card"}
        if event_type == "trade_port":
            return {"type": "trade_bank", "give": "wood", "get": "brick", "rate": 4}
        return {"type": f"unsupported_{event_type}"}

    def get_turn_action(self, player: dict[str, Any], game_state: dict[str, Any]) -> dict[str, Any]:
        game = game_state.get("game", {})
        player_idx = int(game.get("current_player_index", 0) or 0)
        players = game_state.get("players", [])
        if not isinstance(players, list) or not players:
            return {"type": "end_turn"}
        player_idx %= len(players)

        self.menu.set_players(players)
        if self._active_player_idx != player_idx:
            self._active_player_idx = player_idx
            self.menu.set_active_player(player_idx)
            self._render(game_state, player_idx)

        while True:
            delta, pressed = self.encoder.read_input()
            if delta == 0 and not pressed:
                time.sleep(MENU_POLL_DELAY_S)
                continue

            event = self.menu.update(delta, pressed)
            self._render(game_state, player_idx)
            if event:
                return self._normalize_event(event)

    def cleanup(self) -> None:
        if PiRotaryEncoder is not None:
            PiRotaryEncoder.cleanup()


def maybe_attach_direct_pi_turn_input(hardware: HardwareController) -> DirectPiTurnInput | None:
    if PiRotaryEncoder is None or PlayerTurnMenu is None:
        print("[PI-INPUT] Direct rotary menu unavailable; using existing hardware controller.")
        return None

    try:
        turn_input = DirectPiTurnInput()
    except Exception as exc:
        print(f"[PI-INPUT] Failed to initialize direct rotary menu: {exc}")
        return None

    hardware.get_turn_action = turn_input.get_turn_action  # type: ignore[assignment]
    print("[PI-INPUT] Using direct rotary menu + OLED turn input.")
    return turn_input


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


def maybe_start_big_screen_viewer(
    output_path: Path, args: argparse.Namespace
) -> subprocess.Popen[Any] | None:
    if args.no_big_screen:
        return None

    viewer_path = SCRIPT_DIR / "main_display" / "gui_controller.py"
    if not viewer_path.exists():
        print(f"[BIG-SCREEN] Viewer not found at {viewer_path}; continuing without it.")
        return None

    cmd = [
        sys.executable,
        str(viewer_path),
        "--state-file",
        str(output_path),
        "--poll-ms",
        str(args.big_screen_poll_ms),
    ]
    env = os.environ.copy()

    if os.name != "nt" and hasattr(os, "getuid"):
        uid = os.getuid()
        runtime_dir = Path(f"/run/user/{uid}")
        wayland_socket = runtime_dir / "wayland-0"

        if runtime_dir.exists():
            env.setdefault("XDG_RUNTIME_DIR", str(runtime_dir))
        if wayland_socket.exists():
            env.setdefault("WAYLAND_DISPLAY", "wayland-0")
            env.setdefault("DISPLAY", ":0")
        else:
            env.setdefault("DISPLAY", ":0")

        xauth = Path.home() / ".Xauthority"
        if xauth.exists():
            env.setdefault("XAUTHORITY", str(xauth))

    try:
        proc = subprocess.Popen(cmd, cwd=str(SCRIPT_DIR), env=env)
    except Exception as exc:
        print(f"[BIG-SCREEN] Failed to start viewer: {exc}")
        return None

    print(f"[BIG-SCREEN] Viewer started (pid={proc.pid}).")
    return proc


def main() -> None:
    args = parse_args()
    input_path = resolve_path(args.input)
    output_path = resolve_path(args.output)

    game_state = load_state(input_path)
    hardware = HardwareController(interactive=args.interactive)
    rng = random.Random(args.seed)
    detect_board_callback = build_detect_callback(args)
    turn_input = maybe_attach_direct_pi_turn_input(hardware)

    viewer_process = maybe_start_big_screen_viewer(output_path, args)
    try:
        run_game_loop(
            game_state=game_state,
            hardware=hardware,
            rng=rng,
            max_turns=args.max_turns,
            detect_board_callback=detect_board_callback,
            save_snapshot_callback=lambda state: save_state(output_path, state),
        )
    finally:
        if turn_input is not None:
            turn_input.cleanup()
        if viewer_process is not None and viewer_process.poll() is None:
            viewer_process.terminate()
            try:
                viewer_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                viewer_process.kill()

    save_state(output_path, game_state)
    print(f"Saved runtime state to {output_path}")


if __name__ == "__main__":
    main()
