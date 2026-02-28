"""Pico-side player display receiver (render-only, no encoder logic).

Displays per player (shared SCL, distinct SDA):
  pin tuple = (resources, vp, menu)

UART ingress packet types accepted:
- player snapshot packets (resources/vp/dev data)
- menu-render packets (4 text lines for active player's menu screen)
- tile packets are explicitly skipped (shared UART coexistence)
"""

from machine import Pin, SoftI2C, UART
import utime
import ssd1306

from state_packet_protocol import (
    MAGIC,
    PACKET_SIZE,
    TILE_VEC_MAGIC,
    TILE_VEC_PACKET_SIZE,
    MENU_RENDER_MAGIC,
    MENU_RENDER_PACKET_SIZE,
    decode_snapshot,
    decode_menu_render,
)


# ===== UART LINK (Pi -> Pico) =====
UART_ID = 0
UART_BAUD = 115200
UART_TX_PIN = 0
UART_RX_PIN = 1
# ===================================


# ===== DISPLAY WIRING =====
SCL_PIN = 15
WIDTH = 128
HEIGHT = 64
FREQ = 400_000
DISPLAY_ADDR_CANDIDATES = (0x3C, 0x3D)
DEBUG_MENU_RX = True

# Quick hardware debug mode:
# - True: only initialize P1 menu display on SINGLE_MENU_SDA_PIN
# - False: initialize full 3x3 map below
SINGLE_DISPLAY_TEST_MODE = False
SINGLE_MENU_SDA_PIN = 4

# player index -> (resources_sda, vp_sda, menu_sda)
PLAYER_DISPLAY_PINS = {
    0: (2, 3, 4),
    1: (5, 6, 7),
    2: (8, 9, 10),
}
# ==========================

RESOURCE_ORDER = ("wood", "brick", "sheep", "wheat", "ore")


class MultiDisplayBridge:
    def __init__(self):
        self.displays = {}
        self._init_displays()

    def _init_one_display(self, sda_pin):
        try:
            i2c = SoftI2C(scl=Pin(SCL_PIN), sda=Pin(sda_pin), freq=FREQ)
            found = i2c.scan()
            if found:
                print("SDA {} scan -> {}".format(sda_pin, found))
            for addr in DISPLAY_ADDR_CANDIDATES:
                if addr not in found:
                    continue
                oled = ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=addr)
                oled.fill(0)
                oled.show()
                print("OLED on SDA {} addr 0x{:02X}".format(sda_pin, addr))
                return oled
            print("No SSD1306 addr on SDA {} (scan={})".format(sda_pin, found))
            return None
        except OSError:
            # Allow partial hardware bring-up (e.g., testing only one OLED).
            print("No OLED on SDA pin {}".format(sda_pin))
            return None

    def _init_displays(self):
        if SINGLE_DISPLAY_TEST_MODE:
            for idx in range(3):
                self.displays[(idx, "resources")] = None
                self.displays[(idx, "vp")] = None
                self.displays[(idx, "menu")] = None
            self.displays[(0, "menu")] = self._init_one_display(SINGLE_MENU_SDA_PIN)
            # Prove render path works before any UART traffic arrives.
            self._draw_menu_lines(
                self.displays[(0, "menu")],
                ["P1 Action", ">Development", " Trading", " End Turn"],
            )
            return

        for player_idx, pin_triplet in PLAYER_DISPLAY_PINS.items():
            res_pin, vp_pin, menu_pin = pin_triplet
            self.displays[(player_idx, "resources")] = self._init_one_display(res_pin)
            self.displays[(player_idx, "vp")] = self._init_one_display(vp_pin)
            self.displays[(player_idx, "menu")] = self._init_one_display(menu_pin)

    def _draw_resources(self, oled, player_idx, resources):
        if oled is None:
            return
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
        oled.text("H{} O{}".format(resources.get("wheat", 0), resources.get("ore", 0)), 0, 28)
        oled.text("TOTAL {}".format(total), 0, 46)
        oled.show()

    def _draw_vp(self, oled, player_idx, vp):
        if oled is None:
            return
        oled.fill(0)
        oled.text("P{} VP".format(player_idx + 1), 0, 0)
        oled.text("POINTS: {}".format(int(vp)), 0, 20)
        oled.show()

    def _draw_menu_lines(self, oled, lines):
        if oled is None:
            return
        oled.fill(0)
        y = 0
        for line in lines[:4]:
            oled.text(str(line)[:21], 0, y)
            y += 16
        oled.show()

    def apply_snapshot(self, snapshot):
        players = snapshot.get("players", [])
        for player_idx in range(3):
            if player_idx >= len(players):
                continue
            player = players[player_idx]
            resources = player.get("resources", {})
            vp = int(player.get("victory_points", 0) or 0)
            self._draw_resources(self.displays[(player_idx, "resources")], player_idx, resources)
            self._draw_vp(self.displays[(player_idx, "vp")], player_idx, vp)

    def apply_menu_render(self, menu_payload):
        player_idx = int(menu_payload.get("player_idx", 0) or 0)
        if player_idx < 0 or player_idx > 2:
            return
        lines = menu_payload.get("lines", ["", "", "", ""])
        self._draw_menu_lines(self.displays[(player_idx, "menu")], lines)


BRIDGE = MultiDisplayBridge()
UART_LINK = UART(UART_ID, baudrate=UART_BAUD, tx=Pin(UART_TX_PIN), rx=Pin(UART_RX_PIN))


def uart_packet_loop():
    print("PLAYER DISPLAY RX READY (UART)")
    buf = b""

    while True:
        if UART_LINK.any():
            chunk = UART_LINK.read(UART_LINK.any())
            if chunk:
                buf += chunk

        while len(buf) > 0:
            first = buf[0]

            if first == TILE_VEC_MAGIC:
                if len(buf) < TILE_VEC_PACKET_SIZE:
                    break
                buf = buf[TILE_VEC_PACKET_SIZE:]
                continue

            if first == MENU_RENDER_MAGIC:
                if len(buf) < MENU_RENDER_PACKET_SIZE:
                    break
                packet = buf[:MENU_RENDER_PACKET_SIZE]
                buf = buf[MENU_RENDER_PACKET_SIZE:]
                try:
                    payload = decode_menu_render(packet)
                    if DEBUG_MENU_RX:
                        print(
                            "MENU_RX seq={} player={} lines={}".format(
                                payload.get("seq", -1),
                                payload.get("player_idx", -1),
                                payload.get("lines", []),
                            )
                        )
                    BRIDGE.apply_menu_render(payload)
                except Exception as exc:
                    if DEBUG_MENU_RX:
                        print("MENU_RX decode error:", exc)
                continue

            if first == MAGIC:
                if len(buf) < PACKET_SIZE:
                    break
                packet = buf[:PACKET_SIZE]
                buf = buf[PACKET_SIZE:]
                try:
                    snapshot = decode_snapshot(packet)
                    BRIDGE.apply_snapshot(snapshot)
                except Exception:
                    pass
                continue

            buf = buf[1:]

        utime.sleep_ms(4)


uart_packet_loop()
