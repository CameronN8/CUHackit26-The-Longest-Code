"""Shared protocol for Pi -> Pico channelized I2C bridge.

Frame format (bytes):
  [0]  magic      = 0xA5
  [1]  channel_id = 0..8
  [2]  op         = 0x01 (I2C write)
  [3]  target     = downstream I2C 7-bit address
  [4]  length     = payload length (0..64)
  [5:] payload
"""

MAGIC = 0xA5
OP_I2C_WRITE = 0x01
MAX_CHANNEL_ID = 8
MAX_PAYLOAD = 64


def encode_i2c_write(channel_id: int, target_addr: int, payload: bytes) -> bytes:
    if not (0 <= channel_id <= MAX_CHANNEL_ID):
        raise ValueError("channel_id must be 0..8")
    if not (0 <= target_addr <= 0x7F):
        raise ValueError("target_addr must be 7-bit (0..127)")
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"payload too long (max {MAX_PAYLOAD})")
    return bytes([MAGIC, channel_id, OP_I2C_WRITE, target_addr, len(payload)]) + payload


def decode_frame(frame: bytes):
    if len(frame) < 5:
        raise ValueError("frame too short")
    if frame[0] != MAGIC:
        raise ValueError("bad magic")

    channel_id = frame[1]
    op = frame[2]
    target_addr = frame[3]
    payload_len = frame[4]

    if channel_id > MAX_CHANNEL_ID:
        raise ValueError("invalid channel_id")
    if op != OP_I2C_WRITE:
        raise ValueError("unsupported op")
    if len(frame) != 5 + payload_len:
        raise ValueError("length mismatch")

    payload = frame[5:]
    return channel_id, op, target_addr, payload
