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
    "wood": ["wood.png"],
    "brick": ["brick.png"],
    "sheep": ["sheep.png", "Sheep.png", "sheep_icon.png"],
    "wheat": ["wheat.png"],
    "ore": ["ore.png"],
}
DICE_ICON_FILES = {
    1: "dice_1.png",
    2: "dice_2.png",
    3: "dice_3.png",
    4: "dice_4.png",
    5: "dice_5.png",
    6: "dice_6.png",
}
DEV_ICON_CANDIDATES = ["development_card.png", "dev_card.png", "development.png"]
PLAYER_COLORS = {
    "orange": "#f39c12",
    "blue": "#2980b9",
    "red": "#c0392b",
    "white": "#ecf0f1",
}

PANEL_BG = "#f6f8fc"
APP_BG = "#ffffff"
TXT = "#111111"
MUTED = "#5c6472"


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
        self.bank_resource_icons: dict[str, tk.PhotoImage] = {}
        self.dice_icons: dict[int, tk.PhotoImage] = {}
        self.dev_icon: tk.PhotoImage | None = None
        self.bank_dev_icon: tk.PhotoImage | None = None

        self.root.title("Catan Display")
        self.root.configure(bg=APP_BG)
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
        for resource, filenames in RESOURCE_ICON_FILES.items():
            icon = None
            selected_path: Path | None = None
            for filename in filenames:
                candidate = ASSETS_DIR / filename
                icon = self._load_png_scaled(candidate, max_px=56)
                if icon is not None:
                    selected_path = candidate
                    break
            if icon is None or selected_path is None:
                for asset_path in ASSETS_DIR.iterdir():
                    if not asset_path.is_file():
                        continue
                    if asset_path.suffix.lower() != ".png":
                        continue
                    name = asset_path.stem.lower()
                    if name == resource or name.startswith(f"{resource}_"):
                        icon = self._load_png_scaled(asset_path, max_px=56)
                        if icon is not None:
                            selected_path = asset_path
                            break
            if icon is not None:
                self.resource_icons[resource] = icon
                # Cards Remaining uses larger, direct-from-source icons to avoid pixelation.
                if selected_path is not None:
                    bank_icon = self._load_png_scaled(selected_path, max_px=112)
                    if bank_icon is not None:
                        self.bank_resource_icons[resource] = bank_icon

        for face, filename in DICE_ICON_FILES.items():
            icon = self._load_png_scaled(ASSETS_DIR / filename, max_px=128)
            if icon is not None:
                self.dice_icons[face] = icon

        for filename in DEV_ICON_CANDIDATES:
            icon = self._load_png_scaled(ASSETS_DIR / filename, max_px=56)
            if icon is not None:
                self.dev_icon = icon
                bank_icon = self._load_png_scaled(ASSETS_DIR / filename, max_px=112)
                if bank_icon is not None:
                    self.bank_dev_icon = bank_icon
                break

    def _make_panel(self, parent: tk.Widget, title: str) -> tk.Frame:
        panel = tk.Frame(parent, bg=PANEL_BG, bd=1, relief="solid")
        tk.Label(
            panel,
            text=title,
            bg=PANEL_BG,
            fg=TXT,
            font=("Helvetica", 16, "bold"),
        ).pack(anchor="center", pady=(10, 6))
        return panel

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=APP_BG, padx=12, pady=10)
        outer.pack(fill="both", expand=True)

        grid = tk.Frame(outer, bg=APP_BG)
        grid.pack(fill="both", expand=True)

        for col in range(3):
            grid.grid_columnconfigure(col, weight=1, uniform="col")
        for row in range(2):
            grid.grid_rowconfigure(row, weight=1, uniform="row")

        self.panel_top_left = self._make_panel(grid, "Resources Gained")
        self.panel_top_left.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self.panel_top_mid = self._make_panel(grid, "Roll")
        self.panel_top_mid.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)

        self.panel_top_right = self._make_panel(grid, "Cards Remaining")
        self.panel_top_right.grid(row=0, column=2, sticky="nsew", padx=6, pady=6)

        self.panel_bottom_1 = self._make_panel(grid, "")
        self.panel_bottom_1.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)

        self.panel_bottom_2 = self._make_panel(grid, "")
        self.panel_bottom_2.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)

        self.panel_bottom_3 = self._make_panel(grid, "")
        self.panel_bottom_3.grid(row=1, column=2, sticky="nsew", padx=6, pady=6)

        self.gains_body = tk.Frame(self.panel_top_left, bg=PANEL_BG)
        self.gains_body.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        roll_body = tk.Frame(self.panel_top_mid, bg=PANEL_BG)
        roll_body.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self.turn_var = tk.StringVar(value="Turn: -")
        tk.Label(
            roll_body,
            textvariable=self.turn_var,
            bg=PANEL_BG,
            fg=MUTED,
            font=("Helvetica", 14, "bold"),
        ).pack(anchor="center", pady=(1, 4))

        dice_row = tk.Frame(roll_body, bg=PANEL_BG)
        dice_row.pack(anchor="center", pady=(0, 3))

        self.die_1_text = tk.StringVar(value="-")
        self.die_2_text = tk.StringVar(value="-")

        self.die_1_label = tk.Label(
            dice_row,
            textvariable=self.die_1_text,
            bg=PANEL_BG,
            fg=TXT,
            font=("Helvetica", 20, "bold"),
            width=3,
            height=1,
            bd=0,
            relief="flat",
            highlightthickness=0,
        )
        self.die_1_label.pack(side="left", padx=7)

        tk.Label(
            dice_row,
            text="+",
            bg=PANEL_BG,
            fg=TXT,
            font=("Helvetica", 18, "bold"),
        ).pack(side="left", padx=4)

        self.die_2_label = tk.Label(
            dice_row,
            textvariable=self.die_2_text,
            bg=PANEL_BG,
            fg=TXT,
            font=("Helvetica", 20, "bold"),
            width=3,
            height=1,
            bd=0,
            relief="flat",
            highlightthickness=0,
        )
        self.die_2_label.pack(side="left", padx=7)

        self.total_var = tk.StringVar(value="Total: -")
        tk.Label(
            roll_body,
            textvariable=self.total_var,
            bg=PANEL_BG,
            fg=TXT,
            font=("Helvetica", 20, "bold"),
        ).pack(anchor="center", pady=(2, 0))

        bank_body = tk.Frame(self.panel_top_right, bg=PANEL_BG)
        bank_body.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.bank_grid = tk.Frame(bank_body, bg=PANEL_BG)
        self.bank_grid.pack(expand=True)

        self.bank_card_vars: dict[str, tk.StringVar] = {
            "wood": tk.StringVar(value="-"),
            "brick": tk.StringVar(value="-"),
            "sheep": tk.StringVar(value="-"),
            "wheat": tk.StringVar(value="-"),
            "ore": tk.StringVar(value="-"),
            "dev": tk.StringVar(value="-"),
        }

        bank_order = ["wood", "brick", "sheep", "wheat", "ore", "dev"]
        for i, key in enumerate(bank_order):
            row = i // 3
            col = i % 3
            self._make_bank_card_cell(self.bank_grid, row, col, key, self.bank_card_vars[key])

        self.player_panels = [self.panel_bottom_1, self.panel_bottom_2, self.panel_bottom_3]
        self.player_title_labels: list[tk.Label] = []
        self.player_resource_vars: list[tk.StringVar] = []
        self.player_dev_vars: list[tk.StringVar] = []

        for i, panel in enumerate(self.player_panels):
            title_label = tk.Label(
                panel,
                text=f"Player {i + 1}",
                bg=PANEL_BG,
                fg=TXT,
                font=("Helvetica", 18, "bold"),
            )
            title_label.pack(anchor="center", pady=(10, 6))
            self.player_title_labels.append(title_label)

            body = tk.Frame(panel, bg=PANEL_BG)
            body.pack(fill="both", expand=True)

            r_var = tk.StringVar(value="Resources: -")
            d_var = tk.StringVar(value="Dev Cards: -")
            self.player_resource_vars.append(r_var)
            self.player_dev_vars.append(d_var)

            tk.Label(
                body,
                textvariable=r_var,
                bg=PANEL_BG,
                fg=TXT,
                font=("Helvetica", 17, "bold"),
            ).pack(anchor="center", pady=(30, 10))
            tk.Label(
                body,
                textvariable=d_var,
                bg=PANEL_BG,
                fg=MUTED,
                font=("Helvetica", 16, "bold"),
            ).pack(anchor="center")

        self.status_var = tk.StringVar(value=f"Watching: {self.state_file}")
        tk.Label(
            outer,
            textvariable=self.status_var,
            bg=APP_BG,
            fg="#707985",
            font=("Helvetica", 10),
        ).pack(anchor="w", pady=(6, 0))

        self.root.bind("<Escape>", lambda _e: self.root.attributes("-fullscreen", False))
        self.root.bind("<F11>", lambda _e: self.root.attributes("-fullscreen", True))

    def _set_die_label(self, label: tk.Label, value: object, text_var: tk.StringVar) -> None:
        if isinstance(value, int) and value in self.dice_icons:
            icon = self.dice_icons[value]
            label.configure(image=icon, text="", width=icon.width(), height=icon.height())
            label.image = icon
            text_var.set("")
            return

        label.configure(image="", width=3, height=1)
        text_var.set(str(value) if isinstance(value, int) else "-")

    def _make_bank_card_cell(
        self, parent: tk.Widget, row: int, col: int, key: str, value_var: tk.StringVar
    ) -> None:
        cell = tk.Frame(parent, bg="#ffffff", bd=1, relief="solid", padx=2, pady=2)
        cell.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)
        parent.grid_rowconfigure(row, weight=1)

        icon_holder = tk.Frame(cell, bg="#ffffff", width=132, height=126)
        icon_holder.pack(pady=(0, 0))
        icon_holder.pack_propagate(False)

        icon = self.bank_dev_icon if key == "dev" else self.bank_resource_icons.get(key)
        if icon is not None:
            icon_label = tk.Label(icon_holder, image=icon, bg="#ffffff")
            icon_label.image = icon
            icon_label.place(relx=0.5, rely=0.46, anchor="center")
        else:
            fallback = "Dev" if key == "dev" else key.title()
            tk.Label(
                icon_holder,
                text=fallback,
                bg="#ffffff",
                fg=MUTED,
                font=("Helvetica", 15, "bold"),
            ).place(relx=0.5, rely=0.46, anchor="center")

        count_label = tk.Label(
            cell,
            textvariable=value_var,
            bg="#ffffff",
            fg=TXT,
            font=("Helvetica", 10, "bold"),
        )
        count_label.place(relx=0.5, rely=1.0, x=0, y=-2, anchor="s")
        count_label.lift()

    def _render_gain_lines(self, players: list[dict], payouts: dict[str, dict[str, int]]) -> None:
        for child in self.gains_body.winfo_children():
            child.destroy()

        shown = 0
        for player in players[:3]:
            if not isinstance(player, dict):
                continue

            color = str(player.get("color", "unknown"))
            payout = payouts.get(color, {})
            if not isinstance(payout, dict):
                payout = {}

            row = tk.Frame(self.gains_body, bg=PANEL_BG)
            row.pack(fill="x", pady=2)

            circle_wrap = tk.Frame(row, bg=PANEL_BG, width=40, height=40)
            circle_wrap.pack(side="left", padx=(0, 12))
            circle_wrap.pack_propagate(False)
            canvas = tk.Canvas(
                circle_wrap,
                width=36,
                height=36,
                bg=PANEL_BG,
                highlightthickness=0,
                bd=0,
            )
            canvas.pack()
            circle_color = PLAYER_COLORS.get(color.lower(), "#7f8c8d")
            canvas.create_oval(3, 3, 33, 33, fill=circle_color, outline="#333333")

            segments = 0
            for resource in RESOURCE_ORDER:
                amount = int(payout.get(resource, 0) or 0)
                if amount <= 0:
                    continue

                tk.Label(
                    row,
                    text=f"+{amount}",
                    bg=PANEL_BG,
                    fg=TXT,
                    font=("Helvetica", 21, "bold"),
                ).pack(side="left", padx=(0, 4))

                icon = self.resource_icons.get(resource)
                if icon is not None:
                    icon_label = tk.Label(row, image=icon, bg=PANEL_BG)
                    icon_label.image = icon
                    icon_label.pack(side="left", padx=(0, 8))
                else:
                    tk.Label(
                        row,
                        text=resource.title(),
                        bg=PANEL_BG,
                        fg=MUTED,
                        font=("Helvetica", 18, "bold"),
                    ).pack(side="left", padx=(0, 8))
                segments += 1

            if segments == 0:
                tk.Label(
                    row,
                    text="+0",
                    bg=PANEL_BG,
                    fg=MUTED,
                    font=("Helvetica", 21, "bold"),
                ).pack(side="left")

            shown += 1

        while shown < 3:
            row = tk.Frame(self.gains_body, bg=PANEL_BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text="-", bg=PANEL_BG, fg=MUTED, font=("Helvetica", 18, "bold")).pack(
                side="left"
            )
            shown += 1

    def _render_player_summaries(self, players: list[dict]) -> None:
        for idx in range(3):
            if idx >= len(players) or not isinstance(players[idx], dict):
                self.player_title_labels[idx].configure(text="")
                self.player_resource_vars[idx].set("Resources: -")
                self.player_dev_vars[idx].set("Dev Cards: -")
                continue

            player = players[idx]
            color = str(player.get("color", f"Player {idx + 1}")).title()
            resources = player.get("resources", {})
            dev_cards = player.get("development_cards", {})

            total_resources = 0
            if isinstance(resources, dict):
                total_resources = sum(int(resources.get(r, 0) or 0) for r in RESOURCE_ORDER)

            total_dev_cards = 0
            if isinstance(dev_cards, dict):
                total_dev_cards = sum(int(v or 0) for v in dev_cards.values())

            self.player_title_labels[idx].configure(text=color)
            self.player_resource_vars[idx].set(f"Resources: {total_resources}")
            self.player_dev_vars[idx].set(f"Dev Cards: {total_dev_cards}")

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

        if not isinstance(state, dict):
            self.status_var.set("Invalid state format")
            return

        game = state.get("game", {})
        players = state.get("players", [])
        bank = state.get("bank", {})

        if not isinstance(game, dict):
            game = {}
        if not isinstance(players, list):
            players = []
        if not isinstance(bank, dict):
            bank = {}

        last_roll = game.get("last_roll")
        if not isinstance(last_roll, dict):
            last_roll = {}

        die_1 = last_roll.get("die_1")
        die_2 = last_roll.get("die_2")
        total = last_roll.get("total")
        turn_number = game.get("turn_number")

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

        bank_resources = bank.get("resources", {})
        if isinstance(bank_resources, dict):
            for resource in RESOURCE_ORDER:
                self.bank_card_vars[resource].set(str(int(bank_resources.get(resource, 0) or 0)))
        else:
            for resource in RESOURCE_ORDER:
                self.bank_card_vars[resource].set("-")

        dev_deck = bank.get("development_deck", [])
        if isinstance(dev_deck, list):
            self.bank_card_vars["dev"].set(str(len(dev_deck)))
        else:
            self.bank_card_vars["dev"].set("-")

        normalized_players = [p for p in players if isinstance(p, dict)]

        self._render_gain_lines(normalized_players, normalized_payouts)
        self._render_player_summaries(normalized_players)
        self.status_var.set(f"Watching: {self.state_file}")


def main() -> None:
    args = parse_args()
    state_file = Path(args.state_file)

    root = tk.Tk()
    _ = BigScreenViewer(root=root, state_file=state_file, poll_ms=args.poll_ms)
    root.mainloop()


if __name__ == "__main__":
    main()
