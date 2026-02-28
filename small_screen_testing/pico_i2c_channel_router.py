"""Pico-side renderer brain for 9 SSD1306 displays (UART ingress).

Display routing (by SDA pin):
  Player 1: pins 2,3,4  -> resources, VP, dev
  Player 2: pins 5,6,7  -> resources, VP, dev
  Player 3: pins 8,9,10 -> resources, VP, dev

All displays share one SCL pin.

Ingress:
- Pi sends fixed-size snapshot packets over UART.
- Pico reads packets from UART RX, decodes, and renders all 9 displays.
"""

from machine import Pin, SoftI2C, UART
import ssd1306
from player_state_protocol import MAGIC, PACKET_SIZE, decode_snapshot


# ===== UART LINK (Pi -> Pico) =====
UART_ID = 0
UART_BAUD = 115200
UART_TX_PIN = 0
UART_RX_PIN = 1
# ==================================


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

    def _init_one(self, sda_pin):
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

    def _draw_resources(self, oled, player_idx, resources):
        total = 0
        for key in RESOURCE_ORDER:
            total += int(resources.get(key, 0) or 0)

        oled.fill(0)
        oled.text("P{} RES".format(player_idx + 1), 0, 0)
        oled.text(
            "W{} B{} S{}".format(
                resources.get("wood", 0), resources.get("brick", 0), resources.get("sheep", 0)
            ),
            0,
            14,
        )
        oled.text(
            "H{} O{}".format(resources.get("wheat", 0), resources.get("ore", 0)),
            0,
            28,
        )
        oled.text("TOTAL {}".format(total), 0, 46)
        oled.show()

    def _draw_vp(self, oled, player_idx, vp):
        oled.fill(0)
        oled.text("P{} VP".format(player_idx + 1), 0, 0)
        oled.text("POINTS: {}".format(int(vp)), 0, 20)
        oled.show()

    def _draw_dev(self, oled, player_idx, dev_cards):
        total = 0
        for key in DEV_ORDER:
            total += int(dev_cards.get(key, 0) or 0)

        oled.fill(0)
        oled.text("P{} DEV".format(player_idx + 1), 0, 0)
        oled.text(
            "K{} VP{} RB{}".format(
                dev_cards.get("knight", 0),
                dev_cards.get("victory_point", 0),
                dev_cards.get("road_building", 0),
            ),
            0,
            14,
        )
        oled.text(
            "Y{} M{}".format(
                dev_cards.get("year_of_plenty", 0), dev_cards.get("monopoly", 0)
            ),
            0,
            28,
        )
        oled.text("TOTAL {}".format(total), 0, 46)
        oled.show()

    def apply_snapshot(self, snapshot):
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
UART_LINK = UART(UART_ID, baudrate=UART_BAUD, tx=Pin(UART_TX_PIN), rx=Pin(UART_RX_PIN))


def apply_snapshot_packet(packet):
    snapshot = decode_snapshot(packet)
    BRIDGE.apply_snapshot(snapshot)


def uart_packet_loop():
    print("DISPLAY BRIDGE READY (UART)")
    buf = b""

    while True:
        if UART_LINK.any():
            chunk = UART_LINK.read(UART_LINK.any())
            if chunk:
                buf += chunk

        # Sync to magic byte at buffer start.
        while len(buf) > 0 and buf[0] != MAGIC:
            buf = buf[1:]

        if len(buf) < PACKET_SIZE:
            continue

        packet = buf[:PACKET_SIZE]
        buf = buf[PACKET_SIZE:]

        try:
            apply_snapshot_packet(packet)
        except Exception:
            # Keep running even if one packet is malformed.
            pass


uart_packet_loop()
