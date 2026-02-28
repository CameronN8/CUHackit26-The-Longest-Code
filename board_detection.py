from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

try:
    import cv2
except ModuleNotFoundError:  # pragma: no cover - depends on runtime environment
    cv2 = None

DEFAULT_HSV_PROFILE: dict[str, tuple[int, int, int]] = {
    "orange": (15, 170, 170),
    "blue": (105, 170, 170),
    "red": (0, 170, 170),
    "board": (30, 60, 120),
}


def _clip(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _hue_circular_distance(a: int, b: int) -> float:
    d = abs(a - b)
    return float(min(d, 180 - d))


def _hsv_distance(sample: tuple[int, int, int], reference: tuple[int, int, int]) -> float:
    # Hue is circular in OpenCV HSV (0..179), so compare with wrap-around.
    h = _hue_circular_distance(sample[0], reference[0])
    s = abs(sample[1] - reference[1])
    v = abs(sample[2] - reference[2])
    return math.sqrt((2.0 * h) ** 2 + s**2 + v**2)


def _normalize_hsv_triplet(value: Any) -> tuple[int, int, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        h = int(value[0])
        s = int(value[1])
        v = int(value[2])
    except (TypeError, ValueError):
        return None
    return (_clip(h, 0, 179), _clip(s, 0, 255), _clip(v, 0, 255))


def load_hsv_profile(path: Path | None) -> dict[str, tuple[int, int, int]]:
    if path is None:
        return dict(DEFAULT_HSV_PROFILE)
    if not path.exists():
        raise FileNotFoundError(f"HSV profile file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError("HSV profile JSON must be an object.")

    profile = dict(DEFAULT_HSV_PROFILE)
    for color_name, triplet in raw.items():
        normalized = _normalize_hsv_triplet(triplet)
        if normalized is not None:
            profile[str(color_name)] = normalized
    return profile


class HSVBoardDetector:
    def __init__(
        self,
        camera_index: int = 0,
        frames_to_average: int = 5,
        max_color_distance: float = 120.0,
        hsv_profile: dict[str, tuple[int, int, int]] | None = None,
    ) -> None:
        self.camera_index = camera_index
        self.frames_to_average = max(1, frames_to_average)
        self.max_color_distance = max_color_distance
        self.hsv_profile = hsv_profile or dict(DEFAULT_HSV_PROFILE)

    def _capture_frame(self) -> Any:
        if cv2 is None:
            raise RuntimeError("OpenCV (cv2) is not installed. Install requirements first.")
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            raise RuntimeError(
                f"Could not open camera index {self.camera_index} for board detection."
            )

        frame = None
        for _ in range(self.frames_to_average):
            ok, current = cap.read()
            if ok:
                frame = current
        cap.release()

        if frame is None:
            raise RuntimeError("Failed to capture frame for board detection.")
        return frame

    def _sample_hsv_3x3(self, hsv_image: Any, x: int, y: int) -> tuple[int, int, int]:
        h, w = hsv_image.shape[:2]
        pixels = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                px = _clip(x + dx, 0, w - 1)
                py = _clip(y + dy, 0, h - 1)
                pixels.append(hsv_image[py, px])

        avg_h = int(sum(int(p[0]) for p in pixels) / len(pixels))
        avg_s = int(sum(int(p[1]) for p in pixels) / len(pixels))
        avg_v = int(sum(int(p[2]) for p in pixels) / len(pixels))
        return (avg_h, avg_s, avg_v)

    def _classify(self, sample_hsv: tuple[int, int, int]) -> tuple[str, float]:
        best_name = "board"
        best_distance = float("inf")
        for name, ref in self.hsv_profile.items():
            dist = _hsv_distance(sample_hsv, ref)
            if dist < best_distance:
                best_distance = dist
                best_name = name
        return best_name, best_distance

    @staticmethod
    def _is_valid_coord(item: dict[str, Any]) -> bool:
        coord = item.get("cameraCoords")
        if not isinstance(coord, dict):
            return False
        return isinstance(coord.get("x"), int) and isinstance(coord.get("y"), int)

    def detect_and_apply(
        self,
        game_state: dict[str, Any],
        context: str,
        player_color: str | None = None,
    ) -> dict[str, int]:
        if cv2 is None:
            raise RuntimeError("OpenCV (cv2) is not installed. Install requirements first.")
        frame = self._capture_frame()
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        detected_counts: dict[str, int] = {
            "settlements_changed": 0,
            "roads_changed": 0,
            "tiles_sampled": 0,
            "unknown_points": 0,
        }

        for settlement in game_state.get("settlements", []):
            if not isinstance(settlement, dict) or not self._is_valid_coord(settlement):
                continue
            x = settlement["cameraCoords"]["x"]
            y = settlement["cameraCoords"]["y"]
            sample_hsv = self._sample_hsv_3x3(hsv, x, y)
            color_name, distance = self._classify(sample_hsv)
            if distance > self.max_color_distance:
                detected_counts["unknown_points"] += 1
                continue

            old_type = settlement.get("type")
            old_color = settlement.get("color")

            if color_name == "board":
                settlement["type"] = None
                settlement["color"] = None
            else:
                settlement["color"] = color_name
                if old_type is None:
                    settlement["type"] = "settlement"

            if settlement.get("type") != old_type or settlement.get("color") != old_color:
                detected_counts["settlements_changed"] += 1

        for road in game_state.get("roads", []):
            if not isinstance(road, dict) or not self._is_valid_coord(road):
                continue
            x = road["cameraCoords"]["x"]
            y = road["cameraCoords"]["y"]
            sample_hsv = self._sample_hsv_3x3(hsv, x, y)
            color_name, distance = self._classify(sample_hsv)
            if distance > self.max_color_distance:
                detected_counts["unknown_points"] += 1
                continue

            old_color = road.get("color")
            road["color"] = None if color_name == "board" else color_name
            if road.get("color") != old_color:
                detected_counts["roads_changed"] += 1

        for tile in game_state.get("tiles", []):
            if not isinstance(tile, dict) or not self._is_valid_coord(tile):
                continue
            x = tile["cameraCoords"]["x"]
            y = tile["cameraCoords"]["y"]
            sample_hsv = self._sample_hsv_3x3(hsv, x, y)
            color_name, distance = self._classify(sample_hsv)
            if distance > self.max_color_distance:
                detected_counts["unknown_points"] += 1
                continue
            tile["detected_color"] = color_name
            tile["detected_hsv"] = {"h": sample_hsv[0], "s": sample_hsv[1], "v": sample_hsv[2]}
            detected_counts["tiles_sampled"] += 1

        who = player_color if player_color else "system"
        print(
            f"[DETECT] context={context} trigger={who} "
            f"settlements_changed={detected_counts['settlements_changed']} "
            f"roads_changed={detected_counts['roads_changed']} "
            f"tiles_sampled={detected_counts['tiles_sampled']} "
            f"unknown_points={detected_counts['unknown_points']}"
        )
        return detected_counts
