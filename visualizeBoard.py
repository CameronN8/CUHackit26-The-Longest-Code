import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

RESOURCE_COLORS = {
    "wood": "#4a7c59",
    "brick": "#b55239",
    "sheep": "#97c96b",
    "wheat": "#dbc55b",
    "ore": "#7b7b88",
    "desert": "#d6b98c",
}

DEFAULT_ROAD_COLOR = "#444444"
DEFAULT_SETTLEMENT_COLOR = "#202020"
SCRIPT_DIR = Path(__file__).resolve().parent


def load_board(path: Path) -> dict:
    candidate = path
    if not candidate.is_absolute():
        script_relative = SCRIPT_DIR / candidate
        if script_relative.exists():
            candidate = script_relative

    if not candidate.exists():
        raise FileNotFoundError(
            f"Board JSON not found: {path}. "
            f"Tried: {candidate}. "
            "Pass --input with an absolute path or run from the project folder."
        )

    with candidate.open("r", encoding="utf-8") as f:
        return json.load(f)


def settlement_lookup(board: dict) -> dict[int, tuple[int, int]]:
    lookup: dict[int, tuple[int, int]] = {}
    for s in board["settlements"]:
        lookup[s["id"]] = (s["coords"]["x"], s["coords"]["y"])
    return lookup


def draw_tiles(ax, board: dict, settlement_xy: dict[int, tuple[int, int]], show_labels: bool) -> None:
    for tile in board["tiles"]:
        points = [settlement_xy[sid] for sid in tile["settlement_ids"]]
        fill = RESOURCE_COLORS.get(tile["resource_type"], "#cccccc")
        patch = Polygon(points, closed=True, facecolor=fill, edgecolor="#222222", linewidth=1.2, alpha=0.6)
        ax.add_patch(patch)

        if show_labels:
            tx = tile["coords"]["x"]
            ty = tile["coords"]["y"]
            label = tile["resource_type"]
            if tile["roll_number"] is not None:
                label = f"{label}\n{tile['roll_number']}"
            if tile.get("robber"):
                label = f"{label}\nR"
            ax.text(tx, ty, label, ha="center", va="center", fontsize=8, color="#111111")


def draw_roads(ax, board: dict, settlement_xy: dict[int, tuple[int, int]]) -> None:
    for road in board["roads"]:
        a = road["a"]
        b = road["b"]
        ax1, ay1 = settlement_xy[a]
        bx1, by1 = settlement_xy[b]
        color = road["color"] if road["color"] else DEFAULT_ROAD_COLOR
        ax.plot([ax1, bx1], [ay1, by1], color=color, linewidth=3, solid_capstyle="round", zorder=3)


def draw_settlements(ax, board: dict, show_ids: bool) -> None:
    for s in board["settlements"]:
        x = s["coords"]["x"]
        y = s["coords"]["y"]
        color = s["color"] if s["color"] else DEFAULT_SETTLEMENT_COLOR
        ax.scatter([x], [y], s=50, c=color, edgecolors="#ffffff", linewidths=0.8, zorder=4)

        if show_ids:
            ax.text(x + 7, y - 7, str(s["id"]), fontsize=7, color="#000000", zorder=5)


def bounds(settlement_xy: dict[int, tuple[int, int]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in settlement_xy.values()]
    ys = [p[1] for p in settlement_xy.values()]
    pad = 80
    return min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad


def draw_players_panel(ax, players: list[dict]) -> None:
    ax.axis("off")
    ax.set_title("Players", fontsize=11, pad=10)

    y = 0.95
    for idx, player in enumerate(players, start=1):
        color = player.get("color", "unknown")
        victory_points = player.get("victory_points", 0)
        resources = player.get("resources", {})

        resources_line = (
            f"W:{resources.get('wood', 0)}  "
            f"B:{resources.get('brick', 0)}  "
            f"S:{resources.get('sheep', 0)}  "
            f"H:{resources.get('wheat', 0)}  "
            f"O:{resources.get('ore', 0)}"
        )

        ax.text(
            0.03,
            y,
            f"P{idx} ({color})",
            transform=ax.transAxes,
            va="top",
            fontsize=10,
            fontweight="bold",
            color=color,
        )
        y -= 0.06

        ax.text(
            0.03,
            y,
            f"VP: {victory_points}",
            transform=ax.transAxes,
            va="top",
            fontsize=9,
            color="#111111",
        )
        y -= 0.05

        ax.text(
            0.03,
            y,
            resources_line,
            transform=ax.transAxes,
            va="top",
            fontsize=8,
            color="#222222",
        )
        y -= 0.10


def render(board: dict, show_ids: bool, show_labels: bool):
    settlement_xy = settlement_lookup(board)
    players = board.get("players", [])

    if players:
        fig, (ax, players_ax) = plt.subplots(
            1,
            2,
            figsize=(14, 8),
            dpi=120,
            gridspec_kw={"width_ratios": [4, 1]},
        )
        draw_players_panel(players_ax, players)
    else:
        fig, ax = plt.subplots(figsize=(12, 8), dpi=120)

    draw_tiles(ax, board, settlement_xy, show_labels=show_labels)
    draw_roads(ax, board, settlement_xy)
    draw_settlements(ax, board, show_ids=show_ids)

    x_min, x_max, y_min, y_max = bounds(settlement_xy)
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_max, y_min)  # invert y-axis to match pixel coordinates
    ax.set_aspect("equal", adjustable="box")
    ax.set_title("Catan Board Visualization")
    ax.axis("off")
    fig.tight_layout()
    return fig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize detectedGameState.json")
    parser.add_argument("--input", default="detectedGameState.json", help="Path to board JSON file")
    parser.add_argument("--output", default=None, help="Optional output image path, e.g. board.png")
    parser.add_argument("--hide-ids", action="store_true", help="Hide settlement ids")
    parser.add_argument("--hide-labels", action="store_true", help="Hide tile labels")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    board_path = Path(args.input)
    board = load_board(board_path)

    fig = render(board, show_ids=not args.hide_ids, show_labels=not args.hide_labels)

    if args.output:
        out_path = Path(args.output)
        fig.savefig(out_path, dpi=180)
        print(f"Saved visualization to {out_path.resolve()}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
