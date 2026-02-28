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

# Menu control packet (Pi -> player-display Pico):
# [0]=MAGIC [1]=VERSION [2]=SEQ [3]=LEN [4]=active_player [5]=flags [6]=checksum
MENU_CTRL_MAGIC = 0xB7
MENU_CTRL_VERSION = 0x01
MENU_CTRL_LEN = 2
MENU_CTRL_PACKET_SIZE = 7
MENU_CTRL_FLAG_RESET = 0x01

# Menu event packet (player-display Pico -> Pi):
# [0]=MAGIC [1]=VERSION [2]=SEQ [3]=LEN [4..]=payload [last]=checksum
MENU_EVT_MAGIC = 0xE5
MENU_EVT_VERSION = 0x01

MENU_EVT_END_TURN = 1
MENU_EVT_BUY_DEV = 2
MENU_EVT_USE_DEV = 3
MENU_EVT_TRADE_PLAYER = 4
MENU_EVT_TRADE_PORT = 5

DEV_CARD_TO_ID = {
    "knight": 0,
    "victory_point": 1,
    "road_building": 2,
    "year_of_plenty": 3,
    "monopoly": 4,
}
DEV_ID_TO_CARD = {v: k for k, v in DEV_CARD_TO_ID.items()}


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


def encode_menu_control(seq, active_player, reset_menu):
    out = bytearray(MENU_CTRL_PACKET_SIZE)
    out[0] = MENU_CTRL_MAGIC
    out[1] = MENU_CTRL_VERSION
    out[2] = _clip_u8(seq)
    out[3] = MENU_CTRL_LEN
    out[4] = _clip_u8(active_player)
    flags = MENU_CTRL_FLAG_RESET if reset_menu else 0
    out[5] = flags
    out[6] = _checksum(out[:-1])
    return bytes(out)


def decode_menu_control(packet):
    if len(packet) != MENU_CTRL_PACKET_SIZE:
        raise ValueError("bad menu control packet size")
    if packet[0] != MENU_CTRL_MAGIC:
        raise ValueError("bad menu control magic")
    if packet[1] != MENU_CTRL_VERSION:
        raise ValueError("bad menu control version")
    if packet[3] != MENU_CTRL_LEN:
        raise ValueError("bad menu control len")
    if packet[-1] != _checksum(packet[:-1]):
        raise ValueError("menu control checksum mismatch")

    return {
        "seq": packet[2],
        "active_player": packet[4],
        "reset_menu": bool(packet[5] & MENU_CTRL_FLAG_RESET),
    }


def encode_menu_event(seq, event):
    etype = int(event.get("type", 0))
    payload = bytearray()
    payload.append(_clip_u8(etype))

    if etype == MENU_EVT_USE_DEV:
        card = str(event.get("card", "knight"))
        payload.append(_clip_u8(DEV_CARD_TO_ID.get(card, 0)))
    elif etype == MENU_EVT_TRADE_PLAYER:
        payload.append(_clip_u8(event.get("target_player", 0)))
        give = event.get("give", [0, 0, 0, 0, 0])
        receive = event.get("receive", [0, 0, 0, 0, 0])
        for i in range(5):
            payload.append(_clip_u8(give[i] if i < len(give) else 0))
        for i in range(5):
            payload.append(_clip_u8(receive[i] if i < len(receive) else 0))

    out = bytearray(5 + len(payload))
    out[0] = MENU_EVT_MAGIC
    out[1] = MENU_EVT_VERSION
    out[2] = _clip_u8(seq)
    out[3] = len(payload)
    out[4 : 4 + len(payload)] = payload
    out[-1] = _checksum(out[:-1])
    return bytes(out)


def decode_menu_event(packet):
    if len(packet) < 6:
        raise ValueError("menu event packet too short")
    if packet[0] != MENU_EVT_MAGIC:
        raise ValueError("bad menu event magic")
    if packet[1] != MENU_EVT_VERSION:
        raise ValueError("bad menu event version")

    payload_len = packet[3]
    expected_len = 5 + payload_len
    if len(packet) != expected_len:
        raise ValueError("bad menu event packet size")
    if packet[-1] != _checksum(packet[:-1]):
        raise ValueError("menu event checksum mismatch")
    if payload_len < 1:
        raise ValueError("menu event payload empty")

    seq = packet[2]
    payload = packet[4 : 4 + payload_len]
    etype = payload[0]
    out = {"seq": seq, "type": etype}

    if etype == MENU_EVT_USE_DEV:
        card_id = payload[1] if len(payload) > 1 else 0
        out["card"] = DEV_ID_TO_CARD.get(card_id, "knight")
    elif etype == MENU_EVT_TRADE_PLAYER:
        if len(payload) < 12:
            raise ValueError("trade player event payload too short")
        out["target_player"] = payload[1]
        out["give"] = list(payload[2:7])
        out["receive"] = list(payload[7:12])

    return out
