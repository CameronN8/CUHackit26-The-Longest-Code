#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk

RESOURCE_ORDER = ["wood", "brick", "sheep", "wheat", "ore"]
ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STATE_FILE = ROOT_DIR / "runtimeState.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Big-screen viewer for latest Catan dice roll and payouts"
    )
    parser.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE_FILE),
        help="Path to runtime state JSON (default: ../runtimeState.json)",
    )
    parser.add_argument(
        "--poll-ms",
        type=int,
        default=700,
        help="Refresh interval in milliseconds (default: 700)",
    )
    return parser.parse_args()


class BigScreenViewer:
    def __init__(self, root: tk.Tk, state_file: Path, poll_ms: int) -> None:
        self.root = root
        self.state_file = state_file
        self.poll_ms = poll_ms

        self.last_mtime_ns: int | None = None
        self.last_roll_signature: tuple[int | None, int | None, int | None, int | None] | None = None

        self.root.title("Catan Roll Display")
        self.root.configure(bg="#0e1116")
        self.root.attributes("-fullscreen", True)

        self._build_ui()
        self._poll_state_file()

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#0e1116")
        style.configure("TLabel", background="#0e1116", foreground="#f4f7fb")
        style.configure("Title.TLabel", font=("Helvetica", 38, "bold"))
        style.configure("Sub.TLabel", font=("Helvetica", 18))
        style.configure("Roll.TLabel", font=("Helvetica", 88, "bold"))
        style.configure("Header.TLabel", font=("Helvetica", 24, "bold"))
        style.configure("Cell.TLabel", font=("Helvetica", 20))

        container = ttk.Frame(self.root, padding=28)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Catan Live Roll", style="Title.TLabel").pack(anchor="center")

        top = ttk.Frame(container)
        top.pack(fill="x", pady=(18, 24))

        self.roll_total_var = tk.StringVar(value="-")
        self.roll_detail_var = tk.StringVar(value="Waiting for runtimeState.json updates...")
        self.turn_var = tk.StringVar(value="Turn: -")

        ttk.Label(top, textvariable=self.roll_total_var, style="Roll.TLabel").pack(anchor="center")
        ttk.Label(top, textvariable=self.roll_detail_var, style="Sub.TLabel").pack(anchor="center", pady=(4, 6))
        ttk.Label(top, textvariable=self.turn_var, style="Sub.TLabel").pack(anchor="center")

        ttk.Label(container, text="Resources Gained This Roll", style="Header.TLabel").pack(
            anchor="w", pady=(6, 10)
        )

        board = tk.Frame(container, bg="#171c24", highlightthickness=0)
        board.pack(fill="both", expand=True)

        columns = ["Player"] + [name.title() for name in RESOURCE_ORDER] + ["Total"]
        for col, label in enumerate(columns):
            tk.Label(
                board,
                text=label,
                bg="#1e2430",
                fg="#ecf2ff",
                font=("Helvetica", 19, "bold"),
                padx=12,
                pady=10,
            ).grid(row=0, column=col, sticky="nsew", padx=1, pady=1)
            board.grid_columnconfigure(col, weight=1)

        self.player_rows: dict[str, dict[str, tk.StringVar]] = {}

        self.status_var = tk.StringVar(value=f"Watching: {self.state_file}")
        ttk.Label(container, textvariable=self.status_var, style="Sub.TLabel").pack(anchor="w", pady=(12, 0))

        self.root.bind("<Escape>", lambda _e: self.root.attributes("-fullscreen", False))
        self.root.bind("<F11>", lambda _e: self.root.attributes("-fullscreen", True))

        self.board = board

    def _ensure_player_row(self, player_color: str, row_num: int) -> dict[str, tk.StringVar]:
        if player_color in self.player_rows:
            return self.player_rows[player_color]

        var_map: dict[str, tk.StringVar] = {"Player": tk.StringVar(value=player_color.upper())}
        for resource in RESOURCE_ORDER:
            var_map[resource] = tk.StringVar(value="0")
        var_map["Total"] = tk.StringVar(value="0")

        columns = ["Player"] + RESOURCE_ORDER + ["Total"]
        for col, key in enumerate(columns):
            tk.Label(
                self.board,
                textvariable=var_map[key],
                bg="#242c3a",
                fg="#f4f7fb",
                font=("Helvetica", 20),
                padx=12,
                pady=12,
            ).grid(row=row_num, column=col, sticky="nsew", padx=1, pady=1)

        self.player_rows[player_color] = var_map
        return var_map

    def _clear_payout_table(self) -> None:
        for vars_for_player in self.player_rows.values():
            for resource in RESOURCE_ORDER:
                vars_for_player[resource].set("0")
            vars_for_player["Total"].set("0")

    def _poll_state_file(self) -> None:
        try:
            stat = self.state_file.stat()
            if self.last_mtime_ns != stat.st_mtime_ns:
                self.last_mtime_ns = stat.st_mtime_ns
                self._load_and_render_state()
        except FileNotFoundError:
            self.status_var.set(f"State file not found: {self.state_file}")
        except Exception as exc:
            self.status_var.set(f"State read error: {exc}")

        self.root.after(self.poll_ms, self._poll_state_file)

    def _load_and_render_state(self) -> None:
        try:
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception as exc:
            self.status_var.set(f"Invalid JSON: {exc}")
            return

        game = state.get("game", {}) if isinstance(state, dict) else {}
        players = state.get("players", []) if isinstance(state, dict) else []

        last_roll = game.get("last_roll") if isinstance(game, dict) else None
        die_1 = last_roll.get("die_1") if isinstance(last_roll, dict) else None
        die_2 = last_roll.get("die_2") if isinstance(last_roll, dict) else None
        total = last_roll.get("total") if isinstance(last_roll, dict) else None
        turn_number = game.get("turn_number") if isinstance(game, dict) else None

        roll_signature = (die_1, die_2, total, turn_number if isinstance(turn_number, int) else None)
        if roll_signature != self.last_roll_signature:
            self.last_roll_signature = roll_signature
            self._render_roll(die_1, die_2, total, turn_number)
            self._render_payouts(game, players)

        self.status_var.set(f"Watching: {self.state_file}")

    def _render_roll(self, die_1: object, die_2: object, total: object, turn_number: object) -> None:
        total_text = str(total) if isinstance(total, int) else "-"
        if isinstance(die_1, int) and isinstance(die_2, int) and isinstance(total, int):
            detail = f"Dice: {die_1} + {die_2}"
        else:
            detail = "No roll yet"

        self.roll_total_var.set(total_text)
        self.roll_detail_var.set(detail)
        self.turn_var.set(f"Turn: {turn_number}" if isinstance(turn_number, int) else "Turn: -")

    def _render_payouts(self, game: dict, players: list) -> None:
        self._clear_payout_table()

        payouts = game.get("last_roll_payouts", {}) if isinstance(game, dict) else {}
        if not isinstance(payouts, dict):
            payouts = {}

        row_num = 1
        for player in players:
            if not isinstance(player, dict):
                continue

            color = str(player.get("color", "unknown"))
            row = self._ensure_player_row(color, row_num)
            row_num += 1

            payout_for_player = payouts.get(color, {})
            if not isinstance(payout_for_player, dict):
                payout_for_player = {}

            total_gain = 0
            for resource in RESOURCE_ORDER:
                amt = int(payout_for_player.get(resource, 0) or 0)
                row[resource].set(str(amt))
                total_gain += amt
            row["Total"].set(str(total_gain))


def main() -> None:
    args = parse_args()
    state_file = Path(args.state_file)

    root = tk.Tk()
    _ = BigScreenViewer(root=root, state_file=state_file, poll_ms=args.poll_ms)
    root.mainloop()


if __name__ == "__main__":
    main()
