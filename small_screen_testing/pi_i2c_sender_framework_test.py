"""Pi-side test script that uses the function-based sender framework.

Run examples:
  python small_screen_testing/pi_i2c_sender_framework_test.py --bus 1 --pico-addr 0x42 --channel 0 --target 0x3C --text "hello"
  python small_screen_testing/pi_i2c_sender_framework_test.py --bus 1 --pico-addr 0x42 --channel 0 --target 0x3C --loop
"""

import argparse
import datetime as dt
import time

from pi_i2c_channel_sender import send_i2c_payload, send_text


def parse_int(text: str) -> int:
    return int(text, 0)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Framework test: send channelized packets from Pi to Pico bridge"
    )
    parser.add_argument("--bus", type=int, required=True, help="Pi I2C bus (usually 1)")
    parser.add_argument(
        "--pico-addr",
        type=parse_int,
        required=True,
        help="Pico bridge I2C slave address (e.g. 0x42)",
    )
    parser.add_argument("--channel", type=int, required=True, help="Channel id 0..8")
    parser.add_argument(
        "--target",
        type=parse_int,
        required=True,
        help="Downstream target I2C address (e.g. 0x3C)",
    )
    parser.add_argument("--text", default="bridge test", help="Text payload for one-shot send")
    parser.add_argument(
        "--hex-payload",
        default="",
        help='Optional raw hex payload, e.g. "00 A5 FF". If set, this is used instead of --text.',
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Continuously send test text with a counter/timestamp once per interval.",
    )
    parser.add_argument("--interval", type=float, default=1.0, help="Loop interval seconds")
    return parser.parse_args()


def parse_hex_payload(text: str) -> bytes:
    clean = text.strip()
    if not clean:
        return b""
    return bytes(int(part, 16) for part in clean.split())


def send_once(args) -> None:
    if args.hex_payload:
        payload = parse_hex_payload(args.hex_payload)
        frame = send_i2c_payload(
            channel_id=args.channel,
            target_addr=args.target,
            payload=payload,
            pi_i2c_bus=args.bus,
            pico_bridge_addr=args.pico_addr,
        )
        print(
            f"sent raw payload: bus={args.bus} pico=0x{args.pico_addr:02X} "
            f"channel={args.channel} target=0x{args.target:02X} "
            f"payload_bytes={len(payload)} frame_bytes={len(frame)}"
        )
        return

    frame = send_text(
        channel_id=args.channel,
        target_addr=args.target,
        text=args.text,
        pi_i2c_bus=args.bus,
        pico_bridge_addr=args.pico_addr,
    )
    print(
        f"sent text: bus={args.bus} pico=0x{args.pico_addr:02X} "
        f"channel={args.channel} target=0x{args.target:02X} "
        f'text="{args.text}" frame_bytes={len(frame)}'
    )


def send_loop(args) -> None:
    counter = 0
    print("loop mode: Ctrl+C to stop")
    try:
        while True:
            now = dt.datetime.now().strftime("%H:%M:%S")
            text = f"tick={counter} {now}"
            send_text(
                channel_id=args.channel,
                target_addr=args.target,
                text=text,
                pi_i2c_bus=args.bus,
                pico_bridge_addr=args.pico_addr,
            )
            print(f"sent: {text}")
            counter += 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("stopped")


def main():
    args = parse_args()
    if args.loop:
        send_loop(args)
    else:
        send_once(args)


if __name__ == "__main__":
    main()
