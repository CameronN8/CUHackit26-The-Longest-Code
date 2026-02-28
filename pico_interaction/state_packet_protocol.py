"""Binary protocol for Pi -> Pico state snapshots.

Packet format:
  byte 0   : MAGIC (0xC7)
  byte 1   : VERSION (0x01)
  byte 2   : SEQ (0..255)
  byte 3-35: payload (3 players * 11 bytes each)
  byte 36  : CHECKSUM = sum(bytes 0..35) & 0xFF

Per-player payload block (11 bytes):
  [0] wood
  [1] brick
  [2] sheep
  [3] wheat
  [4] ore
  [5] victory points
  [6] knights
  [7] victory-point dev cards
  [8] road-building
  [9] year-of-plenty
  [10] monopoly
"""

MAGIC = 0xC7
VERSION = 0x01
PLAYER_COUNT = 3
PLAYER_BLOCK_SIZE = 11
PACKET_SIZE = 37

RESOURCE_KEYS = ("wood", "brick", "sheep", "wheat", "ore")
DEV_KEYS = ("knight", "victory_point", "road_building", "year_of_plenty", "monopoly")

# Tile vector packet (separate stream type on same UART):
# [0]=MAGIC [1]=VERSION [2]=SEQ [3]=LEN [4..]=19 values [last]=CHECKSUM
TILE_VEC_MAGIC = 0xD3
TILE_VEC_VERSION = 0x01
TILE_VEC_LEN = 19
TILE_VEC_PACKET_SIZE = 24

def _clip_u8(value):
    value = int(value)
    if value < 0:
        return 0
    if value > 255:
        return 255
    return value


def _checksum(data):
    return sum(data) & 0xFF


def encode_snapshot(seq, resources_by_player, victory_points_by_player, dev_by_player):
    if len(resources_by_player) != PLAYER_COUNT:
        raise ValueError("resources_by_player must have 3 entries")
    if len(victory_points_by_player) != PLAYER_COUNT:
        raise ValueError("victory_points_by_player must have 3 entries")
    if len(dev_by_player) != PLAYER_COUNT:
        raise ValueError("dev_by_player must have 3 entries")

    out = bytearray(PACKET_SIZE)
    out[0] = MAGIC
    out[1] = VERSION
    out[2] = _clip_u8(seq)

    cursor = 3
    for idx in range(PLAYER_COUNT):
        resources = resources_by_player[idx]
        dev_cards = dev_by_player[idx]
        vp = victory_points_by_player[idx]

        for key in RESOURCE_KEYS:
            out[cursor] = _clip_u8(resources.get(key, 0))
            cursor += 1

        out[cursor] = _clip_u8(vp)
        cursor += 1

        for key in DEV_KEYS:
            out[cursor] = _clip_u8(dev_cards.get(key, 0))
            cursor += 1

    out[-1] = _checksum(out[:-1])
    return bytes(out)


def decode_snapshot(packet):
    if len(packet) != PACKET_SIZE:
        raise ValueError("bad packet size")
    if packet[0] != MAGIC:
        raise ValueError("bad magic")
    if packet[1] != VERSION:
        raise ValueError("bad version")
    if packet[-1] != _checksum(packet[:-1]):
        raise ValueError("checksum mismatch")

    seq = packet[2]
    players = []
    cursor = 3
    for _ in range(PLAYER_COUNT):
        resources = {}
        for key in RESOURCE_KEYS:
            resources[key] = packet[cursor]
            cursor += 1

        vp = packet[cursor]
        cursor += 1

        dev = {}
        for key in DEV_KEYS:
            dev[key] = packet[cursor]
            cursor += 1

        players.append({"resources": resources, "victory_points": vp, "dev_cards": dev})

    return {"seq": seq, "players": players}


def encode_tile_resource_vector(seq, vector_19):
    if len(vector_19) != TILE_VEC_LEN:
        raise ValueError("tile vector must have 19 entries")

    out = bytearray(TILE_VEC_PACKET_SIZE)
    out[0] = TILE_VEC_MAGIC
    out[1] = TILE_VEC_VERSION
    out[2] = _clip_u8(seq)
    out[3] = TILE_VEC_LEN
    for idx, value in enumerate(vector_19):
        out[4 + idx] = _clip_u8(value)
    out[-1] = _checksum(out[:-1])
    return bytes(out)


def decode_tile_resource_vector(packet):
    if len(packet) != TILE_VEC_PACKET_SIZE:
        raise ValueError("bad tile packet size")
    if packet[0] != TILE_VEC_MAGIC:
        raise ValueError("bad tile magic")
    if packet[1] != TILE_VEC_VERSION:
        raise ValueError("bad tile version")
    if packet[3] != TILE_VEC_LEN:
        raise ValueError("bad tile vector len")
    if packet[-1] != _checksum(packet[:-1]):
        raise ValueError("tile checksum mismatch")

    seq = packet[2]
    vector = list(packet[4 : 4 + TILE_VEC_LEN])
    return {"seq": seq, "vector": vector}


# Menu render packet (Pi -> player-display Pico):
# [0]=MAGIC [1]=VERSION [2]=SEQ [3]=LEN [4]=player_idx [5..88]=4*21 chars [89]=checksum
MENU_RENDER_MAGIC = 0xB9
MENU_RENDER_VERSION = 0x01
MENU_RENDER_LINES = 4
MENU_RENDER_COLS = 21
MENU_RENDER_TEXT_BYTES = MENU_RENDER_LINES * MENU_RENDER_COLS
MENU_RENDER_LEN = 1 + MENU_RENDER_TEXT_BYTES
MENU_RENDER_PACKET_SIZE = 5 + MENU_RENDER_LEN


def _to_fixed_ascii(text, width):
    s = str(text) if text is not None else ""
    s = s[:width]
    s = s.ljust(width)
    return s.encode("ascii", errors="replace")


def encode_menu_render(seq, player_idx, lines):
    if lines is None:
        lines = []
    normalized = list(lines[:MENU_RENDER_LINES])
    while len(normalized) < MENU_RENDER_LINES:
        normalized.append("")

    payload = bytearray(MENU_RENDER_LEN)
    payload[0] = _clip_u8(player_idx)
    cursor = 1
    for line in normalized:
        encoded = _to_fixed_ascii(line, MENU_RENDER_COLS)
        payload[cursor : cursor + MENU_RENDER_COLS] = encoded
        cursor += MENU_RENDER_COLS

    out = bytearray(MENU_RENDER_PACKET_SIZE)
    out[0] = MENU_RENDER_MAGIC
    out[1] = MENU_RENDER_VERSION
    out[2] = _clip_u8(seq)
    out[3] = MENU_RENDER_LEN
    out[4 : 4 + MENU_RENDER_LEN] = payload
    out[-1] = _checksum(out[:-1])
    return bytes(out)


def decode_menu_render(packet):
    if len(packet) != MENU_RENDER_PACKET_SIZE:
        raise ValueError("bad menu render packet size")
    if packet[0] != MENU_RENDER_MAGIC:
        raise ValueError("bad menu render magic")
    if packet[1] != MENU_RENDER_VERSION:
        raise ValueError("bad menu render version")
    if packet[3] != MENU_RENDER_LEN:
        raise ValueError("bad menu render len")
    if packet[-1] != _checksum(packet[:-1]):
        raise ValueError("menu render checksum mismatch")

    payload = packet[4 : 4 + MENU_RENDER_LEN]
    player_idx = payload[0]
    lines = []
    cursor = 1
    for _ in range(MENU_RENDER_LINES):
        raw = payload[cursor : cursor + MENU_RENDER_COLS]
        cursor += MENU_RENDER_COLS
        lines.append(raw.decode("ascii", errors="ignore").rstrip())
    return {"seq": packet[2], "player_idx": player_idx, "lines": lines}
