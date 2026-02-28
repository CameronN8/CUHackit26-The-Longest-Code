"""Pico-side channelized router for 1 ingress stream -> 9 outbound I2C SDA lines.

Important: rp2 MicroPython `machine.I2C` is master-only.
So this file implements routing + frame decode and exposes `process_frame(frame_bytes)`.
You still need an ingress layer to receive bytes from Pi over I2C slave mode
(typically done in Pico SDK C/C++ or a PIO-based slave implementation), then call
`process_frame(...)` with each full frame.

For bench testing without I2C ingress, this file also supports stdin hex lines:
  A5 00 01 3C 03 41 42 43
"""

from machine import Pin, SoftI2C
import sys

from channel_bridge_protocol import decode_frame, OP_I2C_WRITE


# ==== OUTBOUND BUS CONFIG ====
# One shared SCL, nine independent SDA channels.
SCL_PIN = 15
SDA_CHANNEL_PINS = [2, 3, 4, 5, 6, 7, 8, 9, 10]  # channels 0..8
FREQ = 100_000
# =============================


class ChannelRouter:
    def __init__(self, scl_pin: int, sda_pins: list[int], freq: int = 100_000):
        self._buses = []
        for sda_pin in sda_pins:
            bus = SoftI2C(scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)
            self._buses.append(bus)

    def route_write(self, channel_id: int, target_addr: int, payload: bytes) -> None:
        if channel_id < 0 or channel_id >= len(self._buses):
            raise ValueError("invalid channel_id")
        bus = self._buses[channel_id]
        bus.writeto(target_addr, payload)

    def process_frame(self, frame: bytes) -> None:
        channel_id, op, target_addr, payload = decode_frame(frame)
        if op != OP_I2C_WRITE:
            raise ValueError("unsupported op")
        self.route_write(channel_id, target_addr, payload)


def parse_hex_line(line: str) -> bytes:
    parts = line.strip().split()
    if not parts:
        return b""
    return bytes(int(p, 16) for p in parts)


def main():
    router = ChannelRouter(SCL_PIN, SDA_CHANNEL_PINS, FREQ)
    print("ROUTER READY")
    print("stdin test mode: send hex bytes per line")

    while True:
        raw = sys.stdin.readline()
        if not raw:
            continue
        raw = raw.strip()
        if not raw:
            continue
        try:
            frame = parse_hex_line(raw)
            router.process_frame(frame)
            print("OK")
        except Exception as exc:
            print("ERR", exc)


main()
