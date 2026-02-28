"""Pi-side serial sender test for Pico OLED bridge.

Usage:
  python small_screen_testing/pi_oled_bridge_test.py --port /dev/ttyACM0
"""

import argparse
import datetime as dt
import time

import serial


def parse_args():
    parser = argparse.ArgumentParser(description="Send dynamic test frames to Pico OLED bridge")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port for Pico")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument(
        "--interval", type=float, default=1.0, help="Seconds between frame updates"
    )
    return parser.parse_args()


def send_line(ser, line):
    ser.write((line + "\n").encode("utf-8"))


def main():
    args = parse_args()

    with serial.Serial(args.port, args.baud, timeout=1) as ser:
        # Pico often resets when serial opens.
        time.sleep(2.0)
        ser.reset_input_buffer()

        send_line(ser, "PING")
        time.sleep(0.1)
        ack = ser.readline().decode("utf-8", errors="ignore").strip()
        print(f"Pico response: {ack or '<none>'}")

        counter = 0
        print("Sending dynamic frames. Ctrl+C to stop.")
        try:
            while True:
                now = dt.datetime.now().strftime("%H:%M:%S")
                lines = [
                    "CUHackit OLED link",
                    f"Tick: {counter}",
                    f"Time: {now}",
                    "Pi -> Pico -> SSD1306",
                    "Serial bridge test",
                ]
                send_line(ser, "FRAME|" + "|".join(lines))
                counter += 1
                time.sleep(args.interval)
        except KeyboardInterrupt:
            pass

        send_line(ser, "FRAME|Stopped|Bridge test done|||")
        print("Stopped.")


if __name__ == "__main__":
    main()
