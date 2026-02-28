import argparse
import json
from pathlib import Path
from typing import Any

import cv2

SCRIPT_DIR = Path(__file__).resolve().parent
WINDOW_NAME = "Catan Pixel Calibration"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactively calibrate board pixel positions from a USB webcam."
    )
    parser.add_argument(
        "--input",
        default="startingBoard.json",
        help="Path to board JSON (default: startingBoard.json).",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=1,
        help="OpenCV camera index (default: 0).",
    )
    parser.add_argument(
        "--field",
        choices=["cameraCoords", "coords", "both"],
        default="cameraCoords",
        help=(
            "Which coordinate field to update: cameraCoords (default), coords, or both."
        ),
    )
    return parser.parse_args()


def resolve_input(path_text: str) -> Path:
    raw = Path(path_text)
    if raw.is_absolute():
        return raw

    script_local = SCRIPT_DIR / raw
    if script_local.exists():
        return script_local

    cwd_local = Path.cwd() / raw
    if cwd_local.exists():
        return cwd_local

    return script_local


def load_board(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Board JSON not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    required = {"settlements", "roads", "tiles"}
    if not required.issubset(data.keys()):
        raise ValueError("Board JSON missing required keys: settlements, roads, tiles")

    return data


def build_tasks(board: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []

    for s in board["settlements"]:
        sid = s["id"]
        tasks.append(
            {
                "kind": "settlement",
                "label": f"Settlement id={sid}",
                "item": s,
                "short": f"S{sid}",
            }
        )

    for r in board["roads"]:
        a = r["a"]
        b = r["b"]
        tasks.append(
            {
                "kind": "road",
                "label": f"Road a={a}, b={b}",
                "item": r,
                "short": f"R({a},{b})",
            }
        )

    for t in board["tiles"]:
        vec = t["settlement_ids"]
        tasks.append(
            {
                "kind": "tile",
                "label": f"Tile settlement_ids={vec}",
                "item": t,
                "short": f"T{vec}",
            }
        )

    return tasks


def print_task_lists(board: dict[str, Any]) -> None:
    print("\nSettlements:")
    print(", ".join(str(s["id"]) for s in board["settlements"]))

    print("\nRoad id pairs (a,b):")
    print(", ".join(f"({r['a']},{r['b']})" for r in board["roads"]))

    print("\nTile id vectors (settlement_ids):")
    for i, t in enumerate(board["tiles"]):
        print(f"{i:02d}: {t['settlement_ids']}")


def set_coord(item: dict[str, Any], x: int, y: int, field: str) -> None:
    if field in ("cameraCoords", "both"):
        item["cameraCoords"] = {"x": x, "y": y}

    if field in ("coords", "both"):
        item["coords"] = {"x": x, "y": y}


def draw_overlay(frame, index: int, total: int, label: str, field: str) -> Any:
    out = frame.copy()
    lines = [
        f"Target {index + 1}/{total}",
        label,
        f"Writing: {field}",
        "Left click = record",
        "N = skip, B = back, Q/ESC = quit+save",
    ]

    y = 28
    for line in lines:
        cv2.putText(
            out,
            line,
            (16, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        y += 28

    return out


def save_board(board: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(board, indent=2), encoding="utf-8")


def run_calibration(board: dict[str, Any], board_path: Path, camera_index: int, field: str) -> None:
    tasks = build_tasks(board)
    total = len(tasks)

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open camera index {camera_index}. Try a different --camera-index."
        )

    clicked = {"point": None}

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN:
            clicked["point"] = (x, y)

    cv2.namedWindow(WINDOW_NAME)
    cv2.setMouseCallback(WINDOW_NAME, on_mouse)

    idx = 0

    try:
        while idx < total:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("Failed to read frame from webcam.")

            task = tasks[idx]
            shown = draw_overlay(frame, idx, total, task["label"], field)
            cv2.imshow(WINDOW_NAME, shown)

            key = cv2.waitKey(10) & 0xFF

            if clicked["point"] is not None:
                x, y = clicked["point"]
                clicked["point"] = None
                set_coord(task["item"], x, y, field)
                save_board(board, board_path)
                print(f"[{idx + 1:03d}/{total}] {task['label']} -> ({x}, {y})")
                idx += 1
                continue

            if key in (ord("q"), 27):
                print("Stopping calibration early. Progress saved.")
                break

            if key in (ord("n"),):
                print(f"[{idx + 1:03d}/{total}] SKIPPED {task['label']}")
                idx += 1
                continue

            if key in (ord("b"),):
                idx = max(0, idx - 1)
                print(f"Moved back to target {idx + 1}/{total}")

    finally:
        cap.release()
        cv2.destroyAllWindows()

    save_board(board, board_path)
    print(f"Calibration data saved to {board_path}")


def main() -> None:
    args = parse_args()
    board_path = resolve_input(args.input)
    board = load_board(board_path)

    print_task_lists(board)
    print("\nStarting camera calibration...")
    run_calibration(
        board=board,
        board_path=board_path,
        camera_index=args.camera_index,
        field=args.field,
    )


if __name__ == "__main__":
    main()
