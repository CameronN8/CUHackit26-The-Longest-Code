"""Direct Raspberry Pi OLED renderer for a 3-screen player display stack.

This replaces the Pico display bridge by rendering directly from the Pi to SSD1306
OLEDs over software I2C (shared SCL, separate SDA pins per display).

Hardware model mirrored from Pico setup:
- screen 1: resources
- screen 2: victory points
- screen 3: interface menu

Dependencies on Pi:
  pip install adafruit-blinka adafruit-circuitpython-ssd1306 pillow
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

RESOURCE_ORDER = ("wood", "brick", "sheep", "wheat", "ore")


class OledDependencyError(RuntimeError):
    """Raised when required OLED libraries are missing on Raspberry Pi."""


@dataclass(frozen=True)
class OledConfig:
    scl_bcm_pin: int = 15
    resources_sda_bcm_pin: int = 2
    vp_sda_bcm_pin: int = 3
    menu_sda_bcm_pin: int = 4
    width: int = 128
    height: int = 64
    address: int = 0x3C
    i2c_frequency: int = 400_000


class PiSoftI2COled:
    def __init__(
        self,
        *,
        scl_bcm_pin: int,
        sda_bcm_pin: int,
        width: int,
        height: int,
        address: int,
        i2c_frequency: int,
    ) -> None:
        try:
            import board  # type: ignore
            import bitbangio  # type: ignore
            import adafruit_ssd1306  # type: ignore
            from PIL import Image, ImageDraw, ImageFont
        except Exception as exc:  # pragma: no cover - hardware dependency
            raise OledDependencyError(
                "Missing OLED dependencies. Install: "
                "adafruit-blinka adafruit-circuitpython-ssd1306 pillow"
            ) from exc

        self._Image = Image
        self._ImageDraw = ImageDraw
        self._font = ImageFont.load_default()
        self.width = int(width)
        self.height = int(height)
        self._max_chars = 21
        self._line_height = 16

        scl = self._bcm_to_board_pin(board, scl_bcm_pin)
        sda = self._bcm_to_board_pin(board, sda_bcm_pin)
        self._i2c = bitbangio.I2C(scl=scl, sda=sda, frequency=int(i2c_frequency))
        self._oled = adafruit_ssd1306.SSD1306_I2C(
            self.width,
            self.height,
            self._i2c,
            addr=int(address),
        )
        self.clear()

    @staticmethod
    def _bcm_to_board_pin(board_module, bcm_pin: int):
        pin_name = f"D{int(bcm_pin)}"
        if not hasattr(board_module, pin_name):
            raise ValueError(f"Pin BCM{bcm_pin} not exposed as board.{pin_name}")
        return getattr(board_module, pin_name)

    def clear(self) -> None:
        image = self._Image.new("1", (self.width, self.height), color=0)
        self._oled.image(image)
        self._oled.show()

    def draw_lines(self, lines: Sequence[str]) -> None:
        image = self._Image.new("1", (self.width, self.height), color=0)
        draw = self._ImageDraw.Draw(image)

        y = 0
        for line in list(lines)[:4]:
            draw.text((0, y), str(line)[: self._max_chars], font=self._font, fill=255)
            y += self._line_height

        self._oled.image(image)
        self._oled.show()


class PiDirectPlayerDisplays:
    """Render resources / VP / menu to three OLEDs directly from Raspberry Pi."""

    def __init__(self, config: OledConfig | None = None) -> None:
        self.config = config or OledConfig()

        common = {
            "scl_bcm_pin": self.config.scl_bcm_pin,
            "width": self.config.width,
            "height": self.config.height,
            "address": self.config.address,
            "i2c_frequency": self.config.i2c_frequency,
        }

        self.resources = PiSoftI2COled(sda_bcm_pin=self.config.resources_sda_bcm_pin, **common)
        self.vp = PiSoftI2COled(sda_bcm_pin=self.config.vp_sda_bcm_pin, **common)
        self.menu = PiSoftI2COled(sda_bcm_pin=self.config.menu_sda_bcm_pin, **common)

    @staticmethod
    def _resource_total(resources: dict[str, int]) -> int:
        return sum(int(resources.get(k, 0) or 0) for k in RESOURCE_ORDER)

    def draw_resource_count(self, resources: dict[str, int], *, player_idx: int = 0) -> None:
        total = self._resource_total(resources)
        lines = [
            f"P{player_idx + 1} RES",
            f"W{resources.get('wood', 0)} B{resources.get('brick', 0)} S{resources.get('sheep', 0)}",
            f"H{resources.get('wheat', 0)} O{resources.get('ore', 0)}",
            f"TOTAL {total}",
        ]
        self.resources.draw_lines(lines)

    def draw_victory_points(self, victory_points: int, *, player_idx: int = 0) -> None:
        lines = [
            f"P{player_idx + 1} VP",
            "",
            f"POINTS: {int(victory_points)}",
            "",
        ]
        self.vp.draw_lines(lines)

    def draw_interface_menu(self, lines: Iterable[str]) -> None:
        self.menu.draw_lines(list(lines)[:4])

    def draw_turn_menu_root(self, *, player_idx: int = 0, cursor: int = 0) -> None:
        items = ["Development", "Trading", "End Turn"]
        menu_lines = [f"P{player_idx + 1} Action"]
        for idx, text in enumerate(items):
            prefix = ">" if idx == int(cursor) else " "
            menu_lines.append(prefix + text)
        self.draw_interface_menu(menu_lines)

    def apply_snapshot(self, player: dict, *, player_idx: int = 0) -> None:
        resources = player.get("resources", {}) if isinstance(player, dict) else {}
        vp = int((player or {}).get("victory_points", 0) or 0)
        self.draw_resource_count(resources=resources, player_idx=player_idx)
        self.draw_victory_points(victory_points=vp, player_idx=player_idx)


def build_default_player_display() -> PiDirectPlayerDisplays:
    return PiDirectPlayerDisplays(OledConfig())
