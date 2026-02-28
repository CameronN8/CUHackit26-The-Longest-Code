"""Pico-side tile-vector receiver (UART ingress).

Designed to run on a second Pico that shares the same Pi UART TX line.
This script only consumes tile-vector packets and explicitly skips player packets
so mixed traffic does not interfere.

Optional: set ENABLE_LOCAL_OLED = True to render a compact summary on one SSD1306.
"""

from machine import Pin, SoftI2C, UART

import ssd1306
from player_state_protocol import (
    MAGIC,
    PACKET_SIZE,
    TILE_VEC_MAGIC,
    TILE_VEC_PACKET_SIZE,
    decode_tile_resource_vector,
)


# ===== UART LINK (Pi -> Pico) =====
UART_ID = 0
UART_BAUD = 115200
UART_TX_PIN = 0
UART_RX_PIN = 1
# ==================================


# ===== Optional local OLED =====
ENABLE_LOCAL_OLED = False
OLED_SCL_PIN = 15
OLED_SDA_PIN = 2
OLED_ADDR = 0x3C
OLED_W = 128
OLED_H = 64
OLED_FREQ = 400_000
# ===============================


RESOURCE_ID_TO_NAME = {
    0: "wood",
    1: "brick",
    2: "sheep",
    3: "wheat",
    4: "ore",
}


class TileVectorBridge:
    def __init__(self):
        self.last_vector = None
        self.last_seq = None
        self.oled = None

        if ENABLE_LOCAL_OLED:
            i2c = SoftI2C(
                scl=Pin(OLED_SCL_PIN),
                sda=Pin(OLED_SDA_PIN),
                freq=OLED_FREQ,
            )
            self.oled = ssd1306.SSD1306_I2C(OLED_W, OLED_H, i2c, addr=OLED_ADDR)
            self.oled.fill(0)
            self.oled.text("Tile RX ready", 0, 0)
            self.oled.show()

    def _count_resources(self, vector):
        counts = {"wood": 0, "brick": 0, "sheep": 0, "wheat": 0, "ore": 0, "other": 0}
        for value in vector:
            name = RESOURCE_ID_TO_NAME.get(int(value), "other")
            counts[name] += 1
        return counts

    def _render_oled(self, seq, counts):
        if self.oled is None:
            return
        self.oled.fill(0)
        self.oled.text("Tile vec seq", 0, 0)
        self.oled.text(str(seq), 84, 0)
        self.oled.text("W{} B{}".format(counts["wood"], counts["brick"]), 0, 14)
        self.oled.text("S{} H{} O{}".format(counts["sheep"], counts["wheat"], counts["ore"]), 0, 28)
        self.oled.text("Other {}".format(counts["other"]), 0, 42)
        self.oled.show()

    def apply_tile_packet(self, packet):
        decoded = decode_tile_resource_vector(packet)
        seq = decoded["seq"]
        vector = decoded["vector"]

        self.last_seq = seq
        self.last_vector = vector

        counts = self._count_resources(vector)
        print(
            "TILE seq={} vec={} counts={}".format(
                seq, ",".join(str(v) for v in vector), counts
            )
        )
        self._render_oled(seq, counts)


BRIDGE = TileVectorBridge()
UART_LINK = UART(UART_ID, baudrate=UART_BAUD, tx=Pin(UART_TX_PIN), rx=Pin(UART_RX_PIN))


def uart_tile_loop():
    print("TILE VECTOR RX READY (UART)")
    buf = b""

    while True:
        if UART_LINK.any():
            chunk = UART_LINK.read(UART_LINK.any())
            if chunk:
                buf += chunk

        if len(buf) == 0:
            continue

        first = buf[0]

        # Foreign player snapshot packet on shared UART stream: skip whole.
        if first == MAGIC:
            if len(buf) < PACKET_SIZE:
                continue
            buf = buf[PACKET_SIZE:]
            continue

        if first != TILE_VEC_MAGIC:
            buf = buf[1:]
            continue

        if len(buf) < TILE_VEC_PACKET_SIZE:
            continue

        packet = buf[:TILE_VEC_PACKET_SIZE]
        buf = buf[TILE_VEC_PACKET_SIZE:]

        try:
            BRIDGE.apply_tile_packet(packet)
        except Exception:
            # Continue scanning stream even if one packet is malformed.
            pass


uart_tile_loop()
