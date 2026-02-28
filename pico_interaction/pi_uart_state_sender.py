"""Pi-side snapshot sender for 3-player/9-display Pico bridge over UART.

No command-line arguments are required for normal use.
Edit constants below once, then call:
  send_players_to_pico(game_state["players"])
  send_snapshot(...)
or:
  send_from_game_state(...)
"""

import serial

from state_packet_protocol import (
    DEV_KEYS,
    RESOURCE_KEYS,
    TILE_VEC_LEN,
    encode_snapshot,
    encode_tile_resource_vector,
    encode_menu_render,
)


# ===== HARD-CODED PI -> PICO UART LINK SETTINGS =====
UART_DEVICE = "/dev/serial0"   # Pi primary UART device (GPIO14 TX / GPIO15 RX)
UART_BAUD = 115200
UART_TIMEOUT = 0.2
# =====================================================


_seq = 0
_tile_seq = 0

RESOURCE_TYPE_TO_INT = {
    "wood": 0,
    "brick": 1,
    "sheep": 2,
    "wheat": 3,
    "ore": 4,
}


def _next_seq():
    global _seq
    value = _seq
    _seq = (_seq + 1) & 0xFF
    return value


def _next_tile_seq():
    global _tile_seq
    value = _tile_seq
    _tile_seq = (_tile_seq + 1) & 0xFF
    return value


def _write_to_pico(packet):
    """Send one fully encoded packet to Pico over UART."""
    with serial.Serial(UART_DEVICE, UART_BAUD, timeout=UART_TIMEOUT) as ser:
        ser.write(packet)


def send_snapshot(
    resources_by_player: list[dict[str, int]],
    victory_points_by_player: list[int],
    dev_by_player: list[dict[str, int]],
) -> bytes:
    """Encode and send one player-state snapshot.

    Args:
        resources_by_player: list of 3 dicts; each dict should include
            wood/brick/sheep/wheat/ore counts.
        victory_points_by_player: list of 3 VP integers.
        dev_by_player: list of 3 dicts; each dict should include
            knight/victory_point/road_building/year_of_plenty/monopoly counts.

    Returns:
        Raw packet bytes that were sent.
    """
    packet = encode_snapshot(
        seq=_next_seq(),
        resources_by_player=resources_by_player,
        victory_points_by_player=victory_points_by_player,
        dev_by_player=dev_by_player,
    )
    _write_to_pico(packet)
    return packet


def send_players_to_pico(players: list[dict]) -> bytes:
    """Send the first 3 players from a game_state-style players list.

    This is the simplest integration point for your use case:
      send_players_to_pico(game_state["players"])

    Expected per-player keys:
      - resources: dict with wood/brick/sheep/wheat/ore
      - victory_points: int
      - development_cards (or dev_cards): dict with:
        knight/victory_point/road_building/year_of_plenty/monopoly

    Missing keys default to 0.
    """
    if len(players) < 3:
        raise ValueError("players must contain at least 3 entries")

    resources_by_player = []
    victory_points_by_player = []
    dev_by_player = []

    for idx in range(3):
        player = players[idx] if isinstance(players[idx], dict) else {}
        resources = player.get("resources", {})
        dev_cards = player.get("development_cards", player.get("dev_cards", {}))

        resources_by_player.append(
            {key: int(resources.get(key, 0) or 0) for key in RESOURCE_KEYS}
        )
        victory_points_by_player.append(int(player.get("victory_points", 0) or 0))
        dev_by_player.append({key: int(dev_cards.get(key, 0) or 0) for key in DEV_KEYS})

    return send_snapshot(resources_by_player, victory_points_by_player, dev_by_player)


def build_tile_resource_vector(tiles: list[dict], desert_value: int = 0) -> list[int]:
    """Convert game_state tile resource_type values into a 19-length vector of ints.

    Mapping:
      wood->0, brick->1, sheep->2, wheat->3, ore->4
      desert->desert_value (default 0 so all values remain 0..4)
    """
    if len(tiles) < TILE_VEC_LEN:
        raise ValueError("tiles must contain at least 19 entries")
    if not (0 <= int(desert_value) <= 4):
        raise ValueError("desert_value must be in range 0..4")

    out = []
    for idx in range(TILE_VEC_LEN):
        tile = tiles[idx] if isinstance(tiles[idx], dict) else {}
        resource = str(tile.get("resource_type", "")).lower()

        if resource == "desert":
            out.append(int(desert_value))
            continue
        if resource not in RESOURCE_TYPE_TO_INT:
            raise ValueError(f"unknown resource_type at tile {idx}: {resource!r}")

        out.append(RESOURCE_TYPE_TO_INT[resource])

    return out


def send_tile_resource_vector(tiles: list[dict], desert_value: int = 0) -> bytes:
    """Send a compact 19-byte tile resource vector packet over UART.

    Packet layout:
      [0] magic   = 0xD3
      [1] version = 0x01
      [2] seq
      [3] len     = 19
      [4..22] tile vector values (each 0..4)
      [23] checksum over bytes [0..22]
    """
    vector = build_tile_resource_vector(tiles, desert_value=desert_value)

    packet = encode_tile_resource_vector(_next_tile_seq(), vector)
    _write_to_pico(packet)
    return packet


def send_tile_resource_vector_from_game_state(game_state: dict, desert_value: int = 0) -> bytes:
    tiles = game_state.get("tiles", [])
    return send_tile_resource_vector(tiles, desert_value=desert_value)


def send_menu_render(player_idx: int, lines: list[str]) -> bytes:
    """Send 4 text lines for a player's interactive menu display."""
    packet = encode_menu_render(_next_seq(), player_idx, lines)
    _write_to_pico(packet)
    return packet


def send_turn_start_menu(active_player: int) -> bytes:
    lines = ["P{} Action".format(active_player + 1), ">Development", " Trading", " End Turn"]
    return send_menu_render(active_player, lines)


def send_turn_end_menu(next_active_player: int) -> bytes:
    lines = ["P{} Action".format(next_active_player + 1), ">Development", " Trading", " End Turn"]
    return send_menu_render(next_active_player, lines)


def send_from_game_state(game_state: dict) -> bytes:
    """Pull the 3-player snapshot directly from your project game_state object."""
    players = game_state.get("players", [])
    return send_players_to_pico(players)


# Optional direct smoke test with hardcoded dummy values.
def demo_send_once() -> None:
    resources = [
        {"wood": 2, "brick": 1, "sheep": 3, "wheat": 0, "ore": 1},
        {"wood": 0, "brick": 4, "sheep": 1, "wheat": 2, "ore": 2},
        {"wood": 1, "brick": 1, "sheep": 1, "wheat": 1, "ore": 1},
    ]
    vp = [3, 5, 2]
    dev = [
        {"knight": 1, "victory_point": 0, "road_building": 0, "year_of_plenty": 0, "monopoly": 0},
        {"knight": 0, "victory_point": 1, "road_building": 1, "year_of_plenty": 0, "monopoly": 0},
        {"knight": 2, "victory_point": 0, "road_building": 0, "year_of_plenty": 1, "monopoly": 0},
    ]
    packet = send_snapshot(resources, vp, dev)
    print(f"sent {len(packet)} bytes to pico on {UART_DEVICE} @ {UART_BAUD} baud")


if __name__ == "__main__":
    demo_send_once()
