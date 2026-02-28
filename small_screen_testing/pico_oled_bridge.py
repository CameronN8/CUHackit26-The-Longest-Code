"""Pico-side SSD1306 bridge receiver (I2C).

Protocol (newline-delimited ASCII from Pi):
  CLEAR
  SHOW
  TEXT|x|y|message
  FRAME|line1|line2|line3|line4|line5
  PING

For best results, copy this file to the Pico as `main.py` along with `ssd1306.py`.
"""

from machine import I2C, Pin
import ssd1306
import sys


# ==== OLED CONFIG (adjust for your wiring) ====
WIDTH = 128
HEIGHT = 64
I2C_ID = 0
I2C_SCL = 1
I2C_SDA = 0
I2C_FREQ = 400_000
I2C_ADDR = 0x3C
# ==============================================


def init_oled():
    i2c = I2C(I2C_ID, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=I2C_FREQ)
    return ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=I2C_ADDR)


def draw_frame(oled, lines):
    oled.fill(0)
    y = 0
    for line in lines[:5]:
        oled.text(line[:21], 0, y)
        y += 12
    oled.show()


def handle_command(oled, raw_line):
    line = raw_line.strip()
    if not line:
        return

    if line == "PING":
        print("PONG")
        return

    if line == "CLEAR":
        oled.fill(0)
        return

    if line == "SHOW":
        oled.show()
        return

    if line.startswith("TEXT|"):
        parts = line.split("|", 3)
        if len(parts) != 4:
            print("ERR bad TEXT format")
            return
        try:
            x = int(parts[1])
            y = int(parts[2])
        except ValueError:
            print("ERR bad TEXT coords")
            return
        msg = parts[3]
        oled.text(msg[:21], x, y)
        return

    if line.startswith("FRAME|"):
        parts = line.split("|")
        frame_lines = parts[1:] if len(parts) > 1 else []
        draw_frame(oled, frame_lines)
        return

    print("ERR unknown cmd")


def main():
    oled = init_oled()
    oled.fill(0)
    oled.text("Pico bridge up", 0, 0)
    oled.text("Waiting cmd...", 0, 12)
    oled.show()
    print("READY")

    while True:
        try:
            incoming = sys.stdin.readline()
        except Exception:
            continue
        if not incoming:
            continue
        handle_command(oled, incoming)


main()
