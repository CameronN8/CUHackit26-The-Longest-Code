from __future__ import annotations

import time
from typing import Any


class HardwareController:
    """Skeleton hardware abstraction layer.

    Replace these methods with Raspberry Pi GPIO/I2C/SPI implementations.
    The default behavior is console-based and non-blocking for development.
    """

    def __init__(self, interactive: bool = False) -> None:
        self.interactive = interactive

    def set_player_light(self, player_color: str, on: bool, blink: bool = False) -> None:
        mode = "BLINK" if blink else "ON" if on else "OFF"
        print(f"[HW] Player light {player_color}: {mode}")

    def clear_all_player_lights(self) -> None:
        print("[HW] Clear all player lights")

    def flash_winner(self, player_color: str, flashes: int = 8) -> None:
        print(f"[HW] Flash winner light for {player_color} ({flashes} times)")

    def display_dice(self, die_1: int, die_2: int) -> None:
        print(f"[HW] 7-seg dice display: {die_1} + {die_2} = {die_1 + die_2}")

    def display_lcd_message(self, message: str) -> None:
        print(f"[HW] LCD: {message}")

    def wait_for_player_confirm(self, player_color: str) -> None:
        if self.interactive:
            input(f"[HW] {player_color} press Enter to confirm placement...")
        else:
            print(f"[HW] Auto-confirm placement for {player_color} (skeleton mode)")
            time.sleep(0.15)

    def get_turn_action(self, player: dict[str, Any], game_state: dict[str, Any]) -> dict[str, Any]:
        """Return next action command.

        TODO: wire rotary encoder + button flow and return structured commands.
        Example commands:
        - {"type": "buy_road"}
        - {"type": "buy_settlement"}
        - {"type": "buy_city"}
        - {"type": "buy_development_card"}
        - {"type": "trade_bank", "give": "wood", "get": "brick", "rate": 4}
        - {"type": "end_turn"}
        """
        if self.interactive:
            cmd = input(
                "[HW] Enter action (road/settlement/city/dev/trade/end): "
            ).strip().lower()
            mapping = {
                "road": "buy_road",
                "settlement": "buy_settlement",
                "city": "buy_city",
                "dev": "buy_development_card",
                "trade": "trade_bank",
                "end": "end_turn",
            }
            action_type = mapping.get(cmd, "end_turn")
            if action_type == "trade_bank":
                return {
                    "type": "trade_bank",
                    "give": "wood",
                    "get": "brick",
                    "rate": 4,
                }
            return {"type": action_type}

        return {"type": "end_turn"}
