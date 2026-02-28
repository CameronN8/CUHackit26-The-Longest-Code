"""MicroPython OLED test for Raspberry Pi Pico + SSD1306 (I2C only).

Copy both `oled_test.py` and `ssd1306.py` to the Pico filesystem.
Set I2C pin constants to match your wiring.
"""

from machine import I2C, Pin
import time
import ssd1306


# ==== USER CONFIG ====
WIDTH = 128
HEIGHT = 64

# I2C pins (common Pico defaults)
I2C_ID = 0
I2C_SCL = 1
I2C_SDA = 0
I2C_FREQ = 400_000
I2C_ADDR = 0x3C
# =====================


def init_display():
    bus = I2C(I2C_ID, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=I2C_FREQ)
    return ssd1306.SSD1306_I2C(WIDTH, HEIGHT, bus, addr=I2C_ADDR)


def draw_startup_screen(oled):
    oled.fill(0)
    oled.text("CUHackit OLED", 0, 0)
    oled.text("SSD1306 test", 0, 12)
    oled.rect(0, 26, 128, 38, 1)
    oled.text("If you see this,", 6, 36)
    oled.text("driver works.", 6, 48)
    oled.show()


def animate(oled):
    x = 0
    direction = 1
    while True:
        oled.fill(0)
        oled.text("Pico SSD1306 OK", 0, 0)
        oled.text("mode: i2c", 0, 12)
        oled.fill_rect(x, 30, 18, 18, 1)
        oled.text(str(time.ticks_ms() // 1000), 100, 54)
        oled.show()

        x += 3 * direction
        if x <= 0:
            x = 0
            direction = 1
        elif x >= (WIDTH - 18):
            x = WIDTH - 18
            direction = -1
        time.sleep_ms(60)


def main():
    oled = init_display()
    draw_startup_screen(oled)
    time.sleep(2)
    animate(oled)


main()
