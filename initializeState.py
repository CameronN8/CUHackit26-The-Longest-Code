import argparse
import json
from pathlib import Path
from typing import Any

from board_utils import build_board_structure, road_signature, tile_signature

SCRIPT_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset startingBoard.json to blank gameplay state while preserving cameraCoords."
    )
    parser.add_argument(
        "--output",
        default="startingBoard.json",
        help="Output JSON path (default: startingBoard.json).",
    )
    parser.add_argument(
        "--preserve-camera",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Preserve cameraCoords from existing output file (default: true).",
    )
    return parser.parse_args()


def normalize_camera_coords(value: Any) -> dict[str, int | None]:
    if isinstance(value, dict):
        x = value.get("x")
        y = value.get("y")
        if isinstance(x, int) or x is None:
            if isinstance(y, int) or y is None:
                return {"x": x, "y": y}
    return {"x": None, "y": None}


def load_existing(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def preserve_camera_coords(new_board: dict[str, Any], existing: dict[str, Any]) -> None:
    existing_settlements = {
        s.get("id"): normalize_camera_coords(s.get("cameraCoords"))
        for s in existing.get("settlements", [])
        if isinstance(s, dict) and isinstance(s.get("id"), int)
    }

    existing_roads = {}
    for r in existing.get("roads", []):
        if not isinstance(r, dict):
            continue
        a = r.get("a")
        b = r.get("b")
        if isinstance(a, int) and isinstance(b, int):
            existing_roads[road_signature(a, b)] = normalize_camera_coords(
                r.get("cameraCoords")
            )

    existing_tiles = {}
    for t in existing.get("tiles", []):
        if not isinstance(t, dict):
            continue
        ids = t.get("settlement_ids")
        if isinstance(ids, list) and all(isinstance(v, int) for v in ids):
            existing_tiles[tile_signature(ids)] = normalize_camera_coords(
                t.get("cameraCoords")
            )

    for s in new_board["settlements"]:
        sid = s["id"]
        if sid in existing_settlements:
            s["cameraCoords"] = existing_settlements[sid]

    for r in new_board["roads"]:
        sig = road_signature(r["a"], r["b"])
        if sig in existing_roads:
            r["cameraCoords"] = existing_roads[sig]

    for t in new_board["tiles"]:
        sig = tile_signature(t["settlement_ids"])
        if sig in existing_tiles:
            t["cameraCoords"] = existing_tiles[sig]


def main() -> None:
    args = parse_args()
    out_raw = Path(args.output)
    out_path = out_raw if out_raw.is_absolute() else (SCRIPT_DIR / out_raw)

    board = build_board_structure()

    if args.preserve_camera:
        existing = load_existing(out_path)
        if existing is not None:
            preserve_camera_coords(board, existing)

    out_path.write_text(json.dumps(board, indent=2), encoding="utf-8")

    print(
        f"Wrote {out_path} with {len(board['settlements'])} settlements, "
        f"{len(board['roads'])} roads, {len(board['tiles'])} tiles, "
        f"and {len(board['players'])} players. preserve_camera={args.preserve_camera}"
    )


if __name__ == "__main__":
    main()
