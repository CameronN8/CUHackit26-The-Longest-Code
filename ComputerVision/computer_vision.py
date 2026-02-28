from __future__ import annotations

import colorsys
import json
from pathlib import Path
from typing import Any

try:
    import cv2
except ModuleNotFoundError:  # pragma: no cover - depends on runtime environment
    cv2 = None


# Tunable reference colors as HEX (easy to pick visually in VSCode).
# OpenCV HSV refs are auto-derived from these values below.
WHITE_HEX = "#F2F2F2"
ORANGE_HEX = "#F8BD28"
RED_HEX = "#9F1B1B"
BLUE_HEX = "#1A3B96"


def _clip(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def hex_to_hsv(hex_color: str) -> tuple[int, int, int]:
    """Convert #RRGGBB (or RRGGBB) to OpenCV HSV (H:0..179, S/V:0..255)."""
    value = str(hex_color).strip().lstrip("#")
    if len(value) != 6:
        raise ValueError("hex_color must be in RRGGBB format")

    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)

    h_f, s_f, v_f = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    h = int(round(h_f * 179.0))
    s = int(round(s_f * 255.0))
    v = int(round(v_f * 255.0))
    return (_clip(h, 0, 179), _clip(s, 0, 255), _clip(v, 0, 255))


def build_hsv_refs_from_hex(
    white_hex: str,
    orange_hex: str,
    red_hex: str,
    blue_hex: str,
) -> dict[str, tuple[int, int, int]]:
    """Build the 4-color HSV reference dict from hex strings."""
    return {
        "white": hex_to_hsv(white_hex),
        "orange": hex_to_hsv(orange_hex),
        "red": hex_to_hsv(red_hex),
        "blue": hex_to_hsv(blue_hex),
    }


# Tunable HSV color references (OpenCV HSV: H 0..179, S/V 0..255)
HSV_COLOR_REFS: dict[str, tuple[int, int, int]] = build_hsv_refs_from_hex(
    white_hex=WHITE_HEX,
    orange_hex=ORANGE_HEX,
    red_hex=RED_HEX,
    blue_hex=BLUE_HEX,
)


def _hsv_cartesian_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    dh = float(a[0] - b[0])
    ds = float(a[1] - b[1])
    dv = float(a[2] - b[2])
    return (dh * dh + ds * ds + dv * dv) ** 0.5


def _classify_hsv(avg_hsv: tuple[int, int, int]) -> str:
    best_color = "white"
    best_distance = float("inf")
    for color_name, ref_hsv in HSV_COLOR_REFS.items():
        distance = _hsv_cartesian_distance(avg_hsv, ref_hsv)
        if distance < best_distance:
            best_distance = distance
            best_color = color_name
    return best_color


def _sample_hsv_3x3(hsv_image: Any, center_x: int, center_y: int) -> tuple[int, int, int]:
    h, w = hsv_image.shape[:2]
    pixels = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            px = _clip(center_x + dx, 0, w - 1)
            py = _clip(center_y + dy, 0, h - 1)
            pixels.append(hsv_image[py, px])

    avg_h = int(sum(int(p[0]) for p in pixels) / 9)
    avg_s = int(sum(int(p[1]) for p in pixels) / 9)
    avg_v = int(sum(int(p[2]) for p in pixels) / 9)
    return (avg_h, avg_s, avg_v)


def _iter_color_items(game_state: dict[str, Any]):
    # Structures that own a "color" field in gameState.
    for key in ("settlements", "roads"):
        for item in game_state.get(key, []):
            if not isinstance(item, dict):
                continue
            if "color" not in item:
                continue
            coords = item.get("cameraCoords")
            if not isinstance(coords, dict):
                continue
            x = coords.get("x")
            y = coords.get("y")
            if not isinstance(x, int) or not isinstance(y, int):
                continue
            yield item, x, y


def capture_frame(camera_index: int = 1, frames_to_average: int = 3) -> Any:
    if cv2 is None:
        raise RuntimeError("OpenCV (cv2) is not installed.")
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open camera index {camera_index}. Try a different camera index."
        )

    frame = None
    for _ in range(max(1, int(frames_to_average))):
        ok, current = cap.read()
        if not ok:
            cap.release()
            raise RuntimeError("Failed to read frame from webcam.")
        frame = current

    cap.release()
    if frame is None:
        raise RuntimeError("Failed to capture frame from webcam.")
    return frame


def grab_usb_webcam_frame(camera_index: int = 1) -> Any:
    """Grab and return one frame from a USB webcam."""
    return capture_frame(camera_index=camera_index, frames_to_average=1)


def detect_structure_colors_from_frame(game_state: dict[str, Any], frame: Any) -> dict[str, int]:
    if cv2 is None:
        raise RuntimeError("OpenCV (cv2) is not installed.")
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    updated = 0
    white_hits = 0
    sampled = 0

    for item, x, y in _iter_color_items(game_state):
        sampled += 1
        avg_hsv = _sample_hsv_3x3(hsv, x, y)
        detected_color = _classify_hsv(avg_hsv)

        old_color = item.get("color")
        if detected_color == "white":
            item["color"] = None
            white_hits += 1
        else:
            item["color"] = detected_color

        if item.get("color") != old_color:
            updated += 1

    return {"sampled": sampled, "updated": updated, "white_hits": white_hits}


def detect_structure_colors(
    game_state: dict[str, Any],
    camera_index: int = 1,
    frames_to_average: int = 3,
) -> dict[str, int]:
    frame = capture_frame(camera_index=camera_index, frames_to_average=frames_to_average)
    return detect_structure_colors_from_frame(game_state, frame)


def main() -> None:
    input_path = Path("gameState.json")
    output_path = Path("detectedGameState.json")

    if not input_path.exists():
        raise FileNotFoundError(f"Input game state not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        game_state = json.load(f)

    stats = detect_structure_colors(game_state, camera_index=1, frames_to_average=3)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(game_state, f, indent=2)
        f.write("\n")

    print(f"Saved updated game state to {output_path}")
    print(f"Detection stats: {stats}")


if __name__ == "__main__":
    main()
