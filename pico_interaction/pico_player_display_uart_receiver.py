"""Pico-side player display receiver with rotary-interactive third screen.

Displays per player (shared SCL, distinct SDA):
  pin tuple = (resources, vp, interactive_menu)

UART ingress packet types accepted:
- player snapshot packets (resources/vp/dev data)
- menu control packets (set active player, reset root menu)
- tile packets are explicitly skipped (for shared UART coexistence)

UART egress packet types produced:
- menu event packets when local rotary menu actions are confirmed
"""

from machine import Pin, SoftI2C, UART
import utime
import ssd1306

from state_packet_protocol import (
    MAGIC,
    PACKET_SIZE,
    TILE_VEC_MAGIC,
    TILE_VEC_PACKET_SIZE,
    MENU_CTRL_MAGIC,
    MENU_CTRL_PACKET_SIZE,
    MENU_EVT_MAGIC,
    decode_snapshot,
    decode_menu_control,
    encode_menu_event,
)
from rotary_menu_controller import PlayerMenuController, RotaryEncoder


# ===== UART LINK (Pi <-> Pico) =====
UART_ID = 0
UART_BAUD = 115200
UART_TX_PIN = 0
UART_RX_PIN = 1
# ===================================


# ===== DISPLAY WIRING =====
SCL_PIN = 15
DISPLAY_ADDR = 0x3C
WIDTH = 128
HEIGHT = 64
FREQ = 400_000

# player index -> (resources_sda, vp_sda, menu_sda)
PLAYER_DISPLAY_PINS = {
    0: (2, 3, 4),
    1: (5, 6, 7),
    2: (8, 9, 10),
}
# ==========================


# ===== ENCODER WIRING =====
# player index -> (clk, dt, sw)
PLAYER_ENCODER_PINS = {
    0: (11, 12, 13),
    1: (14, 16, 17),
    2: (18, 19, 20),
}
# ==========================

RESOURCE_ORDER = ("wood", "brick", "sheep", "wheat", "ore")


class MultiDisplayBridge:
    def __init__(self):
        self.displays = {}
        self.menu_ctrl = {}
        self.active_player = 0
        self._evt_seq = 0

        self._init_displays_and_encoders()

    def _next_evt_seq(self):
        value = self._evt_seq
        self._evt_seq = (self._evt_seq + 1) & 0xFF
        return value

    def _init_one_display(self, sda_pin):
        i2c = SoftI2C(scl=Pin(SCL_PIN), sda=Pin(sda_pin), freq=FREQ)
        oled = ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=DISPLAY_ADDR)
        oled.fill(0)
        oled.show()
        return oled

    def _init_displays_and_encoders(self):
        for player_idx, pin_triplet in PLAYER_DISPLAY_PINS.items():
            res_pin, vp_pin, menu_pin = pin_triplet
            res_oled = self._init_one_display(res_pin)
            vp_oled = self._init_one_display(vp_pin)
            menu_oled = self._init_one_display(menu_pin)

            self.displays[(player_idx, "resources")] = res_oled
            self.displays[(player_idx, "vp")] = vp_oled
            self.displays[(player_idx, "menu")] = menu_oled

            enc_pins = PLAYER_ENCODER_PINS[player_idx]
            encoder = RotaryEncoder(enc_pins[0], enc_pins[1], enc_pins[2])
            menu = PlayerMenuController(menu_oled, player_idx, encoder)
            menu.set_active(player_idx == self.active_player, reset_menu=True)
            self.menu_ctrl[player_idx] = menu

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
        oled.text("H{} O{}".format(resources.get("wheat", 0), resources.get("ore", 0)), 0, 28)
        oled.text("TOTAL {}".format(total), 0, 46)
        oled.show()

    def _draw_vp(self, oled, player_idx, vp):
        oled.fill(0)
        oled.text("P{} VP".format(player_idx + 1), 0, 0)
        oled.text("POINTS: {}".format(int(vp)), 0, 20)
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
            self.menu_ctrl[player_idx].set_player_data(player)

    def apply_menu_control(self, menu_ctrl):
        active = int(menu_ctrl.get("active_player", 0) or 0)
        if active < 0:
            active = 0
        if active > 2:
            active = 2
        reset_menu = bool(menu_ctrl.get("reset_menu", False))

        self.active_player = active
        for idx in range(3):
            self.menu_ctrl[idx].set_active(idx == active, reset_menu=reset_menu)

    def poll_menu_and_maybe_emit(self, uart_link):
        # Poll all controllers so inactive screens can still redraw "waiting" state.
        for idx in range(3):
            event = self.menu_ctrl[idx].update()
            if event:
                packet = encode_menu_event(self._next_evt_seq(), event)
                uart_link.write(packet)


BRIDGE = MultiDisplayBridge()
UART_LINK = UART(UART_ID, baudrate=UART_BAUD, tx=Pin(UART_TX_PIN), rx=Pin(UART_RX_PIN))


def uart_packet_loop():
    print("PLAYER DISPLAY RX READY (UART)")
    buf = b""

    while True:
        # Always poll menu interaction regardless of ingress traffic.
        BRIDGE.poll_menu_and_maybe_emit(UART_LINK)

        if UART_LINK.any():
            chunk = UART_LINK.read(UART_LINK.any())
            if chunk:
                buf += chunk

        # Parse as many complete packets as are available.
        while len(buf) > 0:
            first = buf[0]

            # Tile packet belongs to second Pico, skip whole frame.
            if first == TILE_VEC_MAGIC:
                if len(buf) < TILE_VEC_PACKET_SIZE:
                    break
                buf = buf[TILE_VEC_PACKET_SIZE:]
                continue

            # Outbound menu events should not appear as inbound; if they do,
            # skip one byte to resync safely.
            if first == MENU_EVT_MAGIC:
                buf = buf[1:]
                continue

            # Menu control packet (Pi -> this Pico)
            if first == MENU_CTRL_MAGIC:
                if len(buf) < MENU_CTRL_PACKET_SIZE:
                    break
                packet = buf[:MENU_CTRL_PACKET_SIZE]
                buf = buf[MENU_CTRL_PACKET_SIZE:]
                try:
                    ctrl = decode_menu_control(packet)
                    BRIDGE.apply_menu_control(ctrl)
                except Exception:
                    pass
                continue

            # Player snapshot packet (Pi -> this Pico)
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

            # Unknown start byte, drop one and continue resync.
            buf = buf[1:]

        utime.sleep_ms(4)


uart_packet_loop()
