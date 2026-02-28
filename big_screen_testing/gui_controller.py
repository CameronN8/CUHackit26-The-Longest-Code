#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tkinter as tk

RESOURCE_ORDER = ["wood", "brick", "sheep", "wheat", "ore"]
ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STATE_FILE = ROOT_DIR / "runtimeState.json"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"

RESOURCE_ICON_FILES = {
    "wood": "wood.png",
    "brick": "brick.png",
    "sheep": "sheep.png",
    "wheat": "wheat.png",
    "ore": "ore.png",
}
DICE_ICON_FILES = {
    1: "dice_1.png",
    2: "dice_2.png",
    3: "dice_3.png",
    4: "dice_4.png",
    5: "dice_5.png",
    6: "dice_6.png",
}


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
        self.resource_icons: dict[str, tk.PhotoImage] = {}
        self.dice_icons: dict[int, tk.PhotoImage] = {}

        self.root.title("Catan Roll Display")
        self.root.configure(bg="#ffffff")
        self.root.attributes("-fullscreen", True)

        self._load_icons()
        self._build_ui()
        self._poll_state_file()

    def _load_png_scaled(self, path: Path, max_px: int) -> tk.PhotoImage | None:
        if not path.exists():
            return None
        try:
            img = tk.PhotoImage(file=str(path))
        except Exception:
            return None

        while img.width() > max_px or img.height() > max_px:
            img = img.subsample(2, 2)
        return img

    def _load_icons(self) -> None:
        for resource, filename in RESOURCE_ICON_FILES.items():
            icon = self._load_png_scaled(ASSETS_DIR / filename, max_px=56)
            if icon is not None:
                self.resource_icons[resource] = icon

        for face, filename in DICE_ICON_FILES.items():
            icon = self._load_png_scaled(ASSETS_DIR / filename, max_px=96)
            if icon is not None:
                self.dice_icons[face] = icon

    def _build_ui(self) -> None:
        self.container = tk.Frame(self.root, bg="#ffffff", padx=18, pady=14)
        self.container.pack(fill="both", expand=True)

        tk.Label(
            self.container,
            text="Catan Live Roll",
            bg="#ffffff",
            fg="#111111",
            font=("Helvetica", 24, "bold"),
        ).pack(anchor="center", pady=(0, 8))

        top = tk.Frame(self.container, bg="#ffffff")
        top.pack(fill="x", pady=(0, 8))

        self.turn_var = tk.StringVar(value="Turn: -")
        tk.Label(
            top,
            textvariable=self.turn_var,
            bg="#ffffff",
            fg="#222222",
            font=("Helvetica", 16, "bold"),
        ).pack(anchor="center", pady=(0, 8))

        dice_row = tk.Frame(top, bg="#ffffff")
        dice_row.pack(anchor="center")

        self.die_1_text = tk.StringVar(value="-")
        self.die_2_text = tk.StringVar(value="-")

        self.die_1_label = tk.Label(
            dice_row,
            textvariable=self.die_1_text,
            bg="#f6f8fb",
            fg="#111111",
            font=("Helvetica", 36, "bold"),
            width=3,
            height=1,
            relief="solid",
            bd=1,
        )
        self.die_1_label.pack(side="left", padx=8)

        tk.Label(
            dice_row,
            text="+",
            bg="#ffffff",
            fg="#111111",
            font=("Helvetica", 30, "bold"),
        ).pack(side="left", padx=6)

        self.die_2_label = tk.Label(
            dice_row,
            textvariable=self.die_2_text,
            bg="#f6f8fb",
            fg="#111111",
            font=("Helvetica", 36, "bold"),
            width=3,
            height=1,
            relief="solid",
            bd=1,
        )
        self.die_2_label.pack(side="left", padx=8)

        self.total_var = tk.StringVar(value="Total: -")
        tk.Label(
            top,
            textvariable=self.total_var,
            bg="#ffffff",
            fg="#111111",
            font=("Helvetica", 22, "bold"),
        ).pack(anchor="center", pady=(8, 0))

        tk.Label(
            self.container,
            text="Resources Gained This Roll",
            bg="#ffffff",
            fg="#111111",
            font=("Helvetica", 20, "bold"),
        ).pack(anchor="w", pady=(12, 8))

        self.table = tk.Frame(self.container, bg="#d5dbe5")
        self.table.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value=f"Watching: {self.state_file}")
        tk.Label(
            self.container,
            textvariable=self.status_var,
            bg="#ffffff",
            fg="#666666",
            font=("Helvetica", 11),
        ).pack(anchor="w", pady=(8, 0))

        self.root.bind("<Escape>", lambda _e: self.root.attributes("-fullscreen", False))
        self.root.bind("<F11>", lambda _e: self.root.attributes("-fullscreen", True))

    def _make_cell(
        self,
        row: int,
        col: int,
        text: str = "",
        *,
        bold: bool = False,
        pad_y: int = 6,
    ) -> tk.Label:
        label = tk.Label(
            self.table,
            text=text,
            bg="#ffffff",
            fg="#111111",
            font=("Helvetica", 14, "bold" if bold else "normal"),
            padx=8,
            pady=pad_y,
            relief="flat",
        )
        label.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)
        return label

    def _render_table(self, players: list[dict], payouts: dict[str, dict[str, int]]) -> None:
        for child in self.table.winfo_children():
            child.destroy()

        columns = ["Player"] + RESOURCE_ORDER + ["Total"]
        for col in range(len(columns)):
            self.table.grid_columnconfigure(col, weight=1)

        self._make_cell(0, 0, "", bold=True, pad_y=12)
        for idx, resource in enumerate(RESOURCE_ORDER, start=1):
            icon = self.resource_icons.get(resource)
            if icon is None:
                self._make_cell(0, idx, resource.title(), bold=True, pad_y=12)
            else:
                label = self._make_cell(0, idx, "", bold=True, pad_y=12)
                label.configure(image=icon)
                label.image = icon
        self._make_cell(0, len(columns) - 1, "Total", bold=True, pad_y=12)

        row = 1
        for player in players:
            color = str(player.get("color", "unknown"))
            payout = payouts.get(color, {})

            self._make_cell(row, 0, color.upper(), bold=True)

            total_gain = 0
            for c, resource in enumerate(RESOURCE_ORDER, start=1):
                amount = int(payout.get(resource, 0) or 0)
                total_gain += amount
                self._make_cell(row, c, str(amount))

            self._make_cell(row, len(columns) - 1, str(total_gain), bold=True)
            row += 1

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

    def _set_die_label(self, label: tk.Label, value: object, text_var: tk.StringVar) -> None:
        if isinstance(value, int) and value in self.dice_icons:
            icon = self.dice_icons[value]
            label.configure(image=icon, text="", width=icon.width(), height=icon.height())
            label.image = icon
            text_var.set("")
            return

        label.configure(image="", width=3, height=2)
        text_var.set(str(value) if isinstance(value, int) else "-")

    def _load_and_render_state(self) -> None:
        try:
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception as exc:
            self.status_var.set(f"Invalid JSON: {exc}")
            return

        game = state.get("game", {}) if isinstance(state, dict) else {}
        players = state.get("players", []) if isinstance(state, dict) else []

        if not isinstance(game, dict):
            game = {}
        if not isinstance(players, list):
            players = []

        last_roll = game.get("last_roll") if isinstance(game, dict) else None
        die_1 = last_roll.get("die_1") if isinstance(last_roll, dict) else None
        die_2 = last_roll.get("die_2") if isinstance(last_roll, dict) else None
        total = last_roll.get("total") if isinstance(last_roll, dict) else None
        turn_number = game.get("turn_number") if isinstance(game, dict) else None

        self.turn_var.set(f"Turn: {turn_number}" if isinstance(turn_number, int) else "Turn: -")
        self.total_var.set(f"Total: {total}" if isinstance(total, int) else "Total: -")
        self._set_die_label(self.die_1_label, die_1, self.die_1_text)
        self._set_die_label(self.die_2_label, die_2, self.die_2_text)

        payouts = game.get("last_roll_payouts", {})
        if not isinstance(payouts, dict):
            payouts = {}

        normalized_payouts: dict[str, dict[str, int]] = {}
        for color, payout in payouts.items():
            if not isinstance(payout, dict):
                continue
            normalized_payouts[str(color)] = {
                resource: int(payout.get(resource, 0) or 0) for resource in RESOURCE_ORDER
            }

        normalized_players: list[dict] = []
        for player in players:
            if not isinstance(player, dict):
                continue
            normalized_players.append(player)

        self._render_table(normalized_players, normalized_payouts)
        self.status_var.set(f"Watching: {self.state_file}")


def main() -> None:
    args = parse_args()
    state_file = Path(args.state_file)

    root = tk.Tk()
    _ = BigScreenViewer(root=root, state_file=state_file, poll_ms=args.poll_ms)
    root.mainloop()


if __name__ == "__main__":
    main()
