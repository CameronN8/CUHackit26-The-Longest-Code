"""Pi-side isolation test for menu rendering on player display #3.

This test does not use rotary input. It only sends fixed MENU_RENDER packets
so you can verify UART path + Pico menu-display rendering independently.
"""

import time

from pi_uart_state_sender import send_menu_render


# 0 -> P1 menu display, 1 -> P2, 2 -> P3
PLAYER_INDEX = 0

# Send one frame repeatedly so late UART starts still catch it.
REPEAT_COUNT = 20
INTERVAL_S = 0.25


def main():
    lines = ["P1 Action", ">Development", " Trading", " End Turn"]
    print("Sending MENU_RENDER isolation packets...")
    print("target player index:", PLAYER_INDEX)
    print("lines:", lines)

    for i in range(REPEAT_COUNT):
        packet = send_menu_render(PLAYER_INDEX, lines)
        print("sent", i + 1, "len", len(packet))
        time.sleep(INTERVAL_S)

    print("done")


if __name__ == "__main__":
    main()
