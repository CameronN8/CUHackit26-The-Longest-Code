"""Rotary-encoder menu controller for one player's interactive display.

This module is UI/state logic only. It expects:
- An SSD1306-compatible `oled` object.
- A rotary encoder with CLK/DT/SW pins.

It emits structured action events for upstream game logic:
- end_turn
- buy_dev_card
- use_dev_card
- trade_player
- trade_port
"""

from machine import Pin
import utime

from state_packet_protocol import (
    MENU_EVT_BUY_DEV,
    MENU_EVT_END_TURN,
    MENU_EVT_TRADE_PLAYER,
    MENU_EVT_TRADE_PORT,
    MENU_EVT_USE_DEV,
)


DEV_DESCRIPTIONS = {
    "knight": "Move robber,\nsteal 1 card.",
    "victory_point": "1 hidden VP\nat game end.",
    "road_building": "Place 2 free\nroads.",
    "year_of_plenty": "Take any 2\nresources.",
    "monopoly": "Take all of\n1 resource.",
}

RESOURCE_KEYS = ("wood", "brick", "sheep", "wheat", "ore")
DEV_KEYS = ("knight", "victory_point", "road_building", "year_of_plenty", "monopoly")


class RotaryEncoder:
    def __init__(self, clk_pin, dt_pin, sw_pin, step_threshold=2, debounce_ms=170):
        self.clk = Pin(clk_pin, Pin.IN, Pin.PULL_UP)
        self.dt = Pin(dt_pin, Pin.IN, Pin.PULL_UP)
        self.sw = Pin(sw_pin, Pin.IN, Pin.PULL_UP)
        self.step_threshold = int(step_threshold)
        self.debounce_ms = int(debounce_ms)

        self._last_clk = self.clk.value()
        self._step_accum = 0
        self._last_btn = self.sw.value()
        self._last_btn_ms = utime.ticks_ms()

    def update(self):
        """Return (delta, pressed_edge). delta is -1/0/+1."""
        delta = 0
        pressed = False

        clk_now = self.clk.value()
        if clk_now != self._last_clk:
            # Count one step per CLK edge; direction from DT relation.
            if self.dt.value() != clk_now:
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

        btn_now = self.sw.value()
        now_ms = utime.ticks_ms()
        if btn_now != self._last_btn:
            self._last_btn = btn_now
            if btn_now == 0 and utime.ticks_diff(now_ms, self._last_btn_ms) >= self.debounce_ms:
                pressed = True
                self._last_btn_ms = now_ms

        return delta, pressed


class PlayerMenuController:
    def __init__(self, oled, player_index, encoder):
        self.oled = oled
        self.player_index = int(player_index)
        self.encoder = encoder

        self.active = False
        self.screen = "root"
        self.cursor = 0
        self.editing = False
        self.toast = ""
        self.toast_until = 0

        self.player_data = {
            "resources": {k: 0 for k in RESOURCE_KEYS},
            "victory_points": 0,
            "dev_cards": {k: 0 for k in DEV_KEYS},
        }
        self.selected_dev = "knight"
        self.selected_trade_player = 0
        self.trade_give = [0, 0, 0, 0, 0]
        self.trade_receive = [0, 0, 0, 0, 0]

        self.reset_to_root()

    def set_player_data(self, player_data):
        resources = player_data.get("resources", {})
        dev_cards = player_data.get("dev_cards", player_data.get("development_cards", {}))
        vp = int(player_data.get("victory_points", 0) or 0)

        self.player_data = {
            "resources": {k: int(resources.get(k, 0) or 0) for k in RESOURCE_KEYS},
            "victory_points": vp,
            "dev_cards": {k: int(dev_cards.get(k, 0) or 0) for k in DEV_KEYS},
        }

    def set_active(self, is_active, reset_menu=False):
        self.active = bool(is_active)
        if reset_menu:
            self.reset_to_root()

    def reset_to_root(self):
        self.screen = "root"
        self.cursor = 0
        self.editing = False
        self.selected_dev = "knight"
        self.selected_trade_player = 0
        self.trade_give = [0, 0, 0, 0, 0]
        self.trade_receive = [0, 0, 0, 0, 0]

    def _set_toast(self, text, ms=900):
        self.toast = text
        self.toast_until = utime.ticks_add(utime.ticks_ms(), ms)

    def _dev_list(self):
        cards = []
        dev = self.player_data["dev_cards"]
        for key in DEV_KEYS:
            if int(dev.get(key, 0) or 0) > 0:
                cards.append(key)
        return cards

    def _draw_lines(self, title, lines, cursor_idx):
        self.oled.fill(0)
        self.oled.text(title[:21], 0, 0)
        y = 14
        for idx, line in enumerate(lines[:4]):
            prefix = ">" if idx == cursor_idx else " "
            self.oled.text((prefix + line)[:21], 0, y)
            y += 12
        self.oled.show()

    def _draw_dev_confirm(self):
        self.oled.fill(0)
        self.oled.text("Use {}".format(self.selected_dev[:12]), 0, 0)
        desc = DEV_DESCRIPTIONS.get(self.selected_dev, "")
        for i, line in enumerate(desc.split("\n")[:2]):
            self.oled.text(line[:21], 0, 14 + i * 12)
        left = ">Use" if self.cursor == 0 else " Use"
        right = ">Back" if self.cursor == 1 else " Back"
        self.oled.text(left, 0, 46)
        self.oled.text(right, 64, 46)
        self.oled.show()

    def _draw_trade_grid(self):
        self.oled.fill(0)
        self.oled.text("Trade P{}".format(self.selected_trade_player + 1), 0, 0)
        self.oled.text("G:{} {} {} {} {}".format(*self.trade_give), 0, 12)
        self.oled.text("R:{} {} {} {} {}".format(*self.trade_receive), 0, 24)

        if self.cursor < 5:
            focus = "G {}".format(RESOURCE_KEYS[self.cursor][0].upper())
        elif self.cursor < 10:
            focus = "R {}".format(RESOURCE_KEYS[self.cursor - 5][0].upper())
        elif self.cursor == 10:
            focus = "CONFIRM"
        else:
            focus = "BACK"

        tag = "*" if self.editing else ">"
        self.oled.text("{}{}".format(tag, focus)[:21], 0, 38)
        self.oled.text("OK" if self.cursor == 10 else " ok", 0, 50)
        self.oled.text("BK" if self.cursor == 11 else " bk", 28, 50)
        self.oled.show()

    def render(self):
        if self.toast and utime.ticks_diff(self.toast_until, utime.ticks_ms()) > 0:
            self.oled.fill(0)
            self.oled.text(self.toast[:21], 0, 24)
            self.oled.show()
            return
        if self.toast and utime.ticks_diff(self.toast_until, utime.ticks_ms()) <= 0:
            self.toast = ""

        if not self.active:
            dev_total = sum(self.player_data["dev_cards"].values())
            self.oled.fill(0)
            self.oled.text("P{} DEV".format(self.player_index + 1), 0, 0)
            self.oled.text("Waiting turn", 0, 16)
            self.oled.text("Cards {}".format(dev_total), 0, 30)
            self.oled.show()
            return

        if self.screen == "root":
            self._draw_lines("P{} Action".format(self.player_index + 1), ["Development", "Trading", "End Turn"], self.cursor)
        elif self.screen == "dev_root":
            self._draw_lines("Development", ["Use Card", "Buy Card", "Back"], self.cursor)
        elif self.screen == "dev_use":
            cards = self._dev_list()
            if not cards:
                self._draw_lines("Use Card", ["No cards", "Back"], self.cursor)
            else:
                lines = [c.replace("_", " ") for c in cards] + ["Back"]
                self._draw_lines("Use Card", lines, self.cursor)
        elif self.screen == "dev_confirm":
            self._draw_dev_confirm()
        elif self.screen == "trade_root":
            self._draw_lines("Trading", ["Player", "Port", "Back"], self.cursor)
        elif self.screen == "trade_player":
            lines = []
            for p in range(3):
                if p != self.player_index:
                    lines.append("Player {}".format(p + 1))
            lines.append("Back")
            self._draw_lines("Select Player", lines, self.cursor)
        elif self.screen == "trade_grid":
            self._draw_trade_grid()

    def _move_cursor(self, delta, max_items):
        if max_items <= 0:
            self.cursor = 0
            return
        self.cursor = (self.cursor + delta) % max_items

    def _enter_root_selection(self):
        if self.cursor == 0:
            self.screen = "dev_root"
            self.cursor = 0
        elif self.cursor == 1:
            self.screen = "trade_root"
            self.cursor = 0
        else:
            self.reset_to_root()
            return {"type": MENU_EVT_END_TURN}
        return None

    def _enter_dev_root_selection(self):
        if self.cursor == 0:
            self.screen = "dev_use"
            self.cursor = 0
            return None
        if self.cursor == 1:
            self.reset_to_root()
            return {"type": MENU_EVT_BUY_DEV}
        self.reset_to_root()
        return None

    def _enter_dev_use_selection(self):
        cards = self._dev_list()
        if not cards:
            # "No cards" or "Back" both route back to root.
            self.reset_to_root()
            return None
        if self.cursor == len(cards):
            self.reset_to_root()
            return None
        self.selected_dev = cards[self.cursor]
        self.screen = "dev_confirm"
        self.cursor = 0
        return None

    def _enter_dev_confirm_selection(self):
        if self.cursor == 0:
            event = {"type": MENU_EVT_USE_DEV, "card": self.selected_dev}
            self.reset_to_root()
            return event
        self.reset_to_root()
        return None

    def _enter_trade_root_selection(self):
        if self.cursor == 0:
            self.screen = "trade_player"
            self.cursor = 0
            return None
        if self.cursor == 1:
            self._set_toast("Port not ready")
            self.reset_to_root()
            return {"type": MENU_EVT_TRADE_PORT}
        self.reset_to_root()
        return None

    def _enter_trade_player_selection(self):
        selectable = [p for p in range(3) if p != self.player_index]
        if self.cursor >= len(selectable):
            self.reset_to_root()
            return None
        self.selected_trade_player = selectable[self.cursor]
        self.screen = "trade_grid"
        self.cursor = 0
        self.editing = False
        self.trade_give = [0, 0, 0, 0, 0]
        self.trade_receive = [0, 0, 0, 0, 0]
        return None

    def _edit_trade_cell(self, delta):
        if self.cursor < 5:
            idx = self.cursor
            self.trade_give[idx] = max(0, min(9, self.trade_give[idx] + delta))
        elif self.cursor < 10:
            idx = self.cursor - 5
            self.trade_receive[idx] = max(0, min(9, self.trade_receive[idx] + delta))

    def _enter_trade_grid_selection(self):
        if self.cursor < 10:
            self.editing = True
            return None
        if self.cursor == 10:
            event = {
                "type": MENU_EVT_TRADE_PLAYER,
                "target_player": self.selected_trade_player,
                "give": list(self.trade_give),
                "receive": list(self.trade_receive),
            }
            self.reset_to_root()
            return event
        self.reset_to_root()
        return None

    def update(self):
        """Poll encoder once, update menu state, return event dict or None."""
        delta, pressed = self.encoder.update()
        event = None

        if self.active and delta != 0:
            if self.screen == "trade_grid" and self.editing:
                self._edit_trade_cell(delta)
            else:
                if self.screen == "root":
                    self._move_cursor(delta, 3)
                elif self.screen == "dev_root":
                    self._move_cursor(delta, 3)
                elif self.screen == "dev_use":
                    cards = self._dev_list()
                    items = (len(cards) + 1) if cards else 2
                    self._move_cursor(delta, items)
                elif self.screen == "dev_confirm":
                    self._move_cursor(delta, 2)
                elif self.screen == "trade_root":
                    self._move_cursor(delta, 3)
                elif self.screen == "trade_player":
                    items = len([p for p in range(3) if p != self.player_index]) + 1
                    self._move_cursor(delta, items)
                elif self.screen == "trade_grid":
                    self._move_cursor(delta, 12)

        if self.active and pressed:
            if self.screen == "root":
                event = self._enter_root_selection()
            elif self.screen == "dev_root":
                event = self._enter_dev_root_selection()
            elif self.screen == "dev_use":
                event = self._enter_dev_use_selection()
            elif self.screen == "dev_confirm":
                event = self._enter_dev_confirm_selection()
            elif self.screen == "trade_root":
                event = self._enter_trade_root_selection()
            elif self.screen == "trade_player":
                event = self._enter_trade_player_selection()
            elif self.screen == "trade_grid":
                if self.editing:
                    self.editing = False
                else:
                    event = self._enter_trade_grid_selection()

        self.render()
        return event
