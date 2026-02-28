"""Pi-side sender for channelized Pi->Pico I2C bridge.

This module is intentionally function-first so you can import it in application
code (for example from `main.py`) and call explicit APIs with explicit values.

Core flow:
1) Build a framed packet with `encode_i2c_write(...)`.
2) Send the frame to the Pico's bridge slave address over Pi I2C bus.
3) Pico decodes `channel_id` and forwards payload to that channel's downstream bus.
"""

import argparse
from typing import Optional

from smbus2 import SMBus, i2c_msg

from channel_bridge_protocol import encode_i2c_write


def send_frame_to_pico(
    frame: bytes,
    *,
    pi_i2c_bus: int,
    pico_bridge_addr: int,
) -> None:
    """Send one already-encoded bridge frame to the Pico bridge address.

    Args:
        frame: Raw bytes following `channel_bridge_protocol` format.
        pi_i2c_bus: Linux I2C bus number on Pi (normally 1 -> /dev/i2c-1).
        pico_bridge_addr: 7-bit I2C slave address of Pico bridge (for example 0x42).
    """
    with SMBus(pi_i2c_bus) as bus:
        # Use low-level i2c message write so payload is not treated as
        # SMBus register/value semantics. The frame is sent as-is.
        msg = i2c_msg.write(pico_bridge_addr, frame)
        bus.i2c_rdwr(msg)


def send_i2c_payload(
    *,
    channel_id: int,
    target_addr: int,
    payload: bytes,
    pi_i2c_bus: int,
    pico_bridge_addr: int,
) -> bytes:
    """Encode and send one channelized downstream I2C write command.

    Args:
        channel_id: Router output channel index (0..8).
        target_addr: Downstream 7-bit I2C address on that channel.
        payload: Raw bytes to forward to downstream target.
        pi_i2c_bus: Pi bus id (usually 1).
        pico_bridge_addr: Pico bridge ingress address.

    Returns:
        The encoded frame bytes that were sent. Useful for logging/tests.
    """
    frame = encode_i2c_write(channel_id, target_addr, payload)
    send_frame_to_pico(
        frame,
        pi_i2c_bus=pi_i2c_bus,
        pico_bridge_addr=pico_bridge_addr,
    )
    return frame


def send_text(
    *,
    channel_id: int,
    target_addr: int,
    text: str,
    pi_i2c_bus: int,
    pico_bridge_addr: int,
    encoding: str = "utf-8",
) -> bytes:
    """Convenience wrapper for ASCII/UTF-8 text payload forwarding."""
    payload = text.encode(encoding)
    return send_i2c_payload(
        channel_id=channel_id,
        target_addr=target_addr,
        payload=payload,
        pi_i2c_bus=pi_i2c_bus,
        pico_bridge_addr=pico_bridge_addr,
    )


def parse_int(text: str) -> int:
    return int(text, 0)


def parse_args(argv: Optional[list[str]] = None):
    """Optional CLI for manual one-shot testing."""
    parser = argparse.ArgumentParser(description="Send one channelized frame to Pico over I2C")
    parser.add_argument("--bus", type=int, required=True, help="Pi I2C bus (e.g. 1)")
    parser.add_argument(
        "--pico-addr",
        type=parse_int,
        required=True,
        help="Pico bridge I2C slave address (e.g. 0x42)",
    )
    parser.add_argument("--channel", type=int, required=True, help="Router channel id 0..8")
    parser.add_argument(
        "--target",
        type=parse_int,
        required=True,
        help="Downstream target I2C address (e.g. 0x3C)",
    )
    parser.add_argument("--text", required=True, help="Text payload to send")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None):
    args = parse_args(argv)
    frame = send_text(
        channel_id=args.channel,
        target_addr=args.target,
        text=args.text,
        pi_i2c_bus=args.bus,
        pico_bridge_addr=args.pico_addr,
    )
    print(
        f"sent: bus={args.bus} pico=0x{args.pico_addr:02X} "
        f"channel={args.channel} target=0x{args.target:02X} "
        f"payload_bytes={len(args.text.encode('utf-8'))} frame_bytes={len(frame)}"
    )


if __name__ == "__main__":
    main()
