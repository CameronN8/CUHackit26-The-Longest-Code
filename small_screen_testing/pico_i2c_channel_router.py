"""Pico-side renderer brain for 9 SSD1306 displays.

Display routing (by SDA pin):
  Player 1: pins 2,3,4  -> resources, VP, dev
  Player 2: pins 5,6,7  -> resources, VP, dev
  Player 3: pins 8,9,10 -> resources, VP, dev

All displays share one SCL pin.

Important transport note:
- This file focuses on packet decode + rendering (the "brainwork").
- RP2040 MicroPython does not provide a robust built-in I2C slave ingress for Pi->Pico.
- Use `apply_snapshot_packet(packet)` from your ingress layer, or use the included
  stdin hex test loop while prototyping.
"""

from machine import Pin, SoftI2C
import sys

import ssd1306
from player_state_protocol import decode_snapshot


# ===== DISPLAY WIRING =====
SCL_PIN = 15
DISPLAY_ADDR = 0x3C
WIDTH = 128
HEIGHT = 64
FREQ = 400_000

# player index -> (resources_sda, vp_sda, dev_sda)
PLAYER_DISPLAY_PINS = {
    0: (2, 3, 4),
    1: (5, 6, 7),
    2: (8, 9, 10),
}
# ==========================

RESOURCE_ORDER = ("wood", "brick", "sheep", "wheat", "ore")
DEV_ORDER = ("knight", "victory_point", "road_building", "year_of_plenty", "monopoly")


class MultiDisplayBridge:
    def __init__(self):
        self.displays = {}
        self._init_displays()

    def _init_one(self, sda_pin: int):
        i2c = SoftI2C(scl=Pin(SCL_PIN), sda=Pin(sda_pin), freq=FREQ)
        oled = ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=DISPLAY_ADDR)
        oled.fill(0)
        oled.show()
        return oled

    def _init_displays(self):
        for player_idx, pin_triplet in PLAYER_DISPLAY_PINS.items():
            res_pin, vp_pin, dev_pin = pin_triplet
            self.displays[(player_idx, "resources")] = self._init_one(res_pin)
            self.displays[(player_idx, "vp")] = self._init_one(vp_pin)
            self.displays[(player_idx, "dev")] = self._init_one(dev_pin)

    def _draw_resources(self, oled, player_idx: int, resources: dict[str, int]):
        total = 0
        for key in RESOURCE_ORDER:
            total += int(resources.get(key, 0) or 0)

        oled.fill(0)
        oled.text(f"P{player_idx + 1} RES", 0, 0)
        oled.text(
            f"W{resources.get('wood', 0)} B{resources.get('brick', 0)} S{resources.get('sheep', 0)}",
            0,
            14,
        )
        oled.text(
            f"H{resources.get('wheat', 0)} O{resources.get('ore', 0)}",
            0,
            28,
        )
        oled.text(f"TOTAL {total}", 0, 46)
        oled.show()

    def _draw_vp(self, oled, player_idx: int, vp: int):
        oled.fill(0)
        oled.text(f"P{player_idx + 1} VP", 0, 0)
        oled.text(f"POINTS: {int(vp)}", 0, 20)
        oled.show()

    def _draw_dev(self, oled, player_idx: int, dev_cards: dict[str, int]):
        total = 0
        for key in DEV_ORDER:
            total += int(dev_cards.get(key, 0) or 0)

        oled.fill(0)
        oled.text(f"P{player_idx + 1} DEV", 0, 0)
        oled.text(
            f"K{dev_cards.get('knight', 0)} VP{dev_cards.get('victory_point', 0)} RB{dev_cards.get('road_building', 0)}",
            0,
            14,
        )
        oled.text(
            f"Y{dev_cards.get('year_of_plenty', 0)} M{dev_cards.get('monopoly', 0)}",
            0,
            28,
        )
        oled.text(f"TOTAL {total}", 0, 46)
        oled.show()

    def apply_snapshot(self, snapshot: dict):
        players = snapshot.get("players", [])
        for player_idx in range(3):
            if player_idx >= len(players):
                continue
            player = players[player_idx]
            resources = player.get("resources", {})
            vp = int(player.get("victory_points", 0) or 0)
            dev_cards = player.get("dev_cards", {})

            self._draw_resources(self.displays[(player_idx, "resources")], player_idx, resources)
            self._draw_vp(self.displays[(player_idx, "vp")], player_idx, vp)
            self._draw_dev(self.displays[(player_idx, "dev")], player_idx, dev_cards)


BRIDGE = MultiDisplayBridge()


def apply_snapshot_packet(packet: bytes):
    """Primary entrypoint for your future Pi->Pico ingress layer."""
    snapshot = decode_snapshot(packet)
    BRIDGE.apply_snapshot(snapshot)


def _parse_hex_line(line: str) -> bytes:
    parts = line.strip().split()
    if not parts:
        return b""
    return bytes(int(part, 16) for part in parts)


def stdin_hex_test_loop():
    """Development helper: paste packet bytes as hex to test rendering logic."""
    print("DISPLAY BRIDGE READY")
    print("stdin hex mode: one packet per line")
    while True:
        raw = sys.stdin.readline()
        if not raw:
            continue
        raw = raw.strip()
        if not raw:
            continue
        try:
            packet = _parse_hex_line(raw)
            apply_snapshot_packet(packet)
            print("OK")
        except Exception as exc:
            print("ERR", exc)


stdin_hex_test_loop()
