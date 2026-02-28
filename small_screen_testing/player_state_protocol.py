"""Binary protocol for Pi -> Pico player-state snapshots.

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
