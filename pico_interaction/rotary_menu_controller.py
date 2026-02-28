"""Pi-side rotary encoder input + menu state machine.

This module runs on the Raspberry Pi (CPython), not on a Pico.
It owns menu logic and emits:
1) render lines for the active player's 3rd OLED (sent over UART to Pico),
2) action events for main game logic.
"""

import time

try:
    import RPi.GPIO as GPIO  # type: ignore
except Exception:  # pragma: no cover - allows dev on non-Pi machines
    GPIO = None


RESOURCE_KEYS = ("wood", "brick", "sheep", "wheat", "ore")
DEV_KEYS = ("knight", "victory_point", "road_building", "year_of_plenty", "monopoly")

DEV_DESCRIPTIONS = {
    "knight": "Move robber",
    "victory_point": "Hidden +1 VP",
    "road_building": "Place 2 roads",
    "year_of_plenty": "Gain any 2",
    "monopoly": "Take all of 1",
}


class PiRotaryEncoder:
    """Simple polled rotary decoder for Pi GPIO pins."""

    def __init__(self, clk_pin, dt_pin, sw_pin, step_threshold=2, debounce_ms=170):
        if GPIO is None:
            raise RuntimeError("RPi.GPIO is not available. Run this on a Raspberry Pi.")

        self.clk_pin = int(clk_pin)
        self.dt_pin = int(dt_pin)
        self.sw_pin = int(sw_pin)
        self.step_threshold = int(step_threshold)
        self.debounce_ms = int(debounce_ms)

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.clk_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.dt_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.sw_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        self._last_clk = GPIO.input(self.clk_pin)
        self._step_accum = 0
        self._last_btn = GPIO.input(self.sw_pin)
        self._last_btn_ms = int(time.monotonic() * 1000)

    def read_input(self):
        """Return (delta, pressed_edge) where delta is -1/0/+1."""
        delta = 0
        pressed = False

        clk_now = GPIO.input(self.clk_pin)
        if clk_now != self._last_clk:
            if GPIO.input(self.dt_pin) != clk_now:
                self._step_accum += 1
            else:
                self._step_accum -= 1
            self._last_clk = clk_now

        if self._step_accum >= self.step_threshold:
            delta = 1
            self._step_accum = 0
        elif self._step_accum <= -self.step_threshold:
            delta = -1
            self._step_accum = 0

        btn_now = GPIO.input(self.sw_pin)
        now_ms = int(time.monotonic() * 1000)
        if btn_now != self._last_btn:
            self._last_btn = btn_now
            if btn_now == 0 and (now_ms - self._last_btn_ms) >= self.debounce_ms:
                pressed = True
                self._last_btn_ms = now_ms

        return delta, pressed

    @staticmethod
    def cleanup():
        if GPIO is not None:
            GPIO.cleanup()


class PlayerTurnMenu:
    """State machine for one active player's turn menu."""

    def __init__(self, active_player_idx=0):
        self.active_player_idx = int(active_player_idx)
        self.players = []
        self.screen = "root"
        self.cursor = 0
        self.editing = False
        self.selected_dev = "knight"
        self.selected_trade_player = 0
        self.trade_give = [0, 0, 0, 0, 0]
        self.trade_receive = [0, 0, 0, 0, 0]

    def set_players(self, players):
        self.players = players or []

    def set_active_player(self, player_idx):
        self.active_player_idx = max(0, min(2, int(player_idx)))
        self.reset()

    def reset(self):
        self.screen = "root"
        self.cursor = 0
        self.editing = False
        self.selected_dev = "knight"
        self.selected_trade_player = 0
        self.trade_give = [0, 0, 0, 0, 0]
        self.trade_receive = [0, 0, 0, 0, 0]

    def _active_dev_cards(self):
        if self.active_player_idx >= len(self.players):
            return []
        player = self.players[self.active_player_idx]
        dev = player.get("development_cards", player.get("dev_cards", {}))
        return [k for k in DEV_KEYS if int(dev.get(k, 0) or 0) > 0]

    @staticmethod
    def _move_cursor(cursor, delta, count):
        if count <= 0:
            return 0
        return (cursor + delta) % count

    def _format_trade_row(self, prefix, values):
        letters = ["W", "B", "S", "H", "O"]
        body = " ".join("{}{}".format(letters[i], values[i]) for i in range(5))
        return "{} {}".format(prefix, body)

    def get_render_lines(self):
        title = "P{} Action".format(self.active_player_idx + 1)
        if self.screen == "root":
            items = ["Development", "Trading", "End Turn"]
            return [title] + [(">" if i == self.cursor else " ") + items[i] for i in range(3)]
        if self.screen == "dev_root":
            items = ["Use Card", "Buy Card", "Back"]
            return ["Development"] + [(">" if i == self.cursor else " ") + items[i] for i in range(3)]
        if self.screen == "dev_use":
            cards = self._active_dev_cards()
            if not cards:
                items = ["No cards", "Back"]
            else:
                items = [c.replace("_", " ") for c in cards] + ["Back"]
            lines = ["Use Card"]
            for i in range(3):
                text = items[i] if i < len(items) else ""
                lines.append((">" if i == self.cursor else " ") + text)
            return lines
        if self.screen == "dev_confirm":
            desc = DEV_DESCRIPTIONS.get(self.selected_dev, "")
            line3 = ">Use  Back" if self.cursor == 0 else " Use >Back"
            return ["Use {}".format(self.selected_dev), desc[:21], "Confirm?", line3]
        if self.screen == "trade_root":
            items = ["Player", "Port", "Back"]
            return ["Trading"] + [(">" if i == self.cursor else " ") + items[i] for i in range(3)]
        if self.screen == "trade_player":
            others = [p for p in range(3) if p != self.active_player_idx]
            items = ["P{}".format(p + 1) for p in others] + ["Back"]
            lines = ["Trade With"]
            for i in range(3):
                text = items[i] if i < len(items) else ""
                lines.append((">" if i == self.cursor else " ") + text)
            return lines
        if self.screen == "trade_grid":
            if self.cursor < 5:
                focus = "G{}".format("WBSHO"[self.cursor])
            elif self.cursor < 10:
                focus = "R{}".format("WBSHO"[self.cursor - 5])
            elif self.cursor == 10:
                focus = "CONFIRM"
            else:
                focus = "BACK"
            marker = "*" if self.editing else ">"
            return [
                "Trade P{}".format(self.selected_trade_player + 1),
                self._format_trade_row("G", self.trade_give),
                self._format_trade_row("R", self.trade_receive),
                "{} {} [{}|{}]".format(marker, focus, "OK" if self.cursor == 10 else "ok", "BK" if self.cursor == 11 else "bk"),
            ]
        return [title, "", "", ""]

    def _edit_trade_value(self, delta):
        if self.cursor < 5:
            idx = self.cursor
            self.trade_give[idx] = max(0, min(9, self.trade_give[idx] + delta))
        elif self.cursor < 10:
            idx = self.cursor - 5
            self.trade_receive[idx] = max(0, min(9, self.trade_receive[idx] + delta))

    def update(self, delta, pressed):
        """Apply one input step. Returns action event dict or None."""
        event = None

        if delta != 0:
            if self.screen == "trade_grid" and self.editing:
                self._edit_trade_value(delta)
            elif self.screen == "root":
                self.cursor = self._move_cursor(self.cursor, delta, 3)
            elif self.screen == "dev_root":
                self.cursor = self._move_cursor(self.cursor, delta, 3)
            elif self.screen == "dev_use":
                cards = self._active_dev_cards()
                count = (len(cards) + 1) if cards else 2
                self.cursor = self._move_cursor(self.cursor, delta, count)
            elif self.screen == "dev_confirm":
                self.cursor = self._move_cursor(self.cursor, delta, 2)
            elif self.screen == "trade_root":
                self.cursor = self._move_cursor(self.cursor, delta, 3)
            elif self.screen == "trade_player":
                others = [p for p in range(3) if p != self.active_player_idx]
                self.cursor = self._move_cursor(self.cursor, delta, len(others) + 1)
            elif self.screen == "trade_grid":
                self.cursor = self._move_cursor(self.cursor, delta, 12)

        if not pressed:
            return None

        if self.screen == "root":
            if self.cursor == 0:
                self.screen = "dev_root"
                self.cursor = 0
            elif self.cursor == 1:
                self.screen = "trade_root"
                self.cursor = 0
            else:
                self.reset()
                event = {"type": "end_turn", "player_idx": self.active_player_idx}

        elif self.screen == "dev_root":
            if self.cursor == 0:
                self.screen = "dev_use"
                self.cursor = 0
            elif self.cursor == 1:
                self.reset()
                event = {"type": "buy_dev_card", "player_idx": self.active_player_idx}
            else:
                self.reset()

        elif self.screen == "dev_use":
            cards = self._active_dev_cards()
            if not cards or self.cursor == len(cards):
                self.reset()
            else:
                self.selected_dev = cards[self.cursor]
                self.screen = "dev_confirm"
                self.cursor = 0

        elif self.screen == "dev_confirm":
            if self.cursor == 0:
                event = {"type": "use_dev_card", "player_idx": self.active_player_idx, "card": self.selected_dev}
            self.reset()

        elif self.screen == "trade_root":
            if self.cursor == 0:
                self.screen = "trade_player"
                self.cursor = 0
            elif self.cursor == 1:
                self.reset()
                event = {"type": "trade_port", "player_idx": self.active_player_idx}
            else:
                self.reset()

        elif self.screen == "trade_player":
            others = [p for p in range(3) if p != self.active_player_idx]
            if self.cursor >= len(others):
                self.reset()
            else:
                self.selected_trade_player = others[self.cursor]
                self.screen = "trade_grid"
                self.cursor = 0
                self.editing = False
                self.trade_give = [0, 0, 0, 0, 0]
                self.trade_receive = [0, 0, 0, 0, 0]

        elif self.screen == "trade_grid":
            if self.editing:
                self.editing = False
            elif self.cursor < 10:
                self.editing = True
            elif self.cursor == 10:
                event = {
                    "type": "trade_player",
                    "player_idx": self.active_player_idx,
                    "target_player": self.selected_trade_player,
                    "give": list(self.trade_give),
                    "receive": list(self.trade_receive),
                }
                self.reset()
            else:
                self.reset()

        return event
