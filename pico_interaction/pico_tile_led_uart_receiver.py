"""Pico-side tile-vector -> 19 RGB LED relay renderer (UART ingress).

Goal:
- Receive tile vector packets over shared UART stream from Pi.
- Each packet carries 19 resource ids (0..4) for the board tiles.
- Drive 19 LEDs using:
  - 1 shared RGB data path (3 PWM pins)
  - 19 individual power-select pins
- Multiplex fast so all 19 appear lit simultaneously with unique colors.

This script intentionally ignores player-state packets on the same UART stream.
"""

from machine import Pin, PWM, UART
import utime

from state_packet_protocol import (
    MAGIC,
    PACKET_SIZE,
    TILE_VEC_MAGIC,
    TILE_VEC_PACKET_SIZE,
    MENU_CTRL_MAGIC,
    MENU_CTRL_PACKET_SIZE,
    decode_tile_resource_vector,
)


# ===== UART LINK (Pi -> Pico) =====
UART_ID = 0
UART_BAUD = 115200
UART_TX_PIN = 0
UART_RX_PIN = 1
# ==================================


# ===== LED RELAY WIRING =====
# Shared RGB lines (PWM-capable GPIOs; adjust to your wiring).
RGB_R_PIN = 18
RGB_G_PIN = 19
RGB_B_PIN = 20

# 19 tile-enable power pins (one per LED path). Must contain exactly 19 entries.
POWER_PINS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 21, 22, 26]

# Electrical behavior toggles:
POWER_ACTIVE_HIGH = True   # True if tile-enable pin HIGH turns that LED path on.
RGB_COMMON_ANODE = False   # True for common-anode RGB path (PWM inverted).

PWM_FREQ = 1200            # RGB PWM carrier
SCAN_DELAY_US = 900        # Dwell time per LED during multiplex scanning
# =============================


# Resource id -> RGB duty (0..65535)
# id mapping from Pi-side conversion:
#   0 wood, 1 brick, 2 sheep, 3 wheat, 4 ore
RESOURCE_RGB = {
    0: (9000, 48000, 7000),    # wood  (green-ish)
    1: (52000, 12000, 7000),   # brick (red/orange)
    2: (22000, 52000, 22000),  # sheep (bright green)
    3: (52000, 47000, 8000),   # wheat (yellow/gold)
    4: (11000, 11000, 52000),  # ore   (blue-ish)
}


def _clamp_u16(value):
    value = int(value)
    if value < 0:
        return 0
    if value > 65535:
        return 65535
    return value


class TileLedRelay:
    def __init__(self):
        if len(POWER_PINS) != 19:
            raise ValueError("POWER_PINS must contain exactly 19 GPIO pins")

        self.pwr = [Pin(pin, Pin.OUT) for pin in POWER_PINS]
        self.pwm_r = PWM(Pin(RGB_R_PIN))
        self.pwm_g = PWM(Pin(RGB_G_PIN))
        self.pwm_b = PWM(Pin(RGB_B_PIN))

        self.pwm_r.freq(PWM_FREQ)
        self.pwm_g.freq(PWM_FREQ)
        self.pwm_b.freq(PWM_FREQ)

        self.vector = [0] * 19
        self.seq = 0
        self.scan_idx = 0

        self._disable_all_paths()
        self._set_rgb(0, 0, 0)

    def _enable_path(self, idx):
        self.pwr[idx].value(1 if POWER_ACTIVE_HIGH else 0)

    def _disable_path(self, idx):
        self.pwr[idx].value(0 if POWER_ACTIVE_HIGH else 1)

    def _disable_all_paths(self):
        for idx in range(len(self.pwr)):
            self._disable_path(idx)

    def _apply_channel(self, pwm_obj, value):
        value = _clamp_u16(value)
        if RGB_COMMON_ANODE:
            value = 65535 - value
        pwm_obj.duty_u16(value)

    def _set_rgb(self, r, g, b):
        self._apply_channel(self.pwm_r, r)
        self._apply_channel(self.pwm_g, g)
        self._apply_channel(self.pwm_b, b)

    def update_vector(self, seq, vector):
        if len(vector) != 19:
            return
        # Keep only expected 0..4 ids; unknown values fall back to off.
        self.vector = [int(v) if int(v) in RESOURCE_RGB else -1 for v in vector]
        self.seq = int(seq) & 0xFF
        print("TILE seq={} vec={}".format(self.seq, ",".join(str(v) for v in self.vector)))

    def scan_step(self):
        # Disable old path first to avoid ghosting during RGB transition.
        self._disable_path(self.scan_idx)
        self.scan_idx = (self.scan_idx + 1) % 19

        rid = self.vector[self.scan_idx]
        rgb = RESOURCE_RGB.get(rid, (0, 0, 0))
        self._set_rgb(rgb[0], rgb[1], rgb[2])
        self._enable_path(self.scan_idx)
        utime.sleep_us(SCAN_DELAY_US)


RELAY = TileLedRelay()
UART_LINK = UART(UART_ID, baudrate=UART_BAUD, tx=Pin(UART_TX_PIN), rx=Pin(UART_RX_PIN))


def apply_tile_packet(packet):
    decoded = decode_tile_resource_vector(packet)
    RELAY.update_vector(decoded["seq"], decoded["vector"])


def main_loop():
    print("TILE LED RELAY READY (UART)")
    buf = b""

    while True:
        if UART_LINK.any():
            chunk = UART_LINK.read(UART_LINK.any())
            if chunk:
                buf += chunk

        # Parse as many complete packets as available.
        while len(buf) > 0:
            first = buf[0]

            # Foreign packet type (player snapshot): skip full packet.
            if first == MAGIC:
                if len(buf) < PACKET_SIZE:
                    break
                buf = buf[PACKET_SIZE:]
                continue

            # Foreign menu-control packet (for player-display Pico): skip full packet.
            if first == MENU_CTRL_MAGIC:
                if len(buf) < MENU_CTRL_PACKET_SIZE:
                    break
                buf = buf[MENU_CTRL_PACKET_SIZE:]
                continue

            # Unknown leading byte: drop one and resync.
            if first != TILE_VEC_MAGIC:
                buf = buf[1:]
                continue

            if len(buf) < TILE_VEC_PACKET_SIZE:
                break

            packet = buf[:TILE_VEC_PACKET_SIZE]
            buf = buf[TILE_VEC_PACKET_SIZE:]

            try:
                apply_tile_packet(packet)
            except Exception:
                # Ignore malformed packet and keep stream alive.
                pass

        # Keep multiplex scan running continuously.
        RELAY.scan_step()


main_loop()
