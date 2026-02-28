from __future__ import annotations

from typing import Any

SQRT3 = 3 ** 0.5

PLAYER_COLORS = ["orange", "blue", "red"]
RESOURCE_KEYS = ["wood", "brick", "sheep", "wheat", "ore"]
RESOURCE_BANK_START = 19

DEV_CARD_COUNTS = {
    "knight": 14,
    "victory_point": 5,
    "road_building": 2,
    "year_of_plenty": 2,
    "monopoly": 2,
}

BUILD_COSTS = {
    "road": {"wood": 1, "brick": 1},
    "settlement": {"wood": 1, "brick": 1, "sheep": 1, "wheat": 1},
    "city": {"wheat": 2, "ore": 3},
    "development_card": {"sheep": 1, "wheat": 1, "ore": 1},
}

CORNERS = [
    (0.0, -1.0),
    (SQRT3 / 2, -0.5),
    (SQRT3 / 2, 0.5),
    (0.0, 1.0),
    (-SQRT3 / 2, 0.5),
    (-SQRT3 / 2, -0.5),
]

AXIAL_TILES = [
    (0, -2),
    (1, -2),
    (2, -2),
    (-1, -1),
    (0, -1),
    (1, -1),
    (2, -1),
    (-2, 0),
    (-1, 0),
    (0, 0),
    (1, 0),
    (2, 0),
    (-2, 1),
    (-1, 1),
    (0, 1),
    (1, 1),
    (-2, 2),
    (-1, 2),
    (0, 2),
]


def hex_center(q: int, r: int) -> tuple[float, float]:
    x = SQRT3 * (q + r / 2.0)
    y = 1.5 * r
    return x, y


def key2(x: float, y: float) -> str:
    return f"{x:.6f},{y:.6f}"


def canonical_edge(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def road_signature(a: int, b: int) -> tuple[int, int]:
    return canonical_edge(a, b)


def tile_signature(settlement_ids: list[int]) -> tuple[int, ...]:
    return tuple(sorted(settlement_ids))


def to_pixels(
    x: float,
    y: float,
    scale: float = 115.0,
    ox: float = 960.0,
    oy: float = 540.0,
) -> tuple[int, int]:
    return int(round(ox + x * scale)), int(round(oy + y * scale))


def build_empty_resources() -> dict[str, int]:
    return {key: 0 for key in RESOURCE_KEYS}


def build_empty_dev_cards() -> dict[str, int]:
    return {card: 0 for card in DEV_CARD_COUNTS}


def build_player(color: str) -> dict[str, Any]:
    return {
        "color": color,
        "resources": build_empty_resources(),
        "development_cards": build_empty_dev_cards(),
        "played_knights": 0,
        "has_longest_road": False,
        "has_largest_army": False,
        "longest_road_length": 0,
        "pending_actions": [],
        "victory_points": 0,
    }


def build_players() -> list[dict[str, Any]]:
    return [build_player(color) for color in PLAYER_COLORS]


def build_resource_bank() -> dict[str, int]:
    return {resource: RESOURCE_BANK_START for resource in RESOURCE_KEYS}


def build_board_structure() -> dict[str, Any]:
    vertex_by_point: dict[str, int] = {}
    settlement_world: dict[int, tuple[float, float]] = {}
    tiles_vertex_ids: list[list[int]] = []

    next_settlement_id = 0

    for q, r in AXIAL_TILES:
        cx, cy = hex_center(q, r)
        corner_ids: list[int] = []

        for dx, dy in CORNERS:
            x = cx + dx
            y = cy + dy
            k = key2(x, y)

            if k not in vertex_by_point:
                sid = next_settlement_id
                next_settlement_id += 1
                vertex_by_point[k] = sid
                settlement_world[sid] = (x, y)
            else:
                sid = vertex_by_point[k]

            corner_ids.append(sid)

        tiles_vertex_ids.append(corner_ids)

    settlements: list[dict[str, Any]] = []
    for sid in sorted(settlement_world.keys()):
        x, y = settlement_world[sid]
        px, py = to_pixels(x, y)
        settlements.append(
            {
                "id": sid,
                "coords": {"x": px, "y": py},
                "cameraCoords": {"x": None, "y": None},
                "type": None,
                "color": None,
            }
        )

    edge_set: set[tuple[int, int]] = set()
    for corner_ids in tiles_vertex_ids:
        for i in range(6):
            a = corner_ids[i]
            b = corner_ids[(i + 1) % 6]
            edge_set.add(canonical_edge(a, b))

    roads: list[dict[str, Any]] = []
    for a, b in sorted(edge_set):
        ax, ay = settlement_world[a]
        bx, by = settlement_world[b]
        mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
        px, py = to_pixels(mx, my)
        roads.append(
            {
                "coords": {"x": px, "y": py},
                "cameraCoords": {"x": None, "y": None},
                "color": None,
                "a": a,
                "b": b,
            }
        )

    tiles: list[dict[str, Any]] = []
    for (q, r), settlement_ids in zip(AXIAL_TILES, tiles_vertex_ids):
        wx, wy = hex_center(q, r)
        px, py = to_pixels(wx, wy)
        tiles.append(
            {
                "coords": {"x": px, "y": py},
                "cameraCoords": {"x": None, "y": None},
                "resource_type": None,
                "roll_number": None,
                "robber": False,
                "settlement_ids": settlement_ids,
            }
        )

    return {
        "settlements": settlements,
        "roads": roads,
        "tiles": tiles,
        "players": build_players(),
    }
